from datetime import date, datetime, time, timedelta
import re

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from ..core.ownership import management_owner_id
from ..models.field import Booking, Field
from ..models.facility import Facility
from ..models.payment import Payment, PaymentType
from ..models.owner_application import OwnerApplication
from ..models.user import User
from ..models.time_slot import TimeSlot
from .booking_repository import BookingRepository
from ..services.location_utils import location_matches

HISTORY_STATUSES = ('pending_payment', 'pending_confirmation', 'confirmed', 'completed')


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

    def latest_owner_application(self, customer_id: int):
        return self.db.scalar(
            select(OwnerApplication).where(OwnerApplication.customer_id == customer_id)
            .order_by(OwnerApplication.created_at.desc(), OwnerApplication.id.desc()).limit(1)
        )

    def platform_account_summary(self):
        return {
            role: int(self.db.scalar(select(func.count(User.id)).where(User.role == role, User.is_active.is_(True))) or 0)
            for role in ('CUSTOMER', 'OWNER', 'SYSTEM_ADMIN')
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
            or_(Field.facility_id.is_(None), Field.facility.has(and_(Facility.is_active.is_(True), Facility.status == 'APPROVED'))),
            *self._field_scope(),
        )
        if sport_type:
            query = query.where(func.lower(Field.sport_type) == sport_type.lower())
        return self.db.execute(query.order_by(Field.name, TimeSlot.start_time)).all()

    def search_venues(self, *, location: str | None = None, sport_type: str | None = None,
                      court_type: str | None = None, max_price: float | None = None, limit: int | None = 6):
        query = select(Field).where(
            Field.status == 'available',
            or_(Field.facility_id.is_(None), Field.facility.has(and_(
                Facility.is_active.is_(True), Facility.status == 'APPROVED',
            ))),
            *self._field_scope(),
        )
        fields = list(self.db.scalars(query.order_by(Field.rating.desc(), Field.name)).all())
        if sport_type:
            normalized_sport = sport_type.casefold()
            fields = [field for field in fields if field.sport_type.casefold() == normalized_sport]
        if location:
            fields = [field for field in fields if location_matches(
                location, field.location,
                field.facility.location if field.facility else None,
                field.facility.city if field.facility else None,
                field.facility.district if field.facility else None,
            )]
        if court_type:
            people = re.search(r'\d{1,2}', court_type)
            if people:
                fields = [field for field in fields if int(field.capacity or 0) >= int(people[0])]
        if max_price is not None:
            fields = [field for field in fields if float(field.base_price) <= max_price]
        return fields[:limit] if limit is not None else fields

    def count_venues(self, *, location: str | None = None, sport_type: str | None = None) -> int:
        fields = self.search_venues(location=location, sport_type=sport_type, limit=None)
        venue_keys = {
            ('facility', field.facility_id) if field.facility_id is not None else ('legacy_field', field.id)
            for field in fields
        }
        return len(venue_keys)

    def available_candidates(self, sport_type: str | None, booking_date: date, max_price: float | None):
        # Compatibility wrapper: booking and every AI flow share one availability source.
        from ..services.availability_service import AvailabilityService
        return AvailabilityService(BookingRepository(self.db)).available_pairs(
            booking_date=booking_date, sport_type=sport_type, max_price=max_price,
            owner_id=self.owner_id, include_legacy_unowned=self.include_legacy_unowned,
        )
