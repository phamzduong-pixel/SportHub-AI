from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from ..models.field import Booking, Field
from ..models.payment import Payment
from ..models.user import User


class PaymentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, payment_id: int, lock: bool = False) -> Payment | None:
        if lock:
            return self.db.scalar(select(Payment).where(Payment.id == payment_id).with_for_update())
        return self.db.scalar(self._details_query().where(Payment.id == payment_id))

    def get_by_transfer_content(self, transfer_content: str, lock: bool = False) -> Payment | None:
        query = select(Payment).where(Payment.transfer_content == transfer_content)
        if lock:
            query = query.with_for_update()
        else:
            query = query.options(
                joinedload(Payment.booking).joinedload(Booking.customer),
                joinedload(Payment.booking).joinedload(Booking.field),
                joinedload(Payment.confirmer),
            )
        return self.db.scalar(query)

    def get_by_provider_reference(self, provider_reference: str) -> Payment | None:
        return self.db.scalar(select(Payment).where(Payment.provider_reference == provider_reference))

    def get_booking(self, booking_id: int, lock: bool = False) -> Booking | None:
        query = select(Booking).where(Booking.id == booking_id)
        if lock:
            query = query.with_for_update()
        else:
            query = query.options(joinedload(Booking.customer), joinedload(Booking.field))
        return self.db.scalar(query)

    def list(self, *, customer_id: int | None, status: str | None, payment_method: str | None, search: str | None, page: int, page_size: int, owner_id: int | None = None):
        filters = []
        if owner_id is not None:
            filters.append(or_(Field.owner_id == owner_id, Field.owner_id.is_(None)))
        if customer_id:
            filters.append(Booking.customer_id == customer_id)
        if status:
            filters.append(Payment.status == status)
        if payment_method:
            filters.append(Payment.payment_method == payment_method)
        if search:
            term = f'%{search.strip()}%'
            filters.append(or_(Payment.transaction_code.ilike(term), Booking.booking_code.ilike(term), User.full_name.ilike(term)))
        joined = select(Payment.id).join(Booking).join(User, Booking.customer_id == User.id).join(Field, Booking.field_id == Field.id).where(*filters)
        total = self.db.scalar(select(func.count()).select_from(joined.subquery())) or 0
        items = list(self.db.scalars(
            self._details_query().join(Booking).join(User, Booking.customer_id == User.id).join(Field, Booking.field_id == Field.id).where(*filters)
            .order_by(Payment.created_at.desc(), Payment.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).unique().all())
        return items, total

    def totals(self, booking_id: int, exclude_id: int | None = None) -> tuple[Decimal, Decimal]:
        query = select(Payment.status, func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.booking_id == booking_id,
            Payment.status.in_(('pending', 'paid')),
            Payment.payment_type != 'refund',
        )
        if exclude_id:
            query = query.where(Payment.id != exclude_id)
        rows = self.db.execute(query.group_by(Payment.status)).all()
        values = {status: Decimal(amount) for status, amount in rows}
        return values.get('paid', Decimal('0')), values.get('pending', Decimal('0'))

    def list_for_booking(self, booking_id: int) -> list[Payment]:
        return list(self.db.scalars(
            self._details_query().where(Payment.booking_id == booking_id)
            .order_by(Payment.created_at.desc(), Payment.id.desc())
        ).unique().all())

    def create(self, payment: Payment) -> Payment:
        self.db.add(payment)
        self.db.commit()
        return self.get(payment.id)

    def update(self, payment: Payment, data: dict) -> Payment:
        for key, value in data.items():
            setattr(payment, key, value)
        self.db.commit()
        return self.get(payment.id)

    def update_booking(self, booking: Booking, data: dict) -> Booking:
        for key, value in data.items():
            setattr(booking, key, value)
        self.db.commit()
        return self.get_booking(booking.id)

    def settle(self, payment: Payment, payment_data: dict, booking: Booking, booking_data: dict) -> Payment:
        for key, value in payment_data.items():
            setattr(payment, key, value)
        for key, value in booking_data.items():
            setattr(booking, key, value)
        self.db.commit()
        return self.get(payment.id)

    @staticmethod
    def _details_query():
        return select(Payment).options(
            joinedload(Payment.booking).joinedload(Booking.customer),
            joinedload(Payment.booking).joinedload(Booking.field),
            joinedload(Payment.confirmer),
        )
