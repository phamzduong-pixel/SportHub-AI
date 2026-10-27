"""Account-scoped, transient topic counts from recent user chat messages."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.ai_conversation import AIConversation, AIMessage


TOPIC_LABELS = {
    'booking_schedule': 'Đặt sân và quản lý lịch chơi',
    'match_results': 'Lịch thi đấu và kết quả',
    'venue_activity': 'Địa điểm, sân bãi và hoạt động thể thao',
    'sports_rules': 'Luật và kiến thức thể thao',
    'teams_clubs': 'Đội tuyển và câu lạc bộ',
    'player_info': 'Thông tin cầu thủ và vận động viên',
}

# One primary subject per message. Business requests and match questions take
# precedence over generic mentions of a venue, team, or athlete.
_TOPIC_PATTERNS = (
    ('booking_schedule', re.compile(
        r'\b(?:dat san|dat lich|lich dat|lich choi|booking|huy san|huy lich|doi lich|'
        r'doi gio|thanh toan|hoan tien|kiem tra lich trong|khung gio trong|san con trong)\b'
    )),
    ('match_results', re.compile(
        r'\b(?:lich thi dau|ket qua|ti so|ty so|tran dau|chung ket|ban ket|'
        r'world cup|vo dich|giai dau)\b'
    )),
    ('venue_activity', re.compile(
        r'\b(?:tim san|san the thao|san bong|san cau long|san pickleball|san tennis|'
        r'san bong ro|san bong chuyen|dia diem choi|dia diem tap|tap luyen|'
        r'khu vuc choi|san o dau|san gan)\b'
    )),
    ('sports_rules', re.compile(
        r'\b(?:luat|quy tac|cach tinh diem|tinh diem|viet vi|giao bong|'
        r'tie break|tiebreak|double bounce|nvz|ky thuat|chien thuat|cach choi)\b'
    )),
    ('teams_clubs', re.compile(
        r'\b(?:doi tuyen|doi bong|cau lac bo|clb|doi the thao|fc)\b'
    )),
    ('player_info', re.compile(
        r'\b(?:cau thu|van dong vien|tay vot|hau ve|tien ve|tien dao|thu mon|'
        r'player|athlete)\b'
    )),
)

_SENSITIVE_PATTERN = re.compile(
    r'\b(?:mat khau|password|passcode|otp|ma xac thuc|ma dang nhap|'
    r'access token|refresh token|api key|secret|cccd|cmnd|the tin dung|'
    r'so tai khoan|tai khoan ngan hang|so dien thoai|email|e mail|'
    r'dia chi nha|so nha|benh|chan doan|ton giao|chinh tri)\b'
)
_PERSONAL_INTEREST_PATTERN = re.compile(
    r'\b(?:toi thuong hoi|toi hay hoi|toi quan tam|chu de toi quan tam|'
    r'goi y chu de cho toi|ca nhan hoa cho toi)\b'
)


def _plain(value: str) -> str:
    value = unicodedata.normalize('NFD', value.casefold())
    return ' '.join(''.join(
        char for char in value if unicodedata.category(char) != 'Mn'
    ).replace('đ', 'd').split())


def _looks_sensitive(message: str, normalized: str) -> bool:
    return bool(
        _SENSITIVE_PATTERN.search(normalized)
        or '@' in message
        or '://' in message
        or re.search(r'\b\d{6,}\b', normalized)
    )


def classify_conversation_topic(message: str) -> str | None:
    """Return a supported topic only for short, non-sensitive text."""
    if not isinstance(message, str) or not message.strip() or len(message) > 500:
        return None
    normalized = _plain(message)
    if _looks_sensitive(message, normalized):
        return None
    for topic, pattern in _TOPIC_PATTERNS:
        if pattern.search(normalized):
            return topic
    return None


class ConversationTopicProfileService:
    WINDOW_DAYS = 180
    MAX_SCANNED_MESSAGES = 2000
    MIN_MESSAGES = 3
    MIN_CONVERSATIONS = 2

    @classmethod
    def build(
        cls, db: Session, user_id: int, *, now: datetime | None = None,
    ) -> list[dict[str, str | int]]:
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=cls.WINDOW_DAYS)
        rows = db.execute(
            select(AIMessage.id, AIMessage.conversation_id, AIMessage.content, AIMessage.created_at)
            .join(AIConversation, AIMessage.conversation_id == AIConversation.id)
            .where(
                AIConversation.user_id == user_id,
                AIMessage.role == 'user',
                AIMessage.created_at >= cutoff,
                AIMessage.created_at <= now,
            )
            .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
            .limit(cls.MAX_SCANNED_MESSAGES)
        ).all()

        counts: dict[str, int] = defaultdict(int)
        conversations: dict[str, set[int]] = defaultdict(set)
        latest: dict[str, datetime] = {}
        seen_ids: set[int] = set()
        for message_id, conversation_id, content, created_at in rows:
            if message_id in seen_ids:
                continue
            seen_ids.add(message_id)
            topic = classify_conversation_topic(content)
            if topic is None:
                continue
            counts[topic] += 1
            conversations[topic].add(conversation_id)
            if topic not in latest or created_at > latest[topic]:
                latest[topic] = created_at

        result = []
        for topic, count in counts.items():
            if count < cls.MIN_MESSAGES or len(conversations[topic]) < cls.MIN_CONVERSATIONS:
                continue
            recent = latest[topic]
            if recent.tzinfo is None:
                recent = recent.replace(tzinfo=timezone.utc)
            result.append({
                'topic': topic,
                'label': TOPIC_LABELS[topic],
                'message_count': count,
                'conversation_count': len(conversations[topic]),
                'latest_at': recent.isoformat(),
            })
        return sorted(result, key=lambda item: (-item['message_count'], item['topic']))

    @staticmethod
    def relevant_to_query(profile: list[dict], query: str) -> list[dict]:
        """Only share matching subjects, or top subjects for an explicit personal request."""
        if not isinstance(query, str) or len(query) > 500 or _looks_sensitive(query, _plain(query)):
            return []
        topic = classify_conversation_topic(query)
        if topic is not None:
            return [item for item in profile if item.get('topic') == topic]
        if isinstance(query, str) and _PERSONAL_INTEREST_PATTERN.search(_plain(query)):
            return profile[:3]
        return []
