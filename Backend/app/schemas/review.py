from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from .user import RequestModel
class ReviewCreate(RequestModel):
    booking_id: int = Field(gt=0)
    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=2, max_length=2000)

    @field_validator('comment')
    @classmethod
    def normalize_comment(cls, value: str):
        value = value.strip()
        if len(value) < 2:
            raise ValueError('Nhận xét phải có ít nhất 2 ký tự')
        return value
class ReviewUpdate(RequestModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=2, max_length=2000)

    @field_validator('comment')
    @classmethod
    def normalize_comment(cls, value: str):
        value = value.strip()
        if len(value) < 2:
            raise ValueError('Nhận xét phải có ít nhất 2 ký tự')
        return value

class ReviewReply(RequestModel):
    reply: str = Field(min_length=2, max_length=2000)
class ReviewResponse(BaseModel):
    id: int; booking_id: int; customer_id: int; customer_name: str; field_id: int; field_name: str
    rating: int; comment: str; owner_reply: str | None; replied_at: datetime | None; created_at: datetime
class ReviewSummaryResponse(BaseModel):
    field_id: int; average_rating: float; total_reviews: int; items: list[ReviewResponse]
