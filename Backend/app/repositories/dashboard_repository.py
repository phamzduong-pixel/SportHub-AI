from datetime import date, datetime

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from ..models.field import Booking, BookingSlot, Field
from ..models.facility import Facility
from ..models.payment import Payment
from ..models.product import BookingProductItem
from ..models.time_slot import TimeSlot
from ..models.user import User


class DashboardRepository:
    def __init__(self, db: Session):
        self.db = db
        self.owner_id: int | None = None

    def scope_to_owner(self, owner_id: int):
        self.owner_id = owner_id

    def field_counts(self, field_id: int | None) -> tuple[int, int]:
        filters = [Field.id == field_id] if field_id else []
        filters.extend(self._field_scope())
        row = self.db.execute(select(
            func.count(Field.id),
            func.coalesce(func.sum(case((Field.status == 'available', 1), else_=0)), 0),
        ).where(*filters)).one()
        return int(row[0]), int(row[1])

    def booking_status_counts(self, date_from: date, date_to: date, field_id: int | None):
        filters = self._booking_filters(date_from, date_to, field_id)
        return self.db.execute(select(Booking.status, func.count(Booking.id)).where(*filters).group_by(Booking.status)).all()

    def booking_series(self, date_from: date, date_to: date, field_id: int | None):
        filters = self._booking_filters(date_from, date_to, field_id)
        return self.db.execute(select(
            Booking.booking_date, Booking.status, func.count(Booking.id),
        ).where(*filters).group_by(Booking.booking_date, Booking.status).order_by(Booking.booking_date)).all()

    def revenue_rows(self, date_from: datetime, date_to: datetime, field_id: int | None):
        query = select(Payment.paid_at, Payment.amount).join(Booking, Payment.booking_id == Booking.id).where(
            Payment.status == 'paid', Payment.paid_at >= date_from, Payment.paid_at < date_to,
            *self._booking_scope(),
        )
        if field_id:
            query = query.where(Booking.field_id == field_id)
        return self.db.execute(query.order_by(Payment.paid_at)).all()

    def fields(self, field_id: int | None):
        query = select(Field).order_by(Field.name)
        query = query.where(*self._field_scope())
        if field_id:
            query = query.where(Field.id == field_id)
        return list(self.db.scalars(query).all())

    def time_slots(self, field_id: int | None):
        query = select(TimeSlot, Field.name).join(Field, TimeSlot.field_id == Field.id).order_by(Field.name, TimeSlot.start_time)
        query = query.where(*self._field_scope())
        if field_id:
            query = query.where(TimeSlot.field_id == field_id)
        return self.db.execute(query).all()

    def booking_performance(self, date_from: date, date_to: date, field_id: int | None):
        filters = self._booking_filters(date_from, date_to, field_id)
        return self.db.execute(select(
            Booking.field_id, Booking.time_slot_id, Booking.status, func.count(Booking.id),
        ).where(*filters).group_by(Booking.field_id, Booking.time_slot_id, Booking.status)).all()

    def slot_booking_performance(self, date_from: date, date_to: date, field_id: int | None):
        filters = self._booking_filters(date_from, date_to, field_id)
        return self.db.execute(select(
            Booking.field_id, BookingSlot.time_slot_id, Booking.status, func.count(BookingSlot.id),
        ).join(BookingSlot, BookingSlot.booking_id == Booking.id).where(
            *filters,
        ).group_by(Booking.field_id, BookingSlot.time_slot_id, Booking.status)).all()

    def legacy_slot_booking_performance(self, date_from: date, date_to: date, field_id: int | None):
        filters = self._booking_filters(date_from, date_to, field_id)
        return self.db.execute(select(
            Booking.field_id, Booking.time_slot_id, Booking.status, func.count(Booking.id),
        ).where(
            *filters, ~Booking.booking_slots.any(),
        ).group_by(Booking.field_id, Booking.time_slot_id, Booking.status)).all()

    def field_booking_performance(self, date_from: date, date_to: date, field_id: int | None):
        filters = self._booking_filters(date_from, date_to, field_id)
        return self.db.execute(select(
            Booking.field_id, Booking.status, func.count(Booking.id),
        ).where(*filters).group_by(Booking.field_id, Booking.status)).all()

    def revenue_performance(self, date_from: datetime, date_to: datetime, field_id: int | None):
        query = select(
            Booking.field_id, Booking.time_slot_id, func.coalesce(func.sum(Payment.amount), 0),
        ).join(Payment, Payment.booking_id == Booking.id).where(
            Payment.status == 'paid', Payment.paid_at >= date_from, Payment.paid_at < date_to,
            *self._booking_scope(),
        )
        if field_id:
            query = query.where(Booking.field_id == field_id)
        return self.db.execute(query.group_by(Booking.field_id, Booking.time_slot_id)).all()

    def field_revenue_performance(self, date_from: datetime, date_to: datetime, field_id: int | None):
        query = select(
            Booking.field_id, func.coalesce(func.sum(Payment.amount), 0),
        ).join(Payment, Payment.booking_id == Booking.id).where(
            Payment.status == 'paid', Payment.payment_type != 'refund',
            Payment.paid_at >= date_from, Payment.paid_at < date_to,
            *self._booking_scope(),
        )
        if field_id:
            query = query.where(Booking.field_id == field_id)
        return self.db.execute(query.group_by(Booking.field_id)).all()

    def slot_revenue_performance(self, date_from: datetime, date_to: datetime, field_id: int | None):
        allocated = case(
            (Booking.total_amount > 0, Payment.amount * BookingSlot.price_snapshot / Booking.total_amount),
            else_=0,
        )
        query = select(
            BookingSlot.time_slot_id, func.coalesce(func.sum(allocated), 0),
        ).join(Booking, BookingSlot.booking_id == Booking.id).join(
            Payment, Payment.booking_id == Booking.id,
        ).where(
            Payment.status == 'paid', Payment.payment_type != 'refund',
            Payment.paid_at >= date_from, Payment.paid_at < date_to,
            *self._booking_scope(),
        )
        if field_id:
            query = query.where(Booking.field_id == field_id)
        return self.db.execute(query.group_by(BookingSlot.time_slot_id)).all()

    def legacy_slot_revenue_performance(self, date_from: datetime, date_to: datetime, field_id: int | None):
        query = select(
            Booking.time_slot_id, func.coalesce(func.sum(Payment.amount), 0),
        ).join(Payment, Payment.booking_id == Booking.id).where(
            Payment.status == 'paid', Payment.payment_type != 'refund',
            Payment.paid_at >= date_from, Payment.paid_at < date_to,
            ~Booking.booking_slots.any(), *self._booking_scope(),
        )
        if field_id:
            query = query.where(Booking.field_id == field_id)
        return self.db.execute(query.group_by(Booking.time_slot_id)).all()

    def active_slot_counts(self, field_id: int | None):
        query = select(TimeSlot.field_id, func.count(TimeSlot.id)).join(Field, TimeSlot.field_id == Field.id).where(TimeSlot.is_active.is_(True), *self._field_scope())
        if field_id:
            query = query.where(TimeSlot.field_id == field_id)
        return self.db.execute(query.group_by(TimeSlot.field_id)).all()

    def financial_rows(self, date_from: date, date_to: date, field_id: int | None = None):
        """Return one database-aggregated row per booking; payments can never duplicate a booking total."""
        payment_totals = select(
            Payment.booking_id.label('booking_id'),
            func.coalesce(func.sum(case((and_(Payment.status == 'paid', Payment.payment_type != 'refund'), Payment.amount), else_=0)), 0).label('collected'),
            func.coalesce(func.sum(case((and_(Payment.status == 'paid', Payment.payment_type == 'deposit'), Payment.amount), else_=0)), 0).label('deposits'),
            func.coalesce(func.sum(case((and_(Payment.status == 'paid', Payment.payment_type == 'deposit', Payment.escrow_status == 'held'), Payment.amount), else_=0)), 0).label('held_deposits'),
            func.coalesce(func.sum(case((and_(Payment.payment_type == 'refund', Payment.status == 'refunded'), Payment.amount), else_=0)), 0).label('refund_transactions'),
            func.coalesce(func.sum(case((and_(Payment.payment_type != 'refund', Payment.status == 'refunded'), Payment.amount), else_=0)), 0).label('legacy_refunded'),
            func.max(case((and_(Payment.status == 'paid', Payment.payment_type != 'refund'), Payment.paid_at), else_=None)).label('last_paid_at'),
        ).group_by(Payment.booking_id).subquery()
        query = select(
            Booking.id, Booking.booking_code, Booking.booking_date, Booking.status,
            Booking.court_amount, Booking.service_amount, Booking.total_amount,
            Booking.deposit_amount, Booking.start_time_snapshot,
            Field.id.label('field_id'), Field.name.label('field_name'), Field.sport_type,
            Facility.id.label('facility_id'), Facility.name.label('facility_name'),
            User.full_name.label('customer_name'),
            func.coalesce(payment_totals.c.collected, 0).label('collected'),
            func.coalesce(payment_totals.c.deposits, 0).label('deposits'),
            func.coalesce(payment_totals.c.held_deposits, 0).label('held_deposits'),
            func.coalesce(payment_totals.c.refund_transactions, 0).label('refund_transactions'),
            func.coalesce(payment_totals.c.legacy_refunded, 0).label('legacy_refunded'),
            payment_totals.c.last_paid_at,
        ).join(Field, Booking.field_id == Field.id).outerjoin(Facility, Booking.facility_id == Facility.id).join(User, Booking.customer_id == User.id).outerjoin(payment_totals, payment_totals.c.booking_id == Booking.id).where(
            Booking.booking_date >= date_from, Booking.booking_date <= date_to,
            Field.owner_id == self.owner_id,
        )
        if field_id:
            query = query.where(Booking.field_id == field_id)
        return self.db.execute(query.order_by(Booking.booking_date.desc(), Booking.id.desc())).mappings().all()

    def popular_products(self, date_from: date, date_to: date, field_id: int | None = None):
        query = select(
            BookingProductItem.product_id,
            func.max(BookingProductItem.product_name_snapshot).label('name'),
            func.max(BookingProductItem.product_type_snapshot).label('product_type'),
            func.coalesce(func.sum(BookingProductItem.quantity), 0).label('quantity'),
            func.count(func.distinct(BookingProductItem.booking_id)).label('booking_count'),
            func.coalesce(func.sum(BookingProductItem.line_total), 0).label('revenue'),
        ).join(Booking, BookingProductItem.booking_id == Booking.id).join(
            Field, Booking.field_id == Field.id,
        ).where(
            Booking.booking_date >= date_from, Booking.booking_date <= date_to,
            Booking.status == 'completed', *self._field_scope(),
        )
        if field_id:
            query = query.where(Booking.field_id == field_id)
        return self.db.execute(query.group_by(BookingProductItem.product_id).order_by(
            func.sum(BookingProductItem.quantity).desc(), func.sum(BookingProductItem.line_total).desc(),
        )).mappings().all()

    def _booking_filters(self, date_from: date, date_to: date, field_id: int | None):
        filters = [Booking.booking_date >= date_from, Booking.booking_date <= date_to, *self._booking_scope()]
        if field_id:
            filters.append(Booking.field_id == field_id)
        return filters

    def _field_scope(self):
        if self.owner_id is None:
            return []
        return [or_(Field.owner_id == self.owner_id, Field.owner_id.is_(None))]

    def _booking_scope(self):
        if self.owner_id is None:
            return []
        return [Booking.field.has(or_(Field.owner_id == self.owner_id, Field.owner_id.is_(None)))]
