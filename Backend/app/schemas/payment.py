from datetime import date, datetime
from decimal import Decimal
from math import ceil

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models.payment import PaymentMethod, PaymentStatus, PaymentType
from .user import RequestModel


class PaymentCreate(RequestModel):
    booking_id: int = Field(gt=0)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    payment_method: PaymentMethod
    payment_type: PaymentType
    note: str | None = Field(default=None, max_length=1000)

    @field_validator('note')
    @classmethod
    def normalize_note(cls, value: str | None):
        return value.strip() or None if value is not None else None


class PaymentActionNote(RequestModel):
    note: str | None = Field(default=None, max_length=1000)


class BankPaymentIntentCreate(RequestModel):
    booking_id: int = Field(gt=0)
    payment_type: PaymentType = PaymentType.DEPOSIT


class BankWebhookPayload(RequestModel):
    provider_reference: str = Field(min_length=3, max_length=120)
    transfer_content: str = Field(min_length=3, max_length=80)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    status: str = Field(pattern='^(success|paid)$')


class InvoiceInfo(BaseModel):
    invoice_number: str
    transaction_code: str
    booking_code: str
    customer_name: str
    customer_email: str
    field_name: str
    facility_name: str
    booking_date: date
    total_amount: float
    deposit_amount: float
    remaining_payment_amount: float
    paid_amount: float
    remaining_amount: float
    payment_method: PaymentMethod
    bank_name: str | None
    paid_at: datetime


class DepositReceiptResponse(BaseModel):
    receipt_number: str
    booking_id: int
    booking_code: str
    customer_name: str
    facility_name: str
    facility_address: str
    field_name: str
    sport_type: str
    booking_date: date
    start_time: str
    end_time: str
    total_amount: float
    deposit_paid: float
    remaining_amount: float
    transaction_code: str
    payment_method: PaymentMethod
    bank_name: str | None
    paid_at: datetime
    booking_status: str
    deposit_status: str
    status_message: str
    refund_status: str
    refund_amount: float
    refunded_at: datetime | None


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_id: int
    booking_code: str
    customer_id: int
    owner_id: int
    customer_name: str
    field_name: str
    booking_date: date
    booking_total: float
    transaction_code: str
    amount: float
    total_amount: float
    deposit_amount: float
    remaining_amount: float
    paid_amount: float
    payment_status: str
    bank_id: str | None
    bank_name: str | None
    bank_account_no: str | None
    bank_account_name: str | None
    transfer_content: str | None
    qr_url: str | None
    expires_at: datetime | None
    provider_reference: str | None
    provider: str | None
    verification_source: str | None
    refund_status: str
    payment_mode: str
    payment_method: PaymentMethod
    payment_type: PaymentType
    status: PaymentStatus
    escrow_status: str
    paid_at: datetime | None
    failed_reason: str | None
    refunded_at: datetime | None
    confirmed_by: int | None
    confirmer_name: str | None
    note: str | None
    invoice: InvoiceInfo | None
    created_at: datetime
    updated_at: datetime


class PaymentListResponse(BaseModel):
    items: list[PaymentResponse]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def from_result(cls, items, total: int, page: int, page_size: int):
        return cls(items=items, total=total, page=page, page_size=page_size, pages=ceil(total / page_size) if total else 0)


class PaymentSummary(BaseModel):
    booking_id: int
    booking_code: str
    total_amount: float
    deposit_amount: float
    additional_paid_amount: float
    paid_amount: float
    pending_amount: float
    remaining_amount: float
    payment_status: str
    transactions: list[PaymentResponse]
