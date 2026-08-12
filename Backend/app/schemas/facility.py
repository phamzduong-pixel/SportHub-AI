from datetime import date, datetime, time
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .user import RequestModel

SPORTS = {'Bóng đá', 'Cầu lông', 'Pickleball', 'Tennis', 'Bóng rổ', 'Bóng chuyền'}


def normalize_phone(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    phone = value.strip()
    if not re.fullmatch(r'\+?[0-9\s().-]+', phone):
        raise ValueError('Hotline không đúng định dạng')
    digit_count = len(re.sub(r'\D', '', phone))
    if digit_count < 9 or digit_count > 15:
        raise ValueError('Hotline phải có từ 9 đến 15 chữ số')
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
        if len(thresholds) != len(set(thresholds)) or 0 not in thresholds:
            raise ValueError('Chính sách hủy không hợp lệ')
        return sorted(rules, key=lambda rule: rule.min_minutes_before, reverse=True)

    @model_validator(mode='after')
    def require_policy(self):
        if self.free_cancellation_minutes is None and self.rules is None:
            raise ValueError('Cần cung cấp chính sách hủy')
        return self


class FacilityCreate(RequestModel):
    name: str = Field(min_length=2, max_length=160)
    location: str = Field(min_length=5, max_length=500)
    description: str | None = Field(default=None, max_length=2000)
    contact_phone: str | None = Field(default=None, max_length=20)
    contact_email: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    opening_time: time | None = None
    closing_time: time | None = None
    sports: list[str] = Field(default_factory=list, max_length=6)
    amenities: list[str] = Field(default_factory=list, max_length=30)
    cancellation_rules: list[CancellationRule] | None = None
    free_cancellation_minutes: int = Field(default=360, ge=0, le=525600)
    image_urls: list[str] = Field(default_factory=list, max_length=20)

    @field_validator('contact_phone', mode='before')
    @classmethod
    def validate_phone(cls, value):
        return normalize_phone(value)

    @field_validator('contact_email')
    @classmethod
    def validate_email(cls, value):
        if value and (value.count('@') != 1 or '.' not in value.rsplit('@', 1)[1]):
            raise ValueError('Email liên hệ không hợp lệ')
        return value.lower() if value else None

    @field_validator('sports')
    @classmethod
    def validate_sports(cls, values):
        normalized = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        invalid = [value for value in normalized if value not in SPORTS]
        if invalid:
            raise ValueError('Môn thể thao không thuộc danh mục hỗ trợ')
        return normalized

    @model_validator(mode='after')
    def validate_hours(self):
        if self.opening_time and self.closing_time and self.opening_time >= self.closing_time:
            raise ValueError('Giờ mở cửa phải trước giờ đóng cửa')
        return self


class FacilityUpdate(FacilityCreate):
    free_cancellation_minutes: int | None = Field(default=None, ge=0, le=525600)


class FacilityHotlineUpdate(RequestModel):
    contact_phone: str | None = Field(default=None, max_length=20)
    _phone = field_validator('contact_phone', mode='before')(normalize_phone)


class FacilityDocumentMeta(RequestModel):
    document_type: str = Field(min_length=2, max_length=50)
    document_name: str = Field(min_length=2, max_length=255)
    document_number: str | None = Field(default=None, max_length=100)
    issued_date: date | None = None
    issued_by: str | None = Field(default=None, max_length=255)


class FacilityReviewRequest(RequestModel):
    action: str
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode='after')
    def validate_action(self):
        if self.action not in {'APPROVE', 'REJECT', 'SUSPEND', 'RESTORE'}:
            raise ValueError('Thao tác xét duyệt không hợp lệ')
        if self.action in {'REJECT', 'SUSPEND'} and len((self.reason or '').strip()) < 3:
            raise ValueError('Phải nhập lý do ít nhất 3 ký tự')
        return self


class FacilityImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category: str
    original_name: str
    mime_type: str
    file_size: int
    sort_order: int
    created_at: datetime
    url: str | None = None


class FacilityDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    document_type: str
    document_name: str
    document_number: str | None
    issued_date: date | None
    issued_by: str | None
    original_name: str
    mime_type: str
    file_size: int
    created_at: datetime


class FacilityReviewEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    actor_id: int | None
    action: str
    from_status: str | None
    to_status: str
    note: str | None
    created_at: datetime


class FacilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner_id: int
    name: str
    location: str
    description: str | None
    contact_phone: str | None
    contact_email: str | None
    city: str | None
    district: str | None
    latitude: float | None
    longitude: float | None
    opening_time: time | None
    closing_time: time | None
    sports: list[str]
    amenities: list[str]
    image_urls: list[str]
    cancellation_rules: list[CancellationRule]
    free_cancellation_minutes: int
    status: str
    is_active: bool
    submitted_at: datetime | None
    approved_at: datetime | None
    approved_by: int | None
    reviewed_at: datetime | None
    rejection_reason: str | None
    field_count: int = 0
    images: list[FacilityImageResponse] = []
    documents: list[FacilityDocumentResponse] = []
    reviews: list[FacilityReviewEventResponse] = []
    created_at: datetime
    updated_at: datetime