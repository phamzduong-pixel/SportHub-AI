from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RepresentativeDetails(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=8, max_length=20, pattern=r'^\+?[0-9 ]+$')
    email: str = Field(min_length=5, max_length=255)
    identity_number: str = Field(min_length=6, max_length=30, pattern=r'^[A-Za-z0-9-]+$')

    @field_validator('email', mode='before')
    @classmethod
    def validate_email_minimum_length(cls, value: Any):
        if isinstance(value, str) and len(value.strip()) < 5:
            raise ValueError('Vui lòng nhập email ít nhất 5 ký tự')
        return value

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str):
        if value.count('@') != 1 or '.' not in value.rsplit('@', 1)[1]:
            raise ValueError('Email người đại diện không hợp lệ')
        return value.lower()


class VenueDetails(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=160)
    address: str = Field(min_length=5, max_length=500)
    city: str = Field(default='', max_length=120)
    district: str = Field(default='', max_length=120)
    phone: str = Field(default='', max_length=20, pattern=r'^(|\+?[0-9 ]+)$')
    sports: list[str] = Field(min_length=1, max_length=20)
    description: str = Field(default='', max_length=2000)

    @field_validator('address', mode='before')
    @classmethod
    def validate_address_minimum_length(cls, value: Any):
        if isinstance(value, str) and len(value.strip()) < 5:
            raise ValueError('Vui lòng nhập địa chỉ ít nhất 5 ký tự')
        return value

    @field_validator('sports')
    @classmethod
    def validate_sports(cls, values: list[str]):
        normalized = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        if not normalized:
            raise ValueError('Phải chọn ít nhất một môn thể thao')
        return normalized


class OwnerApplicationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    representative: RepresentativeDetails
    venue: VenueDetails
    legal_confirmed: bool


class OwnerApplicationDecision(BaseModel):
    approved: bool
    rejection_reason: str | None = Field(default=None, max_length=1000)


class OwnerApplicationReview(BaseModel):
    action: Literal['APPROVE', 'REQUEST_MORE_INFO', 'REJECT']
    admin_note: str | None = Field(default=None, max_length=1000)


class OwnerApplicationWithdraw(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class OwnerApplicationDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    representative: dict[str, Any] = Field(default_factory=dict)
    venue: dict[str, Any] = Field(default_factory=dict)
    legal_confirmed: bool = False


class OwnerApplicationResponse(BaseModel):
    id: int
    customer_id: int
    customer_name: str
    customer_email: str
    customer_phone: str | None
    status: str
    representative: dict[str, Any]
    venue: dict[str, Any]
    legal_confirmed: bool
    rejection_reason: str | None
    admin_note: str | None
    has_document: bool
    document_file_name: str | None
    document_mime: str | None
    document_size: int | None
    document_uploaded_at: datetime | None
    submitted_at: datetime | None
    reviewed_at: datetime | None
    withdrawn_at: datetime | None
    withdraw_reason: str | None
    reviewed_by: int | None
    reviewer_name: str | None
    created_at: datetime
    updated_at: datetime
