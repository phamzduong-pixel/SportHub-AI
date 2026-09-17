from datetime import date, datetime, timezone
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from ...ai.inference.prediction_service import DemandPredictionService
from ...database.session import get_db
from ...models.ai_conversation import AIConversation, AIMessage
from ...models.user import User
from ...repositories.ai_repository import AIRepository
from ...schemas.ai import (
    AIConversationDetailResponse, AIConversationListItem, AIConversationListResponse,
    AIMessageItem, AssistantRequest, AssistantResponse, CustomerRecommendationResponse,
    BookingMessageRequest, BookingMessageResponse, OccupancySummaryResponse,
    SlotRecommendationRequest, SlotRecommendationResponse,
    DemandOverviewResponse, DemandPredictionRequest, DemandPredictionResponse,
    ModelMetricsResponse, RecommendationResponse,
)
from ...services.ai_assistant_service import AIAssistantService
from ...services.ai_feature_service import AIFeatureService
from ...services.booking_message_service import BookingMessageService
from ...services.customer_recommendation_service import CustomerRecommendationService
from ..dependencies import get_current_user, get_optional_current_user, require_owner

router = APIRouter(prefix='/ai', tags=['ai'])
logger = logging.getLogger(__name__)


@router.post('/recommend-slots', response_model=SlotRecommendationResponse)
def recommend_slots(
    payload: SlotRecommendationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ('CUSTOMER', 'OWNER'):
        raise HTTPException(status_code=403, detail='Chức năng gợi ý slot dành cho CUSTOMER')
    return AIFeatureService(db).recommend_slots(payload)


@router.post('/generate-booking-message', response_model=BookingMessageResponse)
def generate_booking_message(
    payload: BookingMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return BookingMessageService(db).generate(payload, current_user)


@router.get('/occupancy-summary', response_model=OccupancySummaryResponse)
def occupancy_summary(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    field_id: int | None = Query(default=None, gt=0),
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    return AIFeatureService(db).occupancy_summary(current_user, date_from, date_to, field_id)


@router.get('/customer-recommendations', response_model=CustomerRecommendationResponse)
def customer_recommendations(
    limit: int = Query(default=3, ge=1, le=12),
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    customer_id = current_user.id if current_user and current_user.role in ('CUSTOMER', 'OWNER') else None
    return CustomerRecommendationService(db).recommend(customer_id, limit)


@router.get('/conversations', response_model=AIConversationListResponse)
def list_conversations(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversations = (
        db.query(AIConversation)
        .filter(AIConversation.user_id == current_user.id)
        .order_by(AIConversation.updated_at.desc())
        .limit(limit)
        .all()
    )
    items = []
    for conv in conversations:
        last_msg = conv.messages[-1].content if conv.messages else None
        items.append(
            AIConversationListItem(
                id=conv.id,
                conversation_id=conv.conversation_id,
                title=conv.title,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=len(conv.messages),
                last_message=last_msg,
            )
        )
    return AIConversationListResponse(items=items)


@router.get('/conversations/{conversation_id}', response_model=AIConversationDetailResponse)
def get_conversation(
    conversation_id: str,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    conv = (
        db.query(AIConversation)
        .filter(AIConversation.conversation_id == conversation_id)
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail='Không tìm thấy cuộc trò chuyện.')

    if conv.user_id is not None:
        if not current_user:
            raise HTTPException(status_code=401, detail='Yêu cầu đăng nhập để truy cập cuộc trò chuyện này.')
        if conv.user_id != current_user.id:
            raise HTTPException(status_code=403, detail='Bạn không có quyền truy cập cuộc trò chuyện này.')

    messages = [
        AIMessageItem(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            payload=msg.payload,
            created_at=msg.created_at,
        )
        for msg in conv.messages
    ]
    return AIConversationDetailResponse(
        id=conv.id,
        conversation_id=conv.conversation_id,
        title=conv.title,
        context_snapshot=conv.context_snapshot,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=messages,
    )


@router.post('/assistant', response_model=AssistantResponse)
def assistant(
    payload: AssistantRequest,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Domain-scoped assistant backed by SportHub data with persistent conversation history."""
    logger.info('AI assistant request received')

    # 1. Resolve or create conversation
    conv = None
    if payload.conversation_id:
        conv = (
            db.query(AIConversation)
            .filter(AIConversation.conversation_id == payload.conversation_id)
            .first()
        )
        if conv:
            if conv.user_id is not None:
                if not current_user or conv.user_id != current_user.id:
                    raise HTTPException(status_code=403, detail='Bạn không có quyền truy cập cuộc trò chuyện này.')
            elif current_user:
                conv.user_id = current_user.id
        else:
            conv = AIConversation(
                conversation_id=payload.conversation_id,
                user_id=current_user.id if current_user else None,
                title=payload.message[:60].strip(),
            )
            db.add(conv)
            db.flush()
    else:
        new_cid = str(uuid.uuid4())
        conv = AIConversation(
            conversation_id=new_cid,
            user_id=current_user.id if current_user else None,
            title=payload.message[:60].strip(),
        )
        db.add(conv)
        db.flush()

    if not conv.title:
        conv.title = payload.message[:60].strip()

    # 2. Save user message immediately
    user_msg = AIMessage(
        conversation_id=conv.id,
        role='user',
        content=payload.message,
        payload=None,
    )
    db.add(user_msg)
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()

    # 3. Context fallback from snapshot if not explicitly provided
    effective_context = payload.context or conv.context_snapshot

    # 4. Process with AI Assistant Service
    try:
        result = AIAssistantService(AIRepository(db), current_user=current_user).ask(
            payload.message,
            context_field_id=payload.context_field_id,
            context=effective_context,
        )
        logger.info('AI response ready: %d suggestions', len(result.get('suggestions', [])))
    except HTTPException:
        raise
    except Exception as error:
        logger.exception('AI assistant failed')
        raise HTTPException(status_code=500, detail='Không thể xử lý yêu cầu từ AI assistant.') from error

    # 5. Save assistant message after AI response
    serializable_result = jsonable_encoder(result)
    assistant_msg = AIMessage(
        conversation_id=conv.id,
        role='assistant',
        content=result.get('reply', ''),
        payload=serializable_result,
    )
    db.add(assistant_msg)
    conv.context_snapshot = jsonable_encoder(result.get('understood'))
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()

    # 6. Inject conversation_id into response
    result['conversation_id'] = conv.conversation_id
    return result


def get_service(db: Session = Depends(get_db)) -> DemandPredictionService:
    return DemandPredictionService(AIRepository(db))


@router.post('/predict-demand', response_model=DemandPredictionResponse)
def predict_demand(
    payload: DemandPredictionRequest,
    current_user: User = Depends(require_owner),
    service: DemandPredictionService = Depends(get_service),
):
    return service.for_user(current_user).predict(payload)


@router.get('/model-metrics', response_model=ModelMetricsResponse)
def model_metrics(
    current_user: User = Depends(require_owner),
    service: DemandPredictionService = Depends(get_service),
):
    return service.for_user(current_user).model_metrics()


@router.get('/demand-overview', response_model=DemandOverviewResponse)
def demand_overview(
    days: int = Query(default=7, ge=1, le=30),
    sport_type: str | None = Query(default=None, min_length=2, max_length=80),
    current_user: User = Depends(require_owner),
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
    current_user: User = Depends(require_owner),
    service: DemandPredictionService = Depends(get_service),
):
    normalized = ' '.join(sport_type.strip().lower().split())
    return service.for_user(current_user).recommendations(sport_type=normalized, booking_date=booking_date, max_price=max_price, limit=limit)
