from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.facility import Facility
from app.models.field import Field, Booking
from app.models.time_slot import TimeSlot
from app.models.user import User
from app.schemas.ai import SlotRecommendationRequest
from app.services.ai_feature_service import AIFeatureService
from app.services.availability_service import AvailabilityService
from app.repositories.booking_repository import BookingRepository


@pytest.fixture
def phase3_db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    owner = User(
        id=1, email='owner_p3@sporthub.vn',
        role='OWNER', full_name='Owner Phase 3',
        hashed_password='hashed_pw', is_active=True,
    )
    customer = User(
        id=2, email='customer_p3@sporthub.vn',
        role='CUSTOMER', full_name='Customer Phase 3',
        hashed_password='hashed_pw', is_active=True,
    )
    facility = Facility(
        id=1, owner_id=1, name='Facility Phase 3',
        is_active=True, status='APPROVED', location='123 Phase 3 St'
    )
    field = Field(
        id=1, facility_id=1, owner_id=1, name='San 1',
        sport_type='Bong da', status='available', location='123 Phase 3 St', capacity=10, base_price=Decimal('100000')
    )
    session.add_all([owner, customer, facility, field])
    session.commit()

    # Create 3 slots: 08:00-09:00, 10:00-11:00, 14:00-15:00
    # Notice the gap between them.
    slots = [
        TimeSlot(id=1, field_id=1, start_time=time(8, 0), end_time=time(9, 0), price=Decimal('100000'), is_active=True, name='08:00-09:00'),
        TimeSlot(id=2, field_id=1, start_time=time(10, 0), end_time=time(11, 0), price=Decimal('100000'), is_active=True, name='10:00-11:00'),
        TimeSlot(id=3, field_id=1, start_time=time(14, 0), end_time=time(15, 0), price=Decimal('100000'), is_active=True, name='14:00-15:00'),
    ]
    session.add_all(slots)
    session.commit()

    yield session
    session.close()

class DummyProvider:
    def generate_json(self, task, system_data, schema):
        if task == 'summarize_occupancy_and_suggest_promotions':
            return {
                'summary': 'Chung',
                'peak_slot_ids': [1],
                'low_demand_slot_ids': [2],
                'promotions': [{'slot_id': 2, 'suggestion': 'GiÃƒÆ’Ã‚Â¡Ãƒâ€šÃ‚ÂºÃƒâ€šÃ‚Â£m 20% vÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â o khung giÃƒÆ’Ã‚Â¡Ãƒâ€šÃ‚Â»Ãƒâ€šÃ‚Â nÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â y'}]
            }
        # Mocking rank_available_slots to pass everything through
        recommendations = []
        for opt in system_data.get('available_slots', []):
            recommendations.append({'court_id': opt['court_id'], 'slot_id': opt['slot_ids'][0], 'reason': 'ok'})
        return {'status': 'OK', 'recommendations': recommendations}

def test_non_consecutive_slots(phase3_db):
    service = AIFeatureService(phase3_db, provider=DummyProvider())
    tomorrow = date.today() + timedelta(days=1)
    
    request = SlotRecommendationRequest(
        sport_type='Bong da',
        booking_date=tomorrow,
        duration_minutes=120, # 2 hours
    )
    
    result = service.recommend_slots(request)
    assert result['status'] == 'OK'
    recs = result['recommendations']
    # 3 slots, length 1 each. We asked for 120 minutes (2 slots).
    # Since they are not consecutive, older logic would fail.
    # New logic should find combination of (Slot 1, Slot 2) or (1, 3) or (2, 3)
    assert len(recs) > 0

def test_availability_filtering_booked(phase3_db):
    tomorrow = date.today() + timedelta(days=1)
    # Book the 08:00 slot
    b = Booking(
        id=1, customer_id=2, field_id=1, facility_id=1,
        booking_date=tomorrow, status='confirmed',
        start_time_snapshot=time(8, 0), end_time_snapshot=time(9, 0),
        total_amount=Decimal('100000'), booking_code='TEST1', time_slot_id=1, price_snapshot=Decimal('100000'),
    )
    phase3_db.add(b)
    phase3_db.commit()

    service = AIFeatureService(phase3_db, provider=DummyProvider())
    
    request = SlotRecommendationRequest(
        sport_type='Bong da',
        booking_date=tomorrow,
        duration_minutes=60,
    )
    
    result = service.recommend_slots(request)
    assert result['status'] == 'OK'
    
    # 08:00 (slot 1) should be excluded
    slot_ids = [r['slot_id'] for r in result['recommendations']]
    assert 1 not in slot_ids
    assert 2 in slot_ids
    assert 3 in slot_ids