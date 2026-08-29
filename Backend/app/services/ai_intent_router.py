import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any

from .location_utils import extract_location


class AssistantIntent(str, Enum):
    SEARCH_VENUE = 'SEARCH_VENUE'
    RECOMMEND_VENUE = 'RECOMMEND_VENUE'
    CHECK_AVAILABILITY = 'CHECK_AVAILABILITY'
    RECOMMEND_SLOT = 'RECOMMEND_SLOT'
    OCCUPANCY_INSIGHT = 'OCCUPANCY_INSIGHT'
    PARTNER_APPLICATION_SUPPORT = 'PARTNER_APPLICATION_SUPPORT'
    GET_VENUE_DETAIL = 'GET_VENUE_DETAIL'
    GET_PRODUCTS = 'GET_PRODUCTS'
    CREATE_BOOKING = 'CREATE_BOOKING'
    GET_BOOKING = 'GET_BOOKING'
    CANCEL_BOOKING = 'CANCEL_BOOKING'
    RESCHEDULE_BOOKING = 'RESCHEDULE_BOOKING'
    PAYMENT_SUPPORT = 'PAYMENT_SUPPORT'
    ACCOUNT_SUPPORT = 'ACCOUNT_SUPPORT'
    SYSTEM_GUIDE = 'SYSTEM_GUIDE'
    GREETING = 'GREETING'
    FOLLOW_UP = 'FOLLOW_UP'
    UNCLEAR = 'UNCLEAR'
    OUT_OF_SCOPE = 'OUT_OF_SCOPE'


SPORT_ALIASES = {
    'bong da': 'bóng đá', 'da bong': 'bóng đá', 'san bong': 'bóng đá', 'football': 'bóng đá',
    'cau long': 'cầu lông', 'badminton': 'cầu lông', 'danh cau long': 'cầu lông', 'choi cau long': 'cầu lông',
    'pickleball': 'pickleball', 'pickle ball': 'pickleball', 'danh pickleball': 'pickleball', 'choi pickleball': 'pickleball',
    'tennis': 'tennis', 'danh tennis': 'tennis', 'choi tennis': 'tennis',
    'bong ro': 'bóng rổ', 'bong chuyen': 'bóng chuyền',
}
WEEKDAYS = {
    'thu hai': 0, 'thu ba': 1, 'thu tu': 2, 'thu nam': 3,
    'thu sau': 4, 'thu bay': 5, 'chu nhat': 6,
}
ENTITY_KEYS = (
    'sport_type', 'court_type', 'venue_name', 'location', 'date', 'start_time', 'end_time',
    'preferred_time', 'max_price', 'booking_code',
)

OUT_OF_SCOPE_TERMS = (
    'python', 'lap trinh', 'code', 'toan hoc', 'giai bai', 'lich su viet', 'chinh tri',
    'suc khoe', 'benh', 'thuoc', 'tai chinh', 'chung khoan', 'phap luat', 'luat su',
    'viet bai', 'bai tho', 'dich thuat', 'dich sang', 'thoi tiet', 'tin tuc',
    'thit cho', 'mon an', 'nau an', 'phim', 'am nhac', 'du lich',
)
DOMAIN_TERMS = (
    'san', 'the thao', 'sporthub', 'co so', 'dia diem', 'tien ich', 'khung gio',
    'lich trong', 'booking', 'ma dat', 'dat lich', 'dat coc', 'thanh toan', 'hoan tien',
    'hoa don', 'bien lai', 'huy', 'doi lich', 'doi gio', 'tai khoan', 'ho so',
    'owner', 'chu san', 'doi tac', 'quan ly', 'gia', 'choi', 'cong suat', 'thap diem', 'cao diem', 'it khach', 'uu dai',
    'san pham', 'dich vu', 'cho thue', 'con hang', 'so luong con', 'ton kho', 'tim', 'giup', 'tro ly',
)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize('NFD', value.casefold())
    return ''.join(char for char in normalized if unicodedata.category(char) != 'Mn').replace('đ', 'd')


@dataclass
class IntentEntities:
    sport_type: str | None = None
    court_type: str | None = None
    venue_name: str | None = None
    location: str | None = None
    date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    preferred_time: str | None = None
    max_price: float | None = None
    number_of_players: int | None = None
    booking_code: str | None = None

    @property
    def price_max(self) -> float | None:
        """Backward-compatible alias; new clients should use max_price."""
        return self.max_price


@dataclass
class IntentRoute:
    intent: AssistantIntent
    confidence: float
    entities: IntentEntities = field(default_factory=IntentEntities)
    needs_clarification: bool = False
    is_follow_up: bool = False
    context_reset: bool = False

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result['intent'] = self.intent.value
        result['entities']['price_max'] = result['entities']['max_price']
        return result


class IntentRouter:
    """Pure routing layer: it never reads SportHub repositories or mutates data."""

    def route(self, message: str, context: dict[str, Any] | None = None, *, today: date | None = None) -> IntentRoute:
        query = normalize_text(' '.join(message.strip().split()))
        context = context or {}
        current_date = today or date.today()
        fresh_entities = self._entities(query, {}, current_date)
        has_context = any(context.get(key) is not None for key in (
            'sport_type', 'location', 'booking_date', 'date', 'field_id', 'result_field_ids', 'booking_code',
            'partner_application_status', 'partner_application_id', 'last_intent',
        ))
        context_reset = has_context and self._starts_new_request(query, fresh_entities, context)
        effective_context = {} if context_reset else context
        entities = self._entities(query, effective_context, current_date)
        follow_up = has_context and (
            self._is_follow_up(query) or self._has_continuation_detail(query)
            or fresh_entities.sport_type is not None or fresh_entities.court_type is not None
        )

        if any(term in query for term in OUT_OF_SCOPE_TERMS):
            return IntentRoute(AssistantIntent.OUT_OF_SCOPE, 0.99, fresh_entities, context_reset=True)
        if self._is_greeting(query):
            return IntentRoute(AssistantIntent.GREETING, 0.99, entities)

        intent, confidence = self._match_intent(query, follow_up, effective_context, fresh_entities)
        if intent is None:
            if follow_up:
                intent, confidence = AssistantIntent.FOLLOW_UP, 0.82
            elif self._looks_ambiguous(query):
                intent, confidence = AssistantIntent.UNCLEAR, 0.35
            elif not any(term in query for term in DOMAIN_TERMS) and not entities.sport_type and not entities.location:
                intent, confidence = AssistantIntent.OUT_OF_SCOPE, 0.86
            else:
                intent, confidence = AssistantIntent.UNCLEAR, 0.4

        if confidence < 0.55:
            intent = AssistantIntent.UNCLEAR
        if intent == AssistantIntent.PARTNER_APPLICATION_SUPPORT and context.get('last_intent') != intent.value:
            context_reset = context_reset or bool(context)
        needs_clarification = self._needs_clarification(intent, entities, has_context)
        return IntentRoute(intent, confidence, entities, needs_clarification, follow_up, context_reset)

    @staticmethod
    def _match_intent(
        query: str,
        follow_up: bool,
        context: dict[str, Any],
        fresh_entities: IntentEntities,
    ) -> tuple[AssistantIntent | None, float]:
        partner_context = context.get('last_intent') == AssistantIntent.PARTNER_APPLICATION_SUPPORT.value
        if any(term in query for term in (
            'tro thanh chu san', 'dang ky lam doi tac', 'dang ky doi tac', 'dang ky owner',
            'ho so doi tac', 'ho so chu san', 'ho so owner', 'gui lai ho so',
            'ho so cua toi dang o trang thai nao', 'ho so cua toi den dau',
            'tai sao ho so bi tu choi', 'cap nhat va gui lai ho so',
            'can chuan bi thong tin gi', 'can chuan bi giay to gi', 'duyet ho so cua toi',
        )) or (partner_context and any(term in query for term in (
            'ho so cua toi', 'trang thai nao', 'den dau roi', 'tai sao bi tu choi',
            'gui lai', 'can chuan bi', 'buoc tiep theo',
        ))):
            return AssistantIntent.PARTNER_APPLICATION_SUPPORT, 0.98
        if any(term in query for term in (
            'cong suat', 'thap diem', 'cao diem', 'it khach', 'gio vang',
            'chay uu dai', 'khuyen mai luc nao', 'san nao vang',
        )):
            return AssistantIntent.OCCUPANCY_INSIGHT, 0.97
        if any(term in query for term in (
            'san pham', 'dich vu them', 'dich vu nao', 'cho thue gi',
            'con hang', 'so luong con', 'ton kho', 'thue vot', 'vot cho thue', 'mua nuoc',
        )):
            return AssistantIntent.GET_PRODUCTS, 0.97
        if any(term in query for term in ('hoan tien', 'thanh toan', 'dat coc', 'tien coc', 'hoa don', 'bien lai', 'giao dich', 'hoan coc', 'doanh thu')):
            return AssistantIntent.PAYMENT_SUPPORT, 0.96
        has_booking_context = bool(
            fresh_entities.booking_code or context.get('booking_code')
            or context.get('last_intent') in {'GET_BOOKING', 'CANCEL_BOOKING', 'RESCHEDULE_BOOKING'}
            or any(term in query for term in ('booking', 'lich dat', 'ma dat'))
        )
        if has_booking_context and any(term in query for term in ('doi lich', 'doi gio', 'doi ngay', 'doi san', 'dời lịch', 'reschedule')):
            return AssistantIntent.RESCHEDULE_BOOKING, 0.97
        if re.search(r'\b(huy|huỷ)\b', query) and any(term in query for term in ('san', 'booking', 'lich dat', 'ma dat')):
            return AssistantIntent.CANCEL_BOOKING, 0.96
        if any(term in query for term in ('trang thai booking', 'booking cua toi', 'lich su dat', 'lich dat cua toi', 'xem booking', 'ma dat', 'bao nhieu booking', 'booking hom nay')) or (
            'booking' in query and ('the nao' in query or 'trang thai' in query)
        ):
            return AssistantIntent.GET_BOOKING, 0.95
        if any(term in query for term in ('tai khoan', 'ho so', 'thong tin cua toi', 'doi mat khau', 'dang nhap', 'bao nhieu owner', 'bao nhieu customer', 'owner dang hoat dong')):
            return AssistantIntent.ACCOUNT_SUPPORT, 0.94
        if any(term in query for term in (
            'huong dan', 'cach su dung', 'cach dat san', 'sporthub lam duoc gi',
            'tro ly nay lam duoc gi', 'lam duoc gi', 'chuc nang', 'tro ly lam gi'
        )):
            return AssistantIntent.SYSTEM_GUIDE, 0.93
        if any(term in query for term in ('bao nhieu co so', 'co bao nhieu co so', 'so luong co so')):
            return AssistantIntent.SEARCH_VENUE, 0.96

        if follow_up and not any(term in query for term in ('gia bao nhieu', 'dia chi', 'tien ich', 'chi tiet')) and (
            re.search(r'\b(san|lua chon|ket qua)\s*(?:thu\s*|so\s*)?(\d+|mot|hai|ba|tu|nam|dau|dau tien|cuoi|cuoi cung)\b', query)
            or any(term in query for term in ('san khac', 'ngay khac', 'gio khac', 'khung khac'))
        ):
            return AssistantIntent.FOLLOW_UP, 0.9

        if any(term in query for term in ('muon dat san', 'dat giup', 'dat san nay', 'xac nhan dat', 'tao booking')):
            return AssistantIntent.CREATE_BOOKING, 0.95

        # Explicit search venue verbs prioritize SEARCH_VENUE
        if any(term in query for term in ('tim san', 'tim co so', 'kiem san', 'cho toi san', 'muon tim san')) or query.startswith('tim '):
            if any(term in query for term in ('con trong', 'lich trong', 'con san', 'con gio', 'co trong khong')):
                return AssistantIntent.CHECK_AVAILABILITY, 0.95
            return AssistantIntent.SEARCH_VENUE, 0.94

        if 're hon' not in query and (any(term in query for term in ('con trong', 'lich trong', 'con san', 'con gio', 'khung gio nao', 'con 19h', 'co trong khong', 'ngay nao trong', 'ngay trong')) or (
            follow_up and re.search(r'\bcon\s+\d{1,2}(?::\d{2})?\s*(?:h|gio)?\b', query)
        )):
            return AssistantIntent.CHECK_AVAILABILITY, 0.95

        if any(term in query for term in ('goi y khung gio', 'goi y gio', 'gio phu hop', 'gio nao phu hop', 'gio gan do', 're hon')) or (
            follow_up and (fresh_entities.start_time is not None or fresh_entities.preferred_time is not None)
        ):
            return AssistantIntent.RECOMMEND_SLOT, 0.94
        if any(term in query for term in ('goi y', 'de xuat', 'phu hop', 'nen chon', 'tot nhat')):
            return AssistantIntent.RECOMMEND_VENUE, 0.93
        if any(term in query for term in (
            'dia chi', 'tien ich', 'thong tin san', 'chi tiet san', 'gia bao nhieu', 'gia san',
            'bao tri', 'dong cua', 'gio mo cua', 'mo cua luc nao', 'bai do xe', 'dieu hoa',
        )):
            return AssistantIntent.GET_VENUE_DETAIL, 0.92

        # General Search / Availability matching
        has_search_entities = bool(fresh_entities.sport_type or fresh_entities.location or fresh_entities.court_type)
        has_date_or_time = bool(fresh_entities.date or fresh_entities.start_time or fresh_entities.preferred_time)
        has_search_terms = any(term in query for term in (
            'co san', 'san nao', 'tim san', 'tim co so', 'kiem san', 'cho toi san',
            'toi muon san', 'muon san', 'muon tim', 'giup toi tim', 'co tim san', 'tim giup', 'giup tim', 'cho toi'
        )) or query.startswith('co ') or query.startswith('tim ') or query.startswith('san ')

        if has_search_entities or has_search_terms:
            if has_date_or_time or any(term in query for term in ('hom nay', 'ngay mai', 'toi nay', 'toi mai', 'ngay kia')):
                return AssistantIntent.CHECK_AVAILABILITY, 0.93
            return AssistantIntent.SEARCH_VENUE, 0.92

        return None, 0.0

    @staticmethod
    def _is_greeting(query: str) -> bool:
        cleaned = re.sub(r'[^a-z0-9 ]', '', query).strip()
        return cleaned in {'chao', 'xin chao', 'hello', 'hi', 'hey', 'chao ban', 'xin chao sporthub'}

    @staticmethod
    def _has_continuation_detail(query: str) -> bool:
        return bool(
            re.search(r'\b(?:hom nay|ngay mai|toi mai|mai|ngay kia|ngay mot|cuoi tuan|thu hai|thu ba|thu tu|thu nam|thu sau|thu bay|chu nhat)\b', query)
            or re.search(r'\b(?:[01]?\d|2[0-3])(?::[0-5]\d)?\s*(?:h|gio)\b', query)
            or re.search(r'\b(?:duoi|toi da|khong qua)\s*[\d.,]+', query)
            or re.search(r'\b(?:buoi sang|buoi chieu|buoi toi|sang som|gio toi)\b', query)
        )

    @staticmethod
    def _is_follow_up(query: str) -> bool:
        return bool(re.search(r'\b(san|lua chon|ket qua)\s*(?:thu\s*|so\s*)?(\d+|mot|hai|ba|tu|nam|dau|dau tien|cuoi|cuoi cung)\b', query)) or any(
            term in query for term in (
                'san nay', 'cai nay', 'phuong an nay', 'san do', 'gia bao nhieu', 'bao nhieu co so',
                'con gio nao', 'con 19h', 'the con', 're hon', 'doi sang',
                'thi sao', 'vay con', 'con khong', 'san khac', 'ngay khac', 'gio khac', 'khung khac', 'khac'
            )
        )

    @staticmethod
    def _looks_ambiguous(query: str) -> bool:
        return len(query.split()) <= 4 and any(term in query for term in ('bao nhieu', 'the nao', 'con khong', 'cai nao', 'gi vay'))

    @staticmethod
    def _needs_clarification(intent: AssistantIntent, entities: IntentEntities, has_context: bool) -> bool:
        if intent == AssistantIntent.UNCLEAR:
            return True
        if intent in (AssistantIntent.SEARCH_VENUE, AssistantIntent.RECOMMEND_VENUE):
            return entities.sport_type is None and entities.location is None
        if intent == AssistantIntent.RECOMMEND_SLOT:
            return entities.sport_type is None or entities.date is None
        if intent == AssistantIntent.CHECK_AVAILABILITY:
            return (entities.venue_name is None and not has_context and entities.sport_type is None) or entities.date is None
        if intent == AssistantIntent.GET_VENUE_DETAIL:
            return entities.venue_name is None and not has_context
        if intent in (AssistantIntent.CANCEL_BOOKING, AssistantIntent.RESCHEDULE_BOOKING):
            return entities.booking_code is None
        return False

    def _entities(self, query: str, context: dict[str, Any], today: date) -> IntentEntities:
        start_time, end_time = self._times(query)
        result = IntentEntities(
            sport_type=next((value for key, value in SPORT_ALIASES.items() if key in query), None),
            court_type=self._court_type(query),
            venue_name=self._venue_name(query),
            location=extract_location(query),
            date=self._date(query, today),
            start_time=start_time,
            end_time=end_time,
            preferred_time=self._preferred_time(query),
            max_price=self._price(query),
            number_of_players=self._players(query),
            booking_code=self._booking_code(query),
        )
        aliases = {
            'sport_type': ('sport_type',), 'court_type': ('court_type',), 'venue_name': ('venue_name', 'field_name'),
            'location': ('location',), 'date': ('date', 'booking_date'),
            'start_time': ('start_time',), 'end_time': ('end_time',),
            'preferred_time': ('preferred_time',), 'max_price': ('max_price', 'price_max'),
            'number_of_players': ('number_of_players', 'people'),
            'booking_code': ('booking_code',),
        }
        for target, keys in aliases.items():
            if getattr(result, target) is None:
                value = next((context.get(key) for key in keys if context.get(key) is not None), None)
                if value is not None:
                    setattr(result, target, value)
        return result

    @staticmethod
    def _starts_new_request(query: str, entities: IntentEntities, context: dict[str, Any]) -> bool:
        explicitly_searching = any(term in query for term in (
            'tim san', 'tim co so', 'kiem san', 'goi y san', 'toi muon san', 'muon tim san',
        ))
        previous_sport = context.get('sport_type')
        changed_sport = bool(entities.sport_type and previous_sport and entities.sport_type != previous_sport)
        previous_location = context.get('location')
        changed_location = bool(entities.location and previous_location and entities.location != previous_location)
        return explicitly_searching or changed_sport or changed_location

    @staticmethod
    def _court_type(query: str) -> str | None:
        people = re.search(r'\b(?:san\s+)?(?:bong\s+)?(\d{1,2})\s*nguoi\b', query)
        if people:
            return f'{int(people[1])} người'
        if 'san don' in query:
            return 'sân đơn'
        if 'san doi' in query:
            return 'sân đôi'
        if 'trong nha' in query:
            return 'trong nhà'
        if 'ngoai troi' in query:
            return 'ngoài trời'
        return None

    @staticmethod
    def _preferred_time(query: str) -> str | None:
        if any(term in query for term in ('buoi sang', 'sang som')):
            return 'morning'
        if 'buoi chieu' in query:
            return 'afternoon'
        if any(term in query for term in ('buoi toi', 'gio toi', 'toi nay', 'toi mai')) or re.search(r'\btoi\s+(?:thu|ngay)', query):
            return 'evening'
        return None

    @staticmethod
    def _booking_code(query: str) -> str | None:
        match = re.search(r'\bSH[- ]?[A-Z0-9-]{3,}\b', query.upper())
        return match[0].replace(' ', '-') if match else None

    @staticmethod
    def _venue_name(query: str) -> str | None:
        quoted = re.search(r'["“]([^"”]{2,80})["”]', query)
        return quoted[1].strip() if quoted else None

    @staticmethod
    def _players(query: str) -> int | None:
        match = re.search(r'\b(\d{1,3})\s*(?:nguoi|thanh vien)\b', query)
        return int(match[1]) if match else None

    @staticmethod
    def _price(query: str) -> float | None:
        match = re.search(r'(?:duoi|toi da|khong qua|<=?)\s*([\d.,]+)\s*(trieu|k|nghin|d|dong)?', query)
        if not match:
            return None
        raw, unit = match[1], match[2]
        value = float(raw.replace('.', '').replace(',', '.'))
        return value * (1_000_000 if unit == 'trieu' else 1_000 if unit in ('k', 'nghin') else 1)

    @staticmethod
    def _times(query: str) -> tuple[str | None, str | None]:
        range_match = re.search(r'\b([01]?\d|2[0-3])(?::([0-5]\d))?\s*(?:-|–|den|toi)\s*([01]?\d|2[0-3])(?::([0-5]\d))?\s*(?:h|gio)?\b', query)
        if range_match:
            return f'{int(range_match[1]):02d}:{int(range_match[2] or 0):02d}', f'{int(range_match[3]):02d}:{int(range_match[4] or 0):02d}'
        match = re.search(r'\b([01]?\d|2[0-3])(?::([0-5]\d))?\s*(?:h|gio)\b', query)
        if not match:
            return None, None
        hour = int(match[1])
        if any(term in query for term in ('toi nay', 'toi mai', 'buoi toi', 'gio toi')) and hour < 12:
            hour += 12
        return f'{hour:02d}:{int(match[2] or 0):02d}', None

    @staticmethod
    def _date(query: str, today: date) -> str | None:
        if 'hom nay' in query or 'toi nay' in query:
            return today.isoformat()
        if 'ngay mai' in query or 'toi mai' in query or re.search(r'\bmai\b', query):
            return (today + timedelta(days=1)).isoformat()
        if 'ngay kia' in query or 'ngay mot' in query:
            return (today + timedelta(days=2)).isoformat()
        if 'cuoi tuan nay' in query or 'cuoi tuan' in query:
            days = (5 - today.weekday()) % 7
            return (today + timedelta(days=days)).isoformat()
        iso = re.search(r'\b(20\d{2})-(\d{1,2})-(\d{1,2})\b', query)
        short = re.search(r'\b(\d{1,2})[/-](\d{1,2})(?:[/-](20\d{2}))?\b', query)
        try:
            if iso:
                return date(int(iso[1]), int(iso[2]), int(iso[3])).isoformat()
            if short:
                return date(int(short[3] or today.year), int(short[2]), int(short[1])).isoformat()
        except ValueError:
            return None
        for label, weekday in WEEKDAYS.items():
            if label in query:
                return (today + timedelta(days=(weekday - today.weekday()) % 7)).isoformat()
        return None
