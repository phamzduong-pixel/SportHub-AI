import unittest
from datetime import datetime, time, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_password_hash
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.field import Booking, Field, FieldStatus
from app.models.time_slot import TimeSlot
from app.models.user import User, UserRole

class TimeSlotTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        self.TestingSession = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(self.engine)
        with self.TestingSession() as db:
            field = Field(
                name='Sân kiểm thử', sport_type='Bóng đá', location='Quận 1',
                capacity=22, base_price=Decimal('300000'), status=FieldStatus.AVAILABLE.value,
                amenities=[],
            )
            operator = User(full_name='Slot Operator', email='slotoperator@test.local', hashed_password=get_password_hash('Operator@123'), role=UserRole.CUSTOMER.value)
            db.add_all([
                field,
                User(full_name='Owner', email='slotowner@test.local', hashed_password=get_password_hash('Owner@123456'), role=UserRole.OWNER.value),
                operator,
                User(full_name='No Permission', email='nopermission@test.local', hashed_password=get_password_hash('Operator@123'), role=UserRole.CUSTOMER.value),
                User(full_name='Customer', email='slotcustomer@test.local', hashed_password=get_password_hash('Customer@123'), role=UserRole.CUSTOMER.value),
            ])
            db.commit()
            self.field_id = field.id

        def override_db():
            with self.TestingSession() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)
        self.owner = self.login('slotowner@test.local', 'Owner@123456')
        self.operator = self.owner
        self.no_permission = self.login('nopermission@test.local', 'Operator@123')
        self.customer = self.login('slotcustomer@test.local', 'Customer@123')

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)

    def login(self, email: str, password: str):
        response = self.client.post('/auth/login', json={'email': email, 'password': password})
        self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': f"Bearer {response.json()['access_token']}"}

    def payload(self, **changes):
        return {
            'field_id': self.field_id, 'name': 'Khung giờ 1',
            'start_time': '08:00', 'end_time': '10:00',
            'price': 400000, 'is_active': True, **changes,
        }

    def create_slot(self, headers=None, **changes):
        response = self.client.post('/time-slots', headers=headers or self.owner, json=self.payload(**changes))
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_owner_crud_and_boundary_times(self):
        first = self.create_slot()
        second = self.create_slot(name='Khung giờ 2', start_time='10:00', end_time='12:00')
        listing = self.client.get(f'/time-slots?field_id={self.field_id}', headers=self.owner)
        self.assertEqual([item['id'] for item in listing.json()], [first['id'], second['id']])
        by_field = self.client.get(f'/fields/{self.field_id}/time-slots', headers=self.owner)
        self.assertEqual(len(by_field.json()), 2)
        updated = self.client.put(f"/time-slots/{first['id']}", headers=self.owner, json=self.payload(name='Giờ sáng', start_time='07:00', end_time='09:00', price=450000))
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()['price'], 450000)
        locked = self.client.patch(f"/time-slots/{first['id']}/status", headers=self.owner, json={'is_active': False})
        self.assertFalse(locked.json()['is_active'])
        opened = self.client.patch(f"/time-slots/{first['id']}/status", headers=self.owner, json={'is_active': True})
        self.assertTrue(opened.json()['is_active'])
        deleted = self.client.delete(f"/time-slots/{first['id']}", headers=self.owner)
        self.assertEqual(deleted.json()['action'], 'deleted')

    def test_active_overlap_and_validation(self):
        self.create_slot()
        overlap = self.client.post('/time-slots', headers=self.owner, json=self.payload(name='Bị trùng', start_time='09:30', end_time='11:00'))
        self.assertEqual(overlap.status_code, 409)
        self.assertIn('chồng lấn', overlap.json()['detail'])
        inactive = self.create_slot(name='Đang khóa', start_time='09:00', end_time='11:00', is_active=False)
        cannot_open = self.client.patch(f"/time-slots/{inactive['id']}/status", headers=self.owner, json={'is_active': True})
        self.assertEqual(cannot_open.status_code, 409)
        invalid_order = self.client.post('/time-slots', headers=self.owner, json=self.payload(start_time='12:00', end_time='11:00'))
        self.assertEqual(invalid_order.status_code, 422)
        negative_price = self.client.post('/time-slots', headers=self.owner, json=self.payload(price=-1))
        self.assertEqual(negative_price.status_code, 422)

    def test_owner_operator_and_customer_permissions(self):
        slot = self.create_slot(headers=self.operator)
        self.assertEqual(self.client.put(f"/time-slots/{slot['id']}", headers=self.operator, json=self.payload(name='Operator sửa')).status_code, 200)
        self.assertEqual(self.client.get('/time-slots', headers=self.no_permission).status_code, 403)
        self.assertEqual(self.client.post('/time-slots', headers=self.no_permission, json=self.payload()).status_code, 403)
        self.assertEqual(self.client.get('/time-slots', headers=self.customer).status_code, 403)
        self.assertEqual(len(self.client.get(f'/fields/{self.field_id}/time-slots', headers=self.customer).json()), 1)
        self.client.patch(f"/time-slots/{slot['id']}/status", headers=self.operator, json={'is_active': False})
        self.assertEqual(self.client.get(f'/fields/{self.field_id}/time-slots', headers=self.customer).json(), [])
        self.assertEqual(len(self.client.get(f'/fields/{self.field_id}/time-slots', headers=self.operator).json()), 1)

    def test_used_slot_is_locked_and_booking_snapshot_does_not_change(self):
        slot = self.create_slot()
        with self.TestingSession() as db:
            customer = db.scalar(select(User).where(User.email == 'slotcustomer@test.local'))
            booking = Booking(
                booking_code='SH-SLOT-USED', customer_id=customer.id, field_id=self.field_id,
                time_slot_id=slot['id'], booking_date=datetime.now(timezone.utc).date(),
                start_time_snapshot=time(8), end_time_snapshot=time(10),
                price_snapshot=Decimal('400000'), total_amount=Decimal('400000'), status='confirmed',
            )
            db.add(booking)
            db.commit()
        updated = self.client.put(f"/time-slots/{slot['id']}", headers=self.owner, json=self.payload(name='Giờ mới', start_time='13:00', end_time='15:00', price=700000))
        self.assertEqual(updated.status_code, 200)
        with self.TestingSession() as db:
            snapshot = db.scalar(select(Booking).where(Booking.time_slot_id == slot['id']))
            self.assertEqual(snapshot.start_time_snapshot, time(8, 0))
            self.assertEqual(snapshot.end_time_snapshot, time(10, 0))
            self.assertEqual(snapshot.price_snapshot, Decimal('400000.00'))
        deleted = self.client.delete(f"/time-slots/{slot['id']}", headers=self.owner)
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json()['action'], 'deactivated')
        self.assertFalse(deleted.json()['time_slot']['is_active'])

if __name__ == '__main__':
    unittest.main()
