import unittest
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_password_hash
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.field import Booking, Field
from app.models.time_slot import TimeSlot
from app.models.user import User, UserRole

class BookingWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(self.engine)
        with self.Session() as db:
            field = Field(name='Sân Booking', sport_type='Bóng đá', location='Quận 3', capacity=22, base_price=300000, status='available', amenities=[])
            db.add(field); db.flush()
            slot = TimeSlot(field_id=field.id, name='Ca sáng', start_time=time(8), end_time=time(10), price=Decimal('450000'), is_active=True)
            second_slot = TimeSlot(field_id=field.id, name='Ca trưa', start_time=time(10), end_time=time(12), price=Decimal('550000'), is_active=True)
            other_field = Field(name='Sân Booking B', sport_type='Bóng đá', location='Quận 3', capacity=14, base_price=300000, status='available', amenities=[])
            db.add(other_field); db.flush()
            other_slot = TimeSlot(field_id=other_field.id, name='Ca sáng B', start_time=time(8), end_time=time(10), price=Decimal('450000'), is_active=True)
            operator = User(full_name='Booking Operator', email='bookingoperator@test.local', hashed_password=get_password_hash('Operator@123'), role=UserRole.CUSTOMER.value)
            db.add_all([
                slot, second_slot, other_slot,
                User(full_name='Owner', email='bookingowner@test.local', hashed_password=get_password_hash('Owner@123456'), role=UserRole.OWNER.value),
                operator,
                User(full_name='No Permission', email='bookingnone@test.local', hashed_password=get_password_hash('Operator@123'), role=UserRole.CUSTOMER.value),
                User(full_name='Customer One', email='customer1@test.local', hashed_password=get_password_hash('Customer@123'), role=UserRole.CUSTOMER.value),
                User(full_name='Customer Two', email='customer2@test.local', hashed_password=get_password_hash('Customer@123'), role=UserRole.CUSTOMER.value),
            ])
            db.commit()
            self.field_id, self.slot_id, self.second_slot_id = field.id, slot.id, second_slot.id
            self.other_field_id, self.other_slot_id = other_field.id, other_slot.id

        def override_db():
            with self.Session() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)
        self.owner = self.login('bookingowner@test.local', 'Owner@123456')
        self.operator = self.owner
        self.no_permission = self.login('bookingnone@test.local', 'Operator@123')
        self.customer1 = self.login('customer1@test.local', 'Customer@123')
        self.customer2 = self.login('customer2@test.local', 'Customer@123')
        self.future_date = date.today() + timedelta(days=7)

    def tearDown(self):
        self.client.close(); app.dependency_overrides.clear(); Base.metadata.drop_all(self.engine)

    def login(self, email, password):
        response = self.client.post('/auth/login', json={'email': email, 'password': password})
        self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': f"Bearer {response.json()['access_token']}"}

    def payload(self, **changes):
        return {'field_id': self.field_id, 'time_slot_id': self.slot_id, 'booking_date': self.future_date.isoformat(), 'note': 'Kiểm thử', **changes}

    def create(self, headers=None, **changes):
        response = self.client.post('/bookings', headers=headers or self.customer1, json=self.payload(**changes))
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_availability_duplicate_prevention_and_snapshot(self):
        available = self.client.get(f'/availability?date={self.future_date}&field_id={self.field_id}')
        self.assertEqual(available.status_code, 200)
        self.assertEqual(len(available.json()[0]['available_slots']), 2)
        booking = self.create()
        self.assertEqual(booking['price_snapshot'], 450000)
        duplicate = self.client.post('/bookings', headers=self.customer2, json=self.payload())
        self.assertEqual(duplicate.status_code, 409)
        available_after = self.client.get(f'/availability?date={self.future_date}&field_id={self.field_id}').json()
        self.assertEqual([slot['id'] for slot in available_after[0]['available_slots']], [self.second_slot_id])
        with self.Session() as db:
            slot = db.get(TimeSlot, self.slot_id)
            slot.start_time = time(13); slot.end_time = time(15); slot.price = Decimal('900000'); db.commit()
        detail = self.client.get(f"/bookings/{booking['id']}", headers=self.customer1).json()
        self.assertEqual(detail['start_time_snapshot'], '08:00:00')
        self.assertEqual(detail['end_time_snapshot'], '10:00:00')
        self.assertEqual(detail['price_snapshot'], 450000)

    def test_availability_and_quote_keep_exact_date_slot_and_server_price(self):
        with self.Session() as db:
            slot = db.get(TimeSlot, self.slot_id)
            slot.weekday_price = Decimal('470000')
            slot.weekend_price = Decimal('520000')
            db.commit()
        expected_price = 520000 if self.future_date.weekday() >= 5 else 470000
        availability = self.client.get(f'/availability?date={self.future_date}&field_id={self.field_id}')
        self.assertEqual(availability.status_code, 200, availability.text)
        selected = next(item for item in availability.json()[0]['available_slots'] if item['id'] == self.slot_id)
        self.assertEqual(selected['start_time'], '08:00:00')
        self.assertEqual(selected['end_time'], '10:00:00')
        self.assertEqual(selected['price'], expected_price)
        quote = self.client.get(f'/bookings/quote?field_id={self.field_id}&time_slot_id={self.slot_id}&date={self.future_date}')
        self.assertEqual(quote.status_code, 200, quote.text)
        self.assertEqual(quote.json()['booking_date'], self.future_date.isoformat())
        self.assertEqual(quote.json()['start_time'], '08:00:00')
        self.assertEqual(quote.json()['end_time'], '10:00:00')
        self.assertEqual(quote.json()['price'], expected_price)
        self.assertEqual(quote.json()['deposit_amount'], expected_price * 0.30)
        self.assertEqual(quote.json()['remaining_amount'], expected_price * 0.70)
        booking = self.create()
        self.assertEqual(booking['price_snapshot'], expected_price)

    def test_booking_from_ai_preserves_selected_slot(self):
        selected = {
            'field_id': self.field_id,
            'time_slot_id': self.second_slot_id,
            'booking_date': self.future_date.isoformat(),
        }
        response = self.client.post('/bookings', headers=self.customer1, json=selected)
        self.assertEqual(response.status_code, 201, response.text)
        booking = response.json()
        self.assertEqual(booking['field_id'], selected['field_id'])
        self.assertEqual(booking['time_slot_id'], selected['time_slot_id'])
        self.assertEqual(booking['booking_date'], selected['booking_date'])
        self.assertEqual(booking['start_time_snapshot'], '10:00:00')
        self.assertEqual(booking['end_time_snapshot'], '12:00:00')

    def test_booking_from_ai_rechecks_availability(self):
        quote = self.client.get(
            f'/bookings/quote?field_id={self.field_id}&time_slot_id={self.slot_id}&date={self.future_date}'
        )
        self.assertEqual(quote.status_code, 200, quote.text)
        self.create()
        response = self.client.post('/bookings', headers=self.customer2, json=self.payload())
        self.assertEqual(response.status_code, 409)
        self.assertIn('vừa được người khác đặt', response.json()['detail'])

    def test_quote_remaining_amount_tracks_deposit_percentage_and_never_goes_negative(self):
        for percent, expected_deposit, expected_remaining in (
            (0, 0, 450000),
            (20, 90000, 360000),
            (50, 225000, 225000),
            (100, 450000, 0),
            (150, 450000, 0),
        ):
            with self.Session() as db:
                field = db.get(Field, self.field_id)
                field.deposit_type = 'percentage'
                field.deposit_value = Decimal(percent)
                db.commit()
            quote = self.client.get(
                f'/bookings/quote?field_id={self.field_id}&time_slot_id={self.slot_id}&date={self.future_date}'
            )
            self.assertEqual(quote.status_code, 200, quote.text)
            self.assertEqual(quote.json()['deposit_amount'], expected_deposit)
            self.assertEqual(quote.json()['remaining_amount'], expected_remaining)

    def test_slot_taken_after_quote_is_rejected_without_switching_slot(self):
        quote = self.client.get(f'/bookings/quote?field_id={self.field_id}&time_slot_id={self.slot_id}&date={self.future_date}')
        self.assertEqual(quote.status_code, 200, quote.text)
        first = self.create()
        response = self.client.post('/bookings', headers=self.customer2, json=self.payload())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['detail'], 'Một hoặc nhiều khung giờ vừa được người khác đặt. Danh sách giờ trống đã được cập nhật.')
        self.assertEqual(first['time_slot_id'], self.slot_id)

    def test_overlap_is_checked_by_snapshot_not_only_slot_id(self):
        self.create()
        with self.Session() as db:
            overlap = TimeSlot(field_id=self.field_id, name='Ca chồng', start_time=time(9), end_time=time(11), price=500000, is_active=True)
            db.add(overlap); db.commit(); overlap_id = overlap.id
        response = self.client.post('/bookings', headers=self.customer2, json=self.payload(time_slot_id=overlap_id))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['detail'], 'Một hoặc nhiều khung giờ vừa được người khác đặt. Danh sách giờ trống đã được cập nhật.')

    def test_exact_overlap_returns_required_conflict(self):
        created = self.create()
        self.assertEqual(created['status'], 'pending_payment')
        self.assertIsNotNone(created['hold_expires_at'])
        response = self.client.post('/bookings', headers=self.customer2, json=self.payload())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['detail'], 'Một hoặc nhiều khung giờ vừa được người khác đặt. Danh sách giờ trống đã được cập nhật.')
        operator_response = self.client.post('/bookings', headers=self.operator, json=self.payload(customer_email='customer2@test.local'))
        self.assertEqual(operator_response.status_code, 409)

    def test_partial_overlap_is_rejected(self):
        self.create()
        with self.Session() as db:
            slot = TimeSlot(field_id=self.field_id, name='Ca giao một phần', start_time=time(9), end_time=time(11), price=500000, is_active=True)
            db.add(slot); db.commit(); slot_id = slot.id
        response = self.client.post('/bookings', headers=self.customer2, json=self.payload(time_slot_id=slot_id))
        self.assertEqual(response.status_code, 409)

    def test_booking_contained_inside_another_is_rejected(self):
        with self.Session() as db:
            outer = TimeSlot(field_id=self.field_id, name='Ca dài', start_time=time(13), end_time=time(17), price=800000, is_active=True)
            inner = TimeSlot(field_id=self.field_id, name='Ca nằm trong', start_time=time(14), end_time=time(15), price=250000, is_active=True)
            db.add_all([outer, inner]); db.commit(); outer_id, inner_id = outer.id, inner.id
        self.create(time_slot_id=outer_id)
        response = self.client.post('/bookings', headers=self.customer2, json=self.payload(time_slot_id=inner_id))
        self.assertEqual(response.status_code, 409)

    def test_adjacent_bookings_do_not_overlap(self):
        self.create()
        response = self.client.post('/bookings', headers=self.customer2, json=self.payload(time_slot_id=self.second_slot_id))
        self.assertEqual(response.status_code, 201, response.text)

    def test_different_courts_can_be_booked_at_same_time(self):
        self.create()
        response = self.client.post('/bookings', headers=self.customer2, json=self.payload(field_id=self.other_field_id, time_slot_id=self.other_slot_id))
        self.assertEqual(response.status_code, 201, response.text)

    def test_slot_reopens_after_cancel_or_expired_hold(self):
        cancelled = self.create()
        cancel_response = self.client.patch(f"/bookings/{cancelled['id']}/cancel", headers=self.customer1, json={'reason': 'Thay đổi kế hoạch'})
        self.assertEqual(cancel_response.status_code, 200)
        replacement = self.client.post('/bookings', headers=self.customer2, json=self.payload())
        self.assertEqual(replacement.status_code, 201, replacement.text)

        next_date = self.future_date + timedelta(days=1)
        expired = self.create(booking_date=next_date.isoformat())
        with self.Session() as db:
            booking = db.get(Booking, expired['id'])
            booking.hold_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
        reopened = self.client.post('/bookings', headers=self.customer2, json=self.payload(booking_date=next_date.isoformat()))
        self.assertEqual(reopened.status_code, 201, reopened.text)
        with self.Session() as db:
            self.assertEqual(db.get(Booking, expired['id']).status, 'expired')

    def test_permissions_history_admin_create_and_reschedule(self):
        booking = self.create()
        my_history = self.client.get('/bookings/my', headers=self.customer1)
        self.assertEqual(my_history.json()['total'], 1)
        self.assertEqual(self.client.get(f"/bookings/{booking['id']}", headers=self.customer2).status_code, 403)
        self.assertEqual(self.client.get('/bookings', headers=self.no_permission).status_code, 403)
        self.assertEqual(self.client.get('/bookings', headers=self.operator).json()['total'], 1)
        behalf = self.client.post('/bookings', headers=self.operator, json=self.payload(
            time_slot_id=self.second_slot_id, customer_email='customer2@test.local',
        ))
        self.assertEqual(behalf.status_code, 201, behalf.text)
        self.assertEqual(behalf.json()['customer_email'], 'customer2@test.local')
        moved = self.client.put(f"/bookings/{booking['id']}", headers=self.operator, json={
            'field_id': self.field_id, 'time_slot_id': self.slot_id,
            'booking_date': (self.future_date + timedelta(days=1)).isoformat(), 'note': 'Đổi lịch',
        })
        self.assertEqual(moved.status_code, 200)
        self.assertEqual(moved.json()['booking_date'], (self.future_date + timedelta(days=1)).isoformat())
        self.assertEqual(self.client.put(f"/bookings/{booking['id']}", headers=self.customer1, json=self.payload()).status_code, 403)

    def test_status_workflow_cancel_and_complete_rules(self):
        booking = self.create()
        confirmed = self.client.patch(f"/bookings/{booking['id']}/confirm", headers=self.operator, json={'note': 'Đã duyệt'})
        self.assertEqual(confirmed.status_code, 409)
        self.assertEqual(self.client.patch(f"/bookings/{booking['id']}/complete", headers=self.operator, json={}).status_code, 409)
        cancelled = self.client.patch(f"/bookings/{booking['id']}/cancel", headers=self.customer1, json={'note': 'Đổi kế hoạch'})
        self.assertEqual(cancelled.json()['status'], 'cancelled_by_customer')
        replacement = self.client.post('/bookings', headers=self.customer2, json=self.payload())
        self.assertEqual(replacement.status_code, 201)
        rejected = self.create(time_slot_id=self.second_slot_id, booking_date=(self.future_date + timedelta(days=1)).isoformat())
        rejected_response = self.client.patch(f"/bookings/{rejected['id']}/reject", headers=self.owner, json={'note': 'Không khả dụng'})
        self.assertEqual(rejected_response.status_code, 409)
        with self.Session() as db:
            customer = db.scalar(select(User).where(User.email == 'customer1@test.local'))
            past = Booking(
                booking_code='SH-PAST-COMPLETE', customer_id=customer.id, field_id=self.field_id,
                time_slot_id=self.second_slot_id, booking_date=date.today() - timedelta(days=1),
                start_time_snapshot=time(10), end_time_snapshot=time(12), price_snapshot=550000,
                total_amount=550000, status='confirmed',
            )
            db.add(past); db.commit(); past_id = past.id
        completed = self.client.patch(f'/bookings/{past_id}/complete', headers=self.operator, json={})
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()['status'], 'completed')
        review = self.client.post('/reviews', headers=self.customer1, json={'booking_id': past_id, 'rating': 5, 'comment': 'Sân tốt, nhân viên hỗ trợ nhiệt tình.'})
        self.assertEqual(review.status_code, 201, review.text)
        self.assertEqual(self.client.post('/reviews', headers=self.customer1, json={'booking_id': past_id, 'rating': 4, 'comment': 'Đánh giá lại'}).status_code, 409)
        summary = self.client.get(f'/fields/{self.field_id}/reviews').json()
        self.assertEqual(summary['average_rating'], 5)
        self.assertEqual(summary['total_reviews'], 1)
        self.assertEqual(self.client.put(f"/management/reviews/{review.json()['id']}/reply", headers=self.customer1, json={'reply': 'Không có quyền'}).status_code, 403)
        replied = self.client.put(f"/management/reviews/{review.json()['id']}/reply", headers=self.owner, json={'reply': 'Cảm ơn bạn đã đánh giá.'})
        self.assertEqual(replied.status_code, 200)
        self.assertEqual(replied.json()['owner_reply'], 'Cảm ơn bạn đã đánh giá.')

if __name__ == '__main__':
    unittest.main()
