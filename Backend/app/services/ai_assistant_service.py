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
    booking_date: date | None = None
    start_minute: int | None = None
    end_minute: int | None = None
    duration_minutes: int | None = None
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
        logger.info('Assistant intent=%s confidence=%.2f', route.intent.value, route.confidence)

        if route.intent == AssistantIntent.OUT_OF_SCOPE:
            return self._response(
                OUT_OF_SCOPE_REPLY, SearchCriteria(), [], needs_clarification=False,
                classification=ScopeClassification.OUT_OF_SCOPE,
            )
        if route.intent == AssistantIntent.GREETING:
            return self._response(
                'Chào bạn! Tôi là trợ lý chuyên biệt của SportHub AI. Bạn muốn tìm sân, kiểm tra lịch trống hay xem booking nào?',
                SearchCriteria(), [],
            )
        if route.intent == AssistantIntent.UNCLEAR:
            return self._response(
                'Bạn muốn hỏi về sân, lịch trống, booking hay thanh toán nào trong SportHub AI?',
                SearchCriteria(), [], needs_clarification=True, classification=ScopeClassification.UNCLEAR,
            )
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

        criteria = self._extract(query, context_field_id)
        self._merge_context(criteria, context or {})
        self._resolve_result_reference(criteria, query, context or {})
        if criteria.requested_field_id and self._active_route and not self._active_route.entities.venue_name:
            referenced_court = self.repository.field_context(criteria.requested_field_id)
            if referenced_court:
                self._active_route.entities.venue_name = referenced_court.name
        if route.intent == AssistantIntent.GET_VENUE_DETAIL:
            if criteria.requested_field_id is None and context_field_id:
                criteria.requested_field_id = context_field_id
            return self._answer_venue_detail(criteria)
        logger.info('Search criteria: %s', self._understood(criteria))

        if criteria.invalid_date:
            return self._response('Ngày bạn nhập không hợp lệ hoặc đã qua. Vui lòng chọn một ngày từ hôm nay trở đi.', criteria, [], needs_clarification=True)
        if criteria.invalid_time:
            return self._response('Khung giờ không hợp lệ. Giờ kết thúc phải sau giờ bắt đầu.', criteria, [], needs_clarification=True)
        if not criteria.sport_type:
            return self._response('Bạn muốn tìm sân cho môn thể thao nào?', criteria, [], needs_clarification=True)
        if not criteria.booking_date:
            return self._response(f'Bạn muốn chơi {criteria.sport_type} vào ngày nào?', criteria, [], needs_clarification=True)
        if criteria.near_me and not criteria.location:
            return self._response('Bạn muốn tìm sân gần khu vực nào?', criteria, [], needs_clarification=True, classification=ScopeClassification.UNCLEAR)

        inventory = self.repository.available_candidates(criteria.sport_type, criteria.booking_date, None)
        if criteria.people is not None:
            inventory = [(court, slot) for court, slot in inventory if court.capacity >= criteria.people]
        now = datetime.now(self.tz)
        if criteria.booking_date == now.date():
            current = now.time().replace(tzinfo=None)
            inventory = [(court, slot) for court, slot in inventory if slot.start_time > current]

        if not inventory:
            label = criteria.booking_date.strftime('%d/%m/%Y')
            return self._response(f'Hiện tôi chưa tìm thấy sân {criteria.sport_type} phù hợp ngày {label} trong dữ liệu SportHub AI.', criteria, [])

        exact = [pair for pair in inventory if self._matches(pair, criteria)]
        logger.info('Backend search completed: %d available, %d exact', len(inventory), len(exact))
        strategy = 'exact' if exact else 'nearest_alternative'
        ranked = sorted(exact or inventory, key=lambda pair: self._rank(pair, criteria, exact=bool(exact)))[:5]
        suggestions = [self._suggestion(pair, criteria, strategy) for pair in ranked]
        reply = self._reply(criteria, suggestions, exact=bool(exact))
        if route.intent == AssistantIntent.CREATE_BOOKING:
            reply += ' Hãy mở phương án phù hợp, kiểm tra lại thông tin rồi tự xác nhận đặt sân.'
        response = self._response(reply, criteria, suggestions)
        response['understood']['result_field_ids'] = [item['field_id'] for item in suggestions]
        response['understood']['result_time_slot_ids'] = [item['time_slot_id'] for item in suggestions]
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
                'Bạn có thể dùng SportHub AI để tìm sân và lịch trống, mở trang chi tiết, chọn khung giờ rồi tự xác nhận booking và thanh toán. Tôi không tự tạo booking hoặc giao dịch thay bạn.',
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
            reply = (
                f'Booking {booking.booking_code} tại {booking.field.name} đang ở trạng thái {booking.status}; '
                f'trạng thái thanh toán là {booking.payment_status}. Ngày chơi {booking.booking_date:%d/%m/%Y}, '
                f'{booking.start_time_snapshot:%H:%M}–{booking.end_time_snapshot:%H:%M}.'
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
        match = re.search(r'\b(?:san|lua chon|ket qua)\s*(?:thu\s*)?(\d+|mot|hai|ba|tu|nam)\b', query)
        if not match:
            return
        ordinals = {'mot': 1, 'hai': 2, 'ba': 3, 'tu': 4, 'nam': 5}
        position = int(match[1]) if match[1].isdigit() else ordinals[match[1]]
        field_ids = context.get('result_field_ids') or []
        if 0 < position <= len(field_ids):
            criteria.requested_field_id = int(field_ids[position - 1])
            time_slot_ids = context.get('result_time_slot_ids') or []
            if position <= len(time_slot_ids):
                criteria.requested_time_slot_id = int(time_slot_ids[position - 1])

    def _extract(self, query: str, context_field_id: int | None) -> SearchCriteria:
        time_query = re.sub(r'\b20\d{2}-\d{1,2}-\d{1,2}\b', ' ', query)
        time_query = re.sub(r'\b\d{1,2}[/-]\d{1,2}(?:[/-]20\d{2})?\b', ' ', time_query)
        start, end = self._time_range(time_query)
        duration = self._duration(time_query)
        if duration and start is not None and end is None:
            end = min(24 * 60, start + duration)
        booking_date, invalid_date = self._date(query)
        requested = context_field_id if context_field_id and ('san nay' in query or 'co so nay' in query) else self._field_by_name(query)
        return SearchCriteria(
            sport_type=next((value for key, value in SPORT_ALIASES.items() if key in query), None),
            booking_date=booking_date,
            start_minute=start,
            end_minute=end,
            duration_minutes=duration or (end - start if start is not None and end is not None else None),
            location=self._location(query),
            max_price=self._price(query),
            people=self._people(query),
            special_requirements=[value for key, value in SPECIAL_REQUIREMENTS.items() if key in query],
            requested_field_id=requested,
            allow_alternatives=any(term in query for term in ('khong co thi', 'gio khac', 'san khac', 'gan nhat')),
            prefer_cheap=any(term in query for term in ('re mot chut', 'gia re', 're nhat', 'tiet kiem')),
            near_me=any(term in query for term in ('gan day', 'gan toi', 'quanh day')),
            invalid_date=invalid_date,
            invalid_time=start is not None and end is not None and end <= start,
        )

    @staticmethod
    def _merge_context(criteria: SearchCriteria, context: dict[str, Any]):
        values = {
            'sport_type': context.get('sport_type'),
            'location': context.get('location'),
            'max_price': context.get('max_price'),
            'people': context.get('people'),
            'requested_field_id': context.get('field_id'),
        }
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

    def _matches(self, pair, criteria: SearchCriteria) -> bool:
        court, slot = pair
        amenities = plain(' '.join(court.amenities or []))
        return (
            (not criteria.requested_field_id or court.id == criteria.requested_field_id)
            and (not criteria.requested_time_slot_id or slot.id == criteria.requested_time_slot_id)
            and (not criteria.location or plain(criteria.location) in plain(court.location))
            and (criteria.max_price is None or float(slot.price) <= criteria.max_price)
            and (criteria.start_minute is None or self._minutes(slot.start_time) == criteria.start_minute)
            and (criteria.end_minute is None or self._minutes(slot.end_time) >= criteria.end_minute)
            and (criteria.people is None or court.capacity >= criteria.people)
            and all(plain(item) in amenities for item in criteria.special_requirements)
        )

    def _rank(self, pair, criteria: SearchCriteria, *, exact: bool) -> tuple:
        court, slot = pair
        location_match = not criteria.location or plain(criteria.location) in plain(court.location)
        same_court = bool(criteria.requested_field_id and court.id == criteria.requested_field_id)
        time_gap = abs(self._minutes(slot.start_time) - criteria.start_minute) if criteria.start_minute is not None else 0
        budget_gap = max(0.0, float(slot.price) - criteria.max_price) if criteria.max_price is not None else 0.0
        amenity_hits = sum(plain(item) in plain(' '.join(court.amenities or [])) for item in criteria.special_requirements)
        if exact:
            fallback_priority = 0
        elif criteria.requested_field_id and same_court:
            fallback_priority = 1
        elif location_match and criteria.start_minute is not None and time_gap == 0:
            fallback_priority = 2
        elif location_match:
            fallback_priority = 3
        elif criteria.start_minute is not None and time_gap <= 120:
            fallback_priority = 4
        else:
            fallback_priority = 5
        distance = court.distance_km if court.distance_km is not None else 999.0
        cheap = float(slot.price) if criteria.prefer_cheap else budget_gap
        return (fallback_priority, time_gap, 0 if location_match else 1, cheap, distance, -float(court.rating), -amenity_hits)

    def _suggestion(self, pair, criteria: SearchCriteria, strategy: str) -> dict[str, Any]:
        court, slot = pair
        exact = strategy == 'exact'
        time_gap = abs(self._minutes(slot.start_time) - criteria.start_minute) if criteria.start_minute is not None else 0
        location_match = not criteria.location or plain(criteria.location) in plain(court.location)
        if exact:
            alternative_type = None
            reason = 'Khớp yêu cầu và còn trống theo dữ liệu booking hiện tại.'
        elif criteria.requested_field_id and court.id == criteria.requested_field_id:
            alternative_type, reason = 'nearest_time', 'Cùng sân, khung giờ còn trống gần nhất.'
        elif location_match and time_gap == 0:
            alternative_type, reason = 'other_court', 'Sân khác trong cùng khu vực, đúng khung giờ.'
        elif location_match:
            alternative_type, reason = 'expanded_time', 'Cùng khu vực, khung giờ còn trống gần nhất.'
        elif criteria.max_price is not None and float(slot.price) > criteria.max_price:
            alternative_type, reason = 'nearest_budget', 'Phương án còn trống có giá gần ngân sách nhất.'
        else:
            alternative_type, reason = 'other_area', 'Cơ sở khác có sân phù hợp còn trống.'
        return {
            'field_id': court.id,
            # Current schema stores a court and its venue-facing information in Field.
            'facility_name': court.facility.name if court.facility else court.name,
            'court_name': court.name,
            'field_name': court.name,
            'sport_type': court.sport_type,
            'location': court.location,
            'image_url': court.image_url,
            'time_slot_id': slot.id,
            'slot_name': slot.name,
            'start_time': slot.start_time.strftime('%H:%M'),
            'end_time': slot.end_time.strftime('%H:%M'),
            'price': float(slot.price),
            'rating': float(court.rating),
            'distance_km': court.distance_km,
            'booking_date': criteria.booking_date,
            'reason': reason,
            'availability_status': 'available',
            'is_nearest_alternative': not exact,
            'alternative_type': alternative_type,
        }

    def _reply(self, criteria: SearchCriteria, suggestions: list[dict[str, Any]], *, exact: bool) -> str:
        if not suggestions:
            return 'Không tìm thấy lịch trống phù hợp từ dữ liệu hiện tại.'
        first = suggestions[0]
        date_label = criteria.booking_date.strftime('%d/%m/%Y') if criteria.booking_date else ''
        price = f"{first['price']:,.0f}".replace(',', '.')
        if exact:
            return (
                f"Có {len(suggestions)} lựa chọn phù hợp ngày {date_label}. Tốt nhất là {first['court_name']} – "
                f"{price}đ, còn trống {first['start_time']}–{first['end_time']}, rating {first['rating']:.1f}/5."
            )
        requested = self._format_minutes(criteria.start_minute)
        prefix = f'Hiện không còn sân khớp hoàn toàn{f" lúc {requested}" if requested else ""}. '
        times = ', '.join(item['start_time'] for item in suggestions[:3])
        return prefix + f'Mình tìm thấy {len(suggestions)} phương án gần nhất còn trống lúc {times}.'

    def _response(
        self, reply: str, criteria: SearchCriteria, suggestions: list[dict[str, Any]], *,
        intent='search_booking', needs_clarification=False,
        classification=ScopeClassification.IN_SCOPE,
    ):
        route = self._active_route
        entities = route.to_dict()['entities'] if route else {
            'sport_type': None, 'venue_name': None, 'location': None, 'date': None,
            'start_time': None, 'end_time': None, 'price_max': None,
            'number_of_players': None, 'booking_code': None,
        }
        criteria_entities = {
            'sport_type': criteria.sport_type,
            'location': criteria.location,
            'date': criteria.booking_date.isoformat() if criteria.booking_date else None,
            'start_time': self._format_minutes(criteria.start_minute),
            'end_time': self._format_minutes(criteria.end_minute),
            'price_max': criteria.max_price,
            'number_of_players': criteria.people,
        }
        entities.update({key: value for key, value in criteria_entities.items() if value is not None})
        understood = self._understood(criteria)
        for key in (
            'sport_type', 'booking_date', 'start_time', 'end_time', 'location', 'field_id',
            'time_slot_id', 'max_price', 'people', 'result_field_ids', 'result_time_slot_ids',
        ):
            if understood.get(key) is None and self._conversation_context.get(key) is not None:
                understood[key] = self._conversation_context[key]
        understood['last_intent'] = route.intent.value if route else intent
        return {
            'reply': reply,
            'understood': understood,
            'suggestions': suggestions,
            'intent': route.intent.value if route else intent,
            'confidence': route.confidence if route else 1.0,
            'entities': entities,
            'needs_clarification': needs_clarification,
            'source': 'live_backend',
            'classification': classification.value,
        }

    def _understood(self, criteria: SearchCriteria):
        return {
            'sport_type': criteria.sport_type,
            'booking_date': criteria.booking_date.isoformat() if criteria.booking_date else None,
            'start_time': self._format_minutes(criteria.start_minute),
            'end_time': self._format_minutes(criteria.end_minute),
            'duration_minutes': criteria.duration_minutes,
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
    def _duration(query: str):
        match = re.search(r'\b(?:choi|trong)\s*(\d+(?:[.,]\d+)?)\s*(?:tieng|gio)\b', query)
        if not match:
            return None
        return round(float(match[1].replace(',', '.')) * 60)

    @staticmethod
    def _location(query: str):
        match = re.search(r'(quan\s+\d+|binh thanh|go vap|tan binh|cau giay|tay ho|thu duc|tp\.?hcm|ho chi minh|ha noi|da nang)', query)
        return match[1] if match else None

    @staticmethod
    def _people(query: str):
        match = re.search(r'\b(\d{1,3})\s*(?:nguoi|thanh vien)\b', query)
        return int(match[1]) if match else None

    @staticmethod
    def _minutes(value: time):
        return value.hour * 60 + value.minute

    @staticmethod
    def _format_minutes(value):
        return None if value is None else f'{value // 60:02d}:{value % 60:02d}'
