from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from ..core.config import settings
from ..core.datetime_utils import as_utc
from ..models.time_slot import TimeSlot
from ..repositories.booking_repository import BookingRepository
from ..schemas.time_slot import TimeSlotResponse


class AvailabilityService:
    """Single read source for bookable slots used by booking and AI flows."""

    def __init__(self, repository: BookingRepository):
        self.repository = repository
        self.timezone = ZoneInfo(settings.TIMEZONE)

    @staticmethod
    def effective_price(slot: TimeSlot, booking_date: date) -> Decimal:
        special = slot.weekend_price if booking_date.weekday() >= 5 else slot.weekday_price
        return Decimal(special if special is not None else slot.price)

    def list(self, *, booking_date: date, field_id: int | None = None,
             search: str | None = None, sport_type: str | None = None,
             location: str | None = None, start_time=None, end_time=None,
             max_price: float | None = None, sort_by: str = 'relevance',
             owner_id: int | None = None, include_legacy_unowned: bool = False):
        self.repository.release_expired_holds()
        now = datetime.now(self.timezone)
        if booking_date < now.date():
            raise HTTPException(status_code=422, detail='Không thể tìm lịch trống trong quá khứ')
        result = self.repository.availability(
            booking_date=booking_date, field_id=field_id, search=search,
            sport_type=sport_type, location=location, owner_id=owner_id,
            include_legacy_unowned=include_legacy_unowned,
        )
        if not result:
            return []
        fields, slots, bookings, blocks, maintenances = result
        response = []
        for field in fields:
            available = []
            for slot in slots:
                if slot.field_id != field.id:
                    continue
                if booking_date == now.date() and slot.start_time <= now.time().replace(tzinfo=None):
                    continue
                if start_time is not None and slot.start_time < start_time:
                    continue
                if end_time is not None and slot.end_time > end_time:
                    continue
                effective_price = self.effective_price(slot, booking_date)
                if max_price is not None and effective_price > Decimal(str(max_price)):
                    continue
                occupied = any(
                    booking.field_id == field.id and any(
                        occupied_start < slot.end_time and occupied_end > slot.start_time
                        for occupied_start, occupied_end in (
                            [(item.start_time_snapshot, item.end_time_snapshot) for item in booking.booking_slots]
                            or [(booking.start_time_snapshot, booking.end_time_snapshot)]
                        )
                    )
                    for booking in bookings
                )
                blocked = any(block.field_id == field.id and block.start_time < slot.end_time
                    and block.end_time > slot.start_time for block in blocks)
                slot_start, slot_end = self.repository._slot_bounds(booking_date, slot.start_time, slot.end_time)
                maintained = any(maintenance.field_id == field.id
                    and as_utc(maintenance.starts_at) < slot_end
                    and as_utc(maintenance.ends_at) > slot_start for maintenance in maintenances)
                if not occupied and not blocked and not maintained:
                    available.append(TimeSlotResponse.model_validate(slot).model_copy(
                        update={'price': float(effective_price)}))
            if available:
                response.append({'field': field, 'available_slots': available})
        if sort_by == 'price':
            response.sort(key=lambda item: min(slot.price for slot in item['available_slots']))
        elif sort_by == 'rating':
            response.sort(key=lambda item: (-float(item['field'].rating or 0), -int(item['field'].review_count or 0)))
        return response

    def available_pairs(self, **filters):
        return [(item['field'], slot) for item in self.list(**filters)
                for slot in item['available_slots']]
