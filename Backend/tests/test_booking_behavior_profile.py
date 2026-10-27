from datetime import datetime, time, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.field import Booking, Field
from app.models.time_slot import TimeSlot
from app.models.user import User
from app.services.booking_behavior_profile_service import BookingBehaviorProfileService


@pytest.fixture
def booking_db(tmp_path):
    database_path = (tmp_path / 'booking-behavior.sqlite3').as_posix()
    engine = create_engine(
        f'sqlite:///{database_path}',
        connect_args={'check_same_thread': False, 'timeout': 30},
    )
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with session_factory() as db:
        users = [
            User(full_name='Profile User A', email='profile-a@test.local', hashed_password='unused', role='CUSTOMER'),
            User(full_name='Profile User B', email='profile-b@test.local', hashed_password='unused', role='CUSTOMER'),
        ]
        db.add_all(users)
        db.flush()
        yield db, users[0].id, users[1].id
    Base.metadata.drop_all(engine)
    engine.dispose()


def _make_field(db, *, sport: str, location: str) -> tuple[Field, TimeSlot]:
    field = Field(
        name=f'{sport} court {location}', sport_type=sport, location=location,
        capacity=4, base_price=100, status='available', amenities=[],
    )
    db.add(field)
    db.flush()
    slot = TimeSlot(
        field_id=field.id, name='Test slot', start_time=time(19), end_time=time(21), price=100,
    )
    db.add(slot)
    db.flush()
    return field, slot


def _make_booking(
    db, *, user_id: int, field: Field, slot: TimeSlot, code: str,
    status: str, created_at: datetime, start_time: time = time(19),
    payment_status: str = 'partial', refund_status: str = 'not_requested',
):
    db.add(Booking(
        booking_code=code, customer_id=user_id, field_id=field.id, time_slot_id=slot.id,
        booking_date=created_at.date(), start_time_snapshot=start_time,
        end_time_snapshot=time(21), price_snapshot=100, total_amount=100,
        deposit_amount=30, paid_amount=30, remaining_amount=70,
        payment_status=payment_status, refund_status=refund_status,
        status=status, created_at=created_at,
    ))


def test_profile_uses_only_recent_accepted_bookings_and_repeated_patterns(booking_db):
    db, user_a_id, user_b_id = booking_db
    now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
    pickleball, pickleball_slot = _make_field(db, sport='pickleball', location='Quận 1')
    pending_field, pending_slot = _make_field(db, sport='tennis', location='Quận 7')
    other_account_field, other_account_slot = _make_field(db, sport='badminton', location='Quận 3')

    _make_booking(db, user_id=user_a_id, field=pickleball, slot=pickleball_slot,
                  code='PROFILE-A-1', status='confirmed', created_at=now - timedelta(days=10),
                  start_time=time(19))
    _make_booking(db, user_id=user_a_id, field=pickleball, slot=pickleball_slot,
                  code='PROFILE-A-2', status='completed', created_at=now - timedelta(days=20),
                  start_time=time(20))
    _make_booking(db, user_id=user_a_id, field=pending_field, slot=pending_slot,
                  code='PROFILE-PENDING', status='pending_confirmation', created_at=now - timedelta(days=1))
    _make_booking(db, user_id=user_a_id, field=pending_field, slot=pending_slot,
                  code='PROFILE-CANCELLED', status='cancelled_by_customer', created_at=now - timedelta(days=2))
    _make_booking(db, user_id=user_a_id, field=pickleball, slot=pickleball_slot,
                  code='PROFILE-REFUNDED', status='completed', payment_status='refunded',
                  refund_status='refunded', created_at=now - timedelta(days=3))
    _make_booking(db, user_id=user_a_id, field=pickleball, slot=pickleball_slot,
                  code='PROFILE-OLD', status='confirmed', created_at=now - timedelta(days=200))
    _make_booking(db, user_id=user_b_id, field=other_account_field, slot=other_account_slot,
                  code='PROFILE-B-1', status='confirmed', created_at=now - timedelta(days=5))
    _make_booking(db, user_id=user_b_id, field=other_account_field, slot=other_account_slot,
                  code='PROFILE-B-2', status='completed', created_at=now - timedelta(days=6))
    db.commit()

    profile = BookingBehaviorProfileService.build(db, user_a_id, now=now)

    assert profile is not None
    assert profile['eligible_booking_count'] == 2
    assert profile['latest_booking_created_at'] == (now - timedelta(days=10)).isoformat()
    assert profile['repeated_sports'] == [{'value': 'pickleball', 'count': 2}]
    assert profile['repeated_time_windows'] == [{'value': 'buổi tối', 'count': 2}]
    assert profile['repeated_locations'] == [{'value': 'Quận 1', 'count': 2}]


def test_one_booking_is_reported_without_becoming_a_repeated_preference(booking_db):
    db, user_a_id, _ = booking_db
    now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
    field, slot = _make_field(db, sport='tennis', location='Quận 5')
    _make_booking(db, user_id=user_a_id, field=field, slot=slot,
                  code='PROFILE-ONLY-ONE', status='confirmed', created_at=now - timedelta(days=2))
    db.commit()

    profile = BookingBehaviorProfileService.build(db, user_a_id, now=now)

    assert profile is not None
    assert profile['eligible_booking_count'] == 1
    assert profile['repeated_sports'] == []
    assert profile['repeated_time_windows'] == []
    assert profile['repeated_locations'] == []


def test_rolling_window_drops_old_booking_patterns(booking_db):
    db, user_a_id, _ = booking_db
    first_now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
    field, slot = _make_field(db, sport='football', location='Quận 10')
    for index in range(2):
        _make_booking(db, user_id=user_a_id, field=field, slot=slot,
                      code=f'PROFILE-AGING-{index}', status='completed',
                      created_at=first_now - timedelta(days=10 + index))
    db.commit()

    assert BookingBehaviorProfileService.build(db, user_a_id, now=first_now)['repeated_sports']
    assert BookingBehaviorProfileService.build(
        db, user_a_id, now=first_now + timedelta(days=200),
    ) is None
