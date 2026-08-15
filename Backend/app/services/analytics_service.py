from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import and_, case, func, select

from ..core.ownership import management_owner_id
from ..models.field import Booking, Field
from ..models.payment import Payment
from ..models.time_slot import TimeSlot


OCCUPIED_STATUSES = ('pending_confirmation', 'confirmed', 'in_progress', 'completed', 'no_show')
CANCELLED_STATUSES = ('cancelled', 'cancelled_by_customer', 'cancelled_by_owner', 'rejected')


class AnalyticsService:
    """Computes authoritative occupancy facts before any AI summarization."""

    def __init__(self, db):
        self.db = db

    @staticmethod
    def _hours(start, end) -> float:
        return max(0, (end.hour * 60 + end.minute - start.hour * 60 - start.minute) / 60)

    def occupancy(self, user, date_from: date, date_to: date, field_id: int | None = None):
        owner_id = management_owner_id(user, self.db)
        if owner_id is None:
            return None
        days = (date_to - date_from).days + 1
        field_filters = [Field.owner_id == owner_id]
        if field_id:
            field_filters.append(Field.id == field_id)
        slots = list(self.db.execute(select(TimeSlot, Field.name).join(Field).where(
            TimeSlot.is_active.is_(True), *field_filters,
        )).all())
        field_ids = {slot.field_id for slot, _ in slots}
        bookings = [] if not field_ids else list(self.db.scalars(select(Booking).where(
            Booking.field_id.in_(field_ids), Booking.booking_date >= date_from,
            Booking.booking_date <= date_to,
        )).unique().all())

        total_hours = sum(self._hours(slot.start_time, slot.end_time) * days for slot, _ in slots)
        occupied = [booking for booking in bookings if booking.status in OCCUPIED_STATUSES]
        booked_hours = sum(self._booking_hours(item) for item in occupied)
        occupancy_rate = round(booked_hours / total_hours * 100, 2) if total_hours else 0.0

        non_refund = case((and_(Payment.status == 'paid', Payment.payment_type != 'refund'), Payment.amount), else_=0)
        refunds = case((and_(Payment.status.in_(('paid', 'refunded')), Payment.payment_type == 'refund'), Payment.amount), else_=0)
        revenue_query = select(func.coalesce(func.sum(non_refund), 0), func.coalesce(func.sum(refunds), 0)).join(
            Booking, Payment.booking_id == Booking.id,
        ).join(Field, Booking.field_id == Field.id).where(
            Field.owner_id == owner_id, Booking.booking_date >= date_from, Booking.booking_date <= date_to,
        )
        if field_id:
            revenue_query = revenue_query.where(Booking.field_id == field_id)
        collected, refunded = self.db.execute(revenue_query).one()
        revenue = max(Decimal(collected or 0) - Decimal(refunded or 0), Decimal('0'))

        by_slot = []
        for slot, field_name in slots:
            matching = [item for item in occupied if self._booking_uses_slot(item, slot.id)]
            capacity = self._hours(slot.start_time, slot.end_time) * days
            used = sum(self._slot_hours(item, {slot.id}) for item in matching)
            by_slot.append({
                'slot_id': slot.id, 'field_id': slot.field_id, 'field_name': field_name,
                'start_time': slot.start_time.strftime('%H:%M'), 'end_time': slot.end_time.strftime('%H:%M'),
                'booking_count': len(matching), 'occupancy_rate': round(used / capacity * 100, 2) if capacity else 0.0,
            })
        by_slot.sort(key=lambda item: (item['occupancy_rate'], item['start_time'], item['field_name']))
        low_peak = by_slot[:3]
        high_peak = sorted(by_slot, key=lambda item: (-item['occupancy_rate'], item['start_time']))[:3]

        occupancy_by_court = []
        fields = {(slot.field_id, field_name) for slot, field_name in slots}
        for current_field_id, field_name in sorted(fields, key=lambda item: item[1]):
            field_slots = [slot for slot, _ in slots if slot.field_id == current_field_id]
            capacity = sum(self._hours(slot.start_time, slot.end_time) * days for slot in field_slots)
            matching = [item for item in occupied if item.field_id == current_field_id]
            used = sum(self._booking_hours(item) for item in matching)
            occupancy_by_court.append({
                'field_id': current_field_id, 'field_name': field_name,
                'total_available_hours': round(capacity, 2), 'booked_hours': round(used, 2),
                'booking_count': len(matching),
                'occupancy_rate': round(used / capacity * 100, 2) if capacity else 0.0,
            })
        occupancy_by_court.sort(key=lambda item: (item['occupancy_rate'], item['field_name']))

        daily_capacity = sum(self._hours(slot.start_time, slot.end_time) for slot, _ in slots)
        occupancy_by_day = []
        for offset in range(days):
            current_date = date_from + timedelta(days=offset)
            matching = [item for item in occupied if item.booking_date == current_date]
            used = sum(self._booking_hours(item) for item in matching)
            occupancy_by_day.append({
                'date': current_date, 'total_available_hours': round(daily_capacity, 2),
                'booked_hours': round(used, 2), 'booking_count': len(matching),
                'occupancy_rate': round(used / daily_capacity * 100, 2) if daily_capacity else 0.0,
            })

        occupancy_by_time = []
        time_groups = sorted({(slot.start_time, slot.end_time) for slot, _ in slots})
        for start_time, end_time in time_groups:
            group_slots = [slot for slot, _ in slots if slot.start_time == start_time and slot.end_time == end_time]
            group_ids = {slot.id for slot in group_slots}
            matching = [item for item in occupied if any(self._booking_uses_slot(item, slot_id) for slot_id in group_ids)]
            capacity = self._hours(start_time, end_time) * len(group_slots) * days
            used = sum(self._slot_hours(item, group_ids) for item in matching)
            occupancy_by_time.append({
                'start_time': start_time.strftime('%H:%M'), 'end_time': end_time.strftime('%H:%M'),
                'total_available_hours': round(capacity, 2), 'booked_hours': round(used, 2),
                'booking_count': len(matching),
                'occupancy_rate': round(used / capacity * 100, 2) if capacity else 0.0,
            })
        cancellations = sum(item.status in CANCELLED_STATUSES for item in bookings)
        measured = len([item for item in bookings if item.status not in ('expired', 'failed')])
        return {
            'date_from': date_from, 'date_to': date_to,
            'total_available_hours': round(total_hours, 2),
            'total_operating_hours': round(total_hours, 2), 'booked_hours': round(booked_hours, 2),
            'occupancy_rate': occupancy_rate, 'booking_count': len(occupied),
            'revenue': float(revenue),
            'occupancy_by_court': occupancy_by_court,
            'occupancy_by_day': occupancy_by_day,
            'occupancy_by_time': occupancy_by_time,
            'peak_hours': high_peak, 'low_demand_hours': low_peak, 'low_peak_hours': low_peak,
            'cancellation_rate': round(cancellations / measured * 100, 2) if measured else 0.0,
        }

    @staticmethod
    def _booking_uses_slot(booking: Booking, slot_id: int) -> bool:
        details = list(booking.booking_slots or [])
        return any(item.time_slot_id == slot_id for item in details) if details else booking.time_slot_id == slot_id

    def _slot_hours(self, booking: Booking, slot_ids: set[int]) -> float:
        details = list(booking.booking_slots or [])
        if not details:
            return self._hours(booking.start_time_snapshot, booking.end_time_snapshot) if booking.time_slot_id in slot_ids else 0.0
        return sum(
            self._hours(item.start_time_snapshot, item.end_time_snapshot)
            for item in details if item.time_slot_id in slot_ids
        )

    def _booking_hours(self, booking: Booking) -> float:
        details = list(booking.booking_slots or [])
        return sum(self._hours(item.start_time_snapshot, item.end_time_snapshot) for item in details) if details else self._hours(booking.start_time_snapshot, booking.end_time_snapshot)
