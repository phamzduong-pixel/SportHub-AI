from datetime import date, datetime, time
from math import ceil

from pydantic import BaseModel


class ManagementCustomerSummary(BaseModel):
    id: int
    full_name: str
    email: str
    phone: str | None
    booking_count: int
    completed_booking_count: int
    active_booking_count: int
    cancelled_booking_count: int
    valid_transaction_value: float
    last_booking_at: datetime
    created_at: datetime


class ManagementCustomerList(BaseModel):
    items: list[ManagementCustomerSummary]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def from_result(cls, items, total: int, page: int, page_size: int):
        return cls(
            items=items, total=total, page=page, page_size=page_size,
            pages=ceil(total / page_size) if total else 0,
        )


class ManagementCustomerBooking(BaseModel):
    id: int
    booking_code: str
    facility_name: str
    field_name: str
    booking_date: date
    start_time: time
    end_time: time
    status: str
    total_amount: float
    deposit_amount: float
    paid_amount: float
    payment_status: str


class ManagementCustomerDetail(ManagementCustomerSummary):
    bookings: list[ManagementCustomerBooking]
