from datetime import date
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...ai.inference.prediction_service import DemandPredictionService
from ...database.session import get_db
from ...models.user import User
from ...repositories.ai_repository import AIRepository
from ...schemas.ai import (
    AssistantRequest, AssistantResponse, CustomerRecommendationResponse,
    DemandOverviewResponse, DemandPredictionRequest, DemandPredictionResponse,
    ModelMetricsResponse, RecommendationResponse,
)
from ...services.ai_assistant_service import AIAssistantService
from ...services.customer_recommendation_service import CustomerRecommendationService
from ..dependencies import get_optional_current_user, require_permission

router = APIRouter(prefix='/ai', tags=['ai'])
logger = logging.getLogger(__name__)


@router.get('/customer-recommendations', response_model=CustomerRecommendationResponse)
def customer_recommendations(
    limit: int = Query(default=3, ge=1, le=12),
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    customer_id = current_user.id if current_user and current_user.role in ('CUSTOMER', 'OWNER') else None
    return CustomerRecommendationService(db).recommend(customer_id, limit)


@router.post('/assistant', response_model=AssistantResponse)
def assistant(
    payload: AssistantRequest,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Read-only, domain-scoped assistant backed exclusively by SportHub data."""
    logger.info('AI request received: %s', payload.message)
    try:
        result = AIAssistantService(AIRepository(db), current_user=current_user).ask(
            payload.message,
            context_field_id=payload.context_field_id,
            context=payload.context,
        )
        logger.info('AI response ready: %d suggestions', len(result['suggestions']))
        return result
    except Exception as error:
        logger.exception('AI assistant failed')
        raise HTTPException(status_code=500, detail='Không thể xử lý yêu cầu tìm sân từ dữ liệu SportHub.') from error


def get_service(db: Session = Depends(get_db)) -> DemandPredictionService:
    return DemandPredictionService(AIRepository(db))


@router.post('/predict-demand', response_model=DemandPredictionResponse)
def predict_demand(
    payload: DemandPredictionRequest,
    current_user: User = Depends(require_permission('ai.view')),
    service: DemandPredictionService = Depends(get_service),
):
    return service.for_user(current_user).predict(payload)


@router.get('/model-metrics', response_model=ModelMetricsResponse)
def model_metrics(
    current_user: User = Depends(require_permission('ai.view')),
    service: DemandPredictionService = Depends(get_service),
):
    return service.for_user(current_user).model_metrics()


@router.get('/demand-overview', response_model=DemandOverviewResponse)
def demand_overview(
    days: int = Query(default=7, ge=1, le=30),
    sport_type: str | None = Query(default=None, min_length=2, max_length=80),
    current_user: User = Depends(require_permission('ai.view')),
    service: DemandPredictionService = Depends(get_service),
):
    normalized = ' '.join(sport_type.strip().lower().split()) if sport_type else None
    return service.for_user(current_user).overview(days=days, sport_type=normalized)


@router.get('/recommendations', response_model=RecommendationResponse)
def recommendations(
    sport_type: str = Query(min_length=2, max_length=80),
    booking_date: date = Query(),
    max_price: float | None = Query(default=None, ge=0, le=1_000_000_000),
    limit: int = Query(default=6, ge=1, le=20),
    current_user: User = Depends(require_permission('ai.view')),
    service: DemandPredictionService = Depends(get_service),
):
    normalized = ' '.join(sport_type.strip().lower().split())
    return service.for_user(current_user).recommendations(sport_type=normalized, booking_date=booking_date, max_price=max_price, limit=limit)
