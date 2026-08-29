import re
import unicodedata
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from ..core.config import settings
from ..models.user import User
from ..repositories.ai_repository import AIRepository
from ..schemas.ai import SlotRecommendationRequest
from .ai_feature_service import AIFeatureService
from .inventory_service import InventoryService
from .ai_domain_policy import NO_DATA_REPLY, OUT_OF_SCOPE_REPLY, ScopeClassification
from .ai_intent_router import AssistantIntent, IntentRoute, IntentRouter


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
    'den': 'đèn chiếu sáng', 'dieu hoa': 'điều hòa', 'tam': 'phòng tắm',
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
    start_minute: int | None = None
    end_minute: int | None = None
    duration_minutes: int | None = None
    time_ranges: list[tuple[int, int]] = field(default_factory=list)
    location: str | None = None
    max_price: float | None = None
    people: int | None = None
    special_requirements: list[str] = field(default_factory=list)
    requested_field_id: int | None = None
    requested_time_slot_id: int | None = None
    allow_alternatives: bool = False
    prefer_cheap: bool = False
    near_me: bool = False
    invalid_date: bool = False
    invalid_time: bool = False


class AIAssistantService:
    def __init__(self, repository: AIRepository, current_user: User | None = None):
        self.repository = repository
        self.current_user = current_user
        self.repository.scope_for_user(current_user)
        self.tz = ZoneInfo(settings.TIMEZONE)
        self.intent_router = IntentRouter()
        self._active_route: IntentRoute | None = None
        self._conversation_context: dict[str, Any] = {}

    def ask(self, message: str, context_field_id: int | None = None, context: dict[str, Any] | None = None):
        query = plain(' '.join(message.strip().split()))
        router_context = dict(context or {})
        if context_field_id and not router_context.get('field_id'):
            router_context['field_id'] = context_field_id
        self._conversation_context = router_context
        route = self.intent_router.route(message, router_context, today=datetime.now(self.tz).date())
        self._active_route = route
        effective_context = {} if route.context_reset else router_context
        self._conversation_context = effective_context
        logger.info('Assistant intent=%s confidence=%.2f', route.intent.value, route.confidence)

        if route.intent == AssistantIntent.OUT_OF_SCOPE:
            return self._response(
                OUT_OF_SCOPE_REPLY, SearchCriteria(), [], needs_clarification=False,
                classification=ScopeClassification.OUT_OF_SCOPE, status='OUT_OF_SCOPE',
            )
        if route.intent == AssistantIntent.GREETING:
            return self._response(
                'Chào bạn! Tôi là trợ lý chuyên biệt của SportHub AI. Bạn muốn tìm sân, kiểm tra lịch trống hay xem booking nào?',
                SearchCriteria(), [],
            )
        if route.intent == AssistantIntent.UNCLEAR:
            return self._response(
                'Bạn muốn tìm sân, kiểm tra lịch trống hay xem thông tin gì trên SportHub AI? Hãy cho mình biết môn thể thao, khu vực hoặc ngày bạn muốn chơi nhé.',
                SearchCriteria(), [], needs_clarification=True, classification=ScopeClassification.UNCLEAR,
                status='NEED_MORE_DATA',
            )
        if route.intent == AssistantIntent.PARTNER_APPLICATION_SUPPORT:
            return self._answer_partner_application(query)
        information_intents = {
            AssistantIntent.GET_BOOKING: 'booking_status',
            AssistantIntent.PAYMENT_SUPPORT: 'payment',
            AssistantIntent.ACCOUNT_SUPPORT: 'profile',
            AssistantIntent.SYSTEM_GUIDE: 'system_help',
        }
        if route.intent in information_intents:
            return self._answer_information(query, information_intents[route.intent])
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
        location_first_request = (criteria.requested_field_id is None) and (
            bool(criteria.location) or (
                criteria.booking_date is None
                and criteria.start_minute is None
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
            if any(term in query for term in ('ngay nao trong', 'ngay trong', 'ngay khac')) or criteria.allow_alternatives:
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
                    allow_alternatives=criteria.allow_alternatives,
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

    def _answer_partner_application(self, query: str):
        criteria = SearchCriteria()
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
        return SearchCriteria(
            sport_type=next((value for key, value in SPORT_ALIASES.items() if key in query), None),
            court_type=self._active_route.entities.court_type if self._active_route else None,
            booking_date=booking_date,
            start_minute=start,
            end_minute=end,
            duration_minutes=duration or (end - start if start is not None and end is not None else None),
            time_ranges=time_ranges,
            location=self._active_route.entities.location if self._active_route else None,
            max_price=self._price(query),
            people=self._people(query),
            special_requirements=[value for key, value in SPECIAL_REQUIREMENTS.items() if key in query],
            requested_field_id=requested,
            allow_alternatives=any(term in query for term in ('khong co thi', 'gio khac', 'san khac', 'gan nhat')),
            prefer_cheap=any(term in query for term in ('re mot chut', 'gia re', 're nhat', 're hon', 'tiet kiem')),
            near_me=any(term in query for term in ('gan day', 'gan toi', 'quanh day')),
            invalid_date=invalid_date,
            invalid_time=start is not None and end is not None and end <= start,
        )

    @staticmethod
    def _merge_context(criteria: SearchCriteria, context: dict[str, Any], query: str):
        values = {
            'sport_type': context.get('sport_type'),
            'court_type': context.get('court_type'),
            'location': context.get('location'),
            'max_price': context.get('max_price'),
            'people': context.get('people'),
        }
        if 'san khac' not in query and 'co so khac' not in query:
            values['requested_field_id'] = context.get('field_id')
        for name, value in values.items():
            if getattr(criteria, name) is None and value is not None:
                setattr(criteria, name, value)
        if criteria.booking_date is None and context.get('booking_date'):
            try:
                criteria.booking_date = date.fromisoformat(str(context['booking_date']))
            except ValueError:
                pass
        for name, key in (('start_minute', 'start_time'), ('end_minute', 'end_time')):
            if getattr(criteria, name) is None and context.get(key):
                try:
                    hour, minute = map(int, str(context[key]).split(':')[:2])
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
            'number_of_players': None, 'booking_code': None,
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
            'sport_type', 'court_type', 'booking_date', 'start_time', 'end_time', 'location', 'field_id',
            'time_slot_id', 'max_price', 'people', 'result_field_ids', 'result_time_slot_ids',
            'result_prices', 'reference_price',
        ):
            if understood.get(key) is None and self._conversation_context.get(key) is not None:
                understood[key] = self._conversation_context[key]
        understood['last_intent'] = route.intent.value if route else intent
        return {
            'reply': reply,
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
        }

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
        }

    def _field_by_name(self, query: str):
        for court, _ in self.repository.inventory():
            if plain(court.name) in query:
                return court.id
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
        evening = bool(re.search(
            r'\b(?:buoi toi|toi (?:nay|mai|luc|khoang|tu|\d{1,2})|\d{1,2}(?::\d{2})?\s*(?:h|gio)\s*toi)\b',
            query,
        ))
        range_match = re.search(r'\b([01]?\d|2[0-3])(?::([0-5]\d))?\s*(?:-|–|den|toi)\s*([01]?\d|2[0-3])(?::([0-5]\d))?\s*(?:h|gio)?\b', query)
        if range_match:
            values = [int(range_match[1]) * 60 + int(range_match[2] or 0), int(range_match[3]) * 60 + int(range_match[4] or 0)]
        else:
            matches = list(re.finditer(r'\b([01]?\d|2[0-3])(?::([0-5]\d))?\s*(?:h|gio)\b', query))
            values = [int(item[1]) * 60 + int(item[2] or 0) for item in matches[:2]]
        if values:
            if evening and 'den' not in query:
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
        evening = bool(re.search(r'\b(?:buoi toi|toi nay|toi mai)\b', query))
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
    def _format_minutes(value):
        return None if value is None else f'{value // 60:02d}:{value % 60:02d}'
