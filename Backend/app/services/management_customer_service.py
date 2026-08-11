from datetime import date

from fastapi import HTTPException

from ..core.ownership import management_owner_id
from ..repositories.management_customer_repository import ManagementCustomerRepository


class ManagementCustomerService:
    def __init__(self, db):
        self.db = db

    def _repository(self, user):
        owner_id = management_owner_id(user, self.db)
        if owner_id is None:
            raise HTTPException(status_code=403, detail='Bạn không có quyền xem khách hàng')
        return ManagementCustomerRepository(self.db, owner_id)

    def list(self, user, *, search, has_active, has_completed, has_cancelled,
             last_booking_from: date | None, last_booking_to: date | None,
             sort_by: str, sort_order: str, page: int, page_size: int):
        repository = self._repository(user)
        items = [repository.summarize(customer, bookings) for customer, bookings in repository.customer_bookings(search).items()]
        if has_active is not None:
            items = [item for item in items if (item['active_booking_count'] > 0) == has_active]
        if has_completed is not None:
            items = [item for item in items if (item['completed_booking_count'] > 0) == has_completed]
        if has_cancelled is not None:
            items = [item for item in items if (item['cancelled_booking_count'] > 0) == has_cancelled]
        if last_booking_from:
            items = [item for item in items if item['last_booking_at'].date() >= last_booking_from]
        if last_booking_to:
            items = [item for item in items if item['last_booking_at'].date() <= last_booking_to]
        key = {
            'last_booking': 'last_booking_at', 'booking_count': 'booking_count',
            'transaction_value': 'valid_transaction_value',
        }[sort_by]
        items.sort(key=lambda item: (item[key], item['id']), reverse=sort_order == 'desc')
        total = len(items)
        start = (page - 1) * page_size
        return items[start:start + page_size], total

    def detail(self, user, customer_id: int):
        repository = self._repository(user)
        customer, bookings = repository.get_customer_bookings(customer_id)
        if customer is None:
            raise HTTPException(status_code=404, detail='Không tìm thấy khách hàng trong các cơ sở của bạn')
        summary = repository.summarize(customer, bookings)
        summary['bookings'] = [{
            'id': booking.id, 'booking_code': booking.booking_code,
            'facility_name': booking.facility_name_snapshot or (booking.field.facility.name if booking.field.facility else booking.field.name),
            'field_name': booking.field.name, 'booking_date': booking.booking_date,
            'start_time': booking.start_time_snapshot, 'end_time': booking.end_time_snapshot,
            'status': booking.status, 'total_amount': float(booking.total_amount or 0),
            'deposit_amount': float(booking.deposit_amount or 0), 'paid_amount': float(booking.paid_amount or 0),
            'payment_status': booking.payment_status,
        } for booking in bookings]
        return summary
