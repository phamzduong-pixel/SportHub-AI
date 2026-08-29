import re
import unicodedata
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.facility import Facility
from app.models.field import Field
from app.models.time_slot import TimeSlot
from app.models.user import User
from app.repositories.ai_repository import AIRepository
from app.services.ai_assistant_service import AIAssistantService
from app.services.ai_intent_router import AssistantIntent, IntentRouter


def plain(value: str) -> str:
    normalized = unicodedata.normalize('NFD', value.casefold())
    stripped = ''.join(char for char in normalized if unicodedata.category(char) != 'Mn')
    stripped = (
        stripped.replace('đ', 'd').replace('â', 'a').replace('ă', 'a')
        .replace('ê', 'e').replace('ô', 'o').replace('ơ', 'o').replace('ư', 'u')
    )
    return re.sub(r'[^a-z0-9]+', ' ', stripped).strip()


@pytest.fixture
def nlu_phase1_db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    owner = User(
        id=1, email='owner_nlu@sporthub.vn',
        role='OWNER', full_name='Owner NLU',
        hashed_password='hashed_pw', is_active=True,
    )
    facility_td = Facility(
        id=1, owner_id=1, name='Co so Thu Duc',
        is_active=True, status='APPROVED', location='Thu Duc'
    )
    field_pickleball = Field(
        id=1, facility_id=1, owner_id=1, name='San Pickleball Thu Duc 1',
        sport_type='pickleball', status='available', location='Thu Duc', capacity=4, base_price=Decimal('150000')
    )
    facility_cg = Facility(
        id=2, owner_id=1, name='Co so Cau Giay',
        is_active=True, status='APPROVED', location='Cau Giay'
    )
    field_badminton = Field(
        id=2, facility_id=2, owner_id=1, name='San Cau Long Cau Giay 1',
        sport_type='cầu lông', status='available', location='Cau Giay', capacity=4, base_price=Decimal('100000')
    )
    facility_hm = Facility(
        id=3, owner_id=1, name='Co so Hoang Mai',
        is_active=True, status='APPROVED', location='Hoang Mai'
    )
    field_tennis = Field(
        id=3, facility_id=3, owner_id=1, name='San Tennis Hoang Mai 1',
        sport_type='tennis', status='available', location='Hoang Mai', capacity=4, base_price=Decimal('200000')
    )
    session.add_all([owner, facility_td, field_pickleball, facility_cg, field_badminton, facility_hm, field_tennis])
    session.commit()

    tomorrow = date.today() + timedelta(days=1)
    slots = [
        TimeSlot(id=1, field_id=1, start_time=time(18, 0), end_time=time(19, 0), price=Decimal('150000'), is_active=True, name='18:00-19:00'),
        TimeSlot(id=2, field_id=2, start_time=time(19, 0), end_time=time(20, 0), price=Decimal('100000'), is_active=True, name='19:00-20:00'),
        TimeSlot(id=3, field_id=3, start_time=time(20, 0), end_time=time(21, 0), price=Decimal('200000'), is_active=True, name='20:00-21:00'),
    ]
    session.add_all(slots)
    session.commit()

    yield session
    session.close()


def test_nlu_phase1_mandatory_cases(nlu_phase1_db):
    service = AIAssistantService(AIRepository(nlu_phase1_db))
    router = IntentRouter()

    # Case 1: "San pickleball o Thu Duc ngay mai"
    q1 = "San pickleball o Thu Duc ngay mai"
    r1 = router.route(q1)
    assert r1.intent in (AssistantIntent.CHECK_AVAILABILITY, AssistantIntent.SEARCH_VENUE)
    assert r1.entities.sport_type == "pickleball"
    assert plain(r1.entities.location) == "thu duc"
    assert r1.entities.date == (date.today() + timedelta(days=1)).isoformat()
    res1 = service.ask(q1)
    assert res1["status"] in ("OK", "NO_AVAILABLE_SLOT", "NEED_MORE_DATA")
    assert "ban muon hoi ve san lich trong booking hay thanh toan" not in plain(res1["reply"])

    # Case 2: "Tim san cau long o Cau Giay ngay mai"
    q2 = "Tim san cau long o Cau Giay ngay mai"
    r2 = router.route(q2)
    assert r2.intent in (AssistantIntent.CHECK_AVAILABILITY, AssistantIntent.SEARCH_VENUE)
    assert r2.entities.sport_type == "cầu lông"
    assert plain(r2.entities.location) == "cau giay"
    res2 = service.ask(q2)
    assert "ban muon hoi ve san lich trong" not in plain(res2["reply"])

    # Case 3: "San tennis Hoang Mai toi nay"
    q3 = "San tennis Hoang Mai toi nay"
    r3 = router.route(q3)
    assert r3.intent in (AssistantIntent.CHECK_AVAILABILITY, AssistantIntent.SEARCH_VENUE)
    assert r3.entities.sport_type == "tennis"
    assert plain(r3.entities.location) == "hoang mai"
    assert r3.entities.date == date.today().isoformat()
    assert r3.entities.preferred_time == "evening"
    res3 = service.ask(q3)
    assert "ban muon hoi ve san lich trong" not in plain(res3["reply"])

    # Case 4: "San pickleball"
    q4 = "San pickleball"
    r4 = router.route(q4)
    assert r4.intent in (AssistantIntent.SEARCH_VENUE, AssistantIntent.CHECK_AVAILABILITY)
    assert r4.entities.sport_type == "pickleball"
    res4 = service.ask(q4)
    assert res4["needs_clarification"] is True
    assert "pickleball" in plain(res4["reply"])

    # Case 5: "Tim san o Thu Duc"
    q5 = "Tim san o Thu Duc"
    r5 = router.route(q5)
    assert r5.intent == AssistantIntent.SEARCH_VENUE
    assert plain(r5.entities.location) == "thu duc"
    res5 = service.ask(q5)
    assert "thu duc" in plain(res5["reply"])

    # Case 6: "Ngay mai con san nao?"
    q6 = "Ngay mai con san nao?"
    r6 = router.route(q6)
    assert r6.intent in (AssistantIntent.CHECK_AVAILABILITY, AssistantIntent.SEARCH_VENUE)
    assert r6.entities.date == (date.today() + timedelta(days=1)).isoformat()
    res6 = service.ask(q6)
    assert res6["needs_clarification"] is True

    # Case 7: "Ban co the giup toi tim san khong?"
    q7 = "Ban co the giup toi tim san khong?"
    r7 = router.route(q7)
    assert r7.intent in (AssistantIntent.SEARCH_VENUE, AssistantIntent.SYSTEM_GUIDE)
    res7 = service.ask(q7)
    assert "ban muon hoi ve san lich trong booking hay thanh toan" not in plain(res7["reply"])
    assert any(w in plain(res7["reply"]) for w in ["tim san", "mon the thao", "khu vuc", "ngay", "sporthub"])

    # Case 8: "Tro ly nay lam duoc gi?"
    q8 = "Tro ly nay lam duoc gi?"
    r8 = router.route(q8)
    assert r8.intent == AssistantIntent.SYSTEM_GUIDE
    res8 = service.ask(q8)
    assert "tro ly ai chuyen biet" in plain(res8["reply"]) or "sporthub" in plain(res8["reply"])

    # Case 9: "Thoi tiet hom nay the nao?"
    q9 = "Thoi tiet hom nay the nao?"
    r9 = router.route(q9)
    assert r9.intent == AssistantIntent.OUT_OF_SCOPE
    res9 = service.ask(q9)
    assert res9["status"] == "OUT_OF_SCOPE"
