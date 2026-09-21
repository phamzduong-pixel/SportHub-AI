import re
import unicodedata
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from ..core.config import settings
from ..models.knowledge_entry import KnowledgeEntry
from ..models.user import User
from ..repositories.ai_repository import AIRepository
from ..schemas.ai import AssistantMode, SlotRecommendationRequest
from .ai_feature_service import AIFeatureService
from .inventory_service import InventoryService
from .ai_domain_policy import (
    COMBINED_OUT_OF_SCOPE_REPLY, NO_DATA_REPLY, OUT_OF_SCOPE_REPLY,
    PROFESSIONAL_SPORTS_KNOWLEDGE_REFUSAL,
    ScopeClassification, ScopeDecision, ScopeDomain, ScopeRouter, ModeScopeEvaluation, evaluate_mode_scope,
    generate_out_of_scope_redirect,
)
from .ai_intent_router import AssistantIntent, IntentRoute, IntentRouter, is_business_intent
from .rag_guardrail import RAGGuardrail
from .rag_response_validator import validate_response
from .ai_system_knowledge import match_system_knowledge
from .llm_sports_processor import get_llm_sports_processor


SPORT_ALIASES = {
    'bong da': 'bóng đá', 'da bong': 'bóng đá', 'san bong': 'bóng đá', 'football': 'bóng đá',
    'cau long': 'cầu lông', 'badminton': 'cầu lông',
    'pickleball': 'pickleball', 'tennis': 'tennis',
    'bong ro': 'bóng rổ', 'bong chuyen': 'bóng chuyền',
}
WEEKDAYS = {
    'thu hai': 0, 'thu ba': 1, 'thu tu': 2, 'thu nam': 3,
    'thu sau': 4, 'thu bay': 5, 'chu nhat': 6,
}
SPECIAL_REQUIREMENTS = {
    'mai che': 'mái che', 'trong nha': 'trong nhà', 'ngoai troi': 'ngoài trời',
    'bai xe': 'bãi xe', 'giu xe': 'bãi xe', 'phong thay do': 'phòng thay đồ',
    'den chieu sang': 'đèn chiếu sáng', 'he thong den': 'đèn chiếu sáng',
    'dieu hoa': 'điều hòa', 'tam': 'phòng tắm',
}
logger = logging.getLogger(__name__)


def plain(value: str) -> str:
    normalized = unicodedata.normalize('NFD', value.casefold())
    return ''.join(char for char in normalized if unicodedata.category(char) != 'Mn').replace('đ', 'd')


@dataclass
class SearchCriteria:
    sport_type: str | None = None
    court_type: str | None = None
    booking_date: date | None = None
    location: str | None = None
    start_minute: int | None = None
    end_minute: int | None = None
    duration_minutes: int = 60
    max_price: float | None = None
    people: int | None = None
    special_requirements: list[str] = field(default_factory=list)
    time_ranges: list[tuple[int, int]] = field(default_factory=list)
    requested_field_id: int | None = None
    requested_time_slot_id: int | None = None
    allow_alternatives: bool = False
    prefer_cheap: bool = False
    near_me: bool = False
    invalid_date: bool = False
    invalid_time: bool = False


class AIAssistantService:
    def __init__(self, repository: AIRepository, current_user: User | None = None, guardrail: RAGGuardrail | None = None):
        self.repository = repository
        self.current_user = current_user
        self.repository.scope_for_user(current_user)
        self.tz = ZoneInfo(settings.TIMEZONE)
        self.intent_router = IntentRouter()
        self.guardrail = guardrail or RAGGuardrail()
        self._active_route: IntentRoute | None = None
        self._conversation_context: dict[str, Any] = {}
        self._assistant_mode: AssistantMode = AssistantMode.NATURAL
        self._mode_evaluation: ModeScopeEvaluation | None = None

    def ask(
        self,
        message: str,
        context_field_id: int | None = None,
        context: dict[str, Any] | None = None,
        assistant_mode: AssistantMode | str | None = None,
    ):
        if isinstance(assistant_mode, AssistantMode):
            self._assistant_mode = assistant_mode
        elif isinstance(assistant_mode, str) and assistant_mode.upper() in AssistantMode.__members__:
            self._assistant_mode = AssistantMode[assistant_mode.upper()]
        elif context and context.get('assistant_mode') in AssistantMode.__members__:
            self._assistant_mode = AssistantMode[context['assistant_mode']]
        else:
            self._assistant_mode = AssistantMode.NATURAL

        query = plain(' '.join(message.strip().split()))
        router_context = dict(context or {})
        if context_field_id and not router_context.get('field_id'):
            router_context['field_id'] = context_field_id
        router_context = self._sanitize_context_for_mode(router_context, self._assistant_mode)
        self._conversation_context = router_context
        
        # Scope Router domain classification
        scope_domain = ScopeRouter.classify_domain(query, router_context, self._assistant_mode)
        
        route = self.intent_router.route(message, router_context, today=datetime.now(self.tz).date())
        self._active_route = route
        effective_context = {} if route.context_reset else router_context
        if route.context_reset and router_context.get('business_context'):
            effective_context['business_context'] = router_context['business_context']
        self._conversation_context = effective_context

        eval_res = evaluate_mode_scope(self._assistant_mode, route.intent, query=query)
        self._mode_evaluation = eval_res
        logger.info(
            'Assistant mode=%s scope_domain=%s scope_decision=%s intent=%s confidence=%.2f is_allowed=%s',
            self._assistant_mode.value, scope_domain.value, eval_res.scope_decision.value, route.intent.value, route.confidence, eval_res.is_allowed,
        )
        if not eval_res.is_allowed:
            if getattr(route, 'is_combined_out_of_scope', False) and eval_res.scope_decision == ScopeDecision.OUT_OF_SCOPE:
                reply_text = COMBINED_OUT_OF_SCOPE_REPLY
            elif eval_res.scope_decision == ScopeDecision.SPORTS_KNOWLEDGE and self._assistant_mode == AssistantMode.PROFESSIONAL:
                reply_text = eval_res.refusal_reply or PROFESSIONAL_SPORTS_KNOWLEDGE_REFUSAL
            else:
                reply_text = generate_out_of_scope_redirect(query, router_context, self._assistant_mode)
            return self._response(
                reply_text, SearchCriteria(), [], needs_clarification=False,
                classification=eval_res.classification, status='OUT_OF_SCOPE',
            )
        if route.intent == AssistantIntent.OUT_OF_SCOPE:
            if getattr(route, 'is_combined_out_of_scope', False):
                reply_text = COMBINED_OUT_OF_SCOPE_REPLY
            else:
                reply_text = generate_out_of_scope_redirect(query, router_context, self._assistant_mode)
            return self._response(
                reply_text, SearchCriteria(), [], needs_clarification=False,
                classification=ScopeClassification.OUT_OF_SCOPE, status='OUT_OF_SCOPE',
            )
        if route.intent == AssistantIntent.ABUSIVE:
            if self._assistant_mode == AssistantMode.PROFESSIONAL:
                reply_text = 'Yêu cầu chứa nội dung không phù hợp. Vui lòng giữ chuẩn mực giao tiếp khi sử dụng dịch vụ SportHub AI.'
            else:
                reply_text = 'Mình luôn hướng tới giao tiếp lịch sự và tôn trọng. Nếu bạn cần hỗ trợ tìm sân thể thao hay tra cứu thông tin trên SportHub AI, mình rất sẵn lòng hỗ trợ bạn! 😊'
            return self._response(
                reply_text, SearchCriteria(), [], needs_clarification=False,
                classification=ScopeClassification.OUT_OF_SCOPE, status='OUT_OF_SCOPE',
            )

        if route.intent == AssistantIntent.NONSENSE:
            if self._assistant_mode == AssistantMode.PROFESSIONAL:
                reply_text = 'Nội dung không rõ ràng. Vui lòng nhập yêu cầu nghiệp vụ cụ thể liên quan đến hệ thống SportHub AI.'
            else:
                reply_text = 'Xin lỗi bạn, mình chưa hiểu được nội dung này. Bạn có thể hỏi mình về tìm sân, đặt sân hoặc các chủ đề thể thao nhé! 🏸⚽'
            return self._response(
                reply_text, SearchCriteria(), [], needs_clarification=False,
                classification=ScopeClassification.OUT_OF_SCOPE, status='OUT_OF_SCOPE',
            )

        if route.intent == AssistantIntent.GREETING:
            if self._assistant_mode == AssistantMode.PROFESSIONAL:
                greeting_text = (
                    'Xin chào! Tôi là Trợ lý Nghiệp vụ SportHub AI. Tôi có thể hỗ trợ bạn tìm kiếm sân, '
                    'kiểm tra lịch trống, báo giá, đặt sân và giải đáp các nghiệp vụ hệ thống. Bạn cần hỗ trợ gì?'
                )
            else:
                greeting_text = (
                    'Xin chào! Tôi là trợ lý chuyên biệt của SportHub AI. Tôi có thể giúp bạn tìm sân, '
                    'kiểm tra lịch trống, đặt sân, hướng dẫn hệ thống hoặc cùng bạn tìm hiểu kiến thức thể thao. '
                    'Bạn đang quan tâm đến môn thể thao nào? 🏸⚽😊'
                )
            return self._response(
                greeting_text,
                SearchCriteria(), [],
            )

        if route.intent == AssistantIntent.AI_IDENTITY:
            if self._assistant_mode == AssistantMode.PROFESSIONAL:
                identity_text = (
                    'Tôi là Trợ lý Nghiệp vụ SportHub AI, được thiết kế để hỗ trợ tra cứu và thao tác các nghiệp vụ đặt sân thể thao trên hệ thống SportHub AI.'
                )
            else:
                identity_text = (
                    'Mình là SportHub AI – trợ lý thông minh hỗ trợ tìm kiếm sân bãi, đặt lịch thể thao '
                    'và giải đáp các kiến thức thể thao hữu ích. Bạn đang quan tâm đến môn thể thao nào? 🏸⚽'
                )
            return self._response(
                identity_text,
                SearchCriteria(), [],
            )

        if route.intent == AssistantIntent.AI_CAPABILITY:
            if self._assistant_mode == AssistantMode.PROFESSIONAL:
                capability_text = (
                    'Tôi hỗ trợ các nghiệp vụ: tìm kiếm sân thể thao, kiểm tra lịch trống, báo giá, đặt sân, '
                    'hủy/đổi lịch, chính sách thanh toán và quản lý cơ sở trên SportHub AI.'
                )
            else:
                capability_text = (
                    'Mình có thể hỗ trợ bạn rất nhiều việc trên SportHub AI:\n'
                    '- 🏟️ **Tìm và gợi ý sân**: Tìm sân bóng đá, cầu lông, pickleball, tennis, bóng rổ, bóng chuyền theo khu vực và mức giá.\n'
                    '- ⏱️ **Kiểm tra lịch trống & đặt sân**: Tra cứu các khung giờ còn trống và hỗ trợ quy trình đặt sân tiện lợi.\n'
                    '- 📖 **Hướng dẫn hệ thống**: Giải đáp chính sách cọc, hoàn tiền, hủy lịch và hướng dẫn đăng ký chủ sân.\n'
                    '- 🏆 **Kiến thức thể thao**: Tra cứu luật thi đấu, thông tin cầu thủ, đội bóng, giải đấu và phong trào thể thao.\n\n'
                    'Bạn cần mình hỗ trợ phần nào trước? 😊'
                )
            return self._response(
                capability_text,
                SearchCriteria(), [],
            )

        if route.intent == AssistantIntent.THANKS:
            if self._assistant_mode == AssistantMode.PROFESSIONAL:
                thanks_text = 'Rất hân hạnh được hỗ trợ bạn. Vui lòng cho tôi biết nếu bạn cần hỗ trợ thêm thông tin nghiệp vụ trên SportHub AI.'
            else:
                thanks_text = 'Không có chi! Rất vui được hỗ trợ bạn. Chúc bạn có những giây phút luyện tập thể thao thật vui vẻ! Nếu cần gì thêm, bạn cứ nhắn mình nhé. 😊🏸⚽'
            return self._response(
                thanks_text,
                SearchCriteria(), [],
            )

        if route.intent == AssistantIntent.GOODBYE:
            if self._assistant_mode == AssistantMode.PROFESSIONAL:
                goodbye_text = 'Cảm ơn bạn đã sử dụng dịch vụ SportHub AI. Chúc bạn một ngày làm việc hiệu quả và hẹn gặp lại.'
            else:
                goodbye_text = 'Tạm biệt bạn nhé! Chúc bạn có những trận đấu thể thao tuyệt vời và tràn đầy năng lượng. Hẹn gặp lại bạn trên SportHub AI! 👋✨'
            return self._response(
                goodbye_text,
                SearchCriteria(), [],
            )

        if route.intent == AssistantIntent.CASUAL:
            if self._assistant_mode == AssistantMode.PROFESSIONAL:
                casual_text = 'Cảm ơn bạn. Tôi luôn sẵn sàng hỗ trợ các nghiệp vụ đặt sân và quản lý trên SportHub AI. Bạn cần thực hiện thao tác nào?'
            else:
                if any(k in query for k in ('khoe', 'the nao', 'on khong', 'dao nay')):
                    casual_text = 'Mình là trợ lý ảo nên luôn sẵn sàng 24/7 với năng lượng tràn đầy để hỗ trợ bạn! Hôm nay bạn có dự định chơi môn thể thao nào không? 🏃‍♂️✨'
                else:
                    casual_text = 'Cảm ơn bạn nhiều nhé! Rất vui vì thông tin hữu ích với bạn. Bạn có muốn tìm sân hay hỏi thêm gì về thể thao không nào? 😊'
            return self._response(
                casual_text,
                SearchCriteria(), [],
            )
        if route.intent == AssistantIntent.UNCLEAR:
            if any(term in query for term in ('muon dat', 'toi dat', 'dat cho', 'muon dat cho')):
                clarification_msg = 'Bạn muốn đặt sân môn thể thao nào và ở khu vực nào ạ?'
            elif any(term in query for term in ('gia the nao', 'gia sao', 'bao nhieu tien')):
                clarification_msg = 'Bạn muốn tham khảo giá của sân nào hoặc môn thể thao nào?'
            elif any(term in query for term in ('con khong', 'con cho khong')):
                clarification_msg = 'Bạn muốn kiểm tra lịch trống của sân nào và vào thời gian nào?'
            else:
                clarification_msg = 'Bạn muốn tìm sân, kiểm tra lịch trống hay xem thông tin gì trên SportHub AI? Hãy cho mình biết môn thể thao, khu vực hoặc ngày bạn muốn chơi nhé.'
            return self._response(
                clarification_msg,
                SearchCriteria(), [], needs_clarification=True, classification=ScopeClassification.UNCLEAR,
                status='NEED_MORE_DATA',
            )
        if route.intent == AssistantIntent.PARTNER_APPLICATION_SUPPORT:
            return self._answer_partner_application(query)
        if route.intent == AssistantIntent.SPORTS_KNOWLEDGE:
            return self._answer_sports_knowledge(query, route)
        # Static knowledge intents that can be answered from the Knowledge Base via RAG
        static_intents = {
            AssistantIntent.SYSTEM_GUIDE,
            AssistantIntent.ACCOUNT_SUPPORT,
            AssistantIntent.PARTNER_APPLICATION_SUPPORT,
            AssistantIntent.PAYMENT_SUPPORT,
        }
        if route.intent in static_intents:
            role = self.current_user.role if self.current_user else 'CUSTOMER'
            guardrail = RAGGuardrail()
            retrieved = guardrail.retrieve_context(query, role, route.intent.name, assistant_mode=self._assistant_mode)
            if retrieved:
                # Concatenate retrieved answers
                answer_text = ' '.join(entry.answer for entry, _ in retrieved)
                answer_text = validate_response(answer_text)
                # Use suggested_action from the first entry if present
                first_entry = retrieved[0][0]
                action = getattr(first_entry, 'suggested_action', None)
                return self._response(
                    answer_text,
                    SearchCriteria(),
                    [],
                    classification=ScopeClassification.OUT_OF_SCOPE,
                    status='OK',
                    action=action,
                )
            # Fallback to existing system knowledge handling
            information_intents = {
                AssistantIntent.GET_BOOKING: 'booking_status',
                AssistantIntent.PAYMENT_SUPPORT: 'payment',
                AssistantIntent.ACCOUNT_SUPPORT: 'profile',
                AssistantIntent.SYSTEM_GUIDE: 'system_help',
            }
            intent_key = information_intents.get(route.intent)
            if intent_key:
                return self._answer_information(query, intent_key)
        if route.intent == AssistantIntent.GET_BOOKING:
            return self._answer_information(query, 'booking_status')
        if route.intent in (AssistantIntent.CANCEL_BOOKING, AssistantIntent.RESCHEDULE_BOOKING):
            return self._answer_booking_action(query, route.intent)
        if route.intent == AssistantIntent.OCCUPANCY_INSIGHT:
            return self._answer_occupancy_insight(query)
        if route.intent == AssistantIntent.GET_PRODUCTS:
            return self._answer_products(query, context_field_id, effective_context)

        criteria = self._extract(query, context_field_id)
        fresh_end_minute = criteria.end_minute
        self._merge_context(criteria, effective_context, query)
        if route.entities.start_time and not route.entities.end_time and fresh_end_minute is None:
            criteria.end_minute = None
        self._resolve_result_reference(criteria, query, effective_context)
        if self._is_venue_count_query(query):
            return self._answer_venue_count(criteria)
        if 're hon' in query and effective_context.get('reference_price') is not None:
            criteria.max_price = max(0, float(effective_context['reference_price']) - 0.01)
            criteria.prefer_cheap = True
        if criteria.requested_field_id and self._active_route and not self._active_route.entities.venue_name:
            referenced_court = self.repository.field_context(criteria.requested_field_id)
            if referenced_court:
                self._active_route.entities.venue_name = referenced_court.name
        if route.intent == AssistantIntent.GET_VENUE_DETAIL:
            if criteria.requested_field_id is None and context_field_id:
                criteria.requested_field_id = context_field_id
            return self._answer_venue_detail(criteria)
        logger.info('Search criteria: %s', self._understood(criteria))

        venue_search_intents = {
            AssistantIntent.SEARCH_VENUE, AssistantIntent.RECOMMEND_VENUE,
            AssistantIntent.FOLLOW_UP, AssistantIntent.CHECK_AVAILABILITY, AssistantIntent.RECOMMEND_SLOT,
        }
        location_first_request = (criteria.requested_field_id is None) and criteria.booking_date is None and (
            bool(criteria.location) or (
                criteria.start_minute is None
                and any(term in query for term in ('co san', 'san nao', 'toi muon san', 'muon san'))
            )
        )
        if route.intent in venue_search_intents and location_first_request:
            venue_response = self._venue_search_response(criteria)
            if venue_response is not None:
                return venue_response

        if criteria.invalid_date:
            return self._response('Ngày bạn nhập không hợp lệ hoặc đã qua. Vui lòng chọn một ngày từ hôm nay trở đi.', criteria, [], needs_clarification=True, status='NEED_MORE_DATA', missing_fields=['date'])
        if criteria.invalid_time:
            return self._response('Khung giờ không hợp lệ. Giờ kết thúc phải sau giờ bắt đầu.', criteria, [], needs_clarification=True, status='NEED_MORE_DATA', missing_fields=['end_time'])
        if not criteria.sport_type:
            return self._response('Bạn muốn tìm sân cho môn thể thao nào?', criteria, [], needs_clarification=True, status='NEED_MORE_DATA', missing_fields=['sport_type'])
        if not criteria.booking_date and not any(term in query for term in ('ngay nao trong', 'ngay trong')):
            return self._response(f'Bạn muốn chơi {criteria.sport_type} vào ngày nào?', criteria, [], needs_clarification=True, status='NEED_MORE_DATA', missing_fields=['date'])
        if criteria.near_me and not criteria.location:
            return self._response('Bạn muốn tìm sân gần khu vực nào?', criteria, [], needs_clarification=True, classification=ScopeClassification.UNCLEAR, status='NEED_MORE_DATA', missing_fields=['location'])

        ranked_result = AIFeatureService(self.repository.db).recommend_slots(SlotRecommendationRequest(
            sport_type=criteria.sport_type, booking_date=criteria.booking_date,
            court_type=criteria.court_type,
            court_id=criteria.requested_field_id, slot_id=criteria.requested_time_slot_id,
            start_time=time(criteria.start_minute // 60, criteria.start_minute % 60) if criteria.start_minute is not None else None,
            end_time=time(criteria.end_minute // 60, criteria.end_minute % 60) if criteria.end_minute is not None and criteria.end_minute < 1440 else None,
            time_ranges=[
                (time(start // 60, start % 60), time(end // 60, end % 60))
                for start, end in criteria.time_ranges
            ],
            duration_minutes=criteria.duration_minutes,
            max_price=criteria.max_price, location=criteria.location,
            allow_alternatives=criteria.allow_alternatives,
        ))
        if ranked_result['status'] != 'OK':
            if ranked_result['status'] == 'NO_AVAILABLE_SLOT' or any(term in query for term in ('ngay nao trong', 'ngay trong', 'ngay khac')) or criteria.allow_alternatives:
                alternative_suggestions = self._search_alternative_dates(SlotRecommendationRequest(
                    sport_type=criteria.sport_type, booking_date=criteria.booking_date or datetime.now(self.tz).date(),
                    court_type=criteria.court_type,
                    court_id=criteria.requested_field_id, slot_id=criteria.requested_time_slot_id,
                    start_time=time(criteria.start_minute // 60, criteria.start_minute % 60) if criteria.start_minute is not None else None,
                    end_time=time(criteria.end_minute // 60, criteria.end_minute % 60) if criteria.end_minute is not None and criteria.end_minute < 1440 else None,
                    time_ranges=[
                        (time(start // 60, start % 60), time(end // 60, end % 60))
                        for start, end in criteria.time_ranges
                    ],
                    duration_minutes=criteria.duration_minutes,
                    max_price=criteria.max_price, location=criteria.location,
                    allow_alternatives=True,
                ))
                if alternative_suggestions:
                    return self._format_alternative_dates_response(alternative_suggestions, criteria, route.intent)

            return self._response(
                ranked_result['message'], criteria, [], status=ranked_result['status'],
                missing_fields=ranked_result.get('missing_fields', []),
                needs_clarification=ranked_result['status'] == 'NEED_MORE_DATA',
            )
        suggestions = []
        for item in ranked_result['recommendations'][:3]:
            start_label = item['start_time'].strftime('%H:%M')
            end_label = item['end_time'].strftime('%H:%M')
            alternative = criteria.start_minute is not None and start_label != self._format_minutes(criteria.start_minute)
            suggestions.append({
                'facility_id': item.get('facility_id'),
                'field_id': item['court_id'], 'facility_name': item['facility_name'],
                'court_name': item['court_name'], 'field_name': item['court_name'],
                'sport_type': item['sport_type'], 'court_type': item.get('court_type'), 'location': item['location'],
                'image_url': item.get('image_url'), 'time_slot_id': item['slot_id'],
                'time_slot_ids': item.get('slot_ids', [item['slot_id']]),
                'selected_slots': item.get('selected_slots', []),
                'slot_name': item['slot_name'], 'start_time': start_label, 'end_time': end_label,
                'price': item['price'], 'duration_minutes': item.get('duration_minutes', 0),
                'rating': item['rating'], 'distance_km': item.get('distance_km'),
                'booking_date': item['booking_date'], 'reason': item['reason'],
                'availability_status': 'available', 'is_nearest_alternative': alternative,
                'alternative_type': 'nearest_time' if alternative else None,
            })
        reply = ranked_result['message']
        if route.intent == AssistantIntent.CREATE_BOOKING:
            reply += ' Hãy mở phương án phù hợp, kiểm tra lại thông tin rồi tự xác nhận đặt sân.'
        response = self._response(reply, criteria, suggestions)
        response['understood']['result_field_ids'] = [item['field_id'] for item in suggestions]
        response['understood']['result_time_slot_ids'] = [item['time_slot_id'] for item in suggestions]
        response['understood']['result_prices'] = [item['price'] for item in suggestions]
        response['understood']['reference_price'] = suggestions[0]['price'] if suggestions else None
        return response

    def _search_alternative_dates(self, payload: SlotRecommendationRequest, days: int = 7) -> list:
        found_suggestions = []
        original_date = payload.booking_date or datetime.now(self.tz).date()
        for i in range(1, days + 1):
            next_date = original_date + timedelta(days=i)
            payload_copy = payload.model_copy(update={'booking_date': next_date})
            result = AIFeatureService(self.repository.db).recommend_slots(payload_copy)
            if result['status'] == 'OK' and result['recommendations']:
                for item in result['recommendations'][:2]:
                    start_label = item['start_time'].strftime('%H:%M')
                    end_label = item['end_time'].strftime('%H:%M')
                    found_suggestions.append({
                        'facility_id': item.get('facility_id'),
                        'field_id': item['court_id'], 'facility_name': item['facility_name'],
                        'court_name': item['court_name'], 'field_name': item['court_name'],
                        'sport_type': item['sport_type'], 'court_type': item.get('court_type'), 'location': item['location'],
                        'image_url': item.get('image_url'), 'time_slot_id': item['slot_id'],
                        'time_slot_ids': item.get('slot_ids', [item['slot_id']]),
                        'selected_slots': item.get('selected_slots', []),
                        'slot_name': item['slot_name'], 'start_time': start_label, 'end_time': end_label,
                        'price': item['price'], 'duration_minutes': item.get('duration_minutes', 0),
                        'rating': item['rating'], 'distance_km': item.get('distance_km'),
                        'booking_date': item['booking_date'], 'reason': item['reason'],
                        'availability_status': 'available', 'is_nearest_alternative': False,
                        'alternative_type': 'alternative_date',
                    })
            if len(found_suggestions) >= 4:
                break
        return found_suggestions

    def _format_alternative_dates_response(self, suggestions: list, criteria: SearchCriteria, intent: AssistantIntent):
        dates_map = {}
        for s in suggestions:
            d_str = s['booking_date'].strftime('%d/%m')
            time_str = f"{s['start_time']}–{s['end_time']}"
            if d_str not in dates_map:
                dates_map[d_str] = []
            if time_str not in dates_map[d_str]:
                dates_map[d_str].append(time_str)
        
        reply = "Hiện chưa còn lịch phù hợp. Gần nhất tôi tìm thấy:\n" if not criteria.booking_date else "Hiện chưa còn lịch phù hợp cho ngày bạn chọn. Gần nhất tôi tìm thấy:\n"
        for d, times in dates_map.items():
            reply += f"- {d}: {', '.join(times)}\n"
        reply += "Bạn muốn xem ngày nào?"
        
        response = self._response(reply, criteria, suggestions, status='OK')
        response['understood']['result_field_ids'] = [item['field_id'] for item in suggestions]
        response['understood']['result_time_slot_ids'] = [item['time_slot_id'] for item in suggestions]
        response['understood']['result_prices'] = [item['price'] for item in suggestions]
        response['understood']['reference_price'] = suggestions[0]['price'] if suggestions else None
        return response

    def _answer_venue_detail(self, criteria: SearchCriteria):
        if not criteria.requested_field_id:
            return self._response(
                'Bạn muốn xem giá, địa chỉ hoặc tiện ích của sân nào trong SportHub AI?',
                criteria, [], needs_clarification=True,
            )
        court = self.repository.field_context(criteria.requested_field_id)
        if not court:
            return self._response(NO_DATA_REPLY, criteria, [])
        slots = [slot for field, slot in self.repository.inventory(court.sport_type) if field.id == court.id]
        prices = [float(slot.price) for slot in slots]
        price_value = min(prices) if prices else float(court.base_price)
        price_text = f"{'Giá khung giờ từ' if prices else 'Giá cơ bản'} {price_value:,.0f}đ".replace(',', '.')
        amenities = ', '.join(court.amenities or []) or 'chưa có dữ liệu tiện ích'
        facility_name = court.facility.name if court.facility else court.name
        reply = (
            f'{facility_name} – {court.name}, môn {court.sport_type}, địa chỉ {court.location}. '
            f'{price_text}; sức chứa {court.capacity} người; tiện ích: {amenities}.'
        )
        if self._active_route:
            self._active_route.entities.venue_name = court.name
        return self._response(reply, criteria, [])

    def _answer_products(self, query: str, context_field_id: int | None, context: dict[str, Any]):
        field_id = context_field_id or context.get('field_id')
        if not field_id:
            result_ids = context.get('result_field_ids') or []
            if len(result_ids) == 1:
                field_id = result_ids[0]
        criteria = SearchCriteria(requested_field_id=int(field_id)) if field_id else SearchCriteria()
        if not field_id:
            return self._response(
                'Bạn muốn xem sản phẩm và dịch vụ của sân/cơ sở nào trong SportHub AI?',
                criteria, [], needs_clarification=True, status='NEED_MORE_DATA',
                missing_fields=['field_id'],
            )
        field = self.repository.field_context(int(field_id))
        if field is None or field.facility_id is None:
            return self._response(NO_DATA_REPLY, criteria, [])
        products = InventoryService(self.repository.db).public_available(field.facility_id, field.sport_type)
        if not products:
            return self._response(
                f'Hiện {field.facility.name if field.facility else field.name} chưa có sản phẩm hoặc dịch vụ khả dụng cho môn {field.sport_type}.',
                criteria, [], status='NO_RESULT',
            )
        lines = []
        for product in products[:10]:
            price = f'{float(product["price"]):,.0f}đ'.replace(',', '.')
            availability = (
                f'còn {product["available_quantity"]} {product["unit"]}'
                if product['track_inventory'] else 'đang cung cấp'
            )
            lines.append(f'{product["name"]}: {price}/{product["unit"]}, {availability}')
        facility_name = field.facility.name if field.facility else field.name
        return self._response(
            f'Sản phẩm/dịch vụ khả dụng tại {facility_name} cho môn {field.sport_type}: ' + '; '.join(lines) + '.',
            criteria, [], status='SUCCESS',
        )

    def _venue_search_response(self, criteria: SearchCriteria):
        if not criteria.location:
            if criteria.sport_type:
                return self._response(
                    f'Bạn muốn tìm sân {criteria.sport_type} ở khu vực nào?', criteria, [],
                    needs_clarification=True, status='NEED_MORE_DATA', missing_fields=['location'],
                )
            return self._response(
                'Được chứ! Bạn cho mình biết môn thể thao (bóng đá, cầu lông, pickleball, tennis...), khu vực và ngày muốn chơi nhé.', criteria, [],
                needs_clarification=True, status='NEED_MORE_DATA', missing_fields=['location', 'sport_type'],
            )
        fields = self.repository.search_venues(
            location=criteria.location, sport_type=criteria.sport_type,
            court_type=criteria.court_type, max_price=criteria.max_price, limit=6,
        )
        if not fields:
            label = criteria.location
            sport = f' cho môn {criteria.sport_type}' if criteria.sport_type else ''
            return self._response(
                f'Hiện tại mình chưa tìm thấy cơ sở SportHub{sport} phù hợp ở {label} trong dữ liệu hệ thống.',
                criteria, [], venue_results=[], status='NO_RESULT',
            )
        results = [self._venue_result(field) for field in fields]
        if not criteria.sport_type:
            response = self._response(
                f'Mình tìm thấy {len(results)} sân/cơ sở thực tế ở {criteria.location}. Bạn muốn chơi môn nào để mình lọc chính xác hơn?',
                criteria, [], venue_results=results, needs_clarification=True,
                status='NEED_MORE_DATA', missing_fields=['sport_type'],
            )
            return self._with_venue_context(response, results)
        if not criteria.booking_date:
            response = self._response(
                f'Mình tìm thấy {len(results)} sân {criteria.sport_type} ở {criteria.location}. Bạn muốn đặt vào ngày nào?',
                criteria, [], venue_results=results, needs_clarification=True,
                status='NEED_MORE_DATA', missing_fields=['date'],
            )
            return self._with_venue_context(response, results)
        return None

    def _answer_venue_count(self, criteria: SearchCriteria):
        count = self.repository.count_venues(
            location=criteria.location, sport_type=criteria.sport_type,
        )
        sport = f' {criteria.sport_type}' if criteria.sport_type else ''
        location = f' ở {criteria.location}' if criteria.location else ''
        if count == 0:
            reply = (
                f'Hiện tại SportHub chưa có cơ sở{sport} phù hợp{location} '
                'trong dữ liệu hệ thống.'
            )
            status = 'NO_RESULT'
        else:
            reply = (
                f'Hiện tại SportHub có {count} cơ sở{sport} phù hợp{location} '
                'trong dữ liệu hệ thống.'
            )
            status = 'OK'
        response = self._response(reply, criteria, [], venue_results=[], status=status)
        response['understood']['venue_count'] = count
        return response

    @staticmethod
    def _is_venue_count_query(query: str) -> bool:
        return any(term in query for term in ('bao nhieu co so', 'co bao nhieu co so', 'so luong co so'))

    @staticmethod
    def _with_venue_context(response, results):
        response['understood']['result_field_ids'] = [item['field_id'] for item in results]
        response['understood']['result_prices'] = [item['base_price'] for item in results]
        response['understood']['reference_price'] = results[0]['base_price'] if results else None
        return response

    @staticmethod
    def _venue_result(field):
        facility = field.facility
        return {
            'facility_id': field.facility_id,
            'field_id': field.id,
            'facility_name': facility.name if facility else field.name,
            'court_name': field.name,
            'sport_type': field.sport_type,
            'court_type': f'Sức chứa {field.capacity} người',
            'location': facility.location if facility else field.location,
            'base_price': float(field.base_price),
            'rating': float(field.rating or 0),
            'image_url': field.image_url,
        }

    def _answer_occupancy_insight(self, query: str):
        criteria = SearchCriteria()
        if not self.current_user:
            return self._response(
                'Bạn cần đăng nhập tài khoản OWNER để xem phân tích công suất.', criteria, [],
                needs_clarification=True, status='NEED_MORE_DATA', missing_fields=['owner_session'],
            )
        if self.current_user.role != 'OWNER':
            return self._response('Phân tích công suất chỉ dành cho OWNER của cơ sở.', criteria, [])
        today = datetime.now(self.tz).date()
        date_from = date_to = None
        if 'tuan nay' in query:
            date_from = today - timedelta(days=today.weekday())
            date_to = date_from + timedelta(days=6)
        elif 'thang nay' in query:
            date_from = today.replace(day=1)
            next_month = (date_from.replace(day=28) + timedelta(days=4)).replace(day=1)
            date_to = next_month - timedelta(days=1)
        report = AIFeatureService(self.repository.db).occupancy_summary(
            self.current_user, date_from, date_to, None,
        )
        promotions = ' '.join(report['promotion_suggestions'][:2])
        reply = f'Gợi ý AI: {report["summary"]}'
        if promotions:
            reply += f' Đề xuất tham khảo: {promotions}'
        reply += ' Tôi không tự thay đổi giá hoặc tạo chương trình khuyến mại.'
        return self._response(reply, criteria, [])

    def _answer_sports_knowledge(self, query: str, route: IntentRoute):
        criteria = SearchCriteria()
        if self._assistant_mode == AssistantMode.PROFESSIONAL:
            return self._response(
                PROFESSIONAL_SPORTS_KNOWLEDGE_REFUSAL,
                criteria,
                [],
                classification=ScopeClassification.OUT_OF_SCOPE,
                status='OUT_OF_SCOPE',
            )
        role = self.current_user.role if self.current_user else 'CUSTOMER'
        sport = route.entities.sport_type
        if route.entities.sport_type and route.entities.active_entity is None and not route.entities.sports_entities:
            target_entities = []
        else:
            target_entities = route.entities.sports_entities or (
                [route.entities.active_entity] if route.entities.active_entity
                else ([route.entities.sports_entity] if route.entities.sports_entity else [])
            )
        guardrail = self.guardrail

        # ── Query Rewriting & Normalization ────────────────────────────
        # Use deterministic rewrite first if available
        effective_query = getattr(route.entities, 'rewritten_query', None) or query

        # ── LLM Query Understanding Phase ─────────────────────────────
        # Use LLM to resolve entities/aliases, detect follow-up, rewrite query.
        # Falls back to deterministic extraction if LLM is unavailable.
        llm_processor = get_llm_sports_processor()
        conversation_messages = self._conversation_context.get('conversation_messages')
        llm_understanding = llm_processor.understand_query(
            query, conversation_messages=conversation_messages, context=self._conversation_context,
        )
        if llm_understanding:
            logger.info(
                'LLM understanding: entities=%s sport=%s topic=%s follow_up=%s rewrite=%s',
                llm_understanding.entities, llm_understanding.sport, llm_understanding.topic,
                llm_understanding.is_follow_up, llm_understanding.rewritten_query[:80],
            )
            # Merge LLM-resolved entities with deterministic ones
            if llm_understanding.entities and not target_entities:
                target_entities = llm_understanding.entities
            elif llm_understanding.entities:
                for llm_ent in llm_understanding.entities:
                    if llm_ent not in target_entities:
                        target_entities.append(llm_ent)
            # Use LLM sport if deterministic didn't find one
            if llm_understanding.sport and not sport:
                sport = llm_understanding.sport
            # Use LLM rewritten query if available
            if llm_understanding.rewritten_query and llm_understanding.rewritten_query != query:
                effective_query = llm_understanding.rewritten_query

        # ── RAG Retrieval Phase ────────────────────────────────────────
        # If no specific entities detected, perform broad sports retrieval
        if not target_entities:
            retrieved = guardrail.retrieve_context(effective_query, role, route.intent.name, sport=sport, entity=None, assistant_mode=self._assistant_mode)
            eval_res = guardrail.evaluate_freshness_and_sufficiency(effective_query, retrieved)
            if eval_res.needs_fresh_web:
                web_evidences = guardrail.retrieve_web_context(effective_query, route.intent.name, sport=sport, entity=None, assistant_mode=self._assistant_mode)
                retrieved = guardrail.merge_and_prefer_evidence(effective_query, retrieved, web_evidences)
            target_entities = [None]
            entity_retrievals = {None: retrieved or []}
        else:
            entity_retrievals = {}
            for ent in target_entities:
                retrieved = guardrail.retrieve_context(effective_query, role, route.intent.name, sport=sport, entity=ent, assistant_mode=self._assistant_mode)
                if not retrieved and ent:
                    search_query = f"{ent} {effective_query}"
                    retrieved = guardrail.retrieve_context(search_query, role, route.intent.name, sport=sport, entity=ent, assistant_mode=self._assistant_mode)
                if not retrieved and route.entities.competition and route.entities.competition != ent:
                    retrieved = guardrail.retrieve_context(effective_query, role, route.intent.name, sport=sport, entity=route.entities.competition, assistant_mode=self._assistant_mode)
                if not retrieved:
                    retrieved = guardrail.retrieve_context(effective_query, role, route.intent.name, sport=sport, entity=None, assistant_mode=self._assistant_mode)
                eval_res = guardrail.evaluate_freshness_and_sufficiency(effective_query, retrieved)
                if eval_res.needs_fresh_web:
                    web_evidences = guardrail.retrieve_web_context(effective_query, route.intent.name, sport=sport, entity=ent, assistant_mode=self._assistant_mode)
                    retrieved = guardrail.merge_and_prefer_evidence(effective_query, retrieved, web_evidences)
                entity_retrievals[ent] = retrieved or []

        # ── LLM Grounded Response Generation Phase ─────────────────────
        # Collect all evidence for LLM response generation
        all_evidence = []
        for ent in target_entities:
            all_evidence.extend(entity_retrievals.get(ent, []))

        target_ent = target_entities[0] if (target_entities and target_entities[0]) else (route.entities.active_entity or route.entities.sports_entity)
        target_top = (llm_understanding.topic if llm_understanding else None) or route.entities.current_topic
        grounded = llm_processor.generate_grounded_response(
            effective_query,
            all_evidence,
            conversation_messages=conversation_messages,
            target_entity=target_ent,
            target_topic=target_top,
        )
        if grounded and grounded.answer:
            # LLM generated a natural response — use it with citations
            answer_text = validate_response(grounded.answer)
            if grounded.citations:
                citation_parts = []
                for cit in grounded.citations:
                    part = f"Nguồn: {cit['source_name']}"
                    if cit.get('source_url'):
                        part += f", {cit['source_url']}"
                    if cit.get('collected_at'):
                        part += f", cập nhật {cit['collected_at']}"
                    citation_parts.append(part)
                answer_text += f"\n\n({'; '.join(citation_parts)})"

            # Build response using existing _response method
            first_entry = all_evidence[0][0] if all_evidence else None
            response = self._response(answer_text, criteria, [], classification=ScopeClassification.IN_SCOPE, status='OK')
            if route.entities.sports_entities:
                response['understood']['sports_entities'] = route.entities.sports_entities
            resolved_active = target_ent or (first_entry.entity if first_entry else None)
            if resolved_active:
                response['understood']['active_entity'] = resolved_active
                response['understood']['sports_entity'] = resolved_active
            if route.entities.recent_entities:
                response['understood']['recent_entities'] = route.entities.recent_entities
            if first_entry and first_entry.sport:
                response['understood']['sport_type'] = first_entry.sport
            elif sport:
                response['understood']['sport_type'] = sport
            if target_top:
                response['understood']['current_topic'] = target_top
                response['understood']['entity_type'] = target_top
            elif first_entry and getattr(first_entry, 'topic', None):
                response['understood']['entity_type'] = first_entry.topic
                response['understood']['current_topic'] = first_entry.topic
            response['understood']['last_intent'] = AssistantIntent.SPORTS_KNOWLEDGE.value
            return response

        # ── Deterministic Fallback Response (existing logic) ───────────
        # If LLM response generation failed/unavailable, use original concatenation
        return self._answer_sports_knowledge_deterministic(
            query, route, criteria, role, sport, target_entities, entity_retrievals, guardrail,
        )

    def _answer_sports_knowledge_deterministic(
        self, query: str, route: IntentRoute, criteria: SearchCriteria,
        role: str, sport: str | None, target_entities: list,
        entity_retrievals: dict, guardrail: RAGGuardrail,
    ):
        """Deterministic sports knowledge response builder — used as fallback when LLM is unavailable."""
        norm_q = plain(query)
        requested_topics = {}
        topic_labels = {
            'identity': 'thông tin giới thiệu',
            'birth_date': 'ngày sinh',
            'birth_place': 'nơi sinh/quê quán',
            'current_club': 'CLB/đội bóng hiện tại',
            'status': 'trạng thái thi đấu',
            'career': 'quá trình thi đấu',
            'achievements': 'thành tích',
        }

        if any(p in norm_q for p in ('cup wc', 'wc', 'world cup', 'cup the gioi')):
            if not any(p in norm_q for p in ('to chuc o dau', 'dien ra o dau', 'dang cai', 'vua pha luoi', 'ghi ban', 'thang ai')):
                requested_topics['world_cup'] = 'FIFA World Cup'
                requested_topics['achievements'] = topic_labels['achievements']
        elif any(p in norm_q for p in ('c1', 'cup c1', 'champions league', 'uefa champions league')):
            if not any(p in norm_q for p in ('to chuc o dau', 'dien ra o dau', 'dang cai', 'vua pha luoi', 'ghi ban', 'thang ai')):
                requested_topics['champions_league'] = 'UEFA Champions League'
                requested_topics['achievements'] = topic_labels['achievements']
        elif any(p in norm_q for p in ('qua bong vang', 'may qua', 'may qua bong vang', 'ballon d\'or', 'ballon dor')):
            requested_topics['ballon_dor'] = 'Quả bóng vàng'
            requested_topics['achievements'] = topic_labels['achievements']
        elif any(p in norm_q for p in ('thanh tich', 'danh hieu', 'giai thuong', 'huy chuong', 'cup', 'vo dich')):
            requested_topics['achievements'] = topic_labels['achievements']

        if any(p in norm_q for p in ('sinh ngay', 'ngay sinh', 'sinh nam', 'sinh vao ngay', 'sinh ngay bao nhieu', 'sinh ngay nao', 'bao nhieu tuoi')):
            requested_topics['birth_date'] = topic_labels['birth_date']
        if any(p in norm_q for p in ('sinh o dau', 'noi sinh', 'que o dau', 'que quan', 'sinh tai', 'que o')):
            requested_topics['birth_place'] = topic_labels['birth_place']
        if any(p in norm_q for p in ('quoc gia nao', 'den tu dau', 'den tu quoc gia', 'o nuoc nao', 'thuoc nuoc nao')):
            requested_topics['country'] = 'quốc gia'
            requested_topics['birth_place'] = topic_labels['birth_place']
        if any(p in norm_q for p in ('la ai', 'gioi thieu', 'tieu su', 'profil', 'la doi nao', 'la doi bong nao', 'la clb nao', 'la doi', 'la clb')):
            requested_topics['identity'] = topic_labels['identity']
        elif any(p in norm_q for p in ('clb hien tai', 'doi hien tai', 'dang choi cho', 'dang thi dau cho', 'khoac ao', 'dang da cho', 'clb nao', 'doi nao', 'dang da', 'thi dau o dau', 'choi o dau', 'da o dau', 'o doi nao', 'thi dau cho clb', 'thi dau cho clb nao')):
            requested_topics['current_club'] = topic_labels['current_club']
        if any(p in norm_q for p in ('trang thai', 'giai nghe', 'con thi dau', 'da gia tu', 'giai nghe chua', 'da giai nghe')):
            requested_topics['status'] = topic_labels['status']
        if any(p in norm_q for p in ('qua trinh thi dau', 'su nghiep', 'tung thi dau', 'cac clb')):
            requested_topics['career'] = topic_labels['career']
        if any(p in norm_q for p in ('chieu cao', 'cao bao nhieu')) and not any(p in norm_q for p in ('kich thuoc', 'luoi', 'vanh')):
            requested_topics['height'] = 'chiều cao'
        if any(p in norm_q for p in ('can nang', 'nang bao nhieu')):
            requested_topics['weight'] = 'cân nặng'
        if any(p in norm_q for p in ('the vang', 'the do', 'the phat', 'phat the', 'bi the', 'dinh the', 'bao nhieu the', 'may the')):
            requested_topics['cards'] = 'thẻ phạt/thẻ vàng/thẻ đỏ'
        if any(p in norm_q for p in ('luong', 'thu nhap', 'tai san', 'gia chuyen nhuong')):
            requested_topics['salary'] = 'tiền lương/thu nhập'
        if any(p in norm_q for p in ('vo', 'ban gai', 'gia dinh', 'con cai', 'ket hon')):
            requested_topics['family'] = 'gia đình/đời tư'
        if any(p in norm_q for p in ('to chuc o dau', 'dien ra o dau', 'dang cai o dau', 'dia diem to chuc', 'dia diem')):
            requested_topics['host_location'] = 'địa điểm tổ chức'
        if any(p in norm_q for p in ('vua pha luoi', 'ghi ban', 'ai ghi ban', 'ghi nhieu ban nhat', 'top scorer', 'cau thu ghi ban')):
            requested_topics['top_scorer'] = 'vua phá lưới/cầu thủ ghi bàn'
        if any(p in norm_q for p in ('thang ai', 'danh bai ai', 'ha ai', 'thang doi nao', 'chung ket', 'tran chung ket')):
            requested_topics['match_result'] = 'kết quả trận đấu'
        if any(p in norm_q for p in ('thanh lap', 'ngay thanh lap', 'nam thanh lap', 'thanh lap khi nao', 'thanh lap nam nao', 'ra mat khi nao', 'thanh lap vao nam')):
            requested_topics['founded'] = 'ngày/năm thành lập'

        TOPIC_ALIASES = {
            'cầu thủ': 'identity',
            'vận động viên': 'identity',
            'profile': 'identity',
            'tiểu sử': 'identity',
            'clb bóng đá': ('identity', 'achievements'),
            'clb bóng đá nữ': ('identity', 'achievements'),
            'clb bóng đá nam': ('identity', 'achievements'),
            'đội bóng thái nguyên': ('identity', 'achievements'),
            'clb bóng đá thái nguyên': ('identity', 'achievements'),
            'bóng đá nữ thái nguyên': ('identity', 'achievements'),
            'bóng đá nam thái nguyên': ('identity', 'achievements'),
            'số lượng clb bóng đá': 'identity',
            'clb chuyên nghiệp thái nguyên': 'identity',
            'bóng đá sinh viên ictu': 'identity',
            'thành tích bóng đá ictu': ('achievements', 'career'),
            'giải bóng đá ictu cup': 'identity',
            'bóng đá nữ ictu': 'identity',
            'bóng đá khoa cntt ictu': 'identity',
            'bóng đá khoa kỹ thuật công nghệ ictu': 'identity',
            'phân biệt ictu và thái nguyên t&t': 'identity',
            'phân biệt ictu và fc thái nguyên': 'identity',
            'đội bóng sinh viên thái nguyên': 'identity',
            'phong trào thể thao ictu': 'identity',
            'cầu lông ictu': 'identity',
            'bóng chuyền ictu': 'identity',
            'bóng bàn ictu': 'identity',
            'pickleball ictu': 'identity',
            'clb thể thao ictu': 'identity',
            'tổng quan thể thao thái nguyên': 'identity',
            'tổng quan thể thao hà nội': 'identity',
            'clb bóng đá hà nội': 'identity',
            'clb bóng rổ hà nội': 'identity',
            'bóng chuyền hà nội': 'identity',
            'cầu lông hà nội': 'identity',
            'thể thao đại học hà nội': 'identity',
            'tổng quan thể thao tp.hcm': 'identity',
            'clb bóng đá tp.hcm': 'identity',
            'clb bóng rổ tp.hcm': 'identity',
            'cầu lông tp.hcm': 'identity',
            'bóng bàn tp.hcm': 'identity',
            'bóng chuyền tp.hcm': 'identity',
            'giải đấu': 'identity',
        }

        all_answers = []
        all_citations = []
        first_entry = None

        is_multi = len([e for e in target_entities if e]) > 1

        for ent in target_entities:
            retrieved = entity_retrievals.get(ent, [])
            if not retrieved:
                target_label = ent if ent else "nội dung này"
                all_answers.append(f"Hiện tại SportHub AI chưa có thông tin kiểm chứng về {target_label} trong cơ sở dữ liệu.")
                continue

            candidates = [entry for entry, score in retrieved]
            if ent is None and any(k in norm_q for k in ('cau thu', 'vdv', 'van dong vien', 'tay vot', 'hlv', 'huan luyen vien')) and not any(k in norm_q for k in ('cac cau thu', 'cac vdv', 'nhung cau thu', 'phong trao', 'luat', 'kich thuoc', 'tieu chuan', 'huong dan')):
                q_words = [w for w in norm_q.split() if len(w) >= 3 and w not in ('cau', 'thu', 'bong', 'hien', 'dang', 'thi', 'dau', 'cho', 'clb', 'nao', 'la', 'ai')]
                has_relevant_content = any(
                    any(w in plain(f"{getattr(e, 'question', getattr(e, 'title', ''))} {getattr(e, 'answer', getattr(e, 'snippet', ''))}") for w in q_words)
                    for e in candidates
                ) if q_words else bool(candidates)
                if not has_relevant_content:
                    all_answers.append("Hiện tại SportHub AI chưa có thông tin kiểm chứng về nội dung này trong cơ sở dữ liệu.")
                    continue

            seen_answers = set()
            selected_entries = []

            # If user asks a specific tournament or trophy question, prioritize entries explicitly matching that target
            target_trophy = getattr(route.entities, 'target_trophy', None)
            has_specific_target = target_trophy or any(k in requested_topics for k in ('world_cup', 'champions_league', 'ballon_dor', 'current_club', 'birth_date', 'birth_place', 'host_location', 'top_scorer', 'match_result'))

            candidates = [entry for entry, score in retrieved]
            if has_specific_target:
                # Filter down to entries that match the specific topic/target
                filtered_candidates = []
                for e in candidates:
                    q_str = getattr(e, 'question', getattr(e, 'title', ''))
                    a_str = getattr(e, 'answer', getattr(e, 'snippet', ''))
                    q_norm = plain(q_str)
                    a_norm = plain(a_str)
                    combined = f"{q_norm} {a_norm}"
                    top_k = (getattr(e, 'topic', '') or "").lower()
                    top_k_val = TOPIC_ALIASES.get(top_k, top_k)
                    top_k_keys = set(top_k_val) if isinstance(top_k_val, (list, tuple, set)) else {top_k_val}

                    matches_target = False
                    if 'world_cup' in requested_topics and ('world cup' in combined or 'wc' in combined):
                        matches_target = True
                    if 'champions_league' in requested_topics and ('champions league' in combined or 'c1' in combined or 'cúp c1' in combined):
                        matches_target = True
                    if 'ballon_dor' in requested_topics and ('quả bóng vàng' in combined or 'ballon' in combined or 'qua bong vang' in combined):
                        matches_target = True
                    if 'current_club' in requested_topics and ('current_club' in top_k_keys or any(k in combined for k in ('thi dau cho', 'khoac ao', 'clb', 'choi cho', 'real madrid', 'inter miami', 'al-nassr', 'cong an ha noi', 'becamex', 'phu dong'))):
                        matches_target = True
                    if 'birth_date' in requested_topics and ('birth_date' in top_k_keys or 'sinh ngay' in combined or 'ngay sinh' in combined):
                        matches_target = True
                    if 'birth_place' in requested_topics and ('birth_place' in top_k_keys or 'country' in requested_topics or 'sinh ra tai' in combined or 'que' in combined or 'phu tho' in combined or 'serbia' in combined):
                        matches_target = True
                    if 'country' in requested_topics and ('birth_place' in top_k_keys or 'serbia' in combined or 'quoc gia' in combined or 'my' in combined or 'viet nam' in combined):
                        matches_target = True
                    if 'status' in requested_topics and ('status' in top_k_keys or 'chua giai nghe' in combined or 'giai nghe' in combined):
                        matches_target = True
                    if 'career' in requested_topics and ('career' in top_k_keys or 'su nghiep' in combined or 'qua trinh' in combined):
                        matches_target = True
                    if 'achievements' in requested_topics and ('achievements' in top_k_keys or 'danh hieu' in combined or 'thanh tich' in combined or 'vo dich' in combined):
                        matches_target = True
                    if 'host_location' in requested_topics and ('host_location' in top_k_keys or any(k in combined for k in ('to chuc o', 'dien ra tai', 'dang cai', 'dia diem to chuc', 'my', 'canada', 'mexico', 'qatar'))):
                        matches_target = True
                    if 'top_scorer' in requested_topics and ('top_scorer' in top_k_keys or any(k in combined for k in ('vua pha luoi', 'ghi ban', 'mbappe', 'ronaldo', 'messi', '8 ban'))):
                        matches_target = True
                    if 'match_result' in requested_topics and ('match_result' in top_k_keys or any(k in combined for k in ('thang', 'danh bai', 'ha', 'chung ket', 'phap', 'argentina', 'pen', 'luan luu'))):
                        matches_target = True
                    if 'founded' in requested_topics and ('founded' in top_k_keys or any(k in combined for k in ('thanh lap vao', 'ngay thanh lap', 'nam thanh lap', 'thanh lap nam'))):
                        matches_target = True
                    if 'identity' in requested_topics and (bool(top_k_keys & {'identity', 'profile', 'cầu thủ', 'vận động viên'}) or any(k in combined for k in ('la cau thu', 'la tien dao', 'tien dao huyen thoai', 'sieu sao', 'la ai', 'profile', 'sinh ra tai', 'khoac ao', 'cau lac bo', 'clb', 'doi bong'))):
                        matches_target = True

                    if matches_target:
                        filtered_candidates.append(e)

                if filtered_candidates:
                    candidates = filtered_candidates

            for entry in candidates:
                norm_ans = plain(getattr(entry, 'answer', getattr(entry, 'snippet', '')))
                if norm_ans not in seen_answers:
                    seen_answers.add(norm_ans)
                    selected_entries.append(entry)

            if not first_entry and selected_entries:
                first_entry = selected_entries[0]

            retrieved_topics = set()
            for e in selected_entries:
                top_key = (getattr(e, 'topic', '') or "").lower()
                top_val = TOPIC_ALIASES.get(top_key, top_key)
                if isinstance(top_val, (list, tuple, set)):
                    for tk in top_val:
                        retrieved_topics.add(tk)
                elif top_val:
                    retrieved_topics.add(top_val)
                combined_e = plain(f"{getattr(e, 'question', '')} {getattr(e, 'answer', getattr(e, 'snippet', ''))}")
                if 'world cup' in combined_e or 'wc' in combined_e:
                    retrieved_topics.add('world_cup')
                    retrieved_topics.add('achievements')
                if 'champions league' in combined_e or 'c1' in combined_e:
                    retrieved_topics.add('champions_league')
                    retrieved_topics.add('achievements')
                if 'qua bong vang' in combined_e or 'ballon' in combined_e:
                    retrieved_topics.add('ballon_dor')
                    retrieved_topics.add('achievements')
                if 'sinh ngay' in combined_e or 'ngay sinh' in combined_e:
                    retrieved_topics.add('birth_date')
                if 'sinh ra tai' in combined_e or 'que o' in combined_e:
                    retrieved_topics.add('birth_place')
                if 'thi dau cho' in combined_e or 'khoac ao' in combined_e or 'clb' in combined_e:
                    retrieved_topics.add('current_club')
                if 'chua giai nghe' in combined_e or 'da giai nghe' in combined_e:
                    retrieved_topics.add('status')
                if 'qua trinh' in combined_e or 'su nghiep' in combined_e:
                    retrieved_topics.add('career')
                if any(k in combined_e for k in ('to chuc o', 'dien ra tai', 'dang cai', 'dia diem')):
                    retrieved_topics.add('host_location')
                if any(k in combined_e for k in ('vua pha luoi', 'ghi ban', 'mbappe', '8 ban')):
                    retrieved_topics.add('top_scorer')
                if any(k in combined_e for k in ('thang', 'danh bai', 'ha', 'chung ket', 'phap')):
                    retrieved_topics.add('match_result')

            missing_labels = []
            logger.warning('DEBUG missing_labels=%s requested_topics=%s retrieved_topics=%s selected_entries=%s', missing_labels, requested_topics, retrieved_topics, [e.id for e in selected_entries])
            if requested_topics:
                for top_key, label in requested_topics.items():
                    if top_key not in retrieved_topics:
                        ans_combined = plain(" ".join(getattr(e, 'answer', getattr(e, 'snippet', '')) for e in selected_entries))
                        if top_key == 'birth_date' and any(k in ans_combined for k in ('sinh ngay', 'thang', 'nam 19', 'nam 20')):
                            continue
                        if top_key == 'birth_place' and any(k in ans_combined for k in ('sinh ra tai', 'que o', 'huyen', 'tinh', 'thanh pho')):
                            continue
                        if top_key == 'current_club' and any(k in ans_combined for k in ('clb', 'cau lac bo', 'thi dau cho', 'khoac ao')):
                            continue
                        if top_key == 'identity' and len(selected_entries) > 0:
                            continue
                        if top_key in ('world_cup', 'champions_league', 'ballon_dor') and 'achievements' in retrieved_topics:
                            continue
                        missing_labels.append(label)

            ent_answers = [validate_response(getattr(e, 'answer', getattr(e, 'snippet', ''))) for e in selected_entries]
            if missing_labels:
                entity_name = ent or (selected_entries[0].entity if selected_entries and hasattr(selected_entries[0], 'entity') else "")
                entity_str = f" của {entity_name}" if entity_name else ""
                missing_text = f"(Lưu ý: Hiện tại SportHub AI chưa có thông tin kiểm chứng về {', '.join(missing_labels)}{entity_str} trong cơ sở dữ liệu)."
                ent_answers.append(missing_text)

            ent_citations = []
            ent_seen_sources = set()
            for e in selected_entries:
                src_name = getattr(e, 'source_name', None) or getattr(e, 'source', None)
                src_url = getattr(e, 'source_url', None)
                updated = getattr(e, 'collected_at', None)
                if src_name and src_name not in ent_seen_sources:
                    ent_seen_sources.add(src_name)
                    cit = f"Nguồn: {src_name}"
                    if src_url:
                        cit += f", {src_url}"
                    if updated:
                        cit += f", cập nhật {updated}"
                    ent_citations.append(cit)

            if is_multi and ent:
                section_text = f"**{ent}**:\n" + "\n\n".join(ent_answers)
                if ent_citations:
                    section_text += f"\n\n({'; '.join(ent_citations)})"
                all_answers.append(section_text)
            else:
                all_answers.extend(ent_answers)
                all_citations.extend(ent_citations)

        if not all_answers:
            entity_label = f" về {', '.join(e for e in target_entities if e)}" if any(target_entities) else (f" về môn {sport}" if sport else "")
            reply = (
                f"Hiện tại SportHub AI chưa có thông tin kiểm chứng{entity_label} trong kho dữ liệu thể thao. "
                "Tôi chỉ cung cấp thông tin đã được xác thực trong phạm vi các môn SportHub hỗ trợ."
            )
            response = self._response(reply, criteria, [], classification=ScopeClassification.IN_SCOPE, status='OK')
            if route.entities.sports_entities:
                response['understood']['sports_entities'] = route.entities.sports_entities
            active_ent = route.entities.active_entity or route.entities.sports_entity
            if active_ent:
                response['understood']['active_entity'] = active_ent
                response['understood']['sports_entity'] = active_ent
            if route.entities.recent_entities:
                response['understood']['recent_entities'] = route.entities.recent_entities
            if route.entities.sport_type:
                response['understood']['sport_type'] = route.entities.sport_type
            response['understood']['last_intent'] = AssistantIntent.SPORTS_KNOWLEDGE.value
            return response

        answer_text = "\n\n".join(all_answers)
        if not is_multi and all_citations:
            answer_text += f"\n\n({'; '.join(all_citations)})"

        if getattr(route.entities, 'conditional_note', None):
            answer_text = f"{route.entities.conditional_note}\n\n" + answer_text
            if not answer_text.endswith("?"):
                answer_text += "\n\n(Nếu bạn đang hỏi về môn thể thao hoặc nhân vật nào khác, hãy chia sẻ thêm ngữ cảnh nhé! 😊)"

        if getattr(route.entities, 'is_meme_or_joke', False):
            if 'Harry Maguire' in target_entities:
                answer_text += "\n\n(Lưu ý vui: 'Đấng Maguire' là biệt danh meme hài hước của người hâm mộ bóng đá trên mạng xã hội, bắt nguồn từ những tình huống thi đấu độc lạ và tính cách giải trí của trung vệ người Anh! 😄⚽)"
            elif 'Romelu Lukaku' in target_entities:
                answer_text += "\n\n(Lưu ý vui: 'Lakaka' là meme vui nhộn của cộng đồng mạng xuất phát từ những pha bóng tấu hài bất đắc dĩ của tiền đạo Romelu Lukaku! 😄⚽)"

        response = self._response(answer_text, criteria, [], classification=ScopeClassification.IN_SCOPE, status='OK')
        if route.entities.sports_entities:
            response['understood']['sports_entities'] = route.entities.sports_entities
        
        resolved_active = route.entities.active_entity or (first_entry.entity if first_entry else (route.entities.sports_entity or (target_entities[0] if target_entities else None)))
        if resolved_active:
            response['understood']['active_entity'] = resolved_active
            response['understood']['sports_entity'] = resolved_active
        if route.entities.recent_entities:
            response['understood']['recent_entities'] = route.entities.recent_entities

        if first_entry and first_entry.sport:
            response['understood']['sport_type'] = first_entry.sport
            response['understood']['sport'] = first_entry.sport
        elif route.entities.sport_type:
            response['understood']['sport_type'] = route.entities.sport_type
            response['understood']['sport'] = route.entities.sport_type

        if route.entities.entity_type:
            response['understood']['entity_type'] = route.entities.entity_type
        elif first_entry and getattr(first_entry, 'entity_type', None):
            response['understood']['entity_type'] = getattr(first_entry, 'entity_type')

        if route.entities.location:
            response['understood']['location'] = route.entities.location

        if route.entities.competition:
            response['understood']['competition'] = route.entities.competition

        if getattr(route.entities, 'year', None):
            response['understood']['year'] = route.entities.year
            response['understood']['competition_year'] = route.entities.year

        curr_top = route.entities.current_topic or (first_entry.topic if first_entry else None)
        if curr_top:
            response['understood']['current_topic'] = curr_top

        response['understood']['last_intent'] = AssistantIntent.SPORTS_KNOWLEDGE.value
        return response

    def _answer_partner_application(self, query: str):
        criteria = SearchCriteria()
        current_role = self.current_user.role if self.current_user else None
        entry, static_reply, action_dict = match_system_knowledge(query, current_role)
        if entry and not any(term in query for term in ('cua toi', 'ho so cua')):
            return self._response(static_reply, criteria, [], action=action_dict)

        process = (
            'Quy trình gồm: mở hồ sơ đối tác, nhập thông tin người đại diện (họ tên, điện thoại, email), '
            'thông tin cơ sở dự kiến (tên, địa chỉ/khu vực, mô tả), xác nhận thông tin rồi gửi để SYSTEM_ADMIN xét duyệt. '
            'Bước xin quyền OWNER này chưa yêu cầu giấy phép hoặc ảnh cơ sở; các tài liệu xác minh thuộc bước đăng ký cơ sở sau khi được duyệt.'
        )
        if not self.current_user:
            return self._response(
                process + ' Bạn cần đăng nhập để tôi kiểm tra trạng thái hồ sơ thuộc tài khoản của bạn.',
                criteria, [], partner_application_status=None,
                action={'label': 'Đăng ký trở thành chủ sân', 'route': '/owner-application', 'kind': 'link'},
            )
        if self.current_user.role == 'SYSTEM_ADMIN':
            return self._response(
                'Chức năng này hướng dẫn CUSTOMER đăng ký trở thành OWNER. SYSTEM_ADMIN là người xem xét và quyết định APPROVED hoặc REJECTED; tôi không tự duyệt hồ sơ.',
                criteria, [],
            )

        application = self.repository.latest_owner_application(self.current_user.id)
        raw_status = application.status if application else None
        if raw_status == 'PENDING':
            status = 'PENDING'
            reply = 'Hồ sơ của bạn đang chờ SYSTEM_ADMIN xét duyệt. Bạn có thể mở hồ sơ để xem lại thông tin đã gửi; AI không thể tự duyệt hoặc thay đổi trạng thái.'
            action = {'label': 'Xem hồ sơ', 'route': '/owner-application/status', 'kind': 'link'}
        elif raw_status == 'APPROVED' or (application is None and self.current_user.role == 'OWNER'):
            status = 'APPROVED'
            reply = 'Hồ sơ của bạn đã được SYSTEM_ADMIN phê duyệt và tài khoản hiện có thể truy cập khu vực quản lý OWNER.'
            action = {'label': 'Đi tới khu vực quản lý', 'route': '/management/dashboard', 'kind': 'link'}
        elif raw_status == 'REJECTED':
            status = 'REJECTED'
            reason = (application.rejection_reason or application.admin_note or '').strip()
            reason_text = f' Lý do được SYSTEM_ADMIN ghi nhận: {reason}' if reason else ' SYSTEM_ADMIN chưa ghi lý do cụ thể trong hồ sơ.'
            reply = 'Hồ sơ của bạn đã bị từ chối.' + reason_text + ' Bạn có thể cập nhật thông tin và gửi lại để được xem xét.'
            action = {'label': 'Cập nhật và gửi lại hồ sơ', 'route': '/owner-application', 'kind': 'link'}
        else:
            status = 'NONE'
            if raw_status == 'DRAFT':
                state_text = 'Bạn có bản nháp chưa gửi xét duyệt.'
            elif raw_status == 'WITHDRAWN':
                state_text = 'Hồ sơ trước đó đã được rút và hiện không có hồ sơ đang chờ xét duyệt.'
            else:
                state_text = 'Bạn chưa có hồ sơ đăng ký OWNER.'
            reply = f'{state_text} {process}'
            action = {'label': 'Đăng ký trở thành chủ sân', 'route': '/owner-application', 'kind': 'link'}

        response = self._response(
            reply, criteria, [], partner_application_status=status, action=action,
        )
        response['understood']['partner_application_status'] = status
        response['understood']['partner_application_id'] = application.id if application else None
        return response

    def _answer_booking_action(self, query: str, intent: AssistantIntent):
        criteria = SearchCriteria()
        booking_code = self._active_route.entities.booking_code if self._active_route else None
        action = 'hủy' if intent == AssistantIntent.CANCEL_BOOKING else 'đổi lịch'
        if not booking_code:
            current_role = self.current_user.role if self.current_user else None
            _, static_reply, action_dict = match_system_knowledge(query, current_role)
            if static_reply:
                return self._response(static_reply, criteria, [], action=action_dict)
            return self._response(
                f'Bạn muốn {action} booking nào? Vui lòng cung cấp mã booking SportHub.',
                criteria, [], needs_clarification=True,
            )
        if not self.current_user:
            return self._login_response(criteria, action)
        booking = self.repository.accessible_booking(self.current_user, booking_code)
        if not booking:
            return self._response(NO_DATA_REPLY, criteria, [])
        if intent == AssistantIntent.CANCEL_BOOKING:
            reply = (
                f'Booking {booking.booking_code} hiện ở trạng thái {booking.status}. Tôi không tự hủy booking; '
                'hãy mở chi tiết booking, xem báo giá hoàn tiền theo chính sách đã snapshot rồi xác nhận hủy.'
            )
        else:
            reply = (
                f'Booking {booking.booking_code} hiện ở trạng thái {booking.status}. Tôi không tự đổi lịch; '
                'hãy mở chi tiết booking, chọn ngày và khung giờ mới còn trống rồi xác nhận thay đổi.'
            )
        return self._response(reply, criteria, [])

    def _answer_information(self, query: str, intent: str):
        criteria = SearchCriteria()
        current_role = self.current_user.role if self.current_user else None

        # Check static knowledge first for system_help, general workflows, or guides
        entry, static_reply, action_dict = match_system_knowledge(query, current_role)
        if static_reply:
            return self._response(static_reply, criteria, [], intent=intent, action=action_dict)

        if intent == 'system_help':
            return self._response(
                'Tôi là trợ lý AI chuyên biệt của SportHub. Tôi có thể giúp bạn: \n• Tìm sân thể thao và kiểm tra lịch trống thực tế theo ngày, giờ, khu vực.\n• Gợi ý khung giờ phù hợp và báo giá niêm yết.\n• Xem thông tin đặt sân và hướng dẫn thanh toán/hủy sân.\n• Phân tích công suất vận hành (dành cho chủ sân OWNER) và hỗ trợ hồ sơ đối tác.',
                criteria, [], intent=intent,
            )
        if intent == 'profile':
            if not self.current_user:
                return self._login_response(criteria, intent)
            if self.current_user.role == 'SYSTEM_ADMIN' and any(
                term in query for term in ('bao nhieu owner', 'bao nhieu customer', 'owner dang hoat dong', 'tai khoan toan he thong')
            ):
                totals = self.repository.platform_account_summary()
                return self._response(
                    f"Toàn hệ thống hiện có {totals['CUSTOMER']} CUSTOMER, {totals['OWNER']} OWNER đang hoạt động "
                    f"và {totals['SYSTEM_ADMIN']} SYSTEM_ADMIN.",
                    criteria, [], intent=intent,
                )
            user = self.current_user
            reply = f'Hồ sơ đang đăng nhập: {user.full_name}, vai trò {user.role}, email {user.email}'
            if user.phone:
                reply += f', số điện thoại {user.phone}'
            return self._response(reply + '.', criteria, [], intent=intent)
        if intent == 'payment' and 'doanh thu' in query:
            if not self.current_user:
                return self._login_response(criteria, intent)
            if self.current_user.role == 'CUSTOMER':
                return self._response('CUSTOMER không có quyền xem dữ liệu doanh thu vận hành.', criteria, [], intent=intent)
            now = datetime.now(self.tz)
            start = datetime(now.year, now.month, 1, tzinfo=self.tz)
            end = datetime(now.year + (1 if now.month == 12 else 0), 1 if now.month == 12 else now.month + 1, 1, tzinfo=self.tz)
            total = self.repository.revenue_total(self.current_user, start, end)
            label = 'toàn nền tảng' if self.current_user.role == 'SYSTEM_ADMIN' else 'các cơ sở trong phạm vi của bạn'
            return self._response(
                f'Doanh thu đã thanh toán trong tháng này của {label} là {total:,.0f}đ.'.replace(',', '.'),
                criteria, [], intent=intent,
            )
        if intent == 'payment' and not self._requests_account_data(query):
            return self._response(
                'Trong SportHub AI, bạn chọn sân và khung giờ, kiểm tra tổng tiền và mức cọc, tự xác nhận booking rồi thực hiện thanh toán. Hệ thống giữ khung giờ theo thời hạn hiển thị, chống booking trùng và cập nhật trạng thái giao dịch; hoàn tiền và hóa đơn phụ thuộc booking cùng chính sách cơ sở thực tế.',
                criteria, [], intent='system_help',
            )
        if intent == 'policy':
            field_id = self._field_by_name(query)
            court = self.repository.field_context(field_id) if field_id else None
            if court:
                refund = court.cancellation_refund_percent
                detail = f', mức hoàn cấu hình là {float(refund):g}%' if refund is not None else ''
                return self._response(
                    f'{court.name} áp dụng chính sách {court.cancellation_policy}{detail}. Dữ liệu lấy từ cấu hình sân hiện tại; chính sách được snapshot khi tạo booking.',
                    criteria, [], intent=intent,
                )
            if not self._requests_account_data(query):
                return self._response(
                    'Bạn muốn xem chính sách hủy của sân hoặc booking nào? Mỗi cơ sở có thể có cấu hình khác nhau và SportHub sẽ snapshot chính sách vào booking.',
                    criteria, [], intent=intent, needs_clarification=True,
                    classification=ScopeClassification.UNCLEAR,
                )
        if not self.current_user:
            return self._login_response(criteria, intent)
        if intent == 'booking_status' and any(term in query for term in ('bao nhieu booking', 'booking hom nay')):
            booking_date = datetime.now(self.tz).date() if 'hom nay' in query else None
            count = self.repository.booking_count(self.current_user, booking_date)
            scope = 'của bạn' if self.current_user.role == 'CUSTOMER' else 'trong phạm vi được phép'
            return self._response(f'Có {count} booking {scope}{" hôm nay" if booking_date else ""}.', criteria, [], intent=intent)
        booking_code = self._active_route.entities.booking_code if self._active_route else None
        booking = self.repository.accessible_booking(self.current_user, booking_code)
        if not booking:
            return self._response(NO_DATA_REPLY, criteria, [], intent=intent)
        if intent == 'booking_status':
            booking_slots = booking.booking_slots or []
            schedule = ', '.join(
                f'{slot.start_time_snapshot:%H:%M}–{slot.end_time_snapshot:%H:%M}'
                for slot in booking_slots
            ) or f'{booking.start_time_snapshot:%H:%M}–{booking.end_time_snapshot:%H:%M}'
            reply = (
                f'Booking {booking.booking_code} tại {booking.field.name} đang ở trạng thái {booking.status}; '
                f'trạng thái thanh toán là {booking.payment_status}. Ngày chơi {booking.booking_date:%d/%m/%Y}, '
                f'các khung giờ: {schedule}.'
            )
        elif intent == 'policy':
            refund = booking.cancellation_refund_percent
            detail = f', mức hoàn theo snapshot là {float(refund):g}%' if refund is not None else ''
            reply = f'Booking {booking.booking_code} áp dụng chính sách {booking.cancellation_policy}{detail}; hủy miễn phí trước {booking.free_cancellation_minutes / 60:g} giờ.'
        else:
            payment = self.repository.latest_payment(booking.id)
            if not payment:
                reply = f'Booking {booking.booking_code} chưa có giao dịch thanh toán trong SportHub AI.'
            else:
                reply = (
                    f'Booking {booking.booking_code}: tổng {float(booking.total_amount):,.0f}đ, đã thanh toán '
                    f'{float(booking.paid_amount):,.0f}đ, còn lại {float(booking.remaining_amount):,.0f}đ. '
                    f'Giao dịch gần nhất {payment.transaction_code} đang ở trạng thái {payment.status}.'
                ).replace(',', '.')
        return self._response(reply, criteria, [], intent=intent)

    @staticmethod
    def _requests_account_data(query: str) -> bool:
        if any(term in query for term in ('lam the nao', 'cach', 'huong dan', 'la gi', 'quy trinh')):
            return False
        return bool(re.search(r'\bSH[- ]?[A-Z0-9-]{3,}\b', query.upper())) or any(
            term in query for term in ('cua toi', 'booking', 'ma dat', 'giao dich gan nhat', 'hoa don cua')
        )

    def _login_response(self, criteria: SearchCriteria, intent: str):
        return self._response(
            'Bạn cần đăng nhập để tôi có thể truy xuất booking, thanh toán hoặc hồ sơ thuộc chính tài khoản của bạn.',
            criteria, [], intent=intent, needs_clarification=True,
        )

    @staticmethod
    def _resolve_result_reference(criteria: SearchCriteria, query: str, context: dict[str, Any]):
        field_ids = context.get('result_field_ids') or []
        if not field_ids:
            return
        position = None
        if any(term in query for term in ('san dau tien', 'san dau', 'lua chon dau', 'ket qua dau', 'san so 1', 'lua chon 1', 'ket qua 1')):
            position = 1
        elif any(term in query for term in ('san cuoi cung', 'san cuoi', 'lua chon cuoi', 'ket qua cuoi')):
            position = len(field_ids)
        else:
            match = re.search(r'\b(?:san|lua chon|ket qua)\s*(?:thu\s*|so\s*)?(\d+|mot|hai|ba|tu|nam)\b', query)
            if match:
                ordinals = {'mot': 1, 'hai': 2, 'ba': 3, 'tu': 4, 'nam': 5}
                position = int(match[1]) if match[1].isdigit() else ordinals.get(match[1], 1)

        if position and 0 < position <= len(field_ids):
            criteria.requested_field_id = int(field_ids[position - 1])
            time_slot_ids = context.get('result_time_slot_ids') or []
            if position <= len(time_slot_ids):
                criteria.requested_time_slot_id = int(time_slot_ids[position - 1])

    def _extract(self, query: str, context_field_id: int | None) -> SearchCriteria:
        time_query = re.sub(r'\b20\d{2}-\d{1,2}-\d{1,2}\b', ' ', query)
        time_query = re.sub(r'\b\d{1,2}[/-]\d{1,2}(?:[/-]20\d{2})?\b', ' ', time_query)
        start, end = self._time_range(time_query)
        time_ranges = self._time_ranges(time_query)
        if len(time_ranges) > 1:
            start, end = time_ranges[0]
        duration = self._duration(time_query)
        if duration and start is not None and end is None:
            end = min(24 * 60, start + duration)
        booking_date, invalid_date = self._date(query)
        requested = context_field_id if context_field_id and ('san nay' in query or 'co so nay' in query) else self._field_by_name(query)
        if requested is None and context_field_id:
            requested = context_field_id
        extracted_sport = next((value for key, value in SPORT_ALIASES.items() if key in query), None)
        extracted_location = self._active_route.entities.location if self._active_route else None
        if requested and not extracted_sport:
            field_ctx = self.repository.field_context(requested)
            if field_ctx:
                extracted_sport = field_ctx.sport_type
                if not extracted_location:
                    extracted_location = field_ctx.location
        return SearchCriteria(
            sport_type=extracted_sport,
            court_type=self._active_route.entities.court_type if self._active_route else None,
            booking_date=booking_date,
            start_minute=start,
            end_minute=end,
            duration_minutes=duration or (end - start if start is not None and end is not None else None),
            time_ranges=time_ranges,
            location=extracted_location,
            max_price=self._price(query),
            people=self._people(query),
            special_requirements=self._special_requirements(query),
            requested_field_id=requested,
            allow_alternatives=any(term in query for term in ('khong co thi', 'gio khac', 'san khac', 'gan nhat', 'con san nao')),
            prefer_cheap=any(term in query for term in ('re mot chut', 'gia re', 're nhat', 're hon', 'tiet kiem')),
            near_me=any(term in query for term in ('gan day', 'gan toi', 'quanh day')),
            invalid_date=invalid_date,
            invalid_time=start is not None and end is not None and end <= start,
        )

    def _merge_context(self, criteria: SearchCriteria, context: dict[str, Any], query: str):
        b_ctx = context.get('business_context') or {}
        is_return_biz = getattr(getattr(self, '_active_route', None), 'entities', None) and getattr(self._active_route.entities, 'is_return_to_business', False)
        if is_return_biz and b_ctx:
            values = {
                'sport_type': b_ctx.get('sport_type') or context.get('sport_type'),
                'court_type': b_ctx.get('court_type') or context.get('court_type'),
                'location': b_ctx.get('location') or context.get('location'),
                'max_price': b_ctx.get('max_price') or context.get('max_price'),
                'people': b_ctx.get('people') or context.get('people'),
            }
        else:
            values = {
                'sport_type': context.get('sport_type') or b_ctx.get('sport_type'),
                'court_type': context.get('court_type') or b_ctx.get('court_type'),
                'location': context.get('location') or b_ctx.get('location'),
                'max_price': context.get('max_price') or b_ctx.get('max_price'),
                'people': context.get('people') or b_ctx.get('people'),
            }
        clearing_court = any(term in query for term in (
            'san khac', 'co so khac', 'con san nao', 'con san khac',
            'vay con san nao', 'con san nao khong', 'san nao khac',
        ))
        if not clearing_court:
            values['requested_field_id'] = context.get('field_id') or b_ctx.get('field_id')
        else:
            criteria.requested_field_id = None
        for name, value in values.items():
            if getattr(criteria, name) is None and value is not None:
                setattr(criteria, name, value)
        if criteria.requested_field_id and not criteria.sport_type:
            field_ctx = self.repository.field_context(criteria.requested_field_id)
            if field_ctx:
                criteria.sport_type = field_ctx.sport_type
                if not criteria.location:
                    criteria.location = field_ctx.location
        booking_date_val = context.get('booking_date') or b_ctx.get('booking_date')
        if criteria.booking_date is None and booking_date_val:
            try:
                criteria.booking_date = date.fromisoformat(str(booking_date_val))
            except ValueError:
                pass
        for name, key in (('start_minute', 'start_time'), ('end_minute', 'end_time')):
            val = context.get(key) or b_ctx.get(key)
            if getattr(criteria, name) is None and val:
                try:
                    hour, minute = map(int, str(val).split(':')[:2])
                    setattr(criteria, name, hour * 60 + minute)
                except (TypeError, ValueError):
                    pass

    def _response(
        self, reply: str, criteria: SearchCriteria, suggestions: list[dict[str, Any]], *,
        intent='search_booking', needs_clarification=False,
        classification=ScopeClassification.IN_SCOPE,
        status='OK', missing_fields: list[str] | None = None,
        venue_results: list[dict[str, Any]] | None = None,
        partner_application_status: str | None = None,
        action: dict[str, str] | None = None,
    ):
        route = self._active_route
        entities = route.to_dict()['entities'] if route else {
            'sport_type': None, 'court_type': None, 'venue_name': None, 'location': None, 'date': None,
            'start_time': None, 'end_time': None, 'preferred_time': None, 'max_price': None, 'price_max': None,
            'number_of_players': None, 'booking_code': None, 'sports_entity': None,
        }
        criteria_entities = {
            'sport_type': criteria.sport_type,
            'court_type': criteria.court_type,
            'location': criteria.location,
            'date': criteria.booking_date.isoformat() if criteria.booking_date else None,
            'start_time': self._format_minutes(criteria.start_minute),
            'end_time': self._format_minutes(criteria.end_minute),
            'max_price': criteria.max_price,
            'price_max': criteria.max_price,
            'number_of_players': criteria.people,
        }
        entities.update({key: value for key, value in criteria_entities.items() if value is not None})
        understood = self._understood(criteria)
        for key in (
            'sport_type', 'sport', 'court_type', 'booking_date', 'start_time', 'end_time', 'location', 'field_id',
            'time_slot_id', 'max_price', 'people', 'result_field_ids', 'result_time_slot_ids',
            'result_prices', 'reference_price', 'sports_entity', 'active_entity', 'recent_entities',
            'entity_type', 'competition', 'team', 'athlete', 'current_topic', 'scope_domain',
        ):
            if understood.get(key) is None and self._conversation_context.get(key) is not None:
                understood[key] = self._conversation_context[key]
        
        # Populate athlete / team from route if present
        if route and getattr(route.entities, 'athlete', None) and not understood.get('athlete'):
            understood['athlete'] = route.entities.athlete
        if route and getattr(route.entities, 'team', None) and not understood.get('team'):
            understood['team'] = route.entities.team

        # Maintain dual context: business context snapshot across sports knowledge shifts
        if is_business_intent(route.intent if route else None):
            business_ctx = {
                'sport_type': criteria.sport_type or understood.get('sport_type'),
                'location': criteria.location or understood.get('location'),
                'booking_date': criteria.booking_date.isoformat() if criteria.booking_date else understood.get('booking_date'),
                'start_time': self._format_minutes(criteria.start_minute) or understood.get('start_time'),
                'end_time': self._format_minutes(criteria.end_minute) or understood.get('end_time'),
                'max_price': criteria.max_price or understood.get('max_price'),
                'court_type': criteria.court_type or understood.get('court_type'),
                'field_id': criteria.requested_field_id or understood.get('field_id'),
            }
            understood['business_context'] = {k: v for k, v in business_ctx.items() if v is not None}
        elif self._conversation_context.get('business_context'):
            understood['business_context'] = self._conversation_context['business_context']
        elif (criteria.sport_type or criteria.location) and (route is None or route.intent != AssistantIntent.SPORTS_KNOWLEDGE):
            business_ctx = {
                'sport_type': criteria.sport_type or understood.get('sport_type'),
                'location': criteria.location or understood.get('location'),
                'booking_date': criteria.booking_date.isoformat() if criteria.booking_date else understood.get('booking_date'),
                'start_time': self._format_minutes(criteria.start_minute) or understood.get('start_time'),
                'end_time': self._format_minutes(criteria.end_minute) or understood.get('end_time'),
                'max_price': criteria.max_price or understood.get('max_price'),
                'court_type': criteria.court_type or understood.get('court_type'),
                'field_id': criteria.requested_field_id or understood.get('field_id'),
            }
            understood['business_context'] = {k: v for k, v in business_ctx.items() if v is not None}

        understood['last_intent'] = route.intent.value if route else intent
        final_reply = reply
        if route and getattr(route, 'is_combined_out_of_scope', False) and route.intent != AssistantIntent.OUT_OF_SCOPE:
            disclaimer = "(Lưu ý: SportHub AI chỉ hỗ trợ các dịch vụ sân thể thao và hệ thống, không hỗ trợ nội dung ngoài phạm vi như thời tiết/nấu ăn).\n\n"
            if disclaimer not in final_reply:
                final_reply = disclaimer + final_reply

        return {
            'reply': final_reply,
            'understood': understood,
            'suggestions': suggestions,
            'venue_results': venue_results or [],
            'intent': route.intent.value if route else intent,
            'confidence': route.confidence if route else 1.0,
            'entities': entities,
            'needs_clarification': needs_clarification,
            'source': 'live_backend',
            'classification': classification.value,
            'status': status,
            'missing_fields': missing_fields or [],
            'context_reset': bool(route.context_reset) if route else False,
            'partner_application_status': partner_application_status,
            'action': action,
            'assistant_mode': self._assistant_mode,
        }

    @staticmethod
    def _sanitize_context_for_mode(context: dict[str, Any], mode: AssistantMode) -> dict[str, Any]:
        sanitized = dict(context)
        if mode == AssistantMode.PROFESSIONAL:
            sanitized.pop('sports_entity', None)
            sanitized.pop('active_entity', None)
            sanitized.pop('recent_entities', None)
            sanitized.pop('sports_entities', None)
            sanitized.pop('entity_type', None)
            sanitized.pop('current_topic', None)
            if sanitized.get('last_intent') == AssistantIntent.SPORTS_KNOWLEDGE.value:
                sanitized.pop('last_intent', None)
        return sanitized

    def _understood(self, criteria: SearchCriteria):
        return {
            'sport_type': criteria.sport_type,
            'court_type': criteria.court_type,
            'booking_date': criteria.booking_date.isoformat() if criteria.booking_date else None,
            'start_time': self._format_minutes(criteria.start_minute),
            'end_time': self._format_minutes(criteria.end_minute),
            'duration_minutes': criteria.duration_minutes,
            'time_ranges': [
                {'start_time': self._format_minutes(start), 'end_time': self._format_minutes(end)}
                for start, end in criteria.time_ranges
            ],
            'location': criteria.location,
            'field_id': criteria.requested_field_id,
            'time_slot_id': criteria.requested_time_slot_id,
            'max_price': criteria.max_price,
            'people': criteria.people,
            'special_requirements': criteria.special_requirements,
            'allow_alternatives': criteria.allow_alternatives,
            'assistant_mode': self._assistant_mode.value if isinstance(self._assistant_mode, AssistantMode) else str(self._assistant_mode),
            'scope_decision': self._mode_evaluation.scope_decision.value if self._mode_evaluation else None,
        }

    def _field_by_name(self, query: str):
        # 1. Exact or substring match in query
        exact_matches = []
        for court, _ in self.repository.inventory():
            court_name_plain = plain(court.name)
            if court_name_plain and court_name_plain in query:
                exact_matches.append(court)
        if exact_matches:
            return sorted(exact_matches, key=lambda c: len(c.name), reverse=True)[0].id

        # 2. Natural court identifier / code matching (e.g. "sân 7", "sân 7A", "sân A7", "sân số 7")
        court_num_match = re.search(r'\b(?:san\s+so\s+|san\s+|so\s+)?([a-z0-9]{1,4})\b', query)
        if court_num_match:
            candidate_num = court_num_match[1].strip().lower()
            # Only search if candidate token is explicitly a court number/code
            if candidate_num and any(char.isdigit() for char in candidate_num):
                code_matches = []
                for court, _ in self.repository.inventory():
                    c_plain = plain(court.name)
                    # Check if candidate_num appears as court number in court.name
                    if re.search(rf'\b(?:san\s+so\s+|san\s+|so\s+)?{re.escape(candidate_num)}\b', c_plain):
                        code_matches.append(court)
                if len(code_matches) == 1:
                    return code_matches[0].id
        return None

    def _date(self, query: str) -> tuple[date | None, bool]:
        today = datetime.now(self.tz).date()
        if 'ngay kia' in query or 'ngay mot' in query:
            return today + timedelta(days=2), False
        if 'hom nay' in query or 'toi nay' in query:
            return today, False
        if 'ngay mai' in query or 'toi mai' in query or re.search(r'\bmai\b', query):
            return today + timedelta(days=1), False
        if 'cuoi tuan nay' in query:
            days = (5 - today.weekday()) % 7
            return today + timedelta(days=days), False
        iso = re.search(r'\b(20\d{2})-(\d{1,2})-(\d{1,2})\b', query)
        short = re.search(r'\b(\d{1,2})[/-](\d{1,2})(?:[/-](20\d{2}))?\b', query)
        if iso or short:
            try:
                result = date(int(iso[1]), int(iso[2]), int(iso[3])) if iso else date(int(short[3] or today.year), int(short[2]), int(short[1]))
                return (result, result < today)
            except ValueError:
                return None, True
        for label, weekday in WEEKDAYS.items():
            if label in query:
                days = (weekday - today.weekday()) % 7
                return today + timedelta(days=days), False
        return None, False

    @staticmethod
    def _price(query: str):
        match = re.search(r'(?:duoi|toi da|khong qua|<=?)\s*([\d.,]+)\s*(trieu|k|nghin|d|dong)?', query)
        if not match:
            match = re.search(r'(?:tam|khoang)\s*([\d.,]+)\s*(trieu|k|nghin|d|dong)\b', query)
        if not match:
            return None
        raw, unit = match[1], match[2]
        value = float(raw.replace('.', '').replace(',', '.'))
        return value * (1_000_000 if unit == 'trieu' else 1_000 if unit in ('k', 'nghin') else 1)

    @staticmethod
    def _time_range(query: str):
        evening = any(term in query for term in ('toi nay', 'toi mai', 'buoi toi', 'gio toi')) or bool(re.search(
            r'\b(?:toi\s+(?:thu|ngay|\d|luc|khoang)|\d{1,2}(?::\d{2})?\s*(?:h|gio)?\s*toi)\b',
            query,
        ))
        range_match = re.search(r'\b([01]?\d|2[0-3])(?::([0-5]\d))?\s*(?:-|–|den|toi)\s*([01]?\d|2[0-3])(?::([0-5]\d))?\s*(?:h|gio)?\b', query)
        if range_match:
            values = [int(range_match[1]) * 60 + int(range_match[2] or 0), int(range_match[3]) * 60 + int(range_match[4] or 0)]
        else:
            matches = list(re.finditer(r'\b([01]?\d|2[0-3])(?::([0-5]\d))?\s*(?:h|gio)\b', query))
            values = [int(item[1]) * 60 + int(item[2] or 0) for item in matches[:2]]
        if values:
            if evening:
                values = [value + 12 * 60 if value < 12 * 60 else value for value in values]
            return values[0], values[1] if len(values) > 1 else None
        if 'sang' in query:
            return 8 * 60, None
        if evening:
            return 19 * 60, None
        if 'chieu' in query:
            return 15 * 60, None
        return None, None

    @staticmethod
    def _time_ranges(query: str):
        matches = list(re.finditer(
            r'\b([01]?\d|2[0-3])(?::([0-5]\d))?\s*(?:-|–|den|toi)\s*([01]?\d|2[0-3])(?::([0-5]\d))?\s*(?:h|gio)?\b',
            query,
        ))
        ranges = [
            (int(item[1]) * 60 + int(item[2] or 0), int(item[3]) * 60 + int(item[4] or 0))
            for item in matches
        ]
        evening = any(term in query for term in ('toi nay', 'toi mai', 'buoi toi', 'gio toi')) or bool(re.search(
            r'\b(?:toi\s+(?:thu|ngay|\d|luc|khoang)|\d{1,2}(?::\d{2})?\s*(?:h|gio)?\s*toi)\b',
            query,
        ))
        if len(ranges) == 1 and evening and ranges[0][0] < 12 * 60 and ranges[0][1] <= 12 * 60:
            ranges = [(ranges[0][0] + 12 * 60, ranges[0][1] + 12 * 60)]
        return [(start, end) for start, end in ranges if end > start]

    @staticmethod
    def _duration(query: str):
        match = re.search(r'\b(?:choi|trong)\s*(\d+(?:[.,]\d+)?)\s*(?:tieng|gio)\b', query)
        if not match:
            return None
        return round(float(match[1].replace(',', '.')) * 60)

    @staticmethod
    def _people(query: str):
        match = re.search(r'\b(\d{1,3})\s*(?:nguoi|thanh vien)\b', query)
        return int(match[1]) if match else None

    @staticmethod
    def _special_requirements(query: str) -> list[str]:
        norm = plain(query)
        found = [value for key, value in SPECIAL_REQUIREMENTS.items() if key in norm]
        if any(term in norm for term in ('den chieu sang', 'he thong den', 'den sang', 'co den', 'dan den', 'bat den')):
            found.append('đèn chiếu sáng')
        elif re.search(r'\bden\b', norm):
            is_preposition = (
                bool(re.search(r'(?:\d{1,2}(?::\d{2})?(?:h|gio)?|sang|chieu|toi|ngay)\s+den\b', norm))
                or bool(re.search(r'\bden\s+(?:\d{1,2}(?::\d{2})?(?:h|gio)?|sang|chieu|toi|ngay)\b', norm))
                or ('tu ' in norm and 'den' in norm)
            )
            if not is_preposition:
                found.append('đèn chiếu sáng')
        return list(dict.fromkeys(found))

    @staticmethod
    def _format_minutes(value):
        return None if value is None else f'{value // 60:02d}:{value % 60:02d}'
