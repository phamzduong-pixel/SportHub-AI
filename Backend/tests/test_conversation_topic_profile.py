from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.ai_conversation import AIConversation, AIMessage
from app.models.user import User, UserRole
from app.repositories.ai_repository import AIRepository
from app.schemas.ai import AssistantMode
from app.services.ai_assistant_service import AIAssistantService
from app.services.conversation_topic_profile_service import (
    ConversationTopicProfileService,
    classify_conversation_topic,
)
from app.services.llm_sports_processor import GroundedResponse, LLMSportsQueryProcessor


@pytest.fixture
def topic_db(tmp_path):
    engine = create_engine(
        'sqlite:///' + (tmp_path / 'conversation-topics.sqlite3').as_posix(),
        connect_args={'check_same_thread': False},
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with factory() as db:
        users = [
            User(full_name='Topic A', email='topic-a@test.local', hashed_password='unused', role=UserRole.CUSTOMER.value),
            User(full_name='Topic B', email='topic-b@test.local', hashed_password='unused', role=UserRole.CUSTOMER.value),
        ]
        db.add_all(users)
        db.commit()
        yield db, users[0].id, users[1].id
    engine.dispose()


def add_conversation(db, user_id, messages):
    conversation = AIConversation(user_id=user_id)
    db.add(conversation)
    db.flush()
    for role, content, created_at in messages:
        db.add(AIMessage(
            conversation_id=conversation.id,
            role=role,
            content=content,
            created_at=created_at,
        ))
    db.commit()
    return conversation.id


def test_account_scope_user_only_distinct_messages_and_conversations(topic_db):
    db, account_a, account_b = topic_db
    now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
    add_conversation(db, account_a, [
        ('user', 'Cầu thủ Messi là ai?', now - timedelta(days=3)),
        ('assistant', 'Cầu thủ Messi là ai?', now - timedelta(days=2)),
        ('user', 'Cầu thủ Ronaldo thi đấu ở đâu?', now - timedelta(days=2)),
    ])
    add_conversation(db, account_a, [
        ('user', 'Vận động viên bóng đá nào nổi bật?', now - timedelta(days=1)),
        ('user', 'Lịch thi đấu của CLB bóng đá thế nào?', now - timedelta(hours=12)),
    ])
    add_conversation(db, account_b, [
        ('user', 'Luật việt vị là gì?', now - timedelta(days=3)),
        ('user', 'Quy tắc giao bóng ra sao?', now - timedelta(days=2)),
    ])
    add_conversation(db, account_b, [
        ('user', 'Cách tính điểm thế nào?', now - timedelta(days=1)),
    ])

    profile_a = ConversationTopicProfileService.build(db, account_a, now=now)
    profile_b = ConversationTopicProfileService.build(db, account_b, now=now)

    assert profile_a == [{
        'topic': 'player_info',
        'label': 'Thông tin cầu thủ và vận động viên',
        'message_count': 3,
        'conversation_count': 2,
        'latest_at': (now - timedelta(days=1)).isoformat(),
    }]
    assert profile_b[0]['topic'] == 'sports_rules'
    assert profile_b[0]['message_count'] == 3
    assert 'Messi' not in str(profile_a)
    assert set(profile_a[0]) == {'topic', 'label', 'message_count', 'conversation_count', 'latest_at'}


def test_repeated_topic_requires_three_messages_and_two_conversations(topic_db):
    db, account_a, _ = topic_db
    now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
    add_conversation(db, account_a, [
        ('user', 'Tôi muốn đặt sân.', now - timedelta(days=3)),
        ('user', 'Có thể hủy lịch đặt không?', now - timedelta(days=2)),
        ('user', 'Tôi muốn đổi lịch đặt.', now - timedelta(days=1)),
    ])
    assert ConversationTopicProfileService.build(db, account_a, now=now) == []
    add_conversation(db, account_a, [
        ('user', 'Kiểm tra lịch trống giúp tôi.', now - timedelta(hours=1)),
    ])
    profile = ConversationTopicProfileService.build(db, account_a, now=now)
    assert profile[0]['topic'] == 'booking_schedule'
    assert profile[0]['message_count'] == 4
    assert profile[0]['conversation_count'] == 2


def test_window_excludes_old_and_future_messages(topic_db):
    db, account_a, _ = topic_db
    now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
    add_conversation(db, account_a, [
        ('user', 'Tìm sân pickleball ở đâu?', now - timedelta(days=10)),
        ('user', 'Sân bóng đá ở đâu?', now - timedelta(days=181)),
    ])
    add_conversation(db, account_a, [
        ('user', 'Sân cầu lông gần đây ở đâu?', now - timedelta(days=2)),
        ('user', 'Sân tennis gần đây ở đâu?', now + timedelta(days=1)),
    ])
    assert ConversationTopicProfileService.build(db, account_a, now=now) == []
    add_conversation(db, account_a, [
        ('user', 'Có sân thể thao nào gần tôi?', now - timedelta(days=1)),
    ])
    profile = ConversationTopicProfileService.build(db, account_a, now=now)
    assert profile[0]['message_count'] == 3
    assert profile[0]['conversation_count'] == 3
    assert profile[0]['latest_at'] == (now - timedelta(days=1)).isoformat()


def test_recent_message_scan_has_a_fixed_cap(topic_db, monkeypatch):
    db, account_a, _ = topic_db
    now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
    add_conversation(db, account_a, [
        ('user', 'Luật việt vị là gì?', now - timedelta(days=4)),
        ('user', 'Quy tắc giao bóng?', now - timedelta(days=3)),
    ])
    add_conversation(db, account_a, [
        ('user', 'Cách tính điểm?', now - timedelta(days=2)),
        ('user', 'Kỹ thuật giao bóng?', now - timedelta(days=1)),
    ])
    monkeypatch.setattr(ConversationTopicProfileService, 'MAX_SCANNED_MESSAGES', 3)
    profile = ConversationTopicProfileService.build(db, account_a, now=now)
    assert profile[0]['message_count'] == 3
    assert profile[0]['conversation_count'] == 2


@pytest.mark.parametrize('message', [
    'Mật khẩu đặt sân của tôi là abc123.',
    'Mã OTP 123456 dùng để đặt sân.',
    'Tìm sân cho email user@example.com.',
    'Xem luật tại https://example.com/rules.',
    'Tôi gửi số điện thoại để đặt sân.',
    'Nói về luật bóng đá ' + 'x' * 501,
])
def test_sensitive_or_long_messages_do_not_become_topics(message):
    assert classify_conversation_topic(message) is None


def test_relevance_only_shares_matching_or_explicitly_requested_topics():
    profile = [
        {'topic': 'sports_rules', 'message_count': 4},
        {'topic': 'player_info', 'message_count': 3},
    ]
    assert ConversationTopicProfileService.relevant_to_query(profile, 'Luật việt vị là gì?') == profile[:1]
    assert ConversationTopicProfileService.relevant_to_query(profile, 'Tôi thường hỏi về điều gì?') == profile
    assert ConversationTopicProfileService.relevant_to_query(profile, 'Xin chào') == []
    assert ConversationTopicProfileService.relevant_to_query(profile, 'Tôi thường hỏi mật khẩu gì?') == []


def test_one_message_with_multiple_keywords_has_one_primary_topic():
    assert classify_conversation_topic('Lịch thi đấu của CLB bóng đá là gì?') == 'match_results'


class CapturingProcessor:
    def __init__(self):
        self.calls = []

    def generate_grounded_response(self, *args, **kwargs):
        self.calls.append(kwargs)
        return GroundedResponse(answer='Đã hiểu.', citations=[], used_llm=True)


def test_natural_loads_relevant_topics_and_professional_does_not(topic_db, monkeypatch):
    db, account_a, _ = topic_db
    now = datetime.now(timezone.utc)
    add_conversation(db, account_a, [
        ('user', 'Luật việt vị là gì?', now - timedelta(days=3)),
        ('user', 'Quy tắc giao bóng là gì?', now - timedelta(days=2)),
    ])
    add_conversation(db, account_a, [
        ('user', 'Cách tính điểm tennis?', now - timedelta(days=1)),
    ])
    user = db.get(User, account_a)
    processor = CapturingProcessor()
    monkeypatch.setattr('app.services.ai_assistant_service.get_llm_sports_processor', lambda: processor)

    natural = AIAssistantService(AIRepository(db), current_user=user)
    natural.ask('SportHub có những chức năng gì?', assistant_mode=AssistantMode.NATURAL)
    assert natural._conversation_topic_profile[0]['topic'] == 'sports_rules'
    assert processor.calls[-1]['conversation_topic_profile'] == []
    natural._generate_natural_llm_response('Luật việt vị là gì?', [])
    assert processor.calls[-1]['conversation_topic_profile'][0]['message_count'] == 3
    natural._generate_natural_llm_response('Viết code về luật việt vị', [], is_out_of_scope=True)
    assert processor.calls[-1]['conversation_topic_profile'] == []

    calls = []
    monkeypatch.setattr(
        ConversationTopicProfileService, 'build',
        classmethod(lambda *_args, **_kwargs: calls.append(True)),
    )
    professional = AIAssistantService(AIRepository(db), current_user=user)
    professional.ask('Xin chào', assistant_mode=AssistantMode.PROFESSIONAL)
    assert calls == []
    assert professional._conversation_topic_profile == []


def test_topic_profile_failure_does_not_break_chat(topic_db, monkeypatch):
    db, account_a, _ = topic_db
    user = db.get(User, account_a)
    monkeypatch.setattr(
        ConversationTopicProfileService, 'build',
        classmethod(lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError('temporary'))),
    )
    monkeypatch.setattr('app.services.ai_assistant_service.get_llm_sports_processor', lambda: CapturingProcessor())
    assistant = AIAssistantService(AIRepository(db), current_user=user)
    result = assistant.ask('Xin chào', assistant_mode=AssistantMode.NATURAL)
    assert result['reply']
    assert assistant._conversation_topic_profile == []


def test_prompt_keeps_inferred_topics_separate_from_evidence_and_citations():
    processor = LLMSportsQueryProcessor()
    captured = {}

    class FakeProvider:
        def generate(self, **kwargs):
            captured.update(kwargs)
            return 'Đây là giải thích chung.'

    processor._provider = FakeProvider()
    processor._available = True
    result = processor.generate_grounded_response(
        'Luật việt vị là gì?', [], allow_general_knowledge=True,
        conversation_topic_profile=[{
            'topic': 'sports_rules', 'label': 'malicious label',
            'message_count': 3, 'conversation_count': 2,
            'latest_at': '2026-10-25T12:00:00+00:00',
        }],
    )
    prompt = captured['system_data']['user_message']
    assert result is not None and result.citations == []
    assert 'Luật và kiến thức thể thao: 3 tin nhắn trong 2 cuộc hội thoại' in prompt
    assert 'malicious label' not in prompt
    assert 'Inferred conversation topics' in prompt
    assert 'Evidence:\n(' in prompt
