import unittest
from datetime import time, timedelta
from decimal import Decimal

from app.models.field import Booking, BookingSlot, Field
from app.models.time_slot import TimeSlot
from app.schemas.ai import SlotRecommendationRequest
from app.services.ai_feature_service import AIFeatureService
from app.services.ai_assistant_service import AIAssistantService
from app.services.ai_provider import AIProviderError
from app.services.analytics_service import AnalyticsService
from app.models.user import User
from tests import test_bookings as booking_tests


class MultiSlotBookingTests(unittest.TestCase):
    def setUp(self):
        self.case = booking_tests.BookingWorkflowTests('test_adjacent_bookings_do_not_overlap')
        self.case.setUp()
        with self.case.Session() as db:
            third = TimeSlot(
                field_id=self.case.field_id, name='Ca chiều', start_time=time(12), end_time=time(14),
                price=Decimal('650000'), is_active=True,
            )
            gap = TimeSlot(
                field_id=self.case.field_id, name='Ca tối', start_time=time(16), end_time=time(18),
                price=Decimal('750000'), is_active=True,
            )
            field = db.get(Field, self.case.field_id)
            field.deposit_type = 'percentage'
            field.deposit_value = Decimal('25')
            db.add_all([third, gap]); db.commit()
            self.third_slot_id, self.gap_slot_id = third.id, gap.id

    def tearDown(self):
        self.case.tearDown()

    def payload(self, slot_ids, **changes):
        return {
            'field_id': self.case.field_id,
            'time_slot_id': slot_ids[0],
            'time_slot_ids': slot_ids,
            'booking_date': self.case.future_date.isoformat(),
            'note': 'Đặt nhiều khung giờ',
            **changes,
        }

    def test_quote_and_create_three_consecutive_slots_use_authoritative_total(self):
        slot_ids = [self.case.slot_id, self.case.second_slot_id, self.third_slot_id]
        query = '&'.join(f'time_slot_ids={slot_id}' for slot_id in slot_ids)
        quote = self.case.client.get(
            f'/bookings/quote?field_id={self.case.field_id}&date={self.case.future_date}&{query}',
        )
        self.assertEqual(quote.status_code, 200, quote.text)
        data = quote.json()
        self.assertEqual(data['time_slot_ids'], slot_ids)
        self.assertEqual(data['duration_minutes'], 360)
        self.assertEqual(data['total_amount'], 1650000)
        self.assertEqual(data['deposit_amount'], 412500)
        self.assertEqual(data['remaining_amount'], 1237500)
        self.assertEqual([item['price'] for item in data['selected_slots']], [450000, 550000, 650000])

        created = self.case.client.post('/bookings', headers=self.case.customer1, json=self.payload(slot_ids))
        self.assertEqual(created.status_code, 201, created.text)
        booking = created.json()
        self.assertEqual(booking['start_time_snapshot'], '08:00:00')
        self.assertEqual(booking['end_time_snapshot'], '14:00:00')
        self.assertEqual(booking['time_slot_ids'], slot_ids)
        with self.case.Session() as db:
            details = db.query(BookingSlot).filter(BookingSlot.booking_id == booking['id']).order_by(BookingSlot.position).all()
            self.assertEqual([item.time_slot_id for item in details], slot_ids)

    def test_two_non_consecutive_slots_create_one_booking_without_blocking_gap(self):
        response = self.case.client.post(
            '/bookings', headers=self.case.customer1,
            json=self.payload([self.case.slot_id, self.gap_slot_id]),
        )
        self.assertEqual(response.status_code, 201, response.text)
        booking = response.json()
        self.assertEqual(booking['time_slot_ids'], [self.case.slot_id, self.gap_slot_id])
        self.assertEqual(booking['duration_minutes'], 240)
        self.assertEqual(booking['total_amount'], 1200000)
        available = self.case.client.get(
            f'/availability?date={self.case.future_date}&field_id={self.case.field_id}',
        ).json()[0]['available_slots']
        self.assertEqual(
            [slot['id'] for slot in available],
            [self.case.second_slot_id, self.third_slot_id],
        )

    def test_three_non_consecutive_slots_sum_each_real_price(self):
        slot_ids = [self.case.slot_id, self.third_slot_id, self.gap_slot_id]
        query = '&'.join(f'time_slot_ids={slot_id}' for slot_id in slot_ids)
        quote = self.case.client.get(
            f'/bookings/quote?field_id={self.case.field_id}&date={self.case.future_date}&{query}',
        ).json()
        self.assertEqual(quote['remaining_amount'], 1387500)
        response = self.case.client.post(
            '/bookings', headers=self.case.customer1, json=self.payload(slot_ids),
        )
        self.assertEqual(response.status_code, 201, response.text)
        booking = response.json()
        self.assertEqual(booking['time_slot_ids'], slot_ids)
        self.assertEqual(booking['duration_minutes'], 360)
        self.assertEqual(booking['total_amount'], 1850000)
        self.assertEqual(booking['deposit_amount'], 462500)
        self.assertEqual(booking['remaining_amount'], 1850000)

    def test_expired_multi_slot_hold_releases_every_selected_slot(self):
        slot_ids = [self.case.slot_id, self.third_slot_id, self.gap_slot_id]
        created = self.case.client.post(
            '/bookings', headers=self.case.customer1, json=self.payload(slot_ids),
        ).json()
        held = self.case.client.get(
            f'/availability?date={self.case.future_date}&field_id={self.case.field_id}',
        ).json()[0]['available_slots']
        self.assertEqual([slot['id'] for slot in held], [self.case.second_slot_id])
        with self.case.Session() as db:
            booking = db.get(Booking, created['id'])
            booking.hold_expires_at = booking.created_at - timedelta(minutes=1)
            db.commit()
        released = self.case.client.get(
            f'/availability?date={self.case.future_date}&field_id={self.case.field_id}',
        ).json()[0]['available_slots']
        self.assertEqual(
            [slot['id'] for slot in released],
            [self.case.slot_id, self.case.second_slot_id, self.third_slot_id, self.gap_slot_id],
        )

    def test_cancel_multi_slot_booking_releases_every_slot(self):
        slot_ids = [self.case.slot_id, self.third_slot_id, self.gap_slot_id]
        created = self.case.client.post(
            '/bookings', headers=self.case.customer1, json=self.payload(slot_ids),
        ).json()
        cancelled = self.case.client.patch(
            f"/bookings/{created['id']}/cancel", headers=self.case.customer1,
            json={'reason': 'Thay đổi kế hoạch sử dụng sân'},
        )
        self.assertEqual(cancelled.status_code, 200, cancelled.text)
        available = self.case.client.get(
            f'/availability?date={self.case.future_date}&field_id={self.case.field_id}',
        ).json()[0]['available_slots']
        self.assertEqual(
            [slot['id'] for slot in available],
            [self.case.slot_id, self.case.second_slot_id, self.third_slot_id, self.gap_slot_id],
        )

    def test_conflict_on_middle_slot_rejects_whole_booking(self):
        occupied = self.case.client.post(
            '/bookings', headers=self.case.customer1,
            json=self.payload([self.case.second_slot_id]),
        )
        self.assertEqual(occupied.status_code, 201, occupied.text)
        response = self.case.client.post(
            '/bookings', headers=self.case.customer2,
            json=self.payload([self.case.slot_id, self.case.second_slot_id, self.third_slot_id]),
        )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(
            self.case.client.get('/bookings/my?page_size=100', headers=self.case.customer2).json()['total'],
            0,
        )

    def test_reschedule_replaces_entire_slot_sequence(self):
        original = self.case.client.post(
            '/bookings', headers=self.case.customer1,
            json=self.payload([self.case.slot_id]),
        ).json()
        with self.case.Session() as db:
            booking = db.get(Booking, original['id'])
            booking.status = 'confirmed'
            booking.free_cancellation_minutes = 0
            db.commit()
        target_date = self.case.future_date + timedelta(days=1)
        payload = self.payload(
            [self.case.second_slot_id, self.third_slot_id],
            booking_date=target_date.isoformat(),
        )
        payload.pop('note')
        quote = self.case.client.post(
            f"/bookings/{original['id']}/reschedule/quote",
            headers=self.case.customer1, json=payload,
        )
        self.assertEqual(quote.status_code, 200, quote.text)
        self.assertEqual(quote.json()['new_total_amount'], 1200000)
        moved = self.case.client.patch(
            f"/bookings/{original['id']}/reschedule",
            headers=self.case.customer1, json=payload,
        )
        self.assertEqual(moved.status_code, 200, moved.text)
        self.assertEqual(moved.json()['time_slot_ids'], [self.case.second_slot_id, self.third_slot_id])
        self.assertEqual(moved.json()['start_time_snapshot'], '10:00:00')
        self.assertEqual(moved.json()['end_time_snapshot'], '14:00:00')

    def test_ai_recommends_only_exact_consecutive_sequence_for_duration(self):
        class UnavailableProvider:
            def generate_json(self, **_kwargs):
                raise AIProviderError('provider unavailable in test')

        with self.case.Session() as db:
            result = AIFeatureService(db, provider=UnavailableProvider()).recommend_slots(
                SlotRecommendationRequest(
                    sport_type='Bóng đá', booking_date=self.case.future_date,
                    court_id=self.case.field_id, start_time=time(8), end_time=time(14),
                    duration_minutes=360,
                ),
            )
        self.assertEqual(result['status'], 'OK')
        self.assertEqual(len(result['recommendations']), 1)
        recommendation = result['recommendations'][0]
        self.assertEqual(
            recommendation['slot_ids'],
            [self.case.slot_id, self.case.second_slot_id, self.third_slot_id],
        )
        self.assertEqual(recommendation['price'], 1650000)
        self.assertEqual(recommendation['duration_minutes'], 360)

    def test_ai_accepts_multiple_disjoint_time_ranges(self):
        class UnavailableProvider:
            def generate_json(self, **_kwargs):
                raise AIProviderError('provider unavailable in test')

        with self.case.Session() as db:
            result = AIFeatureService(db, provider=UnavailableProvider()).recommend_slots(
                SlotRecommendationRequest(
                    sport_type='Bóng đá', booking_date=self.case.future_date,
                    court_id=self.case.field_id,
                    time_ranges=[(time(8), time(10)), (time(16), time(18))],
                ),
            )
        self.assertEqual(result['status'], 'OK')
        recommendation = result['recommendations'][0]
        self.assertEqual(recommendation['slot_ids'], [self.case.slot_id, self.gap_slot_id])
        self.assertEqual(recommendation['duration_minutes'], 240)
        self.assertEqual(recommendation['price'], 1200000)

    def test_ai_parser_keeps_two_disjoint_ranges_in_one_sentence(self):
        ranges = AIAssistantService._time_ranges(
            'toi muon dat san luc 7-8h va 18-19h toi nay',
        )
        self.assertEqual(ranges, [(7 * 60, 8 * 60), (18 * 60, 19 * 60)])

    def test_analytics_counts_only_selected_slot_duration_not_gap(self):
        with self.case.Session() as db:
            owner = db.query(User).filter(User.email == 'bookingowner@test.local').one()
            db.get(Field, self.case.field_id).owner_id = owner.id
            db.commit()
        slot_ids = [self.case.slot_id, self.third_slot_id, self.gap_slot_id]
        created = self.case.client.post(
            '/bookings', headers=self.case.customer1, json=self.payload(slot_ids),
        ).json()
        with self.case.Session() as db:
            booking = db.get(Booking, created['id'])
            booking.status = 'confirmed'
            owner = db.query(User).filter(User.email == 'bookingowner@test.local').one()
            db.commit()
            analytics = AnalyticsService(db).occupancy(
                owner, self.case.future_date, self.case.future_date, self.case.field_id,
            )
        self.assertEqual(analytics['booked_hours'], 6)
        self.assertEqual(analytics['total_available_hours'], 8)
        self.assertEqual(analytics['occupancy_rate'], 75)


if __name__ == '__main__':
    unittest.main()
