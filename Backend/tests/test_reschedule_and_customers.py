import os
import tempfile
import threading
import unittest
from datetime import date, time, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.security import get_password_hash
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.facility import Facility
from app.models.field import Booking, Field
from app.models.payment import Payment
from app.models.time_slot import TimeSlot
from app.models.user import User


class RescheduleAndCustomerManagementTests(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = handle.name
        handle.close()
        self.engine = create_engine(f'sqlite:///{self.db_path}', connect_args={'check_same_thread': False, 'timeout': 10})
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(self.engine)
        self.future = date.today() + timedelta(days=14)
        with self.Session() as db:
            owner_a = User(full_name='Owner A', email='owner-a@test.local', hashed_password=get_password_hash('Owner@123'), role='OWNER')
            owner_b = User(full_name='Owner B', email='owner-b@test.local', hashed_password=get_password_hash('Owner@123'), role='OWNER')
            customer_a = User(full_name='Customer A', email='customer-a@test.local', phone='0901000001', hashed_password=get_password_hash('Customer@123'), role='CUSTOMER')
            customer_b = User(full_name='Customer B', email='customer-b@test.local', phone='0901000002', hashed_password=get_password_hash('Customer@123'), role='CUSTOMER')
            db.add_all([owner_a, owner_b, customer_a, customer_b]); db.flush()
            facility_a = Facility(owner_id=owner_a.id, name='Cơ sở A', location='A', is_active=True)
            facility_b = Facility(owner_id=owner_b.id, name='Cơ sở B', location='B', is_active=True)
            db.add_all([facility_a, facility_b]); db.flush()
            field_a = Field(owner_id=owner_a.id, facility_id=facility_a.id, name='Sân A', sport_type='Bóng đá', location='A', capacity=10, base_price=500000, status='available', amenities=[], deposit_type='percentage', deposit_value=30)
            field_b = Field(owner_id=owner_b.id, facility_id=facility_b.id, name='Sân B', sport_type='Cầu lông', location='B', capacity=4, base_price=300000, status='available', amenities=[])
            db.add_all([field_a, field_b]); db.flush()
            slot_a1 = TimeSlot(field_id=field_a.id, name='Ca 1', start_time=time(8), end_time=time(9), price=500000, is_active=True)
            slot_a2 = TimeSlot(field_id=field_a.id, name='Ca 2', start_time=time(9), end_time=time(10), price=700000, is_active=True)
            slot_a3 = TimeSlot(field_id=field_a.id, name='Ca 3', start_time=time(10), end_time=time(11), price=300000, is_active=True)
            slot_b = TimeSlot(field_id=field_b.id, name='Ca B', start_time=time(8), end_time=time(9), price=300000, is_active=True)
            db.add_all([slot_a1, slot_a2, slot_a3, slot_b]); db.flush()
            booking_a = self._booking(customer_a.id, field_a, slot_a1, 'RS-A', self.future, 'confirmed', 500000, 150000)
            booking_b = self._booking(customer_b.id, field_a, slot_a1, 'RS-B', self.future + timedelta(days=1), 'confirmed', 500000, 150000)
            cross = self._booking(customer_a.id, field_b, slot_b, 'RS-CROSS', self.future - timedelta(days=2), 'completed', 300000, 300000)
            db.add_all([booking_a, booking_b, cross]); db.flush()
            db.add_all([
                self._payment(booking_a, customer_a.id, owner_a.id, 'PAY-A', 150000),
                self._payment(cross, customer_a.id, owner_b.id, 'PAY-CROSS', 300000),
            ])
            db.commit()
            self.owner_a_id, self.customer_a_id = owner_a.id, customer_a.id
            self.field_a_id, self.slot_a1_id, self.slot_a2_id, self.slot_a3_id = field_a.id, slot_a1.id, slot_a2.id, slot_a3.id
            self.booking_a_id, self.booking_b_id = booking_a.id, booking_b.id

        def override_db():
            with self.Session() as db:
                yield db
        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)
        self.owner_a = self.login('owner-a@test.local', 'Owner@123')
        self.owner_b = self.login('owner-b@test.local', 'Owner@123')
        self.customer_a = self.login('customer-a@test.local', 'Customer@123')
        self.customer_b = self.login('customer-b@test.local', 'Customer@123')

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.engine.dispose()
        os.unlink(self.db_path)

    @staticmethod
    def _booking(customer_id, field, slot, code, booking_date, status, total, paid):
        return Booking(
            booking_code=code, customer_id=customer_id, facility_id=field.facility_id,
            facility_name_snapshot=field.facility.name if field.facility else field.name,
            field_id=field.id, time_slot_id=slot.id, booking_date=booking_date,
            start_time_snapshot=slot.start_time, end_time_snapshot=slot.end_time,
            price_snapshot=total, total_amount=total, deposit_type='percentage', deposit_value=30,
            deposit_amount=Decimal(total) * Decimal('0.3'), paid_amount=paid,
            remaining_amount=Decimal(total) - Decimal(paid), payment_status='partial' if paid else 'unpaid', status=status,
        )

    @staticmethod
    def _payment(booking, customer_id, owner_id, code, amount):
        return Payment(
            booking_id=booking.id, customer_id=customer_id, owner_id=owner_id,
            transaction_code=code, amount=amount, total_amount=booking.total_amount,
            deposit_amount=booking.deposit_amount, remaining_amount=booking.remaining_amount,
            paid_amount=amount, payment_status='paid', payment_method='bank_transfer',
            payment_type='deposit', status='paid', escrow_status='held',
        )

    def login(self, email, password):
        response = self.client.post('/auth/login', json={'email': email, 'password': password})
        self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': f"Bearer {response.json()['access_token']}"}

    def target(self, booking_date=None):
        return {'field_id': self.field_a_id, 'time_slot_id': self.slot_a2_id, 'booking_date': (booking_date or self.future).isoformat()}

    def test_customer_reschedule_success_reprices_and_keeps_payment_history(self):
        quote = self.client.post(f'/bookings/{self.booking_a_id}/reschedule/quote', headers=self.customer_a, json=self.target())
        self.assertEqual(quote.status_code, 200, quote.text)
        self.assertEqual(quote.json()['additional_payment_required'], 200000)
        response = self.client.patch(f'/bookings/{self.booking_a_id}/reschedule', headers=self.customer_a, json=self.target())
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body['total_amount'], 700000)
        self.assertEqual(body['paid_amount'], 150000)
        self.assertEqual(body['additional_payment_required'], 200000)
        self.assertEqual(body['timeline'][-1]['action'], 'booking_rescheduled')
        with self.Session() as db:
            self.assertEqual(len(db.scalars(select(Payment).where(Payment.booking_id == self.booking_a_id)).all()), 1)

    def test_reschedule_rejects_conflict_wrong_owner_and_invalid_status(self):
        blocker = self.client.patch(f'/bookings/{self.booking_b_id}/reschedule', headers=self.customer_b, json=self.target())
        self.assertEqual(blocker.status_code, 200, blocker.text)
        conflict = self.client.patch(f'/bookings/{self.booking_a_id}/reschedule', headers=self.customer_a, json=self.target())
        self.assertEqual(conflict.status_code, 409)
        self.assertIn('vừa được người khác đặt', conflict.json()['detail'])
        self.assertEqual(self.client.patch(f'/bookings/{self.booking_a_id}/reschedule', headers=self.customer_b, json=self.target(self.future + timedelta(days=3))).status_code, 403)
        with self.Session() as db:
            booking = db.get(Booking, self.booking_a_id); booking.status = 'completed'; db.commit()
        self.assertEqual(self.client.patch(f'/bookings/{self.booking_a_id}/reschedule', headers=self.customer_a, json=self.target(self.future + timedelta(days=3))).status_code, 409)

    def test_lower_price_records_credit_without_fabricating_refund(self):
        payload = {'field_id': self.field_a_id, 'time_slot_id': self.slot_a3_id, 'booking_date': self.future.isoformat()}
        response = self.client.patch(f'/bookings/{self.booking_a_id}/reschedule', headers=self.customer_a, json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['credit_amount'], 200000)
        self.assertEqual(response.json()['refund_status'], 'not_requested')
        with self.Session() as db:
            payments = db.scalars(select(Payment).where(Payment.booking_id == self.booking_a_id)).all()
            self.assertEqual(len(payments), 1)
            self.assertNotEqual(payments[0].payment_type, 'refund')

    def test_reschedule_respects_configured_lead_time(self):
        with self.Session() as db:
            booking = db.get(Booking, self.booking_a_id)
            booking.free_cancellation_minutes = 30 * 24 * 60
            db.commit()
        response = self.client.patch(f'/bookings/{self.booking_a_id}/reschedule', headers=self.customer_a, json=self.target())
        self.assertEqual(response.status_code, 409)
        self.assertIn('trước giờ bắt đầu', response.json()['detail'])

    def test_two_reschedules_to_same_slot_only_one_succeeds(self):
        target_date = self.future + timedelta(days=5)
        barrier = threading.Barrier(2)
        statuses = []
        def move(booking_id, headers):
            barrier.wait()
            with TestClient(app) as client:
                statuses.append(client.patch(f'/bookings/{booking_id}/reschedule', headers=headers, json=self.target(target_date)).status_code)
        first = threading.Thread(target=move, args=(self.booking_a_id, self.customer_a))
        second = threading.Thread(target=move, args=(self.booking_b_id, self.customer_b))
        first.start(); second.start(); first.join(); second.join()
        self.assertEqual(sorted(statuses), [200, 409])

    def test_owner_customer_list_and_detail_are_strictly_isolated(self):
        owner_a_list = self.client.get('/management/customers', headers=self.owner_a)
        self.assertEqual(owner_a_list.status_code, 200, owner_a_list.text)
        self.assertEqual({item['id'] for item in owner_a_list.json()['items']}, {self.customer_a_id, self.booking_customer_id(self.booking_b_id)})
        customer = next(item for item in owner_a_list.json()['items'] if item['id'] == self.customer_a_id)
        self.assertEqual(customer['valid_transaction_value'], 150000)
        detail = self.client.get(f'/management/customers/{self.customer_a_id}', headers=self.owner_a)
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual([item['booking_code'] for item in detail.json()['bookings']], ['RS-A'])
        owner_b_detail = self.client.get(f'/management/customers/{self.booking_customer_id(self.booking_b_id)}', headers=self.owner_b)
        self.assertEqual(owner_b_detail.status_code, 404)

    def booking_customer_id(self, booking_id):
        with self.Session() as db:
            return db.get(Booking, booking_id).customer_id


if __name__ == '__main__':
    unittest.main()
