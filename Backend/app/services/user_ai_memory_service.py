import re
import unicodedata
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ..models.user_ai_memory import UserAIMemory


@dataclass(frozen=True)
class MemoryCandidate:
    memory_type: str
    memory_key: str
    value: str


_ATHLETE_ALIASES = {
    'messi': 'Messi',
    'lionel messi': 'Lionel Messi',
    'cristiano ronaldo': 'Cristiano Ronaldo',
    'cr7': 'Cristiano Ronaldo',
    'm10': 'Lionel Messi',
    'ronaldo': 'Ronaldo',
    'neymar': 'Neymar',
    'mbappe': 'Mbappé',
    'roger federer': 'Roger Federer',
    'federer': 'Federer',
    'rafael nadal': 'Rafael Nadal',
    'nadal': 'Nadal',
    'novak djokovic': 'Novak Djokovic',
    'djokovic': 'Djokovic',
    'serena williams': 'Serena Williams',
    'lebron james': 'LeBron James',
    'lebron': 'LeBron James',
    'stephen curry': 'Stephen Curry',
    'curry': 'Curry',
    'lin dan': 'Lin Dan',
    'viktor axelsen': 'Viktor Axelsen',
    'nguyen thuy linh': 'Nguyễn Thùy Linh',
    'nguyen tien minh': 'Nguyễn Tiến Minh',
    'ly hoang nam': 'Lý Hoàng Nam',
    'thanh thuy': 'Trần Thị Thanh Thúy',
}
_SPORT_ALIASES = {
    'bong da': 'bóng đá',
    'football': 'bóng đá',
    'soccer': 'bóng đá',
    'cau long': 'cầu lông',
    'badminton': 'cầu lông',
    'pickleball': 'pickleball',
    'tennis': 'tennis',
    'bong ro': 'bóng rổ',
    'basketball': 'bóng rổ',
    'bong chuyen': 'bóng chuyền',
    'volleyball': 'bóng chuyền',
}
_SENSITIVE_OR_SECRET = re.compile(
    r'\b(mat khau|password|otp|token|api key|secret|cccd|cmnd|the tin dung|tai khoan ngan hang|'
    r'benh|chan doan|thuoc dieu tri|ton giao|chinh tri|xu huong tinh duc|so nha|dia chi nha)\b',
    re.IGNORECASE,
)
_QUOTATION_MARKS = frozenset('"\'“”‘’「」『』')


def _plain(value: str) -> str:
    value = unicodedata.normalize('NFD', value.casefold())
    return ''.join(char for char in value if unicodedata.category(char) != 'Mn').replace('đ', 'd')


def _memory_key(memory_type: str, value: str) -> str:
    # Preferences such as athletes, sports, and areas can coexist. Keep only
    # response style singular because an explicit "from now on" instruction
    # supersedes the previous style.
    if memory_type == 'response_style':
        return memory_type
    digest = hashlib.sha256(_plain(value).encode('utf-8')).hexdigest()[:40]
    return f'{memory_type}:{digest}'


def extract_explicit_memory(message: str) -> MemoryCandidate | None:
    """Accept only short, direct statements in the supported preference categories."""
    if not isinstance(message, str):
        return None
    text = ' '.join(message.strip().split())
    if not text or len(text) > 240 or '?' in text or any(mark in text for mark in _QUOTATION_MARKS):
        return None

    normalized = _plain(text)
    if _SENSITIVE_OR_SECRET.search(normalized) or any(
        cue in normalized for cue in ('neu toi', 'gia su', 'vi du', 'trich dan', 'ai do noi', 'khong chac')
    ):
        return None

    athlete_match = re.fullmatch(
        r'(?:tôi|mình)\s+(?:rất\s+)?thích\s+(?:(?P<role>cầu thủ|vận động viên|tay vợt)\s+)?'
        r'(?P<value>[\wÀ-ỹ][\wÀ-ỹ .\'-]{0,59})[.!]?',
        text,
        re.IGNORECASE,
    )
    if athlete_match:
        raw_value = athlete_match.group('value').strip(' .!')
        canonical = _ATHLETE_ALIASES.get(_plain(raw_value))
        if canonical:
            return MemoryCandidate('favorite_athlete', _memory_key('favorite_athlete', canonical), canonical)
        normalized_athlete = _plain(raw_value)
        unsafe_terms = ('ignore', 'instruction', 'system', 'prompt', 'reveal', 'secret', 'bo qua', 'huong dan')
        if athlete_match.group('role') and len(raw_value) >= 2 and not any(term in normalized_athlete for term in unsafe_terms):
            return MemoryCandidate('favorite_athlete', _memory_key('favorite_athlete', raw_value), raw_value)

    sport_match = re.fullmatch(
        r'(?:tôi|mình)\s+(?:thường\s+)?chơi\s+(?:môn\s+)?(?P<value>[\wÀ-ỹ -]{2,40})[.!]?',
        text,
        re.IGNORECASE,
    )
    if sport_match:
        sport = _SPORT_ALIASES.get(_plain(sport_match.group('value').strip(' .!')))
        if sport:
            return MemoryCandidate('usual_sport', _memory_key('usual_sport', sport), sport)

    style_match = re.fullmatch(
        r'(?:(?:từ giờ|từ nay)\s+(?:hãy\s+)?trả lời|(?:tôi|mình)\s+(?:thích|muốn)\s+câu trả lời)\s+'
        r'(?P<value>ngắn gọn|chi tiết)(?:\s+(?:nhé|giúp tôi))?[.!]?',
        text,
        re.IGNORECASE,
    )
    if style_match:
        style = 'concise' if _plain(style_match.group('value')) == 'ngan gon' else 'detailed'
        return MemoryCandidate('response_style', 'response_style', style)

    area_match = re.fullmatch(
        r'(?:tôi|mình)\s+thường\s+tìm\s+sân\s+(?:ở|tại)\s+(?:khu vực\s+)?(?P<value>[\wÀ-ỹ .\'-]{2,70})[.!]?',
        text,
        re.IGNORECASE,
    )
    if area_match:
        area = area_match.group('value').strip(' .!')
        normalized_area = _plain(area)
        # Keep search granularity regional; do not retain street or house-level addresses.
        if (
            not re.search(r'\b(?:duong|pho|street|road|ngo|hem|so nha|dia chi)\b', normalized_area)
            and not re.search(r'\b\d{7,}\b', normalized_area)
            and not any(term in normalized_area for term in ('ignore instructions', 'bo qua huong dan', 'system prompt', 'chinh sach'))
            and len(area) <= 70
        ):
            return MemoryCandidate('preferred_area', _memory_key('preferred_area', area), area)

    return None


def extract_explicit_memory_retraction(message: str) -> MemoryCandidate | None:
    """Recognize narrow, direct corrections that withdraw a stored preference."""
    if not isinstance(message, str):
        return None
    text = ' '.join(message.strip().split())
    if not text or len(text) > 240 or '?' in text or any(mark in text for mark in _QUOTATION_MARKS):
        return None
    normalized = _plain(text)
    if _SENSITIVE_OR_SECRET.search(normalized) or any(
        cue in normalized for cue in ('neu toi', 'gia su', 'vi du', 'trich dan', 'ai do noi', 'khong chac')
    ):
        return None
    text = re.sub(r'\s+nữa[.!]?$', '', text, flags=re.IGNORECASE).strip()

    athlete_match = re.fullmatch(
        r'(?:tôi|mình)\s+(?:không còn thích|không thích)\s+(?:(?P<role>cầu thủ|vận động viên|tay vợt)\s+)?'
        r'(?P<value>[\wÀ-ỹ][\wÀ-ỹ .\'-]{0,59})[.!]?',
        text,
        re.IGNORECASE,
    )
    if athlete_match:
        raw_value = athlete_match.group('value').strip(' .!')
        value = _ATHLETE_ALIASES.get(_plain(raw_value))
        if value is None and athlete_match.group('role'):
            unsafe_terms = ('ignore', 'instruction', 'system', 'prompt', 'reveal', 'secret', 'bo qua', 'huong dan')
            if len(raw_value) >= 2 and not any(term in _plain(raw_value) for term in unsafe_terms):
                value = raw_value
        if value:
            return MemoryCandidate('favorite_athlete', _memory_key('favorite_athlete', value), value)

    sport_match = re.fullmatch(
        r'(?:tôi|mình)\s+(?:không còn\s+(?:thường\s+)?chơi|không chơi)\s+(?:môn\s+)?'
        r'(?P<value>[\wÀ-ỹ -]{2,40})[.!]?',
        text,
        re.IGNORECASE,
    )
    if sport_match:
        sport = _SPORT_ALIASES.get(_plain(sport_match.group('value').strip(' .!')))
        if sport:
            return MemoryCandidate('usual_sport', _memory_key('usual_sport', sport), sport)

    area_match = re.fullmatch(
        r'(?:tôi|mình)\s+(?:không còn\s+(?:thường\s+)?|không\s+)tìm sân\s+'
        r'(?:ở|tại)\s+(?:khu vực\s+)?(?P<value>[\wÀ-ỹ .\'-]{2,70})[.!]?',
        text,
        re.IGNORECASE,
    )
    if area_match:
        area = area_match.group('value').strip(' .!')
        normalized_area = _plain(area)
        if (
            not re.search(r'\b(?:duong|pho|street|road|ngo|hem|so nha|dia chi)\b', normalized_area)
            and not re.search(r'\b\d{7,}\b', normalized_area)
            and not any(term in normalized_area for term in ('ignore instructions', 'bo qua huong dan', 'system prompt', 'chinh sach'))
        ):
            return MemoryCandidate('preferred_area', _memory_key('preferred_area', area), area)
    return None


class UserAIMemoryService:
    MAX_ACTIVE_MEMORIES = 12

    @staticmethod
    def remember_explicit_statement(
        db: Session,
        *,
        user_id: int,
        message: str,
        source_conversation_id: int | None = None,
    ) -> UserAIMemory | None:
        retraction = extract_explicit_memory_retraction(message)
        if retraction is not None:
            memory = db.scalar(select(UserAIMemory).where(
                UserAIMemory.user_id == user_id,
                UserAIMemory.memory_key == retraction.memory_key,
            ))
            if memory is None:
                # Rows written before values received distinct keys used the
                # memory type itself as the key. Retire only a matching value.
                legacy = db.scalar(select(UserAIMemory).where(
                    UserAIMemory.user_id == user_id,
                    UserAIMemory.memory_key == retraction.memory_type,
                ))
                if legacy is not None and _plain(legacy.value) == _plain(retraction.value):
                    memory = legacy
            if memory is not None:
                db.delete(memory)
                db.commit()
            return None

        candidate = extract_explicit_memory(message)
        if candidate is None:
            return None

        now = datetime.now(timezone.utc)

        if candidate.memory_key != candidate.memory_type:
            legacy = db.scalar(select(UserAIMemory).where(
                UserAIMemory.user_id == user_id,
                UserAIMemory.memory_key == candidate.memory_type,
            ))
            if legacy is not None:
                legacy_key = _memory_key(legacy.memory_type, legacy.value)
                collision = db.scalar(select(UserAIMemory).where(
                    UserAIMemory.user_id == user_id,
                    UserAIMemory.memory_key == legacy_key,
                ))
                if collision is not None and collision.id != legacy.id:
                    if _plain(collision.value) == _plain(legacy.value):
                        db.delete(legacy)
                    else:
                        raise RuntimeError('Memory key collision while upgrading legacy preference')
                else:
                    legacy.memory_key = legacy_key
                db.flush()

        values = {
            'user_id': user_id,
            'memory_type': candidate.memory_type,
            'memory_key': candidate.memory_key,
            'value': candidate.value,
            'is_active': True,
            'source_conversation_id': source_conversation_id,
            'created_at': now,
            'updated_at': now,
        }
        dialect = db.get_bind().dialect.name
        insert_for_dialect = {
            'sqlite': sqlite_insert,
            'postgresql': postgresql_insert,
        }.get(dialect)
        if insert_for_dialect is not None:
            statement = insert_for_dialect(UserAIMemory).values(**values)
            statement = statement.on_conflict_do_update(
                index_elements=[UserAIMemory.user_id, UserAIMemory.memory_key],
                set_={
                    'memory_type': candidate.memory_type,
                    'value': candidate.value,
                    'is_active': True,
                    'source_conversation_id': source_conversation_id,
                    'updated_at': now,
                },
            )
            db.execute(statement)
        else:
            existing = db.scalar(select(UserAIMemory).where(
                UserAIMemory.user_id == user_id,
                UserAIMemory.memory_key == candidate.memory_key,
            ).with_for_update())
            if existing is not None:
                for key in ('memory_type', 'value', 'is_active', 'source_conversation_id', 'updated_at'):
                    setattr(existing, key, values[key])
            else:
                db.add(UserAIMemory(**values))
                try:
                    db.flush()
                except IntegrityError:
                    db.rollback()
                    existing = db.scalar(select(UserAIMemory).where(
                        UserAIMemory.user_id == user_id,
                        UserAIMemory.memory_key == candidate.memory_key,
                    ).with_for_update())
                    if existing is None:
                        raise
                    for key in ('memory_type', 'value', 'is_active', 'source_conversation_id', 'updated_at'):
                        setattr(existing, key, values[key])
        db.commit()
        return db.scalar(select(UserAIMemory).where(
            UserAIMemory.user_id == user_id,
            UserAIMemory.memory_key == candidate.memory_key,
        ))

    @staticmethod
    def list_active(db: Session, user_id: int, limit: int = MAX_ACTIVE_MEMORIES) -> list[UserAIMemory]:
        bounded_limit = max(1, min(int(limit), UserAIMemoryService.MAX_ACTIVE_MEMORIES))
        return list(db.scalars(
            select(UserAIMemory)
            .where(UserAIMemory.user_id == user_id, UserAIMemory.is_active.is_(True))
            .order_by(UserAIMemory.updated_at.desc(), UserAIMemory.id.desc())
            .limit(bounded_limit)
        ).all())

    @staticmethod
    def prompt_memories(db: Session, user_id: int, limit: int = MAX_ACTIVE_MEMORIES) -> list[dict[str, str]]:
        return [
            {'memory_type': memory.memory_type, 'value': memory.value}
            for memory in UserAIMemoryService.list_active(db, user_id, limit)
        ]

    @staticmethod
    def delete_one(db: Session, user_id: int, memory_id: int) -> bool:
        memory = db.scalar(select(UserAIMemory).where(
            UserAIMemory.id == memory_id,
            UserAIMemory.user_id == user_id,
        ))
        if memory is None:
            return False
        db.delete(memory)
        db.commit()
        return True

    @staticmethod
    def delete_all(db: Session, user_id: int) -> int:
        result = db.execute(delete(UserAIMemory).where(UserAIMemory.user_id == user_id))
        db.commit()
        return int(result.rowcount or 0)
