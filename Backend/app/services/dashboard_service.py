from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from ..core.config import settings
from ..core.ownership import management_owner_id
from ..repositories.dashboard_repository import DashboardRepository
from ..schemas.dashboard import (
    BookingReport, DashboardSummary, FieldPerformanceReport,
    RevenueAnalyticsReport, RevenueReport, TimeSlotPerformanceReport,
)


class DashboardService:
    def __init__(self, repository: DashboardRepository):
        self.repository = repository
        self.timezone = ZoneInfo(settings.TIMEZONE)

    def for_user(self, user):
        owner_id = management_owner_id(user, self.repository.db)
        if owner_id is None:
            raise HTTPException(status_code=403, detail='Tài khoản quản lý chưa được gán cho OWNER')
        self.repository.scope_to_owner(owner_id)
        return self

    def summary(self, date_from: date | None, date_to: date | None, field_id: int | None):
        start, end = self._range(date_from, date_to)
        total_fields, active_fields = self.repository.field_counts(field_id)
        counts = {status: int(count) for status, count in self.repository.booking_status_counts(start, end, field_id)}
        revenue = sum((Decimal(amount) for _, amount in self.repository.revenue_rows(*self._date_times(start, end), field_id)), Decimal('0'))
        return DashboardSummary(
            date_from=start, date_to=end, total_fields=total_fields, active_fields=active_fields,
            total_bookings=sum(counts.values()), pending_bookings=sum(counts.get(status, 0) for status in ('pending', 'pending_payment', 'pending_confirmation')),
            confirmed_bookings=counts.get('confirmed', 0), paid_revenue=float(revenue),
        )

    def revenue(self, date_from: date | None, date_to: date | None, field_id: int | None):
        start, end = self._range(date_from, date_to)
        granularity = self._revenue_granularity(start, end)
        values: dict[str, Decimal] = {}
        for paid_at, amount in self.repository.revenue_rows(*self._date_times(start, end), field_id):
            key = self._period(self._local_date(paid_at), granularity)
            values[key] = values.get(key, Decimal('0')) + Decimal(amount)
        items = [{'period': period, 'revenue': float(values.get(period, 0))} for period in self._periods(start, end, granularity)]
        return RevenueReport(granularity=granularity, total=float(sum(values.values(), Decimal('0'))), items=items)

    def bookings(self, date_from: date | None, date_to: date | None, field_id: int | None):
        start, end = self._range(date_from, date_to)
        granularity = self._granularity(start, end)
        values: dict[str, dict[str, int]] = {}
        for booking_date, status, count in self.repository.booking_series(start, end, field_id):
            key = self._period(booking_date, granularity)
            status = 'pending' if status in ('pending_payment', 'pending_confirmation') else status
            values.setdefault(key, {})[status] = values.setdefault(key, {}).get(status, 0) + int(count)
        items = []
        for period in self._periods(start, end, granularity):
            row = values.get(period, {})
            items.append({'period': period, 'total': sum(row.values()), **{status: row.get(status, 0) for status in ('pending', 'confirmed', 'completed', 'cancelled', 'rejected')}})
        return BookingReport(granularity=granularity, total=sum(item['total'] for item in items), items=items)

    def field_performance(self, date_from: date | None, date_to: date | None, field_id: int | None):
        start, end = self._range(date_from, date_to)
        booking_stats, revenue_stats = self._performance_maps(start, end, field_id)
        slot_counts = {row_field_id: int(count) for row_field_id, count in self.repository.active_slot_counts(field_id)}
        days = (end - start).days + 1
        items = []
        for field in self.repository.fields(field_id):
            stats = booking_stats.get(('field', field.id), {})
            capacity = slot_counts.get(field.id, 0) * days
            slot_stats = booking_stats.get(('field_slots', field.id), {})
            used = slot_stats.get('confirmed', 0) + slot_stats.get('completed', 0)
            items.append({
                'field_id': field.id, 'field_name': field.name, 'sport_type': field.sport_type, 'status': field.status,
                'booking_count': sum(stats.values()), 'confirmed_count': stats.get('confirmed', 0),
                'completed_count': stats.get('completed', 0), 'paid_revenue': float(revenue_stats.get(('field', field.id), 0)),
                'utilization_rate': round(min(used / capacity * 100, 100), 2) if capacity else 0,
            })
        items.sort(key=lambda item: (-item['booking_count'], -item['paid_revenue'], item['field_name']))
        return FieldPerformanceReport(items=items)

    def time_slot_performance(self, date_from: date | None, date_to: date | None, field_id: int | None):
        start, end = self._range(date_from, date_to)
        booking_stats, revenue_stats = self._performance_maps(start, end, field_id)
        items = []
        for slot, field_name in self.repository.time_slots(field_id):
            stats = booking_stats.get(('slot', slot.id), {})
            items.append({
                'time_slot_id': slot.id, 'time_slot_name': slot.name,
                'field_id': slot.field_id, 'field_name': field_name,
                'start_time': slot.start_time.strftime('%H:%M'), 'end_time': slot.end_time.strftime('%H:%M'),
                'booking_count': sum(stats.values()), 'confirmed_count': stats.get('confirmed', 0),
                'completed_count': stats.get('completed', 0), 'paid_revenue': float(revenue_stats.get(('slot', slot.id), 0)),
            })
        items.sort(key=lambda item: (-item['booking_count'], item['field_name'], item['start_time']))
        return TimeSlotPerformanceReport(items=items)

    def revenue_analytics(self, date_from: date | None, date_to: date | None, field_id: int | None):
        start, end = self._range(date_from, date_to)
        rows = self.repository.financial_rows(start, end, field_id)
        days = (end - start).days + 1
        previous_end = start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=days - 1)
        previous = self._financial_summary(self.repository.financial_rows(previous_start, previous_end, field_id))
        summary = self._financial_summary(rows)
        today = datetime.now(self.timezone).date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        today_net = self._financial_summary(self.repository.financial_rows(today, today, field_id))['net_revenue']
        week_net = self._financial_summary(self.repository.financial_rows(week_start, today, field_id))['net_revenue']
        month_net = self._financial_summary(self.repository.financial_rows(month_start, today, field_id))['net_revenue']
        previous_net = previous['net_revenue']
        change = None if previous_net == 0 else round((summary['net_revenue'] - previous_net) / previous_net * 100, 2)
        granularity = self._granularity(start, end)
        return RevenueAnalyticsReport(
            summary={
                'date_from': start, 'date_to': end, **summary,
                'previous_net_revenue': previous_net, 'change_percent': change,
                'today_revenue': today_net, 'week_revenue': week_net, 'month_revenue': month_net,
            },
            granularity=granularity,
            trend=self._breakdown(rows, lambda row: self._period(row['booking_date'], granularity), lambda key: key),
            by_facility=self._breakdown(rows, lambda row: str(row['facility_id'] or 0), lambda key, source=rows: next((row['facility_name'] for row in source if str(row['facility_id'] or 0) == key), None) or 'Chưa gán cơ sở'),
            by_field=self._breakdown(rows, lambda row: str(row['field_id']), lambda key, source=rows: next(row['field_name'] for row in source if str(row['field_id']) == key)),
            by_sport=self._breakdown(rows, lambda row: row['sport_type'], lambda key: key),
            by_time_slot=self._breakdown(rows, lambda row: row['start_time_snapshot'].strftime('%H:%M'), lambda key: key),
            popular_products=[{
                'product_id': row['product_id'], 'name': row['name'],
                'product_type': row['product_type'], 'quantity': int(row['quantity']),
                'booking_count': int(row['booking_count']), 'revenue': float(row['revenue']),
            } for row in self.repository.popular_products(start, end, field_id)],
            transactions=[self._transaction(row) for row in rows],
        )

    @staticmethod
    def _financial_summary(rows):
        valid_statuses = {'pending_payment', 'pending_confirmation', 'confirmed', 'in_progress', 'completed', 'no_show'}
        cancelled_statuses = {'cancelled', 'cancelled_by_customer', 'cancelled_by_owner', 'expired', 'failed', 'rejected'}
        booking_value = collected = deposits = held = refunded = completed_revenue = outstanding = Decimal('0')
        court_revenue = service_revenue = Decimal('0')
        completed_count = cancelled_count = 0
        for row in rows:
            total = Decimal(row['total_amount'] or 0); paid = Decimal(row['collected'] or 0); refund = DashboardService._refund_value(row)
            net = max(paid - refund, Decimal('0'))
            court_net, service_net = DashboardService._revenue_parts(row, paid, refund)
            court_revenue += court_net; service_revenue += service_net
            if row['status'] in valid_statuses:
                booking_value += total
                outstanding += max(total - paid, Decimal('0'))
            collected += paid; deposits += Decimal(row['deposits'] or 0); held += Decimal(row['held_deposits'] or 0); refunded += refund
            if row['status'] == 'completed':
                completed_count += 1
                if paid >= total:
                    completed_revenue += net
            if row['status'] in cancelled_statuses:
                cancelled_count += 1
        return {
            'booking_value': float(booking_value), 'collected_amount': float(collected),
            'deposit_amount': float(deposits), 'held_deposit_amount': float(held),
            'outstanding_amount': float(outstanding), 'completed_revenue': float(completed_revenue),
            'refunded_amount': float(refunded), 'net_revenue': float(max(collected - refunded, Decimal('0'))),
            'court_revenue': float(court_revenue), 'service_revenue': float(service_revenue),
            'total_revenue': float(court_revenue + service_revenue),
            'completed_bookings': completed_count, 'cancelled_bookings': cancelled_count,
        }

    def _breakdown(self, rows, key_fn, label_fn):
        groups = {}
        for row in rows:
            key = key_fn(row); group = groups.setdefault(key, {'booking_count': 0, 'collected': Decimal('0'), 'refunded': Decimal('0')})
            group['booking_count'] += 1; group['collected'] += Decimal(row['collected'] or 0); group['refunded'] += self._refund_value(row)
        return [{
            'key': key, 'label': label_fn(key), 'booking_count': value['booking_count'],
            'collected_amount': float(value['collected']), 'refunded_amount': float(value['refunded']),
            'net_revenue': float(max(value['collected'] - value['refunded'], Decimal('0'))),
        } for key, value in sorted(groups.items(), key=lambda item: item[0])]

    @staticmethod
    def _transaction(row):
        total = Decimal(row['total_amount'] or 0); collected = Decimal(row['collected'] or 0); refunded = DashboardService._refund_value(row)
        active = row['status'] in {'pending_payment', 'pending_confirmation', 'confirmed', 'in_progress', 'completed', 'no_show'}
        return {
            'booking_id': row['id'], 'booking_code': row['booking_code'], 'customer_name': row['customer_name'],
            'facility_name': row['facility_name'] or 'Chưa gán cơ sở', 'field_name': row['field_name'], 'sport_type': row['sport_type'],
            'booking_date': row['booking_date'], 'court_amount': float(row['court_amount'] or 0),
            'service_amount': float(row['service_amount'] or 0),
            'total_amount': float(total), 'collected_amount': float(collected),
            'refunded_amount': float(refunded), 'net_revenue': float(max(collected - refunded, Decimal('0'))),
            'outstanding_amount': float(max(total - collected, Decimal('0'))) if active else 0,
            'status': row['status'], 'last_paid_at': row['last_paid_at'],
        }

    @staticmethod
    def _revenue_parts(row, collected: Decimal, refunded: Decimal):
        court = Decimal(row['court_amount'] or 0)
        service = Decimal(row['service_amount'] or 0)
        if court == 0 and service == 0:
            court = Decimal(row['total_amount'] or 0)
        court_collected = min(collected, court)
        service_collected = min(max(collected - court_collected, Decimal('0')), service)
        court_refund = min(refunded, court_collected)
        service_refund = min(max(refunded - court_refund, Decimal('0')), service_collected)
        return max(court_collected - court_refund, Decimal('0')), max(service_collected - service_refund, Decimal('0'))

    @staticmethod
    def _refund_value(row):
        # Some legacy records marked the original payment REFUNDED without a refund transaction.
        # Taking the larger representation supports both schemas without subtracting one refund twice.
        return max(Decimal(row['refund_transactions'] or 0), Decimal(row['legacy_refunded'] or 0))

    @staticmethod
    def _revenue_granularity(start: date, end: date):
        days = (end - start).days
        return 'month' if days > 180 else 'week' if days > 45 else 'day'

    def _performance_maps(self, start: date, end: date, field_id: int | None):
        booking_stats: dict[tuple[str, int], dict[str, int]] = {}
        for row_field_id, status, count in self.repository.field_booking_performance(start, end, field_id):
            booking_stats.setdefault(('field', row_field_id), {})[status] = int(count)
        slot_rows = [
            *self.repository.slot_booking_performance(start, end, field_id),
            *self.repository.legacy_slot_booking_performance(start, end, field_id),
        ]
        for row_field_id, slot_id, status, count in slot_rows:
            booking_stats.setdefault(('slot', slot_id), {})[status] = int(count)
            field_slot_stats = booking_stats.setdefault(('field_slots', row_field_id), {})
            field_slot_stats[status] = field_slot_stats.get(status, 0) + int(count)
        revenue_stats: dict[tuple[str, int], Decimal] = {}
        period = self._date_times(start, end)
        for row_field_id, amount in self.repository.field_revenue_performance(*period, field_id):
            revenue_stats[('field', row_field_id)] = Decimal(amount)
        slot_revenue_rows = [
            *self.repository.slot_revenue_performance(*period, field_id),
            *self.repository.legacy_slot_revenue_performance(*period, field_id),
        ]
        for slot_id, amount in slot_revenue_rows:
            revenue_stats[('slot', slot_id)] = revenue_stats.get(('slot', slot_id), Decimal('0')) + Decimal(amount)
        return booking_stats, revenue_stats

    def _range(self, date_from: date | None, date_to: date | None):
        end = date_to or datetime.now(self.timezone).date()
        start = date_from or end - timedelta(days=29)
        if start > end:
            raise HTTPException(status_code=422, detail='date_from phải nhỏ hơn hoặc bằng date_to')
        if (end - start).days > 730:
            raise HTTPException(status_code=422, detail='Khoảng thống kê không được vượt quá 731 ngày')
        return start, end

    def _date_times(self, start: date, end: date):
        local_start = datetime.combine(start, time.min, tzinfo=self.timezone)
        local_end = datetime.combine(end + timedelta(days=1), time.min, tzinfo=self.timezone)
        return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)

    def _local_date(self, value: datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(self.timezone).date()

    @staticmethod
    def _granularity(start: date, end: date):
        return 'month' if (end - start).days > 90 else 'day'

    @staticmethod
    def _period(value: date, granularity: str):
        if granularity == 'month':
            return value.strftime('%Y-%m')
        if granularity == 'week':
            return (value - timedelta(days=value.weekday())).isoformat()
        return value.isoformat()

    def _periods(self, start: date, end: date, granularity: str):
        if granularity == 'day':
            return [(start + timedelta(days=offset)).isoformat() for offset in range((end - start).days + 1)]
        values, current = [], start.replace(day=1)
        while current <= end:
            values.append(current.strftime('%Y-%m'))
            current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
        return values
