from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .user import RequestModel

class TimeSlotBase(RequestModel):
    field_id: int = Field(gt=0)
    name: str = Field(min_length=2, max_length=120)
    start_time: time
    end_time: time
    price: float = Field(ge=0, le=1_000_000_000)
    weekday_price: float | None = Field(default=None, ge=0, le=1_000_000_000)
    weekend_price: float | None = Field(default=None, ge=0, le=1_000_000_000)
    is_active: bool = True

    @field_validator('name')
    @classmethod
    def normalize_name(cls, value: str):
        value = value.strip()
        if len(value) < 2:
            raise ValueError('Tên khung giờ không được để trống')
        return value

    @model_validator(mode='after')
    def validate_time_order(self):
        if self.start_time >= self.end_time:
            raise ValueError('Giờ bắt đầu phải nhỏ hơn giờ kết thúc')
        return self

class TimeSlotCreate(TimeSlotBase):
    pass

class TimeSlotUpdate(TimeSlotBase):
    pass

class TimeSlotStatusUpdate(RequestModel):
    is_active: bool

class TimeSlotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    field_id: int
    name: str
    start_time: time
    end_time: time
    price: float
    weekday_price: float | None
    weekend_price: float | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

class TimeSlotDeleteResponse(BaseModel):
    message: str
    action: str
    time_slot: TimeSlotResponse | None = None
