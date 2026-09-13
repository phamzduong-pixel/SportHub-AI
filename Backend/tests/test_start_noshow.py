from datetime import datetime, time, timedelta, timezone, date
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.field import Booking, BookingStatus, Field, BookingSlot
from app.models.facility import Facility
from app.models.user import User
from app.api.dependencies import get_current_user, require_owner

@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def owner(db):
    user = User(email="owner_start@test.com", hashed_password="hash", full_name="Owner", role="OWNER", is_active=True, phone="0999999999")
    db.add(user)
    db.commit()
    return user

@pytest.fixture
def field(db, owner):
    facility = Facility(name="Facility Start", location="Address", owner_id=owner.id, status="APPROVED", is_active=True)
    db.add(facility)
    db.flush()
    field = Field(
        facility_id=facility.id,
        owner_id=owner.id,
        name="Sân Start",
        sport_type="Bóng đá",
        location="Address",
        capacity=10,
        base_price=100000,
        status="available",
    )
    db.add(field)
    db.flush()
    from app.models.time_slot import TimeSlot
    slot = TimeSlot(
        id=1,
        field_id=field.id,
        name="Ca 1",
        start_time=time(6, 0),
        end_time=time(23, 0),
        price=Decimal("100"),
        is_active=True,
    )
    db.add(slot)
    db.commit()
    return field

def test_early_start_requires_confirm(client, db, owner, field):
    tz = timezone(timedelta(hours=7))
    now = datetime.now(tz)
    future_time = (now + timedelta(hours=2)).time()
    
    booking = Booking(
        booking_code="START01",
        customer_id=owner.id,
        field_id=field.id,
        time_slot_id=1,
        booking_date=now.date(),
        start_time_snapshot=future_time,
        end_time_snapshot=(now + timedelta(hours=3)).time(),
        price_snapshot=100, total_amount=100, deposit_amount=0, paid_amount=0, remaining_amount=100,
        status=BookingStatus.CONFIRMED.value
    )
    db.add(booking)
    db.commit()

    client.app.dependency_overrides[require_owner] = lambda: owner

    # 1. Early start fails without confirm
    res = client.patch(f"/bookings/{booking.id}/start", json={})
    assert res.status_code == 400
    assert "Vui lòng xác nhận để bắt đầu sớm" in res.json()["detail"]

    # 2. Early start succeeds with confirm
    res = client.patch(f"/bookings/{booking.id}/start", json={"confirm_early": True})
    assert res.status_code == 200
    assert res.json()["status"] == "in_progress"
    
    client.app.dependency_overrides.clear()

def test_noshow_early_fails(client, db, owner, field):
    tz = timezone(timedelta(hours=7))
    now = datetime.now(tz)
    future_time = (now + timedelta(hours=1)).time()
    
    booking = Booking(
        booking_code="NOSHOW01",
        customer_id=owner.id,
        field_id=field.id,
        time_slot_id=1,
        booking_date=now.date(),
        start_time_snapshot=future_time,
        end_time_snapshot=(now + timedelta(hours=2)).time(),
        price_snapshot=100, total_amount=100, deposit_amount=0, paid_amount=0, remaining_amount=100,
        status=BookingStatus.CONFIRMED.value
    )
    db.add(booking)
    db.commit()
    
    client.app.dependency_overrides[require_owner] = lambda: owner

    res = client.patch(f"/bookings/{booking.id}/no-show", json={})
    assert res.status_code == 409
    assert "Chưa đến giờ no-show" in res.json()["detail"]
    
    client.app.dependency_overrides.clear()
