from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.field import Booking, BookingStatus, Field


class BookingBehaviorProfileService:
    """Build a short-lived, account-scoped profile from accepted booking rows."""

    WINDOW_DAYS = 180
    MIN_REPEATED_BOOKINGS = 2
    ELIGIBLE_STATUSES = (
        BookingStatus.CONFIRMED.value,
        BookingStatus.IN_PROGRESS.value,
        BookingStatus.COMPLETED.value,
    )
    EXCLUDED_REFUND_STATES = ('refund_pending', 'refunded')

    @classmethod
    def build(cls, db: Session, user_id: int, *, now: datetime | None = None) -> dict | None:
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=cls.WINDOW_DAYS)
        filters = (
            Booking.customer_id == user_id,
            Booking.status.in_(cls.ELIGIBLE_STATUSES),
            Booking.created_at >= cutoff,
            Booking.created_at <= now,
            Booking.payment_status != 'refunded',
            Booking.refund_status.not_in(cls.EXCLUDED_REFUND_STATES),
        )

        summary = db.execute(
            select(
                func.count(Booking.id),
                func.max(Booking.created_at),
                func.max(Booking.booking_date),
            ).where(*filters)
        ).one()
        booking_count, latest_created_at, latest_selected_date = summary
        if not booking_count:
            return None
        if latest_created_at is not None and latest_created_at.tzinfo is None:
            latest_created_at = latest_created_at.replace(tzinfo=timezone.utc)

        sports = cls._repeated_groups(db, Field.sport_type, filters)
        locations = cls._repeated_groups(db, Field.location, filters)
        time_counts: Counter[str] = Counter()
        time_rows = db.execute(
            select(Booking.start_time_snapshot, func.count(Booking.id))
            .where(*filters)
            .group_by(Booking.start_time_snapshot)
        ).all()
        for start_time, count in time_rows:
            time_counts[cls._time_window(start_time.hour)] += int(count)

        repeated_times = [
            {'value': value, 'count': count}
            for value, count in sorted(time_counts.items(), key=lambda item: (-item[1], item[0]))
            if count >= cls.MIN_REPEATED_BOOKINGS
        ]
        return {
            'window_days': cls.WINDOW_DAYS,
            'eligible_booking_count': int(booking_count),
            'latest_booking_created_at': latest_created_at.isoformat() if latest_created_at else None,
            'latest_selected_date': latest_selected_date.isoformat() if latest_selected_date else None,
            'repeated_sports': sports,
            'repeated_time_windows': repeated_times,
            'repeated_locations': locations,
        }

    @classmethod
    def _repeated_groups(cls, db: Session, dimension, filters: tuple) -> list[dict[str, str | int]]:
        rows = db.execute(
            select(dimension, func.count(Booking.id))
            .select_from(Booking)
            .join(Field, Booking.field_id == Field.id)
            .where(*filters, dimension.is_not(None))
            .group_by(dimension)
            .order_by(func.count(Booking.id).desc(), dimension.asc())
        ).all()
        return [
            {'value': str(value).strip()[:100], 'count': int(count)}
            for value, count in rows
            if value is not None and str(value).strip() and count >= cls.MIN_REPEATED_BOOKINGS
        ][:3]

    @staticmethod
    def _time_window(hour: int) -> str:
        if hour < 6:
            return 'đêm hoặc rạng sáng'
        if hour < 12:
            return 'buổi sáng'
        if hour < 18:
            return 'buổi chiều'
        return 'buổi tối'
