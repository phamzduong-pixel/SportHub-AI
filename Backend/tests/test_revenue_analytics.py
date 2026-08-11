import unittest
from datetime import date, datetime, time, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, get_password_hash
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.facility import Facility
from app.models.field import Booking, Field
from app.models.payment import Payment
from app.models.time_slot import TimeSlot
from app.models.user import User, UserRole


class RevenueAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)
        with self.Session() as db:
            owner_a = User(full_name='Owner A', email='revenue.a@test.local', hashed_password=get_password_hash('Owner@123456'), role=UserRole.OWNER.value)
            owner_b = User(full_name='Owner B', email='revenue.b@test.local', hashed_password=get_password_hash('Owner@123456'), role=UserRole.OWNER.value)
            customer = User(full_name='Customer', email='revenue.customer@test.local', hashed_password=get_password_hash('Customer@123'), role=UserRole.CUSTOMER.value)
            manager = User(full_name='Legacy Manager', email='revenue.manager@test.local', hashed_password=get_password_hash('Manager@123'), role='MANAGER')
            db.add_all([owner_a, owner_b, customer, manager]); db.flush()
            facility_a = Facility(owner_id=owner_a.id, name='Cơ sở A', location='Hà Nội', amenities=[], image_urls=[])
            facility_b = Facility(owner_id=owner_b.id, name='Cơ sở B', location='Đà Nẵng', amenities=[], image_urls=[])
            db.add_all([facility_a, facility_b]); db.flush()
            field_a = Field(owner_id=owner_a.id, facility_id=facility_a.id, name='Sân A', sport_type='Cầu lông', location='Hà Nội', capacity=4, base_price=300000, amenities=[])
            field_b = Field(owner_id=owner_b.id, facility_id=facility_b.id, name='Sân B', sport_type='Tennis', location='Đà Nẵng', capacity=4, base_price=999000, amenities=[])
            db.add_all([field_a, field_b]); db.flush()
            slot_a = TimeSlot(field_id=field_a.id, name='Tối', start_time=time(18), end_time=time(20), price=300000)
            slot_a2 = TimeSlot(field_id=field_a.id, name='Chiều', start_time=time(15), end_time=time(17), price=150000)
            slot_b = TimeSlot(field_id=field_b.id, name='Tối', start_time=time(18), end_time=time(20), price=999000)
            db.add_all([slot_a, slot_a2, slot_b]); db.flush()
            today = date.today(); paid_at = datetime.now(timezone.utc)

            def booking(code, total, status, field=field_a, slot=slot_a, day=today):
                item = Booking(booking_code=code, customer_id=customer.id, facility_id=field.facility_id, facility_name_snapshot=field.facility.name, field_id=field.id, time_slot_id=slot.id, booking_date=day, start_time_snapshot=slot.start_time, end_time_snapshot=slot.end_time, price_snapshot=total, total_amount=total, deposit_amount=0, paid_amount=0, remaining_amount=total, status=status)
                db.add(item); db.flush(); return item

            unpaid = booking('REV-UNPAID', 100000, 'pending_payment')
            completed = booking('REV-COMPLETE', 300000, 'completed')
            confirmed = booking('REV-CONFIRMED', 150000, 'confirmed', slot=slot_a2)
            owner_cancel = booking('REV-OWNER-CANCEL', 200000, 'cancelled_by_owner')
            late_cancel = booking('REV-LATE-CANCEL', 250000, 'cancelled_by_customer')
            other_owner = booking('REV-OTHER-OWNER', 999000, 'completed', field_b, slot_b)
            old = booking('REV-OLD', 40000, 'completed', day=today - timedelta(days=3))

            def payment(booking_item, code, amount, payment_type, status='paid', escrow='held'):
                db.add(Payment(booking_id=booking_item.id, customer_id=customer.id, owner_id=booking_item.field.owner_id, transaction_code=code, amount=amount, payment_method='bank_transfer', payment_type=payment_type, status=status, payment_status=status, escrow_status=escrow, paid_at=paid_at if status == 'paid' else None))

            payment(completed, 'PAY-DEP', 100000, 'deposit', escrow='released')
            payment(completed, 'PAY-REMAIN', 200000, 'remaining', escrow='released')
            payment(confirmed, 'PAY-HELD', 50000, 'deposit', escrow='held')
            payment(confirmed, 'PAY-FAILED', 100000, 'remaining', status='failed', escrow='failed')
            payment(owner_cancel, 'PAY-CANCELLED', 200000, 'deposit', escrow='refunded')
            payment(owner_cancel, 'REF-CANCELLED', 200000, 'refund', status='refunded', escrow='refunded')
            payment(late_cancel, 'PAY-FORFEIT', 75000, 'deposit', escrow='released')
            payment(other_owner, 'PAY-OTHER', 999000, 'full', escrow='released')
            payment(old, 'PAY-OLD', 40000, 'full', escrow='released')
            db.commit()
            self.ids = {'owner_a': owner_a.id, 'manager': manager.id, 'field_a': field_a.id, 'field_b': field_b.id, 'unpaid': unpaid.id}

        def override_db():
            with self.Session() as db:
                yield db
        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)
        self.owner_a = self.login('revenue.a@test.local', 'Owner@123456')
        self.owner_b = self.login('revenue.b@test.local', 'Owner@123456')
        self.customer = self.login('revenue.customer@test.local', 'Customer@123')

    def tearDown(self):
        self.client.close(); app.dependency_overrides.clear(); Base.metadata.drop_all(self.engine)

    def login(self, email, password):
        response = self.client.post('/auth/login', json={'email': email, 'password': password})
        self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': f"Bearer {response.json()['access_token']}"}

    def report(self, headers, day=None):
        day = day or date.today()
        response = self.client.get(f'/dashboard/revenue-analytics?date_from={day}&date_to={day}', headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_revenue_formula_avoids_double_count_and_excludes_failed(self):
        data = self.report(self.owner_a); summary = data['summary']
        self.assertEqual(summary['booking_value'], 550000)
        self.assertEqual(summary['collected_amount'], 625000)
        self.assertEqual(summary['deposit_amount'], 425000)
        self.assertEqual(summary['held_deposit_amount'], 50000)
        self.assertEqual(summary['outstanding_amount'], 200000)
        self.assertEqual(summary['completed_revenue'], 300000)
        self.assertEqual(summary['refunded_amount'], 200000)
        self.assertEqual(summary['net_revenue'], 425000)
        self.assertEqual(summary['completed_bookings'], 1)
        self.assertEqual(summary['cancelled_bookings'], 2)
        complete = next(item for item in data['transactions'] if item['booking_code'] == 'REV-COMPLETE')
        self.assertEqual(complete['collected_amount'], 300000)  # deposit + remaining, each transaction exactly once
        failed = next(item for item in data['transactions'] if item['booking_code'] == 'REV-CONFIRMED')
        self.assertEqual(failed['collected_amount'], 50000)

    def test_refund_owner_cancel_and_forfeited_deposit(self):
        transactions = {item['booking_code']: item for item in self.report(self.owner_a)['transactions']}
        self.assertEqual(transactions['REV-OWNER-CANCEL']['net_revenue'], 0)
        self.assertEqual(transactions['REV-OWNER-CANCEL']['refunded_amount'], 200000)
        self.assertEqual(transactions['REV-LATE-CANCEL']['net_revenue'], 75000)
        self.assertEqual(transactions['REV-LATE-CANCEL']['outstanding_amount'], 0)
        self.assertEqual(transactions['REV-UNPAID']['net_revenue'], 0)

    def test_date_filter_and_owner_isolation(self):
        today_a = self.report(self.owner_a)
        self.assertNotIn('REV-OLD', {item['booking_code'] for item in today_a['transactions']})
        old = self.report(self.owner_a, date.today() - timedelta(days=3))
        self.assertEqual(old['summary']['net_revenue'], 40000)
        self.assertNotIn('REV-OTHER-OWNER', {item['booking_code'] for item in today_a['transactions']})
        owner_b = self.report(self.owner_b)
        self.assertEqual(owner_b['summary']['net_revenue'], 999000)
        self.assertEqual({item['booking_code'] for item in owner_b['transactions']}, {'REV-OTHER-OWNER'})
        foreign_field = self.client.get(f"/dashboard/revenue-analytics?date_from={date.today()}&date_to={date.today()}&field_id={self.ids['field_b']}", headers=self.owner_a)
        self.assertEqual(foreign_field.status_code, 200)
        self.assertEqual(foreign_field.json()['transactions'], [])
        forged = {'Authorization': f"Bearer {create_access_token({'sub': str(self.ids['manager']), 'role': 'MANAGER'})}"}
        self.assertEqual(self.client.get('/dashboard/revenue-analytics', headers=self.customer).status_code, 403)
        self.assertEqual(self.client.get('/dashboard/revenue-analytics', headers=forged).status_code, 403)


if __name__ == '__main__':
    unittest.main()
