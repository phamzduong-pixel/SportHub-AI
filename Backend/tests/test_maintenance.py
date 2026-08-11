import unittest
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import get_password_hash
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.facility import Facility
from app.models.field import Booking, Field
from app.models.maintenance import FieldMaintenance
from app.models.time_slot import TimeSlot
from app.models.user import User


class MaintenanceWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(self.engine)
        self.day = date.today() + timedelta(days=10)
        with self.Session() as db:
            owner_a = User(full_name='Owner A', email='maint-owner-a@test.local', hashed_password=get_password_hash('Owner@123'), role='OWNER')
            owner_b = User(full_name='Owner B', email='maint-owner-b@test.local', hashed_password=get_password_hash('Owner@123'), role='OWNER')
            customer = User(full_name='Customer', email='maint-customer@test.local', hashed_password=get_password_hash('Customer@123'), role='CUSTOMER')
            manager = User(full_name='Manager legacy', email='maint-manager@test.local', hashed_password=get_password_hash('Manager@123'), role='MANAGER')
            db.add_all([owner_a, owner_b, customer, manager]); db.flush()
            facility_a = Facility(owner_id=owner_a.id, name='Cơ sở bảo trì A', location='A')
            facility_b = Facility(owner_id=owner_b.id, name='Cơ sở bảo trì B', location='B')
            db.add_all([facility_a, facility_b]); db.flush()
            field_a = Field(owner_id=owner_a.id, facility_id=facility_a.id, name='Sân bảo trì A', sport_type='Bóng đá', location='A', capacity=10, base_price=500000, status='available', amenities=[])
            field_b = Field(owner_id=owner_b.id, facility_id=facility_b.id, name='Sân bảo trì B', sport_type='Bóng đá', location='B', capacity=10, base_price=500000, status='available', amenities=[])
            db.add_all([field_a, field_b]); db.flush()
            slot_a = TimeSlot(field_id=field_a.id, name='Ca sáng A', start_time=time(8), end_time=time(10), price=Decimal('500000'), is_active=True)
            slot_b = TimeSlot(field_id=field_b.id, name='Ca sáng B', start_time=time(8), end_time=time(10), price=Decimal('500000'), is_active=True)
            db.add_all([slot_a, slot_b]); db.commit()
            self.owner_a_id, self.customer_id = owner_a.id, customer.id
            self.field_a_id, self.field_b_id, self.slot_a_id = field_a.id, field_b.id, slot_a.id

        def override_db():
            with self.Session() as db:
                yield db
        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)
        self.owner_a = self.login('maint-owner-a@test.local', 'Owner@123')
        self.customer = self.login('maint-customer@test.local', 'Customer@123')

    def tearDown(self):
        self.client.close(); app.dependency_overrides.clear(); Base.metadata.drop_all(self.engine)

    def login(self, email, password):
        response = self.client.post('/auth/login', json={'email': email, 'password': password})
        self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': f"Bearer {response.json()['access_token']}"}

    def at(self, hour):
        return datetime.combine(self.day, time(hour), tzinfo=ZoneInfo(settings.TIMEZONE)).isoformat()

    def payload(self, **changes):
        return {'field_id': self.field_a_id, 'maintenance_type': 'preventive', 'title': 'Bảo dưỡng mặt sân',
                'starts_at': self.at(8), 'ends_at': self.at(10), 'priority': 'HIGH', 'notes': 'Kiểm tra định kỳ',
                'estimated_cost': 1000000, 'actual_cost': None, **changes}

    def create_maintenance(self, **changes):
        response = self.client.post('/maintenance', headers=self.owner_a, json=self.payload(**changes))
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def create_booking_direct(self, booking_date=None, status='confirmed'):
        with self.Session() as db:
            booking = Booking(booking_code=f'MAINT-{datetime.now().timestamp()}', customer_id=self.customer_id,
                              field_id=self.field_a_id, time_slot_id=self.slot_a_id, booking_date=booking_date or self.day,
                              start_time_snapshot=time(8), end_time_snapshot=time(10), price_snapshot=500000,
                              total_amount=500000, deposit_amount=150000, paid_amount=150000,
                              remaining_amount=350000, payment_status='partial', status=status)
            db.add(booking); db.commit(); return booking.id

    def test_create_and_status_history(self):
        item = self.create_maintenance()
        self.assertEqual(item['status'], 'SCHEDULED')
        self.assertEqual(item['field_name'], 'Sân bảo trì A')
        started = self.client.patch(f"/maintenance/{item['id']}/start", headers=self.owner_a)
        self.assertEqual(started.json()['status'], 'IN_PROGRESS')
        completed = self.client.patch(f"/maintenance/{item['id']}/complete", headers=self.owner_a)
        self.assertEqual(completed.json()['status'], 'COMPLETED')
        history = self.client.get('/maintenance?status=COMPLETED', headers=self.owner_a).json()
        self.assertEqual([entry['id'] for entry in history], [item['id']])

    def test_owner_isolation_customer_and_legacy_manager_are_blocked(self):
        response = self.client.post('/maintenance', headers=self.owner_a, json=self.payload(field_id=self.field_b_id))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get('/maintenance', headers=self.customer).status_code, 403)
        manager = self.client.post('/auth/login', json={'email': 'maint-manager@test.local', 'password': 'Manager@123'})
        self.assertEqual(manager.status_code, 200)
        manager_headers = {'Authorization': f"Bearer {manager.json()['access_token']}"}
        self.assertEqual(self.client.get('/maintenance', headers=manager_headers).status_code, 403)

    def test_invalid_range_is_rejected(self):
        response = self.client.post('/maintenance', headers=self.owner_a, json=self.payload(ends_at=self.at(8)))
        self.assertEqual(response.status_code, 422)

    def test_maintenance_blocks_booking_and_reschedule(self):
        self.create_maintenance()
        booking = self.client.post('/bookings', headers=self.customer, json={'field_id': self.field_a_id, 'time_slot_id': self.slot_a_id, 'booking_date': self.day.isoformat(), 'note': None})
        self.assertEqual(booking.status_code, 409)
        self.assertIn('bảo trì', booking.json()['detail'])
        existing_id = self.create_booking_direct(self.day + timedelta(days=1))
        moved = self.client.patch(f'/bookings/{existing_id}/reschedule', headers=self.customer, json={'field_id': self.field_a_id, 'time_slot_id': self.slot_a_id, 'booking_date': self.day.isoformat()})
        self.assertEqual(moved.status_code, 409)
        self.assertIn('bảo trì', moved.json()['detail'])

    def test_booking_conflict_warns_without_auto_cancellation(self):
        booking_id = self.create_booking_direct()
        item = self.create_maintenance()
        self.assertEqual([booking['id'] for booking in item['affected_bookings']], [booking_id])
        with self.Session() as db:
            self.assertEqual(db.get(Booking, booking_id).status, 'confirmed')

    def test_cancel_reopens_availability(self):
        item = self.create_maintenance()
        unavailable = self.client.get(f'/availability?date={self.day}&field_id={self.field_a_id}').json()
        self.assertEqual(unavailable, [])
        cancelled = self.client.patch(f"/maintenance/{item['id']}/cancel", headers=self.owner_a)
        self.assertEqual(cancelled.json()['status'], 'CANCELLED')
        reopened = self.client.get(f'/availability?date={self.day}&field_id={self.field_a_id}').json()
        self.assertEqual([slot['id'] for slot in reopened[0]['available_slots']], [self.slot_a_id])

    def test_ai_does_not_suggest_maintenance_slot(self):
        self.create_maintenance()
        response = self.client.post('/ai/assistant', json={'message': f'Tìm sân bóng đá lúc 8 giờ ngày {self.day.isoformat()}'})
        self.assertEqual(response.status_code, 200, response.text)
        suggestions = response.json()['suggestions']
        self.assertFalse(any(item['field_id'] == self.field_a_id and item['time_slot_id'] == self.slot_a_id for item in suggestions))


if __name__ == '__main__':
    unittest.main()
