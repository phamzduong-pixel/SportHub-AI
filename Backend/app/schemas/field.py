from datetime import datetime
from math import ceil

from pydantic import BaseModel, ConfigDict, Field as SchemaField, field_validator, model_validator

from ..models.field import FieldStatus
from .user import RequestModel

class FieldBase(RequestModel):
    facility_id: int | None = SchemaField(default=None, gt=0)
    name: str = SchemaField(min_length=2, max_length=120)
    sport_type: str = SchemaField(min_length=2, max_length=80)
    description: str | None = SchemaField(default=None, max_length=2000)
    location: str = SchemaField(min_length=3, max_length=255)
    capacity: int = SchemaField(gt=0, le=100000)
    base_price: float = SchemaField(ge=0, le=1_000_000_000)
    status: FieldStatus = FieldStatus.AVAILABLE
    image_url: str | None = SchemaField(default=None, max_length=500)
    amenities: list[str] = SchemaField(default_factory=list, max_length=30)
    rating: float = SchemaField(default=0, ge=0, le=5)
    review_count: int = SchemaField(default=0, ge=0)
    distance_km: float | None = SchemaField(default=None, ge=0)
    deposit_type: str = SchemaField(default='percentage', pattern='^(percentage|fixed)$')
    deposit_value: float = SchemaField(default=30, gt=0, le=1_000_000_000)
    cancellation_policy: str = SchemaField(default='manual_review', pattern='^(manual_review|full_refund|partial_refund|non_refundable)$')
    cancellation_refund_percent: float | None = SchemaField(default=None, ge=0, le=100)

    @model_validator(mode='after')
    def validate_deposit_and_cancellation(self):
        if self.deposit_type == 'percentage' and self.deposit_value > 100:
            raise ValueError('Mức đặt cọc theo phần trăm không được vượt quá 100%')
        if self.cancellation_policy == 'partial_refund' and self.cancellation_refund_percent is None:
            raise ValueError('Cần cấu hình tỷ lệ hoàn cọc cho chính sách hoàn một phần')
        return self

    @field_validator('name', 'sport_type', 'location')
    @classmethod
    def strip_required_text(cls, value: str):
        value = value.strip()
        if len(value) < 2:
            raise ValueError('Giá trị không được để trống')
        return value

    @field_validator('description', 'image_url')
    @classmethod
    def normalize_optional_text(cls, value: str | None):
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator('image_url')
    @classmethod
    def validate_image_url(cls, value: str | None):
        if value and not value.lower().startswith(('http://', 'https://')):
            raise ValueError('URL hình ảnh phải bắt đầu bằng http:// hoặc https://')
        return value

    @field_validator('amenities')
    @classmethod
    def normalize_amenities(cls, values: list[str]):
        cleaned: list[str] = []
        for value in values:
            item = value.strip()
            if not item or len(item) > 50:
                raise ValueError('Mỗi tiện ích phải có từ 1 đến 50 ký tự')
            if item.casefold() not in {entry.casefold() for entry in cleaned}:
                cleaned.append(item)
        return cleaned

class FieldCreate(FieldBase):
    pass

class FieldUpdate(FieldBase):
    pass

class FieldStatusUpdate(RequestModel):
    status: FieldStatus

class FieldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int | None = None
    facility_id: int | None = None
    name: str
    sport_type: str
    description: str | None
    location: str
    capacity: int
    base_price: float
    status: FieldStatus
    image_url: str | None
    amenities: list[str]
    rating: float
    review_count: int
    distance_km: float | None
    deposit_type: str
    deposit_value: float
    cancellation_policy: str
    cancellation_refund_percent: float | None
    created_at: datetime
    updated_at: datetime

class FieldListResponse(BaseModel):
    items: list[FieldResponse]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def from_result(cls, items, total: int, page: int, page_size: int):
        return cls(items=items, total=total, page=page, page_size=page_size, pages=ceil(total / page_size) if total else 0)

class FieldDeleteResponse(BaseModel):
    message: str
    action: str
    field: FieldResponse | None = None
