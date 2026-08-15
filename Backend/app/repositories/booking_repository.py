from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.orm import Session, joinedload, selectinload

from ..models.field import Booking, BookingSlot, Field
from ..models.facility import Facility
from ..models.time_slot import TimeSlot
from ..models.user import User
from ..models.payment import Payment
from ..models.product import BookingProductItem
from ..models.refund import BookingActivity
from ..models.operations import FieldBlock
from ..models.maintenance import FieldMaintenance
from ..core.config import settings
from zoneinfo import ZoneInfo

BLOCKING_STATUSES = ('pending_confirmation', 'confirmed', 'in_progress')
CONFLICT_MESSAGE = 'Một hoặc nhiều khung giờ vừa được người khác đặt. Danh sách giờ trống đã được cập nhật.'

class BookingRepository:
    def __init__(self, db: Session):
        self.db = db

    def availability(self, *, booking_date: date, field_id: int | None, search: str | None, sport_type: str | None, location: str | None = None, owner_id: int | None = None, include_legacy_unowned: bool = False):
        field_filters = [
            Field.status == 'available',
            or_(Field.facility_id.is_(None), Field.facility.has(and_(Facility.is_active.is_(True), Facility.status == 'APPROVED'))),
        ]
        if field_id:
            field_filters.append(Field.id == field_id)
        if search:
            field_filters.append(Field.name.ilike(f'%{search.strip()}%'))
        if sport_type:
            field_filters.append(func.lower(Field.sport_type) == sport_type.strip().lower())
        if location:
            field_filters.append(Field.location.ilike(f'%{location.strip()}%'))
        if owner_id is not None:
            field_filters.append(or_(Field.owner_id == owner_id, Field.owner_id.is_(None)) if include_legacy_unowned else Field.owner_id == owner_id)
        fields = list(self.db.scalars(select(Field).where(*field_filters).order_by(Field.name)).all())
        if not fields:
            return []
        field_ids = [field.id for field in fields]
        slots = list(self.db.scalars(select(TimeSlot).where(TimeSlot.field_id.in_(field_ids), TimeSlot.is_active.is_(True)).order_by(TimeSlot.start_time)).all())
        now = datetime.now(timezone.utc)
        bookings = list(self.db.scalars(select(Booking).options(selectinload(Booking.booking_slots)).where(
            Booking.field_id.in_(field_ids), Booking.booking_date == booking_date,
            or_(
                Booking.status.in_(BLOCKING_STATUSES),
                and_(Booking.status == 'pending_payment', Booking.hold_expires_at > now),
            ),
        )).all())
        blocks = list(self.db.scalars(select(FieldBlock).where(
            FieldBlock.field_id.in_(field_ids), FieldBlock.block_date == booking_date,
        )).all())
        day_start, day_end = self._day_bounds(booking_date)
        maintenances = list(self.db.scalars(select(FieldMaintenance).where(
            FieldMaintenance.field_id.in_(field_ids),
            FieldMaintenance.status.in_(('SCHEDULED', 'IN_PROGRESS')),
            FieldMaintenance.starts_at < day_end, FieldMaintenance.ends_at > day_start,
        )).all())
        return fields, slots, bookings, blocks, maintenances

    def find_conflict(self, *, field_id: int, booking_date: date, ranges: list[tuple[time, time]], exclude_id: int | None = None) -> Booking | None:
        now = datetime.now(timezone.utc)
        query = select(Booking).options(selectinload(Booking.booking_slots)).where(
            Booking.field_id == field_id,
            Booking.booking_date == booking_date,
            or_(
                Booking.status.in_(BLOCKING_STATUSES),
                and_(Booking.status == 'pending_payment', Booking.hold_expires_at > now),
            ),
        ).with_for_update()
        if exclude_id:
            query = query.where(Booking.id != exclude_id)
        for booking in self.db.scalars(query).unique().all():
            occupied = [
                (item.start_time_snapshot, item.end_time_snapshot)
                for item in booking.booking_slots
            ] or [(booking.start_time_snapshot, booking.end_time_snapshot)]
            if any(start < occupied_end and end > occupied_start
                   for start, end in ranges for occupied_start, occupied_end in occupied):
                return booking
        return None

    def find_block(self, *, field_id: int, booking_date: date, start_time: time, end_time: time) -> FieldBlock | None:
        return self.db.scalar(select(FieldBlock).where(
            FieldBlock.field_id == field_id, FieldBlock.block_date == booking_date,
            FieldBlock.start_time < end_time, FieldBlock.end_time > start_time,
        ).limit(1))

    def find_maintenance(self, *, field_id: int, booking_date: date, start_time: time, end_time: time) -> FieldMaintenance | None:
        start_at, end_at = self._slot_bounds(booking_date, start_time, end_time)
        return self.db.scalar(select(FieldMaintenance).where(
            FieldMaintenance.field_id == field_id,
            FieldMaintenance.status.in_(('SCHEDULED', 'IN_PROGRESS')),
            FieldMaintenance.starts_at < end_at, FieldMaintenance.ends_at > start_at,
        ).limit(1))

    @staticmethod
    def _slot_bounds(booking_date: date, start_time: time, end_time: time):
        tz = ZoneInfo(settings.TIMEZONE)
        return (
            datetime.combine(booking_date, start_time, tzinfo=tz).astimezone(timezone.utc),
            datetime.combine(booking_date, end_time, tzinfo=tz).astimezone(timezone.utc),
        )

    @classmethod
    def _day_bounds(cls, booking_date: date):
        return cls._slot_bounds(booking_date, time.min, time.max)

    def lock_field(self, field_id: int) -> Field | None:
        return self.db.scalar(select(Field).where(Field.id == field_id).with_for_update())

    def begin_booking_write_lock(self):
        # SQLite ignores SELECT ... FOR UPDATE; reserve the writer before the
        # availability check so concurrent overlapping slots are serialized.
        if self.db.bind and self.db.bind.dialect.name == 'sqlite' and not self.db.in_transaction():
            self.db.execute(text('BEGIN IMMEDIATE'))

    def release_expired_holds(self) -> int:
        expired = list(self.db.scalars(select(Booking).where(
            Booking.status == 'pending_payment',
            Booking.hold_expires_at <= datetime.now(timezone.utc),
        )).all())
        if not expired:
            # End the read transaction so SQLite can acquire BEGIN IMMEDIATE
            # for the authoritative availability check that follows.
            self.db.commit()
            return 0
        expired_ids = [booking.id for booking in expired]
        self.db.execute(update(Payment).where(
            Payment.booking_id.in_(expired_ids), Payment.status == 'pending',
        ).values(status='failed', payment_status='failed').execution_options(synchronize_session=False))
        from ..services.inventory_service import InventoryService
        inventory = InventoryService(self.db)
        for booking in expired:
            for item in booking.product_items:
                inventory.release(item)
            booking.status = 'expired'
            booking.hold_expires_at = None
        self.db.commit()
        return len(expired)

    def get(self, booking_id: int, lock: bool = False) -> Booking | None:
        query = self._details_query().where(Booking.id == booking_id)
        if lock:
            query = query.with_for_update()
        return self.db.scalar(query)

    def get_customer(self, customer_id: int | None, customer_email: str | None) -> User | None:
        if customer_id:
            return self.db.scalar(select(User).where(User.id == customer_id, User.role == 'CUSTOMER', User.is_active.is_(True)))
        if customer_email:
            return self.db.scalar(select(User).where(User.email == customer_email.lower(), User.role == 'CUSTOMER', User.is_active.is_(True)))
        return None

    def list(self, *, customer_id: int | None, booking_date: date | None, field_id: int | None, status: str | None, search: str | None, page: int, page_size: int, owner_id: int | None = None):
        filters = []
        if owner_id is not None:
            filters.append(or_(Field.owner_id == owner_id, Field.owner_id.is_(None)))
        if customer_id:
            filters.append(Booking.customer_id == customer_id)
        if booking_date:
            filters.append(Booking.booking_date == booking_date)
        if field_id:
            filters.append(Booking.field_id == field_id)
        if status:
            filters.append(Booking.status == status)
        if search:
            term = f'%{search.strip()}%'
            filters.append(or_(
                Booking.booking_code.ilike(term), User.full_name.ilike(term), User.email.ilike(term),
                User.phone.ilike(term), Field.name.ilike(term),
            ))
        total = self.db.scalar(select(func.count(Booking.id)).join(User, Booking.customer_id == User.id).join(Field, Booking.field_id == Field.id).where(*filters)) or 0
        items = list(self.db.scalars(
            self._details_query().join(User, Booking.customer_id == User.id).join(Field, Booking.field_id == Field.id).where(*filters)
            .order_by(Booking.booking_date.desc(), Booking.start_time_snapshot.desc(), Booking.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).unique().all())
        return items, total

    def create(self, booking: Booking, *, commit: bool = True) -> Booking:
        self.db.add(booking)
        if commit:
            self.db.commit()
            return self.get(booking.id)
        self.db.flush()
        return booking

    def update(self, booking: Booking, data: dict) -> Booking:
        for key, value in data.items():
            setattr(booking, key, value)
        self.db.commit()
        return self.get(booking.id)

    def flush_update(self, booking: Booking, data: dict):
        for key, value in data.items():
            setattr(booking, key, value)
        self.db.flush()

    def reject_with_refund(self, booking: Booking, data: dict) -> Booking:
        for key, value in data.items():
            setattr(booking, key, value)
        self.db.execute(update(Payment).where(
            Payment.booking_id == booking.id, Payment.status == 'paid',
        ).values(refund_status='refund_pending', payment_status='refund_pending'))
        self.db.commit()
        return self.get(booking.id)

    def committed_payment_amount(self, booking_id: int) -> Decimal:
        amount = self.db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.booking_id == booking_id, Payment.status.in_(('pending', 'paid')),
            Payment.payment_type != 'refund',
        ))
        return Decimal(amount)

    @staticmethod
    def _details_query():
        return select(Booking).options(
            joinedload(Booking.customer), joinedload(Booking.field).joinedload(Field.facility),
            joinedload(Booking.facility), joinedload(Booking.time_slot),
            joinedload(Booking.invoice), selectinload(Booking.payments),
            selectinload(Booking.booking_slots),
            selectinload(Booking.product_items).selectinload(BookingProductItem.added_by_user),
            joinedload(Booking.review),
            selectinload(Booking.activities).joinedload(BookingActivity.actor),
        )
