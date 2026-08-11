from datetime import datetime, time
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .user import RequestModel


def normalize_phone(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    phone = value.strip()
    if not re.fullmatch(r'\+?[0-9\s().-]+', phone):
        raise ValueError('Số điện thoại chỉ được chứa chữ số, dấu +, khoảng trắng, dấu chấm, gạch ngang hoặc ngoặc')
    digit_count = len(re.sub(r'\D', '', phone))
    if digit_count < 9 or digit_count > 15:
        raise ValueError('Số điện thoại phải có từ 9 đến 15 chữ số')
    return phone


class CancellationRule(RequestModel):
    min_minutes_before: int = Field(ge=0, le=525600)
    refund_percent: float = Field(ge=0, le=100)


class CancellationPolicyUpdate(RequestModel):
    free_cancellation_minutes: int | None = Field(default=None, ge=0, le=525600)
    rules: list[CancellationRule] | None = Field(default=None, min_length=1, max_length=10)

    @field_validator('rules')
    @classmethod
    def validate_rules(cls, rules):
        if rules is None:
            return None
        thresholds = [rule.min_minutes_before for rule in rules]
        if len(thresholds) != len(set(thresholds)):
            raise ValueError('Các mốc thời gian hủy không được trùng nhau')
        if 0 not in thresholds:
            raise ValueError('Chính sách phải có mốc 0 phút')
        return sorted(rules, key=lambda rule: rule.min_minutes_before, reverse=True)

    @model_validator(mode='after')
    def require_policy(self):
        if self.free_cancellation_minutes is None and self.rules is None:
            raise ValueError('Cần cung cấp thời hạn hủy miễn phí')
        return self


class FacilityCreate(RequestModel):
    name: str = Field(min_length=2, max_length=160)
    location: str = Field(min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    cancellation_rules: list[CancellationRule] | None = None
    free_cancellation_minutes: int = Field(default=360, ge=0, le=525600)
    contact_phone: str | None = Field(default=None, max_length=20)
    opening_time: time | None = None
    closing_time: time | None = None
    amenities: list[str] = Field(default_factory=list, max_length=30)
    image_urls: list[str] = Field(default_factory=list, max_length=20)

    @field_validator('contact_phone', mode='before')
    @classmethod
    def validate_contact_phone(cls, value):
        return normalize_phone(value)


class FacilityUpdate(FacilityCreate):
    free_cancellation_minutes: int | None = Field(default=None, ge=0, le=525600)


class FacilityHotlineUpdate(RequestModel):
    contact_phone: str | None = Field(default=None, max_length=20)

    @field_validator('contact_phone', mode='before')
    @classmethod
    def validate_contact_phone(cls, value):
        return normalize_phone(value)


class FacilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner_id: int
    name: str
    location: str
    description: str | None
    contact_phone: str | None
    opening_time: time | None
    closing_time: time | None
    amenities: list[str]
    image_urls: list[str]
    cancellation_rules: list[CancellationRule]
    free_cancellation_minutes: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
