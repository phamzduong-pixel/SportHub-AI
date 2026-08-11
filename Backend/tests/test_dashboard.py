import unittest
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_password_hash
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.field import Booking, Field
from app.models.payment import Payment
from app.models.time_slot import TimeSlot
from app.models.user import User, UserRole


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(self.engine)
        with self.Session() as db:
            owner = User(full_name='Owner', email='reportowner@test.local', hashed_password=get_password_hash('Owner@123456'), role=UserRole.OWNER.value)
            reporter = User(full_name='Reporter', email='reporter@test.local', hashed_password=get_password_hash('Operator@123'), role=UserRole.CUSTOMER.value)
            operator = User(full_name='Operator', email='noreport@test.local', hashed_password=get_password_hash('Operator@123'), role=UserRole.CUSTOMER.value)
            customer = User(full_name='Customer', email='reportcustomer@test.local', hashed_password=get_password_hash('Customer@123'), role=UserRole.CUSTOMER.value)
            db.add_all([owner, reporter, operator, customer]); db.flush()
            field1 = Field(name='Sân A', sport_type='Bóng đá', location='Q1', capacity=10, base_price=300000, status='available', amenities=[])
            field2 = Field(name='Sân B', sport_type='Cầu lông', location='Q2', capacity=4, base_price=200000, status='inactive', amenities=[])
            db.add_all([field1, field2]); db.flush()
            slot1 = TimeSlot(field_id=field1.id, name='Sáng', start_time=time(8), end_time=time(10), price=300000, is_active=True)
            slot2 = TimeSlot(field_id=field1.id, name='Chiều', start_time=time(15), end_time=time(17), price=400000, is_active=True)
            slot3 = TimeSlot(field_id=field2.id, name='Tối', start_time=time(18), end_time=time(20), price=200000, is_active=True)
            db.add_all([slot1, slot2, slot3]); db.flush()
            today = date.today()
            bookings = [
                Booking(booking_code='REPORT-1', customer_id=customer.id, field_id=field1.id, time_slot_id=slot1.id, booking_date=today - timedelta(days=2), start_time_snapshot=slot1.start_time, end_time_snapshot=slot1.end_time, price_snapshot=300000, total_amount=300000, status='completed'),
                Booking(booking_code='REPORT-2', customer_id=customer.id, field_id=field1.id, time_slot_id=slot2.id, booking_date=today - timedelta(days=1), start_time_snapshot=slot2.start_time, end_time_snapshot=slot2.end_time, price_snapshot=400000, total_amount=400000, status='confirmed'),
                Booking(booking_code='REPORT-3', customer_id=customer.id, field_id=field1.id, time_slot_id=slot1.id, booking_date=today, start_time_snapshot=slot1.start_time, end_time_snapshot=slot1.end_time, price_snapshot=300000, total_amount=300000, status='pending'),
                Booking(booking_code='REPORT-OLD', customer_id=customer.id, field_id=field2.id, time_slot_id=slot3.id, booking_date=today - timedelta(days=20), start_time_snapshot=slot3.start_time, end_time_snapshot=slot3.end_time, price_snapshot=200000, total_amount=200000, status='completed'),
            ]
            db.add_all(bookings); db.flush()
            db.add_all([
                Payment(booking_id=bookings[0].id, transaction_code='PAY-REPORT-1', amount=300000, payment_method='cash', payment_type='full', status='paid', paid_at=datetime.now(timezone.utc) - timedelta(days=2), confirmed_by=owner.id),
                Payment(booking_id=bookings[1].id, transaction_code='PAY-REPORT-2', amount=100000, payment_method='bank_transfer', payment_type='deposit', status='paid', paid_at=datetime.now(timezone.utc) - timedelta(days=1), confirmed_by=reporter.id),
                Payment(booking_id=bookings[2].id, transaction_code='PAY-REPORT-3', amount=100000, payment_method='mock_online', payment_type='deposit', status='pending'),
            ])
            db.commit()
            self.field1_id = field1.id
            self.start = today - timedelta(days=2)
            self.end = today

        def override_db():
            with self.Session() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)
        self.owner = self.login('reportowner@test.local', 'Owner@123456')
        self.reporter = self.owner
        self.no_report = self.login('noreport@test.local', 'Operator@123')
        self.customer = self.login('reportcustomer@test.local', 'Customer@123')

    def tearDown(self):
        self.client.close(); app.dependency_overrides.clear(); Base.metadata.drop_all(self.engine)

    def login(self, email, password):
        response = self.client.post('/auth/login', json={'email': email, 'password': password})
        self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': f"Bearer {response.json()['access_token']}"}

    @property
    def query(self):
        return f'?date_from={self.start}&date_to={self.end}'

    def test_summary_series_and_performance(self):
        summary = self.client.get(f'/dashboard/summary{self.query}', headers=self.reporter)
        self.assertEqual(summary.status_code, 200, summary.text)
        self.assertEqual(summary.json()['total_fields'], 2)
        self.assertEqual(summary.json()['active_fields'], 1)
        self.assertEqual(summary.json()['total_bookings'], 3)
        self.assertEqual(summary.json()['pending_bookings'], 1)
        self.assertEqual(summary.json()['confirmed_bookings'], 1)
        self.assertEqual(summary.json()['paid_revenue'], 400000)

        revenue = self.client.get(f'/dashboard/revenue{self.query}', headers=self.owner).json()
        self.assertEqual(revenue['granularity'], 'day')
        self.assertEqual(revenue['total'], 400000)
        self.assertEqual(len(revenue['items']), 3)
        bookings = self.client.get(f'/dashboard/bookings{self.query}', headers=self.owner).json()
        self.assertEqual(bookings['total'], 3)
        self.assertEqual(sum(item['completed'] for item in bookings['items']), 1)

        fields = self.client.get(f'/dashboard/field-performance{self.query}', headers=self.owner).json()['items']
        self.assertEqual(fields[0]['field_name'], 'Sân A')
        self.assertEqual(fields[0]['booking_count'], 3)
        self.assertEqual(fields[0]['paid_revenue'], 400000)
        self.assertEqual(fields[0]['utilization_rate'], 33.33)
        slots = self.client.get(f'/dashboard/time-slot-performance{self.query}', headers=self.owner).json()['items']
        morning = next(item for item in slots if item['time_slot_name'] == 'Sáng')
        self.assertEqual(morning['booking_count'], 2)
        self.assertEqual(morning['paid_revenue'], 300000)

    def test_permissions_filters_and_validation(self):
        paths = ('summary', 'revenue', 'bookings', 'field-performance', 'time-slot-performance')
        for path in paths:
            self.assertEqual(self.client.get(f'/dashboard/{path}', headers=self.no_report).status_code, 403)
            self.assertEqual(self.client.get(f'/dashboard/{path}', headers=self.customer).status_code, 403)
            self.assertEqual(self.client.get(f'/dashboard/{path}', headers=self.reporter).status_code, 200)
        filtered = self.client.get(f'/dashboard/summary{self.query}&field_id={self.field1_id}', headers=self.owner).json()
        self.assertEqual(filtered['total_fields'], 1)
        self.assertEqual(filtered['total_bookings'], 3)
        invalid = self.client.get(f'/dashboard/summary?date_from={self.end}&date_to={self.start}', headers=self.owner)
        self.assertEqual(invalid.status_code, 422)


class EmptyDashboardTests(unittest.TestCase):
    def test_service_returns_zero_filled_data(self):
        engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Session = sessionmaker(bind=engine)
        Base.metadata.create_all(engine)
        from app.repositories.dashboard_repository import DashboardRepository
        from app.services.dashboard_service import DashboardService
        with Session() as db:
            service = DashboardService(DashboardRepository(db))
            today = date.today()
            summary = service.summary(today - timedelta(days=2), today, None)
            self.assertEqual(summary.total_bookings, 0)
            self.assertEqual(summary.paid_revenue, 0)
            self.assertEqual(len(service.revenue(today - timedelta(days=2), today, None).items), 3)
            self.assertEqual(service.field_performance(today - timedelta(days=2), today, None).items, [])
        Base.metadata.drop_all(engine)


if __name__ == '__main__':
    unittest.main()
