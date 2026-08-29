from datetime import date, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.facility import Facility
from app.models.field import Field, Booking
from app.models.time_slot import TimeSlot
from app.models.user import User
from app.repositories.ai_repository import AIRepository
from app.services.ai_assistant_service import AIAssistantService
from app.services.ai_intent_router import IntentRouter, AssistantIntent
from app.services.location_utils import extract_location, canonical_location


@pytest.fixture
def phase2_db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    owner = User(
        id=1, email='owner_p2@sporthub.vn',
        role='OWNER', full_name='Chủ Sân Phase 2',
        hashed_password='hashed_pw', is_active=True,
    )
    customer = User(
        id=2, email='customer_p2@sporthub.vn',
        role='CUSTOMER', full_name='Khách Hàng Phase 2',
        hashed_password='hashed_pw', is_active=True,
    )
    session.add_all([owner, customer])
    session.commit()

    fac1 = Facility(
        id=1, owner_id=owner.id, name='SportHub Cầu Giấy',
        location='Cầu Giấy, Hà Nội', is_active=True, status='APPROVED',
    )
    fac2 = Facility(
        id=2, owner_id=owner.id, name='SportHub Hoàn Kiếm',
        location='Hoàn Kiếm, Hà Nội', is_active=True, status='APPROVED',
    )
    session.add_all([fac1, fac2])
    session.commit()

    field1 = Field(
        id=1, facility_id=fac1.id, name='Sân Cầu Lông VIP 1',
        sport_type='cầu lông', capacity=4, base_price=150000,
        location='Cầu Giấy, Hà Nội', status='available', rating=4.8,
        amenities=['Điều hòa', 'Bãi đỗ xe'],
    )
    field2 = Field(
        id=2, facility_id=fac1.id, name='Sân Cầu Lông VIP 2',
        sport_type='cầu lông', capacity=4, base_price=100000,
        location='Cầu Giấy, Hà Nội', status='available', rating=4.5,
        amenities=['Quạt gió'],
    )
    field3 = Field(
        id=3, facility_id=fac2.id, name='Sân Bóng Đá 7 Người',
        sport_type='bóng đá', capacity=14, base_price=300000,
        location='Hoàn Kiếm, Hà Nội', status='available', rating=4.9,
        amenities=['Đèn chiếu sáng', 'Bãi đỗ xe'],
    )
    session.add_all([field1, field2, field3])
    session.commit()

    from datetime import time
    slot1_0 = TimeSlot(
        field_id=field1.id, name='Khung 14h-15h',
        start_time=time(14, 0), end_time=time(15, 0), price=80000, is_active=True,
    )
    slot1_1 = TimeSlot(
        field_id=field1.id, name='Khung 17h-18h',
        start_time=time(17, 0), end_time=time(18, 0), price=150000, is_active=True,
    )
    slot1_2 = TimeSlot(
        field_id=field1.id, name='Khung 18h-19h',
        start_time=time(18, 0), end_time=time(19, 0), price=160000, is_active=True,
    )
    slot1_3 = TimeSlot(
        field_id=field1.id, name='Khung 19h-20h',
        start_time=time(19, 0), end_time=time(20, 0), price=170000, is_active=True,
    )
    slot2_0 = TimeSlot(
        field_id=field2.id, name='Khung 14h-15h',
        start_time=time(14, 0), end_time=time(15, 0), price=70000, is_active=True,
    )
    slot2_1 = TimeSlot(
        field_id=field2.id, name='Khung 17h-18h',
        start_time=time(17, 0), end_time=time(18, 0), price=100000, is_active=True,
    )
    slot2_2 = TimeSlot(
        field_id=field2.id, name='Khung 18h-19h',
        start_time=time(18, 0), end_time=time(19, 0), price=110000, is_active=True,
    )
    slot2_3 = TimeSlot(
        field_id=field2.id, name='Khung 19h-20h',
        start_time=time(19, 0), end_time=time(20, 0), price=120000, is_active=True,
    )
    slot3_1 = TimeSlot(
        field_id=field3.id, name='Khung 19h-20h',
        start_time=time(19, 0), end_time=time(20, 0), price=300000, is_active=True,
    )
    session.add_all([slot1_0, slot1_1, slot1_2, slot1_3, slot2_0, slot2_1, slot2_2, slot2_3, slot3_1])
    session.commit()

    yield session
    session.close()


def test_intent_router_relative_dates():
    router = IntentRouter()
    today = date(2026, 8, 27)

    route_mai = router.route('tìm sân cầu lông ngày mai', today=today)
    assert route_mai.entities.date == '2026-08-28'

    route_kia = router.route('tìm sân cầu lông ngày kia', today=today)
    assert route_kia.entities.date == '2026-08-29'

    route_mot = router.route('tìm sân bóng đá ngày mốt', today=today)
    assert route_mot.entities.date == '2026-08-29'

    route_cuoi_tuan = router.route('đá bóng cuối tuần này', today=today)
    assert route_cuoi_tuan.entities.date is not None


def test_location_aliases_expansion():
    assert extract_location('sân bóng ở hoàn kiếm') == 'Hoàn Kiếm'
    assert extract_location('tìm sân cầu lông ba đình') == 'Ba Đình'
    assert extract_location('sân tennis ở đông đa') == 'Đống Đa'
    assert extract_location('sân ở thủ đức có không') == 'Thủ Đức'
    assert extract_location('sân ở tân bình') == 'Tân Bình'


def test_venue_detail_and_maintenance_intent():
    router = IntentRouter()
    route1 = router.route('sân này có bảo trì không?')
    assert route1.intent == AssistantIntent.GET_VENUE_DETAIL

    route2 = router.route('sân mở cửa lúc nào?')
    assert route2.intent == AssistantIntent.GET_VENUE_DETAIL

    route3 = router.route('sân có bãi đỗ xe không?')
    assert route3.intent == AssistantIntent.GET_VENUE_DETAIL


def test_multi_turn_ordinal_and_follow_up(phase2_db):
    repo = AIRepository(phase2_db)
    service = AIAssistantService(repo)

    # Lượt 1: Tìm sân cầu lông ở Cầu Giấy tối mai (khung giờ tối 100k - 170k)
    res1 = service.ask('Tìm sân cầu lông ở Cầu Giấy tối mai')
    assert res1['status'] in ('OK', 'NEED_MORE_DATA')
    context1 = res1.get('understood', {})
    assert context1.get('sport_type') == 'cầu lông'
    assert context1.get('location') == 'Cầu Giấy'
    result_field_ids = context1.get('result_field_ids', [])
    assert len(result_field_ids) >= 1

    if len(result_field_ids) >= 2:
        res2 = service.ask('Sân thứ 2 còn giờ nào?', context=context1)
        assert res2['status'] == 'OK'
        assert res2['understood'].get('field_id') == result_field_ids[1]

    res2_first = service.ask('Sân đầu tiên còn giờ nào?', context=context1)
    assert res2_first['status'] == 'OK'
    assert res2_first['understood'].get('field_id') == result_field_ids[0]

    res3 = service.ask('Còn sân khác không?', context=context1)
    assert res3['status'] == 'OK'

    res4 = service.ask('Giờ rẻ hơn thì sao?', context=context1)
    assert res4['status'] in ('OK', 'NO_AVAILABLE_SLOT')

    res5 = service.ask('Ngày kia thì sao?', context=context1)
    assert res5['status'] == 'OK'
    expected_day = (date.today() + timedelta(days=2)).isoformat()
    assert res5['understood'].get('booking_date') == expected_day


def test_out_of_scope_rejection(phase2_db):
    repo = AIRepository(phase2_db)
    service = AIAssistantService(repo)

    res = service.ask('Thời tiết Hà Nội hôm nay thế nào?')
    assert res['status'] == 'OUT_OF_SCOPE'
    assert 'trợ lý chuyên biệt của SportHub AI' in res['reply']

    res2 = service.ask('Viết cho tôi một đoạn code Python Flask')
    assert res2['status'] == 'OUT_OF_SCOPE'


def test_unaccented_vietnamese_queries(phase2_db):
    repo = AIRepository(phase2_db)
    service = AIAssistantService(repo)

    res = service.ask('tim san cau long o cau giay toi mai')
    assert res['understood'].get('sport_type') == 'cầu lông'
    assert res['understood'].get('location') == 'Cầu Giấy'
    assert res['status'] == 'OK'
