import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, time, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import get_password_hash
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.field import Booking, Field
from app.models.payment import Payment
from app.models.time_slot import TimeSlot
from app.models.user import User, UserRole
from tests import test_bookings as booking_tests


class ProfessionalBookingWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.case = booking_tests.BookingWorkflowTests('test_adjacent_bookings_do_not_overlap')
        self.case.setUp()

    def tearDown(self):
        self.case.tearDown()

    def pay(self, booking_id: int, payment_type: str, headers=None):
        headers = headers or self.case.customer1
        created = self.case.client.post('/payments', headers=headers, json={
            'booking_id': booking_id, 'payment_method': 'mock_online',
            'payment_type': payment_type,
        })
        self.assertEqual(created.status_code, 201, created.text)
        settled = self.case.client.patch(
            f"/payments/{created.json()['id']}/confirm", headers=headers, json={},
        )
        self.assertEqual(settled.status_code, 200, settled.text)
        return settled.json()

    def confirmed_booking(self, **changes):
        booking = self.case.create(**changes)
        self.pay(booking['id'], 'deposit')
        confirmed = self.case.client.patch(
            f"/bookings/{booking['id']}/confirm", headers=self.case.operator, json={},
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        return confirmed.json()

    def test_cancellation_quote_creates_single_tenant_aware_refund(self):
        booking = self.case.create()
        self.pay(booking['id'], 'deposit')
        quote = self.case.client.get(
            f"/bookings/{booking['id']}/cancellation-quote", headers=self.case.customer1,
        )
        self.assertEqual(quote.status_code, 200, quote.text)
        self.assertEqual(quote.json()['refund_percent'], 100)
        cancelled = self.case.client.patch(
            f"/bookings/{booking['id']}/cancel", headers=self.case.customer1,
            json={'reason': 'Thay đổi kế hoạch thi đấu'},
        )
        self.assertEqual(cancelled.status_code, 200, cancelled.text)
        self.assertEqual(cancelled.json()['status'], 'cancelled_by_customer')
        self.assertEqual(cancelled.json()['refund_amount'], booking['deposit_amount'])
        self.assertEqual(cancelled.json()['refund_status'], 'refunded')
        self.assertEqual(cancelled.json()['cancelled_by'], booking['customer_id'])
        self.assertIsNotNone(cancelled.json()['cancelled_at'])
        with self.case.Session() as db:
            refunds = db.query(Payment).filter(
                Payment.booking_id == booking['id'], Payment.payment_type == 'refund',
            ).all()
            self.assertEqual(len(refunds), 1)
            self.assertEqual(refunds[0].customer_id, booking['customer_id'])
            self.assertEqual(refunds[0].status, 'refunded')
            self.assertEqual(refunds[0].escrow_status, 'refunded')
        request = self.case.client.get('/refunds/my', headers=self.case.customer1).json()['items'][0]
        self.assertEqual(request['status'], 'refunded')
        original = self.case.client.get('/payments/my', headers=self.case.customer1).json()['items']
        self.assertTrue(all(item['escrow_status'] == 'refunded' for item in original if item['payment_type'] != 'refund'))
        duplicate = self.case.client.patch(
            f"/bookings/{booking['id']}/cancel", headers=self.case.customer1,
            json={'reason': 'Gọi lại API hủy'},
        )
        self.assertEqual(duplicate.status_code, 409)

    def test_late_customer_cancellation_forfeits_deposit_to_owner(self):
        booking = self.case.create()
        deposit = self.pay(booking['id'], 'deposit')
        with self.case.Session() as db:
            row = db.get(Booking, booking['id'])
            row.free_cancellation_minutes = 20000
            db.commit()
        quote = self.case.client.get(
            f"/bookings/{booking['id']}/cancellation-quote", headers=self.case.customer1,
        )
        self.assertEqual(quote.status_code, 200, quote.text)
        self.assertTrue(quote.json()['is_late_cancellation'])
        self.assertEqual(quote.json()['refund_amount'], 0)
        self.assertEqual(quote.json()['forfeited_deposit_amount'], booking['deposit_amount'])
        cancelled = self.case.client.patch(
            f"/bookings/{booking['id']}/cancel", headers=self.case.customer1,
            json={'reason': 'Hủy sát giờ sử dụng'},
        )
        self.assertEqual(cancelled.status_code, 200, cancelled.text)
        self.assertEqual(cancelled.json()['status'], 'cancelled_by_customer')
        self.assertEqual(cancelled.json()['refund_amount'], 0)
        payment = self.case.client.get(f"/payments/{deposit['id']}", headers=self.case.customer1).json()
        self.assertEqual(payment['escrow_status'], 'released')
        self.assertEqual(self.case.client.patch(
            f"/bookings/{booking['id']}/cancel", headers=self.case.customer1,
            json={'reason': 'Hủy lại lần hai'},
        ).status_code, 409)

    def test_reschedule_price_increase_requires_exact_additional_payment(self):
        booking = self.confirmed_booking()
        target_date = self.case.future_date + timedelta(days=1)
        payload = {
            'field_id': self.case.field_id, 'time_slot_id': self.case.second_slot_id,
            'booking_date': target_date.isoformat(),
        }
        quote = self.case.client.post(
            f"/bookings/{booking['id']}/reschedule/quote", headers=self.case.customer1,
            json=payload,
        )
        self.assertEqual(quote.status_code, 200, quote.text)
        self.assertEqual(quote.json()['price_difference'], 100000)
        self.assertEqual(quote.json()['additional_payment_required'], 100000)
        moved = self.case.client.patch(
            f"/bookings/{booking['id']}/reschedule", headers=self.case.customer1, json=payload,
        )
        self.assertEqual(moved.status_code, 200, moved.text)
        self.assertEqual(moved.json()['status'], 'pending_payment')
        extra = self.pay(booking['id'], 'remaining')
        self.assertEqual(extra['amount'], 100000)
        detail = self.case.client.get(
            f"/bookings/{booking['id']}", headers=self.case.customer1,
        ).json()
        self.assertEqual(detail['status'], 'pending_confirmation')
        self.assertEqual(detail['additional_payment_required'], 0)

    def test_in_progress_completion_invoice_and_no_show_transitions(self):
        booking = self.confirmed_booking()
        self.pay(booking['id'], 'remaining')
        with self.case.Session() as db:
            row = db.get(Booking, booking['id']); row.booking_date = date.today() - timedelta(days=1); db.commit()
        started = self.case.client.patch(
            f"/bookings/{booking['id']}/start", headers=self.case.operator, json={},
        )
        self.assertEqual(started.status_code, 200, started.text)
        self.assertEqual(started.json()['status'], 'in_progress')
        completed = self.case.client.patch(
            f"/bookings/{booking['id']}/complete", headers=self.case.operator, json={},
        )
        self.assertEqual(completed.status_code, 200, completed.text)
        released = self.case.client.get(f"/bookings/{booking['id']}/payment-summary", headers=self.case.customer1).json()
        self.assertTrue(all(payment['escrow_status'] == 'released' for payment in released['transactions'] if payment['payment_type'] != 'refund'))
        self.assertTrue(any(event['action'] == 'booking_completed_funds_released' for event in completed.json()['timeline']))
        invoice = self.case.client.get(
            f"/bookings/{booking['id']}/invoice", headers=self.case.customer1,
        )
        self.assertEqual(invoice.status_code, 200, invoice.text)
        self.assertEqual(invoice.json()['booking_code'], booking['booking_code'])
        self.assertEqual(invoice.json()['net_received_amount'], booking['total_amount'])

        review = self.case.client.post('/reviews', headers=self.case.customer1, json={
            'booking_id': booking['id'], 'rating': 5, 'comment': 'Sân tốt và đúng giờ.',
        })
        self.assertEqual(review.status_code, 201, review.text)
        reviewed_booking = self.case.client.get(
            f"/bookings/{booking['id']}", headers=self.case.customer1,
        ).json()
        self.assertTrue(reviewed_booking['reviewed'])
        duplicate_review = self.case.client.post('/reviews', headers=self.case.customer1, json={
            'booking_id': booking['id'], 'rating': 4, 'comment': 'Đánh giá lần hai.',
        })
        self.assertEqual(duplicate_review.status_code, 409, duplicate_review.text)
        field_summary = self.case.client.get(f"/fields/{self.case.field_id}/reviews").json()
        self.assertEqual(field_summary['total_reviews'], 1)
        self.assertEqual(field_summary['average_rating'], 5.0)

        no_show = self.confirmed_booking(
            time_slot_id=self.case.second_slot_id,
            booking_date=(self.case.future_date + timedelta(days=2)).isoformat(),
        )
        with self.case.Session() as db:
            row = db.get(Booking, no_show['id']); row.booking_date = date.today() - timedelta(days=2); db.commit()
        response = self.case.client.patch(
            f"/bookings/{no_show['id']}/no-show", headers=self.case.operator, json={},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['status'], 'no_show')

    def test_only_owner_can_configure_owned_facility_policy(self):
        created = self.case.client.post('/facilities', headers=self.case.owner, json={
            'name': 'Cơ sở trung tâm', 'location': 'Quận 3',
        })
        self.assertEqual(created.status_code, 201, created.text)
        facility_id = created.json()['id']
        self.assertEqual(self.case.client.get('/facilities', headers=self.case.customer1).status_code, 403)
        updated = self.case.client.put(
            f'/facilities/{facility_id}/cancellation-policy', headers=self.case.owner,
            json={'free_cancellation_minutes': 360},
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()['free_cancellation_minutes'], 360)
        self.assertEqual(updated.json()['cancellation_rules'], [
            {'min_minutes_before': 360, 'refund_percent': 100.0},
            {'min_minutes_before': 0, 'refund_percent': 0.0},
        ])

    def test_facility_hotline_is_validated_and_visible_to_customer(self):
        created = self.case.client.post('/facilities', headers=self.case.owner, json={
            'name': 'Cơ sở hotline', 'location': 'Quận 3',
            'contact_phone': '0901234567',
        })
        self.assertEqual(created.status_code, 201, created.text)
        facility_id = created.json()['id']
        with self.case.Session() as db:
            from app.models.facility import Facility
            facility = db.get(Facility, facility_id)
            facility.status = 'APPROVED'; facility.is_active = True
            field = db.get(Field, self.case.field_id)
            field.facility_id = facility_id
            db.commit()

        public_detail = self.case.client.get(f'/public/courts/{self.case.field_id}')
        self.assertEqual(public_detail.status_code, 200, public_detail.text)
        self.assertEqual(public_detail.json()['facility']['contact_phone'], '0901234567')
        booking = self.case.create()
        self.assertEqual(booking['facility_hotline'], '0901234567')

        updated = self.case.client.patch(
            f'/facilities/{facility_id}/hotline', headers=self.case.owner,
            json={'contact_phone': '0912345678'},
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()['contact_phone'], '0912345678')
        booking_detail = self.case.client.get(
            f"/bookings/{booking['id']}", headers=self.case.customer1,
        )
        self.assertEqual(booking_detail.json()['facility_hotline'], '0912345678')

    def test_missing_facility_hotline_is_not_replaced_with_demo_data(self):
        created = self.case.client.post('/facilities', headers=self.case.owner, json={
            'name': 'Cơ sở chưa có hotline', 'location': 'Quận 4',
        })
        self.assertEqual(created.status_code, 201, created.text)
        facility_id = created.json()['id']
        with self.case.Session() as db:
            from app.models.facility import Facility
            facility = db.get(Facility, facility_id)
            facility.status = 'APPROVED'; facility.is_active = True
            field = db.get(Field, self.case.field_id)
            field.facility_id = facility_id
            db.commit()

        public_detail = self.case.client.get(f'/public/courts/{self.case.field_id}')
        self.assertEqual(public_detail.status_code, 200, public_detail.text)
        self.assertIsNone(public_detail.json()['facility']['contact_phone'])
        booking = self.case.create()
        self.assertIsNone(booking['facility_hotline'])

        invalid = self.case.client.patch(
            f'/facilities/{facility_id}/hotline', headers=self.case.owner,
            json={'contact_phone': 'hotline-abc'},
        )
        self.assertEqual(invalid.status_code, 422, invalid.text)
        forbidden = self.case.client.patch(
            f'/facilities/{facility_id}/hotline', headers=self.case.customer1,
            json={'contact_phone': '0901234567'},
        )
        self.assertEqual(forbidden.status_code, 403, forbidden.text)


class ConcurrentBookingTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        path = Path(self.temp.name) / 'concurrency.db'
        self.engine = create_engine(f'sqlite:///{path}', connect_args={'check_same_thread': False, 'timeout': 15})
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(self.engine)
        with self.Session() as db:
            field = Field(name='Sân đồng thời', sport_type='Bóng đá', location='Quận 1', capacity=10, base_price=400000, status='available', amenities=[])
            db.add(field); db.flush()
            first = TimeSlot(field_id=field.id, name='Ca A', start_time=time(8), end_time=time(10), price=Decimal('400000'), is_active=True)
            overlap = TimeSlot(field_id=field.id, name='Ca B', start_time=time(9), end_time=time(11), price=Decimal('450000'), is_active=True)
            db.add_all([first, overlap,
                User(full_name='Khách A', email='race-a@test.local', hashed_password=get_password_hash('Customer@123'), role=UserRole.CUSTOMER.value),
                User(full_name='Khách B', email='race-b@test.local', hashed_password=get_password_hash('Customer@123'), role=UserRole.CUSTOMER.value),
            ]); db.commit(); self.field_id, self.first_id, self.overlap_id = field.id, first.id, overlap.id
        def override_db():
            with self.Session() as db: yield db
        app.dependency_overrides[get_db] = override_db
        self.clients = [TestClient(app), TestClient(app)]
        self.headers = []
        for client, email in zip(self.clients, ['race-a@test.local', 'race-b@test.local']):
            token = client.post('/auth/login', json={'email': email, 'password': 'Customer@123'}).json()['access_token']
            self.headers.append({'Authorization': f'Bearer {token}'})

    def tearDown(self):
        for client in self.clients: client.close()
        app.dependency_overrides.clear(); self.engine.dispose(); self.temp.cleanup()

    def test_overlapping_slots_created_at_same_time_only_allow_one(self):
        booking_date = (date.today() + timedelta(days=3)).isoformat()
        def create(index: int):
            return self.clients[index].post('/bookings', headers=self.headers[index], json={
                'field_id': self.field_id,
                'time_slot_id': self.first_id if index == 0 else self.overlap_id,
                'booking_date': booking_date,
            })
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(create, [0, 1]))
        self.assertEqual(sorted(response.status_code for response in responses), [201, 409])
        with self.Session() as db:
            self.assertEqual(db.query(Booking).filter(Booking.booking_date == date.fromisoformat(booking_date)).count(), 1)

    def test_concurrent_booking_still_prevents_overlap(self):
        self.test_overlapping_slots_created_at_same_time_only_allow_one()


if __name__ == '__main__':
    unittest.main()
