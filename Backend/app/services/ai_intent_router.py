import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any


class AssistantIntent(str, Enum):
    SEARCH_VENUE = 'SEARCH_VENUE'
    RECOMMEND_VENUE = 'RECOMMEND_VENUE'
    CHECK_AVAILABILITY = 'CHECK_AVAILABILITY'
    GET_VENUE_DETAIL = 'GET_VENUE_DETAIL'
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
    'cau long': 'cầu lông', 'badminton': 'cầu lông', 'pickleball': 'pickleball',
    'tennis': 'tennis', 'bong ro': 'bóng rổ', 'bong chuyen': 'bóng chuyền',
}
WEEKDAYS = {
    'thu hai': 0, 'thu ba': 1, 'thu tu': 2, 'thu nam': 3,
    'thu sau': 4, 'thu bay': 5, 'chu nhat': 6,
}
ENTITY_KEYS = (
    'sport_type', 'venue_name', 'location', 'date', 'start_time', 'end_time',
    'price_max', 'number_of_players', 'booking_code',
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
    'owner', 'quan ly', 'gia', 'choi',
)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize('NFD', value.casefold())
    return ''.join(char for char in normalized if unicodedata.category(char) != 'Mn').replace('đ', 'd')


@dataclass
class IntentEntities:
    sport_type: str | None = None
    venue_name: str | None = None
    location: str | None = None
    date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    price_max: float | None = None
    number_of_players: int | None = None
    booking_code: str | None = None


@dataclass
class IntentRoute:
    intent: AssistantIntent
    confidence: float
    entities: IntentEntities = field(default_factory=IntentEntities)
    needs_clarification: bool = False
    is_follow_up: bool = False

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result['intent'] = self.intent.value
        return result


class IntentRouter:
    """Pure routing layer: it never reads SportHub repositories or mutates data."""

    def route(self, message: str, context: dict[str, Any] | None = None, *, today: date | None = None) -> IntentRoute:
        query = normalize_text(' '.join(message.strip().split()))
        context = context or {}
        entities = self._entities(query, context, today or date.today())
        has_context = any(context.get(key) is not None for key in (
            'sport_type', 'booking_date', 'date', 'field_id', 'result_field_ids', 'booking_code', 'last_intent',
        ))
        follow_up = has_context and (self._is_follow_up(query) or self._has_continuation_detail(query))

        if any(term in query for term in OUT_OF_SCOPE_TERMS):
            return IntentRoute(AssistantIntent.OUT_OF_SCOPE, 0.99, entities)
        if self._is_greeting(query):
            return IntentRoute(AssistantIntent.GREETING, 0.99, entities)

        intent, confidence = self._match_intent(query, follow_up)
        if intent is None:
            if follow_up:
                intent, confidence = AssistantIntent.FOLLOW_UP, 0.82
            elif self._looks_ambiguous(query):
                intent, confidence = AssistantIntent.UNCLEAR, 0.35
            elif not any(term in query for term in DOMAIN_TERMS) and not entities.sport_type:
                intent, confidence = AssistantIntent.OUT_OF_SCOPE, 0.86
            else:
                intent, confidence = AssistantIntent.UNCLEAR, 0.4

        if confidence < 0.55:
            intent = AssistantIntent.UNCLEAR
        needs_clarification = self._needs_clarification(intent, entities, has_context)
        return IntentRoute(intent, confidence, entities, needs_clarification, follow_up)

    @staticmethod
    def _match_intent(query: str, follow_up: bool) -> tuple[AssistantIntent | None, float]:
        if any(term in query for term in ('hoan tien', 'thanh toan', 'dat coc', 'tien coc', 'hoa don', 'bien lai', 'giao dich', 'hoan coc', 'doanh thu')):
            return AssistantIntent.PAYMENT_SUPPORT, 0.96
        if any(term in query for term in ('doi lich', 'doi gio', 'doi ngay', 'doi san', 'dời lịch', 'reschedule')):
            return AssistantIntent.RESCHEDULE_BOOKING, 0.97
        if re.search(r'\b(huy|huỷ)\b', query) and any(term in query for term in ('san', 'booking', 'lich dat', 'ma dat')):
            return AssistantIntent.CANCEL_BOOKING, 0.96
        if any(term in query for term in ('trang thai booking', 'booking cua toi', 'lich su dat', 'lich dat cua toi', 'xem booking', 'ma dat', 'bao nhieu booking', 'booking hom nay')) or (
            'booking' in query and ('the nao' in query or 'trang thai' in query)
        ):
            return AssistantIntent.GET_BOOKING, 0.95
        if any(term in query for term in ('tai khoan', 'ho so', 'thong tin cua toi', 'doi mat khau', 'dang nhap', 'bao nhieu owner', 'bao nhieu customer', 'owner dang hoat dong')):
            return AssistantIntent.ACCOUNT_SUPPORT, 0.94
        if any(term in query for term in ('huong dan', 'cach su dung', 'cach dat san', 'sporthub lam duoc gi', 'chuc nang')):
            return AssistantIntent.SYSTEM_GUIDE, 0.93
        if any(term in query for term in ('muon dat san', 'dat giup', 'dat san nay', 'xac nhan dat', 'tao booking')):
            return AssistantIntent.CREATE_BOOKING, 0.95
        if any(term in query for term in ('con trong', 'lich trong', 'con san', 'con gio', 'khung gio nao', 'con 19h', 'co trong khong')) or (
            follow_up and re.search(r'\bcon\s+\d{1,2}(?::\d{2})?\s*(?:h|gio)?\b', query)
        ):
            return AssistantIntent.CHECK_AVAILABILITY, 0.95
        if any(term in query for term in ('goi y', 'de xuat', 'phu hop', 'nen chon', 'tot nhat')):
            return AssistantIntent.RECOMMEND_VENUE, 0.93
        if any(term in query for term in ('dia chi', 'tien ich', 'thong tin san', 'chi tiet san', 'gia bao nhieu', 'gia san')):
            return AssistantIntent.GET_VENUE_DETAIL, 0.92
        if any(term in query for term in ('tim san', 'tim co so', 'kiem san', 'cho toi san')):
            return AssistantIntent.SEARCH_VENUE, 0.94
        if follow_up and re.search(r'\b(san|lua chon|ket qua)\s*(?:thu\s*)?(\d+|mot|hai|ba|tu|nam)\b', query):
            return AssistantIntent.FOLLOW_UP, 0.9
        return None, 0.0

    @staticmethod
    def _is_greeting(query: str) -> bool:
        cleaned = re.sub(r'[^a-z0-9 ]', '', query).strip()
        return cleaned in {'chao', 'xin chao', 'hello', 'hi', 'hey', 'chao ban', 'xin chao sporthub'}

    @staticmethod
    def _is_follow_up(query: str) -> bool:
        return bool(re.search(r'\b(san|lua chon|ket qua)\s*(?:thu\s*)?(\d+|mot|hai|ba|tu|nam)\b', query)) or any(
            term in query for term in ('san nay', 'cai nay', 'phuong an nay', 'gia bao nhieu', 'con gio nao', 'con 19h', 'the con')
        )

    @staticmethod
    def _has_continuation_detail(query: str) -> bool:
        return bool(
            re.search(r'\b(?:hom nay|ngay mai|toi mai|mai|thu hai|thu ba|thu tu|thu nam|thu sau|thu bay|chu nhat)\b', query)
            or re.search(r'\b(?:[01]?\d|2[0-3])(?::[0-5]\d)?\s*(?:h|gio)\b', query)
            or re.search(r'\b(?:duoi|toi da|khong qua)\s*[\d.,]+', query)
        )

    @staticmethod
    def _looks_ambiguous(query: str) -> bool:
        return len(query.split()) <= 4 and any(term in query for term in ('bao nhieu', 'the nao', 'con khong', 'cai nao', 'gi vay'))

    @staticmethod
    def _needs_clarification(intent: AssistantIntent, entities: IntentEntities, has_context: bool) -> bool:
        if intent == AssistantIntent.UNCLEAR:
            return True
        if intent in (AssistantIntent.SEARCH_VENUE, AssistantIntent.RECOMMEND_VENUE):
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
            venue_name=self._venue_name(query),
            location=self._location(query),
            date=self._date(query, today),
            start_time=start_time,
            end_time=end_time,
            price_max=self._price(query),
            number_of_players=self._players(query),
            booking_code=self._booking_code(query),
        )
        aliases = {
            'sport_type': ('sport_type',), 'venue_name': ('venue_name', 'field_name'),
            'location': ('location',), 'date': ('date', 'booking_date'),
            'start_time': ('start_time',), 'end_time': ('end_time',),
            'price_max': ('price_max', 'max_price'), 'number_of_players': ('number_of_players', 'people'),
            'booking_code': ('booking_code',),
        }
        for target, keys in aliases.items():
            if getattr(result, target) is None:
                value = next((context.get(key) for key in keys if context.get(key) is not None), None)
                if value is not None:
                    setattr(result, target, value)
        return result

    @staticmethod
    def _booking_code(query: str) -> str | None:
        match = re.search(r'\bSH[- ]?[A-Z0-9-]{3,}\b', query.upper())
        return match[0].replace(' ', '-') if match else None

    @staticmethod
    def _venue_name(query: str) -> str | None:
        quoted = re.search(r'["“]([^"”]{2,80})["”]', query)
        return quoted[1].strip() if quoted else None

    @staticmethod
    def _location(query: str) -> str | None:
        match = re.search(r'(quan\s+\d+|binh thanh|go vap|tan binh|cau giay|tay ho|thu duc|tp\.?hcm|ho chi minh|ha noi|da nang)', query)
        return match[1] if match else None

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
        if any(term in query for term in ('toi nay', 'toi mai', 'buoi toi')) and hour < 12:
            hour += 12
        return f'{hour:02d}:{int(match[2] or 0):02d}', None

    @staticmethod
    def _date(query: str, today: date) -> str | None:
        if 'hom nay' in query or 'toi nay' in query:
            return today.isoformat()
        if 'ngay mai' in query or 'toi mai' in query or re.search(r'\bmai\b', query):
            return (today + timedelta(days=1)).isoformat()
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
