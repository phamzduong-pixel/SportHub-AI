import re
from datetime import date, datetime, time
from math import ceil

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..models.field import BookingStatus
from .field import FieldResponse
from .time_slot import TimeSlotResponse
from .user import RequestModel


class BookingProductSelection(RequestModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=1000)


class BookingProductQuantityUpdate(RequestModel):
    quantity: int = Field(gt=0, le=1000)


class BookingProductSnapshot(BaseModel):
    item_id: int | None = None
    product_id: int
    name: str
    product_type: str
    unit: str
    quantity: int
    unit_price: float
    subtotal: float
    inventory_status: str | None = None
    source: str = 'CUSTOMER_BOOKING'
    added_by: int | None = None
    added_by_name: str | None = None
    added_at: datetime | None = None

class BookingCreate(RequestModel):
    field_id: int = Field(gt=0)
    time_slot_id: int | None = Field(default=None, gt=0)
    time_slot_ids: list[int] | None = Field(default=None, min_length=1, max_length=24)
    booking_date: date
    note: str | None = Field(default=None, max_length=1000)
    customer_id: int | None = Field(default=None, gt=0)
    customer_email: str | None = Field(default=None, max_length=255)
    product_items: list[BookingProductSelection] = Field(default_factory=list, max_length=20)

    @model_validator(mode='after')
    def normalize_slots(self):
        ids = self.time_slot_ids or ([self.time_slot_id] if self.time_slot_id else [])
        if not ids or len(ids) != len(set(ids)) or any(slot_id <= 0 for slot_id in ids):
            raise ValueError('Danh sách khung giờ không hợp lệ')
        self.time_slot_ids, self.time_slot_id = ids, ids[0]
        product_ids = [item.product_id for item in self.product_items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError('Danh sách sản phẩm bị trùng')
        return self

    @field_validator('note', 'customer_email')
    @classmethod
    def normalize_optional(cls, value: str | None):
        if value is None:
            return None
        return value.strip() or None

    @field_validator('customer_email')
    @classmethod
    def validate_email(cls, value: str | None):
        if value and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Email khách hàng không hợp lệ')
        return value.lower() if value else None

class BookingUpdate(RequestModel):
    field_id: int = Field(gt=0)
    time_slot_id: int | None = Field(default=None, gt=0)
    time_slot_ids: list[int] | None = Field(default=None, min_length=1, max_length=24)
    booking_date: date
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode='after')
    def normalize_slots(self):
        ids = self.time_slot_ids or ([self.time_slot_id] if self.time_slot_id else [])
        if not ids or len(ids) != len(set(ids)):
            raise ValueError('Danh sách khung giờ không hợp lệ')
        self.time_slot_ids, self.time_slot_id = ids, ids[0]
        return self

class BookingActionNote(RequestModel):
    note: str | None = Field(default=None, max_length=1000)

class BookingCancellationRequest(RequestModel):
    reason: str | None = Field(default=None, min_length=3, max_length=1000)
    note: str | None = Field(default=None, max_length=1000)

    @field_validator('reason')
    @classmethod
    def normalize_reason(cls, value: str | None):
        return value.strip() if value else None

class BookingCancellationQuote(BaseModel):
    booking_id: int
    cancellable: bool
    minutes_before_start: int
    refund_percent: float
    paid_deposit_amount: float
    refund_amount: float
    forfeited_deposit_amount: float
    free_cancellation_minutes: int
    free_cancellation_deadline: datetime
    is_late_cancellation: bool
    warning_message: str | None = None
    reason_required: bool = True

class BookingRescheduleRequest(RequestModel):
    field_id: int = Field(gt=0)
    time_slot_id: int | None = Field(default=None, gt=0)
    time_slot_ids: list[int] | None = Field(default=None, min_length=1, max_length=24)
    booking_date: date

    @model_validator(mode='after')
    def normalize_slots(self):
        ids = self.time_slot_ids or ([self.time_slot_id] if self.time_slot_id else [])
        if not ids or len(ids) != len(set(ids)):
            raise ValueError('Danh sách khung giờ không hợp lệ')
        self.time_slot_ids, self.time_slot_id = ids, ids[0]
        return self

class BookingSlotSnapshot(BaseModel):
    time_slot_id: int
    name: str
    start_time: time
    end_time: time
    price: float

class BookingRescheduleQuote(BaseModel):
    booking_id: int
    field_id: int
    time_slot_id: int
    time_slot_ids: list[int] = []
    booking_date: date
    old_total_amount: float
    new_total_amount: float
    price_difference: float
    additional_payment_required: float
    credit_amount: float

class BookingInvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    invoice_number: str
    booking_id: int
    booking_code: str
    customer_name: str
    customer_email: str
    facility_name: str
    field_name: str
    booking_date: date
    start_time: time
    end_time: time
    duration_minutes: int
    selected_slots: list[BookingSlotSnapshot] = []
    court_amount: float
    service_amount: float
    product_items: list[BookingProductSnapshot] = []
    total_amount: float
    deposit_amount: float
    remaining_payment_amount: float
    refund_amount: float
    net_received_amount: float
    payment_methods: str
    paid_at: datetime | None
    issued_at: datetime

class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_code: str
    customer_id: int
    customer_name: str
    customer_email: str
    customer_phone: str | None
    facility_id: int | None
    facility_name: str
    facility_hotline: str | None
    field_id: int
    field_name: str
    sport_type: str
    field_capacity: int
    location: str
    time_slot_id: int
    time_slot_ids: list[int] = []
    selected_slots: list[BookingSlotSnapshot] = []
    time_slot_name: str
    booking_date: date
    start_time_snapshot: time
    end_time_snapshot: time
    price_snapshot: float
    court_amount: float
    service_amount: float
    product_items: list[BookingProductSnapshot] = []
    total_amount: float
    deposit_type: str
    deposit_value: float
    deposit_amount: float
    paid_amount: float
    additional_paid_amount: float
    remaining_amount: float
    payment_status: str
    status: BookingStatus
    hold_expires_at: datetime | None
    note: str | None
    created_at: datetime
    updated_at: datetime
    duration_minutes: int
    cancellation_policy: str
    cancellation_refund_percent: float | None
    free_cancellation_minutes: int
    refundable_deposit_amount: float | None
    refund_amount: float
    credit_amount: float
    additional_payment_required: float
    refund_status: str
    cancellation_reason: str | None
    cancelled_at: datetime | None
    cancelled_by: int | None
    rescheduled_at: datetime | None
    reviewed: bool
    timeline: list[dict] = []

class BookingQuote(BaseModel):
    venue_id: int | None
    venue_name: str
    field_id: int
    field_name: str
    sport_type: str
    field_type: str
    location: str
    time_slot_id: int
    time_slot_ids: list[int] = []
    selected_slots: list[BookingSlotSnapshot] = []
    time_slot_name: str
    booking_date: date
    start_time: time
    end_time: time
    duration_minutes: int
    price: float
    court_amount: float
    service_amount: float
    product_items: list[BookingProductSnapshot] = []
    total_amount: float
    deposit_amount: float
    remaining_amount: float
    deposit_type: str
    deposit_value: float
    hold_minutes: int
    free_cancellation_minutes: int
    cancellation_policy_summary: str

class BookingListResponse(BaseModel):
    items: list[BookingResponse]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def from_result(cls, items, total: int, page: int, page_size: int):
        return cls(items=items, total=total, page=page, page_size=page_size, pages=ceil(total / page_size) if total else 0)

class AvailabilityField(BaseModel):
    field: FieldResponse
    available_slots: list[TimeSlotResponse]
