from datetime import date, time
from enum import Enum
from typing import Any, Literal

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
    facility_id: int | None
    field_id: int
    facility_name: str
    court_name: str
    field_name: str
    sport_type: str
    court_type: str | None = None
    location: str
    image_url: str | None
    time_slot_id: int
    time_slot_ids: list[int] = []
    selected_slots: list[dict[str, Any]] = []
    slot_name: str
    start_time: str
    end_time: str
    price: float
    duration_minutes: int = 0
    rating: float
    distance_km: float | None
    booking_date: date
    reason: str
    availability_status: str = 'available'
    is_nearest_alternative: bool = False
    alternative_type: str | None = None


class AssistantVenueResult(BaseModel):
    facility_id: int | None
    field_id: int
    facility_name: str
    court_name: str
    sport_type: str
    court_type: str
    location: str
    base_price: float
    rating: float
    image_url: str | None


class AssistantAction(BaseModel):
    label: str
    route: str
    kind: Literal['link'] = 'link'


class AssistantResponse(BaseModel):
    reply: str
    understood: dict[str, Any]
    suggestions: list[AssistantSuggestion]
    venue_results: list[AssistantVenueResult] = Field(default_factory=list)
    intent: str = 'search_booking'
    needs_clarification: bool = False
    source: str = 'live_backend'
    classification: str
    confidence: float = Field(ge=0, le=1)
    entities: dict[str, Any]
    status: str = 'OK'
    missing_fields: list[str] = Field(default_factory=list)
    context_reset: bool = False
    partner_application_status: Literal['NONE', 'PENDING', 'APPROVED', 'REJECTED'] | None = None
    action: AssistantAction | None = None


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


class AIResultStatus(str, Enum):
    OK = 'OK'
    NEED_MORE_DATA = 'NEED_MORE_DATA'
    NO_AVAILABLE_SLOT = 'NO_AVAILABLE_SLOT'


class SlotRecommendationRequest(RequestModel):
    sport_type: str | None = Field(default=None, min_length=2, max_length=80)
    court_type: str | None = Field(default=None, max_length=80)
    court_id: int | None = Field(default=None, gt=0)
    slot_id: int | None = Field(default=None, gt=0)
    booking_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    time_ranges: list[tuple[time, time]] = []
    duration_minutes: int | None = Field(default=None, gt=0, le=1440)
    max_price: float | None = Field(default=None, ge=0, le=1_000_000_000)
    location: str | None = Field(default=None, max_length=120)
    allow_alternatives: bool = False

    @field_validator('sport_type')
    @classmethod
    def normalize_recommendation_sport(cls, value: str | None):
        return ' '.join(value.strip().lower().split()) if value else None


class ValidatedSlotRecommendation(BaseModel):
    facility_id: int | None
    court_id: int
    slot_id: int
    facility_name: str
    court_name: str
    sport_type: str
    court_type: str | None = None
    location: str
    booking_date: date
    start_time: time
    end_time: time
    price: float
    reason: str


class SlotRecommendationResponse(BaseModel):
    status: AIResultStatus
    message: str
    recommendations: list[ValidatedSlotRecommendation]
    source: str
    missing_fields: list[str] = Field(default_factory=list)


class BookingMessageEvent(str, Enum):
    DEPOSIT_PAID = 'DEPOSIT_PAID'
    WAITING_OWNER_CONFIRM = 'WAITING_OWNER_CONFIRM'
    BOOKING_CONFIRMED = 'BOOKING_CONFIRMED'
    BOOKING_REMINDER = 'BOOKING_REMINDER'
    BOOKING_RESCHEDULED = 'BOOKING_RESCHEDULED'
    BOOKING_CANCELLED = 'BOOKING_CANCELLED'
    PAYMENT_COMPLETED = 'PAYMENT_COMPLETED'
    PAYMENT_REFUNDED = 'PAYMENT_REFUNDED'
    # Legacy API values remain accepted during migration.
    DEPOSIT_SUCCEEDED = 'DEPOSIT_SUCCEEDED'
    OWNER_CONFIRMED = 'OWNER_CONFIRMED'
    REMINDER = 'REMINDER'
    RESCHEDULED = 'RESCHEDULED'
    CANCELLED = 'CANCELLED'
    REFUNDED = 'REFUNDED'


class BookingMessageRequest(RequestModel):
    booking_id: int = Field(gt=0)
    event: BookingMessageEvent


class BookingMessageResponse(BaseModel):
    event: BookingMessageEvent
    message: str
    booking_facts: dict[str, Any]
    source: str


class OccupancySlotInsight(BaseModel):
    slot_id: int
    field_id: int
    field_name: str
    start_time: str
    end_time: str
    booking_count: int
    occupancy_rate: float


class OccupancyCourtInsight(BaseModel):
    field_id: int
    field_name: str
    total_available_hours: float
    booked_hours: float
    booking_count: int
    occupancy_rate: float


class OccupancyDayInsight(BaseModel):
    date: date
    total_available_hours: float
    booked_hours: float
    booking_count: int
    occupancy_rate: float


class OccupancyTimeInsight(BaseModel):
    start_time: str
    end_time: str
    total_available_hours: float
    booked_hours: float
    booking_count: int
    occupancy_rate: float


class OccupancyMetrics(BaseModel):
    date_from: date
    date_to: date
    total_operating_hours: float
    total_available_hours: float
    booked_hours: float
    occupancy_rate: float
    booking_count: int
    revenue: float
    peak_hours: list[OccupancySlotInsight]
    low_demand_hours: list[OccupancySlotInsight]
    low_peak_hours: list[OccupancySlotInsight]
    occupancy_by_court: list[OccupancyCourtInsight]
    occupancy_by_day: list[OccupancyDayInsight]
    occupancy_by_time: list[OccupancyTimeInsight]
    cancellation_rate: float


class OccupancySummaryResponse(BaseModel):
    label: str = 'Gợi ý AI'
    summary: str
    promotion_suggestions: list[str]
    peak_hours: list[OccupancySlotInsight]
    low_demand_hours: list[OccupancySlotInsight]
    analytics: OccupancyMetrics
    source: str
