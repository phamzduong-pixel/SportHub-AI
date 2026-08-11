from datetime import date, datetime, time

from pydantic import BaseModel, Field, field_validator, model_validator

from .user import RequestModel


class FieldBlockCreate(RequestModel):
    field_id: int = Field(gt=0)
    block_date: date
    start_time: time = time(0, 0)
    end_time: time = time(23, 59, 59)
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator('reason')
    @classmethod
    def normalize_reason(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError('Lý do khóa phải có ít nhất 3 ký tự')
        return value

    @model_validator(mode='after')
    def validate_range(self):
        if self.start_time >= self.end_time:
            raise ValueError('Giờ bắt đầu phải nhỏ hơn giờ kết thúc')
        return self


class FieldBlockResponse(BaseModel):
    id: int
    field_id: int
    field_name: str
    block_date: date
    start_time: time
    end_time: time
    reason: str
    created_by: int
    created_by_name: str
    created_at: datetime


class ComplaintCreate(RequestModel):
    booking_id: int = Field(gt=0)
    category: str = Field(pattern='^(service|facility|payment|safety|other)$')
    description: str = Field(min_length=5, max_length=2000)
    evidence_url: str | None = Field(default=None, max_length=1000)

    @field_validator('description')
    @classmethod
    def normalize_description(cls, value):
        value = value.strip()
        if len(value) < 5:
            raise ValueError('Mô tả phải có ít nhất 5 ký tự')
        return value

    @field_validator('evidence_url')
    @classmethod
    def normalize_optional(cls, value):
        return value.strip() or None if value is not None else None


class ComplaintUpdate(RequestModel):
    status: str = Field(pattern='^(in_review|resolved|rejected)$')
    resolution: str = Field(min_length=3, max_length=2000)


class ComplaintResponse(BaseModel):
    id: int
    booking_id: int
    booking_code: str
    customer_id: int
    customer_name: str
    field_id: int
    field_name: str
    category: str
    description: str
    evidence_url: str | None
    status: str
    resolution: str | None
    resolved_by: int | None
    resolved_by_name: str | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AuditLogResponse(BaseModel):
    id: int
    actor_id: int | None
    actor_name: str | None
    actor_role: str | None
    entity_type: str
    entity_id: int | None
    action: str
    changes: dict
    created_at: datetime
