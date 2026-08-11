from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .user import RequestModel


class DemandLevel(str, Enum):
    LOW = 'LOW'
    MEDIUM = 'MEDIUM'
    HIGH = 'HIGH'


class DemandPredictionRequest(RequestModel):
    sport_type: str = Field(min_length=2, max_length=80)
    booking_date: date
    start_hour: int = Field(ge=0, le=23)
    price: float = Field(ge=0, le=1_000_000_000)
    previous_booking_count: int | None = Field(default=None, ge=0, le=10000)
    field_capacity: int | None = Field(default=None, ge=1, le=100000)
    field_id: int | None = Field(default=None, gt=0)

    @field_validator('sport_type')
    @classmethod
    def normalize_sport(cls, value: str):
        return ' '.join(value.strip().lower().split())


class DemandPredictionResponse(BaseModel):
    demand_level: DemandLevel
    confidence: float
    probabilities: dict[str, float]
    explanation: str
    features: dict[str, str | int | float]
    model_name: str


class ModelMetricItem(BaseModel):
    model_name: str
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    confusion_matrix: list[list[int]] | None = None


class ModelMetricsResponse(BaseModel):
    selected_model: str
    selected_metrics: ModelMetricItem
    models: list[ModelMetricItem]
    metadata: dict


class DemandOverviewItem(BaseModel):
    date: date
    low: int
    medium: int
    high: int
    total: int


class DemandOverviewResponse(BaseModel):
    sport_type: str | None
    days: int
    items: list[DemandOverviewItem]
    distribution: dict[str, int]


class DemandRecommendation(BaseModel):
    field_id: int
    field_name: str
    sport_type: str
    location: str
    time_slot_id: int
    time_slot_name: str
    start_time: str
    end_time: str
    price: float
    demand_level: DemandLevel
    demand_confidence: float
    recommendation_score: float
    reasons: list[str]


class RecommendationResponse(BaseModel):
    booking_date: date
    sport_type: str
    strategy: str
    items: list[DemandRecommendation]


class AssistantRequest(RequestModel):
    message: str = Field(min_length=2, max_length=500)
    context_field_id: int | None = Field(default=None, gt=0)
    context: dict[str, Any] | None = None


class AssistantSuggestion(BaseModel):
    field_id: int
    facility_name: str
    court_name: str
    field_name: str
    sport_type: str
    location: str
    image_url: str | None
    time_slot_id: int
    slot_name: str
    start_time: str
    end_time: str
    price: float
    rating: float
    distance_km: float | None
    booking_date: date
    reason: str
    availability_status: str = 'available'
    is_nearest_alternative: bool = False
    alternative_type: str | None = None


class AssistantResponse(BaseModel):
    reply: str
    understood: dict[str, Any]
    suggestions: list[AssistantSuggestion]
    intent: str = 'search_booking'
    needs_clarification: bool = False
    source: str = 'live_backend'
    classification: str
    confidence: float = Field(ge=0, le=1)
    entities: dict[str, Any]


class CustomerRecommendation(BaseModel):
    field_id: int
    field_name: str
    sport_type: str
    location: str
    image_url: str | None
    price: float
    rating: float
    review_count: int
    distance_km: float | None
    available_slots: list[dict[str, str | int | float]]
    score: float
    reason: str


class CustomerRecommendationResponse(BaseModel):
    strategy: str
    personalized: bool
    items: list[CustomerRecommendation]
