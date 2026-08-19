import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.models.field import Booking, BookingStatus, Field
from app.models.review import Review
from app.models.user import User
from app.api.dependencies import get_current_user
from app.database.session import get_db

client = TestClient(app)

def test_completed_booking_can_be_reviewed():
    mock_db = MagicMock()
    mock_booking = Booking(id=10, customer_id=1, field_id=5, status=BookingStatus.COMPLETED.value)
    
    def mock_get(model, pk):
        if model == Booking and pk == 10:
            return mock_booking
        if model == Field and pk == 5:
            return Field(id=5, rating=0, review_count=0)
        return None
    mock_db.get.side_effect = mock_get
    
    # First scalar call checks if review exists (return None).
    from datetime import datetime, timezone
    mock_review = Review(id=1, booking_id=10, customer_id=1, field_id=5, rating=5, comment="Great", customer=User(full_name="Test User"), field=Field(name="Test Field"), created_at=datetime.now(timezone.utc))
    mock_db.scalar.side_effect = [None, mock_review]
    mock_db.execute.return_value.one.return_value = (5.0, 1)
    
    user = User(id=1, email="test@example.com", full_name="Test User", role="CUSTOMER")
    
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db
    
    response = client.post("/reviews", json={"booking_id": 10, "rating": 5, "comment": "Great field!"})
    
    assert response.status_code == 201
    assert response.json()["rating"] == 5
    app.dependency_overrides.clear()

def test_cannot_review_twice():
    mock_db = MagicMock()
    mock_booking = Booking(id=10, customer_id=1, field_id=5, status=BookingStatus.COMPLETED.value)
    mock_db.get.return_value = mock_booking
    mock_db.scalar.return_value = 1  # Review ID already exists
    
    user = User(id=1, email="test@example.com", full_name="Test User", role="CUSTOMER")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db
    
    response = client.post("/reviews", json={"booking_id": 10, "rating": 5, "comment": "Great field!"})
    
    assert response.status_code == 409
    assert response.json()["detail"] == "Booking này đã được đánh giá"
    app.dependency_overrides.clear()

def test_uncompleted_booking_cannot_be_reviewed():
    mock_db = MagicMock()
    # status is not COMPLETED
    mock_booking = Booking(id=10, customer_id=1, field_id=5, status=BookingStatus.CONFIRMED.value)
    mock_db.get.return_value = mock_booking
    
    user = User(id=1, email="test@example.com", full_name="Test User", role="CUSTOMER")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db
    
    response = client.post("/reviews", json={"booking_id": 10, "rating": 5, "comment": "Great field!"})
    
    assert response.status_code == 409
    assert response.json()["detail"] == "Chỉ được đánh giá sau khi booking hoàn thành"
    app.dependency_overrides.clear()

def test_cannot_review_others_booking():
    mock_db = MagicMock()
    # Booking belongs to user 2
    mock_booking = Booking(id=10, customer_id=2, field_id=5, status=BookingStatus.COMPLETED.value)
    mock_db.get.return_value = mock_booking
    
    user = User(id=1, email="test@example.com", full_name="Test User", role="CUSTOMER")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db
    
    response = client.post("/reviews", json={"booking_id": 10, "rating": 5, "comment": "Great field!"})
    
    assert response.status_code == 404
    assert response.json()["detail"] == "Không tìm thấy booking của bạn"
    app.dependency_overrides.clear()

def test_invalid_rating():
    user = User(id=1, email="test@example.com", full_name="Test User", role="CUSTOMER")
    app.dependency_overrides[get_current_user] = lambda: user
    
    response = client.post("/reviews", json={"booking_id": 10, "rating": 6, "comment": "Great field!"})
    
    # Validation error from pydantic
    assert response.status_code == 422
    app.dependency_overrides.clear()
