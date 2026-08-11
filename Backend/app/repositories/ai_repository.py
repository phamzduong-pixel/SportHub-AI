from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from ..core.ownership import management_owner_id
from ..core.datetime_utils import as_utc
from ..models.field import Booking, Field
from ..models.facility import Facility
from ..models.payment import Payment, PaymentType
from ..models.user import User
from ..models.time_slot import TimeSlot
from ..models.operations import FieldBlock
from ..models.maintenance import FieldMaintenance
from .booking_repository import BookingRepository

HISTORY_STATUSES = ('pending_payment', 'pending_confirmation', 'confirmed', 'completed')
BLOCKING_STATUSES = ('pending_confirmation', 'confirmed', 'in_progress')


class AIRepository:
    def __init__(self, db: Session):
        self.db = db
        self.owner_id: int | None = None
        self.include_legacy_unowned = True

    def scope_to_owner(self, owner_id: int, *, include_legacy_unowned: bool = True):
        self.owner_id = owner_id
        self.include_legacy_unowned = include_legacy_unowned

    def scope_for_user(self, user: User | None):
        if user and user.role == 'OWNER':
            owner_id = management_owner_id(user, self.db)
            if owner_id is not None:
                # The assistant never treats unowned legacy records as tenant data.
                self.scope_to_owner(owner_id, include_legacy_unowned=False)

    def _field_scope(self):
        if self.owner_id is None:
            return []
        if self.include_legacy_unowned:
            return [or_(Field.owner_id == self.owner_id, Field.owner_id.is_(None))]
        return [Field.owner_id == self.owner_id]

    def field_context(self, field_id: int):
        return self.db.scalar(select(Field).where(Field.id == field_id, *self._field_scope()))

    def accessible_booking(self, user: User, booking_code: str | None = None):
        query = select(Booking).join(Field, Booking.field_id == Field.id)
        if user.role == 'CUSTOMER':
            query = query.where(Booking.customer_id == user.id)
        elif user.role == 'OWNER':
            owner_id = management_owner_id(user, self.db)
            if owner_id is None:
                return None
            query = query.where(Field.owner_id == owner_id)
        else:
            return None
        if booking_code:
            query = query.where(func.upper(Booking.booking_code) == booking_code.upper())
        return self.db.scalar(query.order_by(Booking.created_at.desc()).limit(1))

    def latest_payment(self, booking_id: int):
        return self.db.scalar(
            select(Payment).where(Payment.booking_id == booking_id).order_by(Payment.created_at.desc()).limit(1)
        )

    def platform_account_summary(self):
        return {
            role: int(self.db.scalar(select(func.count(User.id)).where(User.role == role, User.is_active.is_(True))) or 0)
            for role in ('CUSTOMER', 'OWNER', 'MANAGER', 'SYSTEM_ADMIN')
        }

    def booking_count(self, user: User, booking_date: date | None = None) -> int:
        query = select(func.count(Booking.id)).join(Field, Booking.field_id == Field.id)
        if booking_date:
            query = query.where(Booking.booking_date == booking_date)
        if user.role == 'CUSTOMER':
            query = query.where(Booking.customer_id == user.id)
        elif user.role == 'OWNER':
            owner_id = management_owner_id(user, self.db)
            if owner_id is None:
                return 0
            query = query.where(Field.owner_id == owner_id)
        elif user.role != 'SYSTEM_ADMIN':
            return 0
        return int(self.db.scalar(query) or 0)

    def revenue_total(self, user: User, date_from: datetime, date_to: datetime) -> float:
        query = select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.status == 'paid', Payment.payment_type != PaymentType.REFUND.value,
            Payment.created_at >= date_from, Payment.created_at < date_to,
        )
        if user.role == 'OWNER':
            owner_id = management_owner_id(user, self.db)
            if owner_id is None:
                return 0.0
            query = query.where(Payment.owner_id == owner_id)
        elif user.role != 'SYSTEM_ADMIN':
            return 0.0
        return float(self.db.scalar(query) or 0)

    def average_capacity(self, sport_type: str) -> int:
        value = self.db.scalar(select(func.avg(Field.capacity)).where(func.lower(Field.sport_type) == sport_type.lower(), *self._field_scope()))
        return max(1, round(float(value))) if value is not None else 10

    def previous_booking_count(self, *, sport_type: str, before_date: date, start_hour: int, field_id: int | None = None) -> int:
        lower = time(max(0, start_hour - 1), 0)
        upper = time(min(23, start_hour + 1), 59, 59)
        query = select(func.count(Booking.id)).join(Field, Booking.field_id == Field.id).where(
            func.lower(Field.sport_type) == sport_type.lower(),
            Booking.booking_date >= before_date - timedelta(days=90),
            Booking.booking_date < before_date,
            Booking.start_time_snapshot >= lower,
            Booking.start_time_snapshot <= upper,
            Booking.status.in_(HISTORY_STATUSES),
            *self._field_scope(),
        )
        if field_id:
            query = query.where(Booking.field_id == field_id)
        return int(self.db.scalar(query) or 0)

    def inventory(self, sport_type: str | None = None):
        query = select(Field, TimeSlot).join(TimeSlot, TimeSlot.field_id == Field.id).where(
            Field.status == 'available', TimeSlot.is_active.is_(True),
            or_(Field.facility_id.is_(None), Field.facility.has(Facility.is_active.is_(True))),
            *self._field_scope(),
        )
        if sport_type:
            query = query.where(func.lower(Field.sport_type) == sport_type.lower())
        return self.db.execute(query.order_by(Field.name, TimeSlot.start_time)).all()

    def available_candidates(self, sport_type: str | None, booking_date: date, max_price: float | None):
        inventory = self.inventory(sport_type)
        if max_price is not None:
            inventory = [(field, slot) for field, slot in inventory if float(slot.price) <= max_price]
        if not inventory:
            return []
        field_ids = {field.id for field, _ in inventory}
        bookings = list(self.db.scalars(select(Booking).where(
            Booking.field_id.in_(field_ids), Booking.booking_date == booking_date,
            or_(
                Booking.status.in_(BLOCKING_STATUSES),
                and_(Booking.status == 'pending_payment', Booking.hold_expires_at > datetime.now(timezone.utc)),
            ),
        )).all())
        blocks = list(self.db.scalars(select(FieldBlock).where(
            FieldBlock.field_id.in_(field_ids), FieldBlock.block_date == booking_date,
        )).all())
        day_start, day_end = BookingRepository._day_bounds(booking_date)
        maintenances = list(self.db.scalars(select(FieldMaintenance).where(
            FieldMaintenance.field_id.in_(field_ids),
            FieldMaintenance.status.in_(('SCHEDULED', 'IN_PROGRESS')),
            FieldMaintenance.starts_at < day_end, FieldMaintenance.ends_at > day_start,
        )).all())
        return [
            (field, slot) for field, slot in inventory
            if not any(
                booking.field_id == field.id
                and booking.start_time_snapshot < slot.end_time
                and booking.end_time_snapshot > slot.start_time
                for booking in bookings
            )
            and not any(block.field_id == field.id and block.start_time < slot.end_time and block.end_time > slot.start_time for block in blocks)
            and not any(
                maintenance.field_id == field.id
                and as_utc(maintenance.starts_at) < BookingRepository._slot_bounds(booking_date, slot.start_time, slot.end_time)[1]
                and as_utc(maintenance.ends_at) > BookingRepository._slot_bounds(booking_date, slot.start_time, slot.end_time)[0]
                for maintenance in maintenances
            )
        ]
