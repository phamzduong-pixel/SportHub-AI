from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from ..models.field import Booking, Field
from ..models.user import User


ACTIVE_STATUSES = {'pending_payment', 'pending_confirmation', 'confirmed', 'in_progress'}
CANCELLED_STATUSES = {'cancelled', 'cancelled_by_customer', 'cancelled_by_owner', 'expired', 'rejected', 'failed'}


class ManagementCustomerRepository:
    """Read-only customer projection, always scoped through fields owned by one OWNER."""

    def __init__(self, db: Session, owner_id: int):
        self.db = db
        self.owner_id = owner_id

    def customer_bookings(self, search: str | None = None) -> dict[User, list[Booking]]:
        filters = [Field.owner_id == self.owner_id]
        if search:
            term = f'%{search.strip()}%'
            filters.append(or_(User.full_name.ilike(term), User.email.ilike(term), User.phone.ilike(term)))
        rows = self.db.execute(
            select(User, Booking)
            .join(Booking, Booking.customer_id == User.id)
            .join(Field, Booking.field_id == Field.id)
            .options(joinedload(Booking.field).joinedload(Field.facility), joinedload(Booking.payments))
            .where(*filters)
            .order_by(Booking.created_at.desc(), Booking.id.desc())
        ).unique().all()
        grouped: dict[User, list[Booking]] = {}
        for customer, booking in rows:
            grouped.setdefault(customer, []).append(booking)
        return grouped

    def get_customer_bookings(self, customer_id: int) -> tuple[User | None, list[Booking]]:
        grouped = self.customer_bookings()
        for customer, bookings in grouped.items():
            if customer.id == customer_id:
                return customer, bookings
        return None, []

    @staticmethod
    def summarize(customer: User, bookings: list[Booking]):
        valid_value = sum((
            Decimal(payment.amount) for booking in bookings for payment in booking.payments
            if payment.status == 'paid' and payment.payment_type != 'refund'
        ), Decimal(0))
        last_booking_at = max(booking.created_at for booking in bookings)
        return {
            'id': customer.id, 'full_name': customer.full_name, 'email': customer.email,
            'phone': customer.phone, 'booking_count': len(bookings),
            'completed_booking_count': sum(booking.status == 'completed' for booking in bookings),
            'active_booking_count': sum(booking.status in ACTIVE_STATUSES for booking in bookings),
            'cancelled_booking_count': sum(booking.status in CANCELLED_STATUSES for booking in bookings),
            'valid_transaction_value': float(valid_value), 'last_booking_at': last_booking_at,
            'created_at': customer.created_at,
        }
