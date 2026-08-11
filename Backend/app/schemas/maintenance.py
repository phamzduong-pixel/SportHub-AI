from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from .user import RequestModel


class MaintenanceWrite(RequestModel):
    field_id: int = Field(gt=0)
    maintenance_type: str = Field(min_length=2, max_length=40)
    title: str = Field(min_length=3, max_length=180)
    starts_at: datetime
    ends_at: datetime
    priority: str = Field(default='MEDIUM', pattern='^(LOW|MEDIUM|HIGH|URGENT)$')
    notes: str | None = Field(default=None, max_length=2000)
    estimated_cost: float | None = Field(default=None, ge=0, le=1_000_000_000)
    actual_cost: float | None = Field(default=None, ge=0, le=1_000_000_000)

    @field_validator('maintenance_type', 'title')
    @classmethod
    def normalize_required(cls, value: str):
        return value.strip()

    @field_validator('notes')
    @classmethod
    def normalize_optional(cls, value: str | None):
        return value.strip() or None if value is not None else None

    @model_validator(mode='after')
    def valid_range(self):
        if self.ends_at <= self.starts_at:
            raise ValueError('Thời gian kết thúc phải sau thời gian bắt đầu')
        return self


class MaintenanceCreate(MaintenanceWrite):
    pass


class MaintenanceUpdate(MaintenanceWrite):
    pass


class AffectedBooking(BaseModel):
    id: int
    booking_code: str
    customer_name: str
    starts_at: datetime
    ends_at: datetime
    status: str
    paid_amount: float


class MaintenanceResponse(BaseModel):
    id: int
    field_id: int
    field_name: str
    facility_id: int | None
    facility_name: str
    maintenance_type: str
    title: str
    starts_at: datetime
    ends_at: datetime
    priority: str
    notes: str | None
    estimated_cost: float | None
    actual_cost: float | None
    status: str
    created_by: int
    created_by_name: str
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime
    affected_bookings: list[AffectedBooking]


class MaintenanceSummary(BaseModel):
    upcoming: int
    in_progress: int
    completed: int
    cancelled: int
