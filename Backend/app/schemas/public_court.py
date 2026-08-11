from pydantic import BaseModel

from .field import FieldResponse
from .time_slot import TimeSlotResponse


class PublicFacilitySummary(BaseModel):
    id: int
    name: str
    location: str
    description: str | None
    contact_phone: str | None
    opening_time: str | None
    closing_time: str | None
    amenities: list[str]
    image_urls: list[str]


class PublicCourtDetail(BaseModel):
    court: FieldResponse
    facility: PublicFacilitySummary | None
    time_slots: list[TimeSlotResponse]
    images: list[str]
    min_price: float
    max_price: float
