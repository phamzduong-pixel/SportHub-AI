from collections import Counter
from datetime import date, datetime, timezone
from statistics import median

from sqlalchemy import func, select
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..models.field import Booking, Field
from ..models.facility import Facility
from ..models.time_slot import TimeSlot
from ..models.operations import FieldBlock
from ..models.maintenance import FieldMaintenance
from ..repositories.booking_repository import BookingRepository
from ..core.datetime_utils import as_utc
from ..core.config import settings
from zoneinfo import ZoneInfo


VALID_HISTORY = ('pending_confirmation', 'confirmed', 'completed')


class CustomerRecommendationService:
    def __init__(self, db: Session):
        self.db = db

    def recommend(self, customer_id: int | None, limit: int):
        history = [] if customer_id is None else list(self.db.scalars(select(Booking).where(
            Booking.customer_id == customer_id, Booking.status.in_(VALID_HISTORY),
        )).all())
        fields = list(self.db.scalars(select(Field).where(
            Field.status == 'available',
            or_(Field.facility_id.is_(None), Field.facility.has(Facility.is_active.is_(True))),
        )).all())
        booking_counts = dict(self.db.execute(select(Booking.field_id, func.count(Booking.id)).where(
            Booking.status.in_(VALID_HISTORY),
        ).group_by(Booking.field_id)).all())

        preferred_sports = Counter(item.field.sport_type for item in history)
        preferred_locations = Counter(item.field.location for item in history)
        preferred_hour = round(median(item.start_time_snapshot.hour for item in history)) if history else None
        preferred_price = median(float(item.price_snapshot) for item in history) if history else None
        personalized = bool(history)

        ranked = []
        for field in fields:
            slots = self._available_slots(field.id)
            if not slots:
                continue
            popularity = min(20, booking_counts.get(field.id, 0) * 2)
            score = field.rating * 10 + popularity
            reasons = []
            if personalized:
                if field.sport_type in preferred_sports:
                    score += 30 + preferred_sports[field.sport_type] * 3; reasons.append('đúng môn bạn thường chơi')
                if field.location in preferred_locations:
                    score += 18; reasons.append('thuộc khu vực bạn thường đặt')
                closest = min(slots, key=lambda slot: abs(slot.start_time.hour - preferred_hour))
                score += max(0, 12 - abs(closest.start_time.hour - preferred_hour) * 3)
                if preferred_price and min(float(slot.price) for slot in slots) <= preferred_price * 1.2:
                    score += 12; reasons.append('phù hợp khoảng giá quen thuộc')
            else:
                reasons.append('được đánh giá cao và phổ biến trên SportHub')
            if not reasons:
                reasons.append('có lịch trống gần với thói quen đặt sân của bạn')
            ranked.append((score, field, slots, reasons))

        ranked.sort(key=lambda row: (-row[0], -row[1].rating, row[1].distance_km or 999))
        items = []
        for score, field, slots, reasons in ranked[:limit]:
            items.append({
                'field_id': field.id, 'field_name': field.name, 'sport_type': field.sport_type,
                'location': field.location, 'image_url': field.image_url, 'price': min(float(slot.price) for slot in slots),
                'rating': field.rating, 'review_count': field.review_count, 'distance_km': field.distance_km,
                'available_slots': [{'id': slot.id, 'start_time': slot.start_time.strftime('%H:%M'), 'end_time': slot.end_time.strftime('%H:%M'), 'price': float(slot.price)} for slot in slots[:3]],
                'score': round(score, 1), 'reason': 'Phù hợp vì ' + ', '.join(reasons) + '.',
            })
        return {'strategy': 'booking_history' if personalized else 'popular_and_high_rated', 'personalized': personalized, 'items': items}

    def _available_slots(self, field_id: int):
        target_day = datetime.now(ZoneInfo(settings.TIMEZONE)).date()
        slots = list(self.db.scalars(select(TimeSlot).where(TimeSlot.field_id == field_id, TimeSlot.is_active.is_(True)).order_by(TimeSlot.start_time)).all())
        bookings = list(self.db.scalars(select(Booking).where(
            Booking.field_id == field_id, Booking.booking_date == target_day,
            or_(
                Booking.status.in_(('pending_confirmation', 'confirmed', 'in_progress')),
                and_(Booking.status == 'pending_payment', Booking.hold_expires_at > datetime.now(timezone.utc)),
            ),
        )).all())
        maintenance = list(self.db.scalars(select(FieldBlock).where(FieldBlock.field_id == field_id, FieldBlock.block_date == target_day)).all())
        day_start, day_end = BookingRepository._day_bounds(target_day)
        field_maintenance = list(self.db.scalars(select(FieldMaintenance).where(
            FieldMaintenance.field_id == field_id, FieldMaintenance.status.in_(('SCHEDULED', 'IN_PROGRESS')),
            FieldMaintenance.starts_at < day_end, FieldMaintenance.ends_at > day_start,
        )).all())
        return [slot for slot in slots if not any(booking.start_time_snapshot < slot.end_time and booking.end_time_snapshot > slot.start_time for booking in bookings)
                and not any(item.start_time < slot.end_time and item.end_time > slot.start_time for item in maintenance)
                and not any(as_utc(item.starts_at) < BookingRepository._slot_bounds(target_day, slot.start_time, slot.end_time)[1]
                            and as_utc(item.ends_at) > BookingRepository._slot_bounds(target_day, slot.start_time, slot.end_time)[0]
                            for item in field_maintenance)]
