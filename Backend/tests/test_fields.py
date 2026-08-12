import unittest
from datetime import datetime, timedelta, time, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_password_hash
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.field import Booking
from app.models.facility import Facility
from app.models.time_slot import TimeSlot
from app.models.user import User, UserRole

FIELD_PAYLOAD = {
    'name': 'Sân bóng trung tâm',
    'sport_type': 'Bóng đá',
    'description': 'Sân cỏ nhân tạo tiêu chuẩn',
    'location': 'Quận 1, TP.HCM',
    'capacity': 22,
    'base_price': 500000,
    'status': 'available',
    'image_url': 'https://example.com/field.jpg',
    'amenities': ['Bãi xe', 'Phòng thay đồ'],
}

class FieldCrudTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        self.TestingSession = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(self.engine)
        with self.TestingSession() as db:
            users = [
                User(full_name='Owner', email='owner@fields.local', hashed_password=get_password_hash('Owner@123456'), role=UserRole.OWNER.value),
                User(full_name='Customer', email='customer@fields.local', hashed_password=get_password_hash('Customer@123'), role=UserRole.CUSTOMER.value),
                User(full_name='Operator', email='operator@fields.local', hashed_password=get_password_hash('Operator@123'), role=UserRole.CUSTOMER.value),
                User(full_name='No View Operator', email='noview@fields.local', hashed_password=get_password_hash('Operator@123'), role=UserRole.CUSTOMER.value),
            ]
            db.add_all(users)
            db.flush()
            facility = Facility(owner_id=users[0].id, name='Cơ sở đã duyệt', location='Quận 1, TP.HCM', status='APPROVED', is_active=True)
            db.add(facility)
            db.commit()
            self.facility_id = facility.id

        def override_db():
            with self.TestingSession() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)
        self.owner = self.login('owner@fields.local', 'Owner@123456')
        self.customer = self.login('customer@fields.local', 'Customer@123')
        self.operator = self.owner
        self.no_view_operator = self.login('noview@fields.local', 'Operator@123')

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)

    def login(self, email: str, password: str):
        response = self.client.post('/auth/login', json={'email': email, 'password': password})
        self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': f"Bearer {response.json()['access_token']}"}

    def create_field(self, payload=None):
        data = {**(payload or FIELD_PAYLOAD), 'facility_id': self.facility_id}
        response = self.client.post('/fields', headers=self.owner, json=data)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_owner_crud_search_filter_and_pagination(self):
        first = self.create_field()
        second = self.create_field({**FIELD_PAYLOAD, 'name': 'Sân cầu lông A', 'sport_type': 'Cầu lông', 'status': 'maintenance'})
        listing = self.client.get('/fields?search=cầu&sport_type=Cầu lông&status=maintenance&page=1&page_size=1', headers=self.owner)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()['total'], 1)
        self.assertEqual(listing.json()['pages'], 1)
        self.assertEqual(listing.json()['items'][0]['id'], second['id'])
        detail = self.client.get(f"/fields/{first['id']}", headers=self.owner)
        self.assertEqual(detail.status_code, 200)
        updated = self.client.put(f"/fields/{first['id']}", headers=self.owner, json={**FIELD_PAYLOAD, 'name': 'Sân bóng đã sửa', 'base_price': 650000})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()['name'], 'Sân bóng đã sửa')
        status = self.client.patch(f"/fields/{first['id']}/status", headers=self.owner, json={'status': 'inactive'})
        self.assertEqual(status.json()['status'], 'inactive')
        deleted = self.client.delete(f"/fields/{first['id']}", headers=self.owner)
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json()['action'], 'deleted')
        self.assertEqual(self.client.get(f"/fields/{first['id']}", headers=self.owner).status_code, 404)

    def test_customer_and_public_only_see_available_fields(self):
        available = self.create_field()
        maintenance = self.create_field({**FIELD_PAYLOAD, 'name': 'Sân bảo trì', 'status': 'maintenance'})
        for headers in ({}, self.customer):
            listing = self.client.get('/fields?status=maintenance', headers=headers)
            self.assertEqual(listing.status_code, 200)
            self.assertEqual([item['id'] for item in listing.json()['items']], [available['id']])
            self.assertEqual(self.client.get(f"/fields/{maintenance['id']}", headers=headers).status_code, 404)
        self.assertEqual(self.client.post('/fields', headers=self.customer, json=FIELD_PAYLOAD).status_code, 403)

    def test_owner_has_full_field_access_and_customer_cannot_mutate(self):
        viewed = self.create_field()
        self.assertEqual(self.client.get('/fields', headers=self.operator).status_code, 200)
        self.assertEqual(self.client.get('/fields', headers=self.no_view_operator).status_code, 200)
        self.assertEqual(self.client.get(f"/fields/{viewed['id']}", headers=self.no_view_operator).status_code, 200)
        created = self.client.post('/fields', headers=self.operator, json={**FIELD_PAYLOAD, 'facility_id': self.facility_id, 'name': 'Sân do Operator tạo'})
        self.assertEqual(created.status_code, 201)
        field_id = viewed['id']
        self.assertEqual(self.client.put(f'/fields/{field_id}', headers=self.operator, json=FIELD_PAYLOAD).status_code, 200)
        self.assertEqual(self.client.patch(f'/fields/{field_id}/status', headers=self.operator, json={'status': 'inactive'}).status_code, 200)
        self.assertEqual(self.client.post('/fields', headers=self.no_view_operator, json=FIELD_PAYLOAD).status_code, 403)

    def test_future_booking_deactivates_instead_of_physical_delete(self):
        field = self.create_field()
        with self.TestingSession() as db:
            customer = db.scalar(select(User).where(User.email == 'customer@fields.local'))
            slot = TimeSlot(field_id=field['id'], name='Slot future', start_time=time(8), end_time=time(10), price=Decimal('500000'), is_active=True)
            db.add(slot); db.flush()
            future_date = (datetime.now(timezone.utc) + timedelta(days=2)).date()
            db.add(Booking(
                booking_code='SH-FIELD-FUTURE', customer_id=customer.id, field_id=field['id'], time_slot_id=slot.id,
                booking_date=future_date, start_time_snapshot=time(8), end_time_snapshot=time(10),
                price_snapshot=Decimal('500000'), total_amount=Decimal('500000'), status='confirmed',
            ))
            db.commit()
        deleted = self.client.delete(f"/fields/{field['id']}", headers=self.owner)
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json()['action'], 'deactivated')
        self.assertEqual(deleted.json()['field']['status'], 'inactive')
        detail = self.client.get(f"/fields/{field['id']}", headers=self.owner)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()['status'], 'inactive')

    def test_validation(self):
        invalid = self.client.post('/fields', headers=self.owner, json={**FIELD_PAYLOAD, 'capacity': 0, 'base_price': -1, 'image_url': 'invalid-url'})
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(self.client.get('/fields?page=0&page_size=101').status_code, 422)

    def test_past_booking_also_prevents_physical_delete(self):
        field = self.create_field({**FIELD_PAYLOAD, 'name': 'Sân có lịch sử'})
        with self.TestingSession() as db:
            customer = db.scalar(select(User).where(User.email == 'customer@fields.local'))
            slot = TimeSlot(field_id=field['id'], name='Slot history', start_time=time(6), end_time=time(8), price=Decimal('300000'), is_active=True)
            db.add(slot); db.flush()
            db.add(Booking(
                booking_code='SH-FIELD-HISTORY', customer_id=customer.id, field_id=field['id'], time_slot_id=slot.id,
                booking_date=(datetime.now(timezone.utc) - timedelta(days=7)).date(),
                start_time_snapshot=time(6), end_time_snapshot=time(8),
                price_snapshot=Decimal('300000'), total_amount=Decimal('300000'), status='completed',
            )); db.commit()
        response = self.client.delete(f"/fields/{field['id']}", headers=self.owner)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['action'], 'deactivated')

if __name__ == '__main__':
    unittest.main()
