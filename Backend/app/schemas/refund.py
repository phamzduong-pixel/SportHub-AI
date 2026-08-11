from datetime import datetime
from math import ceil

from pydantic import BaseModel, Field, field_validator

from .user import RequestModel


class RefundMarkPaidRequest(RequestModel):
    transaction_reference: str = Field(min_length=3, max_length=120)
    evidence_url: str | None = Field(default=None, max_length=1000)
    note: str | None = Field(default=None, max_length=1000)

    @field_validator('transaction_reference')
    @classmethod
    def normalize_reference(cls, value: str):
        value = value.strip()
        if len(value) < 3:
            raise ValueError('Mã giao dịch phải có ít nhất 3 ký tự')
        return value

    @field_validator('evidence_url', 'note')
    @classmethod
    def normalize_optional(cls, value: str | None):
        return value.strip() or None if value is not None else None


class RefundDisputeRequest(RequestModel):
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator('reason')
    @classmethod
    def normalize_reason(cls, value: str):
        value = value.strip()
        if len(value) < 3:
            raise ValueError('Lý do khiếu nại phải có ít nhất 3 ký tự')
        return value


class BookingActivityResponse(BaseModel):
    id: int
    actor_id: int | None
    actor_name: str | None
    actor_role: str | None
    action: str
    from_status: str | None
    to_status: str | None
    details: dict
    created_at: datetime


class RefundResponse(BaseModel):
    id: int
    booking_id: int
    booking_code: str
    customer_id: int
    customer_name: str
    field_name: str
    amount: float
    status: str
    reason: str
    requested_by: int
    requested_by_name: str
    processed_by: int | None
    processed_by_name: str | None
    requested_at: datetime
    due_at: datetime
    refunded_at: datetime | None
    customer_confirmed_at: datetime | None
    disputed_at: datetime | None
    transaction_reference: str | None
    evidence_url: str | None
    dispute_reason: str | None
    is_overdue: bool
    activities: list[BookingActivityResponse]
    created_at: datetime
    updated_at: datetime


class RefundListResponse(BaseModel):
    items: list[RefundResponse]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def from_result(cls, items, total: int, page: int, page_size: int):
        return cls(items=items, total=total, page=page, page_size=page_size, pages=ceil(total / page_size) if total else 0)


class RefundReputationResponse(BaseModel):
    total_bookings: int
    owner_cancelled_bookings: int
    owner_cancellation_rate: float
    completed_refunds: int
    on_time_refunds: int
    on_time_refund_rate: float
