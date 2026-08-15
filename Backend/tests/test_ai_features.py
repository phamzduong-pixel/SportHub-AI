import unittest
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_password_hash
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.field import Booking, Field
from app.models.maintenance import FieldMaintenance
from app.models.payment import Payment
from app.models.time_slot import TimeSlot
from app.models.user import User
from app.repositories.booking_repository import BookingRepository
from app.services.ai_provider import AIProviderError


class RankingProvider:
    def __init__(self, valid_pair=None, invalid_only=False):
        self.valid_pair = valid_pair
        self.invalid_only = invalid_only

    def generate_json(self, **kwargs):
        task = kwargs['task']
        if task == 'rank_available_slots':
            choices = [{'court_id': 999999, 'slot_id': 999999, 'reason': 'invented'}]
            if self.valid_pair and not self.invalid_only:
                choices.append({'court_id': self.valid_pair[0], 'slot_id': self.valid_pair[1], 'reason': 'Phù hợp nhất.'})
            return {'status': 'OK', 'recommendations': choices}
        if task == 'write_booking_message_copy':
            return {'lead': 'Mã 123 đã đổi thành dữ liệu khác', 'closing': 'Hẹn gặp bạn.'}
        analytics = kwargs['system_data']['analytics']
        slot_id = analytics['low_peak_hours'][0]['slot_id']
        return {'summary': 'Nhu cầu đang tập trung không đồng đều trong kỳ.',
                'peak_slot_ids': [item['slot_id'] for item in analytics['peak_hours']],
                'low_demand_slot_ids': [item['slot_id'] for item in analytics['low_demand_hours']],
                'promotions': [{'slot_id': slot_id, 'suggestion': 'Cân nhắc ưu đãi giới hạn theo nhóm.'}]}


class FailingProvider:
    def generate_json(self, **_kwargs):
        raise AIProviderError('timeout')


class CapturingAnalyticsProvider(RankingProvider):
    def __init__(self):
        super().__init__()
        self.analytics = None

    def generate_json(self, **kwargs):
        if kwargs['task'] == 'summarize_occupancy_and_suggest_promotions':
            self.analytics = kwargs['system_data']['analytics']
        return super().generate_json(**kwargs)


class InventedAnalyticsProvider:
    def generate_json(self, **_kwargs):
        return {'summary': 'Công suất ổn định.', 'peak_slot_ids': [999999],
                'low_demand_slot_ids': [999998], 'promotions': []}


class PricingMutationProvider:
    def generate_json(self, **kwargs):
        analytics = kwargs['system_data']['analytics']
        low = analytics['low_demand_hours'][0]['slot_id']
        return {'summary': 'Nhu cầu phân bổ chưa đồng đều.',
                'peak_slot_ids': [item['slot_id'] for item in analytics['peak_hours']],
                'low_demand_slot_ids': [low],
                'promotions': [{'slot_id': low, 'suggestion': 'Đã cập nhật giá và tự động sửa bảng giá.'}]}


class AIFeatureTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(self.engine)
        with self.Session() as db:
            owner = User(full_name='AI Owner', email='feature-owner@test.local', hashed_password=get_password_hash('Owner@123456'), role='OWNER')
            customer = User(full_name='AI Customer', email='feature-customer@test.local', hashed_password=get_password_hash('Customer@123'), role='CUSTOMER')
            db.add_all([owner, customer]); db.flush()
            fields = [Field(owner_id=owner.id, name=name, sport_type='tennis', location='Quận 1', capacity=4,
                            base_price=price, status='available', amenities=[])
                      for name, price in [('Sân trống', 100), ('Sân đã đặt', 200), ('Sân bảo trì', 300)]]
            db.add_all(fields); db.flush()
            slots = [TimeSlot(field_id=field.id, name='Ca sáng', start_time=time(10), end_time=time(11),
                              price=Decimal(str(price)), weekday_price=Decimal(str(price + 10)),
                              weekend_price=Decimal(str(price + 50)), is_active=True)
                     for field, price in zip(fields, (100, 200, 300))]
            db.add_all(slots); db.flush()
            future = date.today() + timedelta(days=1)
            while future.weekday() != 5:
                future += timedelta(days=1)
            booking = Booking(booking_code='AI-FEATURE-001', customer_id=customer.id, field_id=fields[1].id,
                time_slot_id=slots[1].id, booking_date=future, start_time_snapshot=time(10), end_time_snapshot=time(11),
                price_snapshot=250, total_amount=250, deposit_amount=75, paid_amount=75, remaining_amount=175,
                payment_status='partial', status='confirmed')
            db.add(booking); db.flush()
            starts, ends = BookingRepository._slot_bounds(future, time(10), time(11))
            db.add(FieldMaintenance(field_id=fields[2].id, maintenance_type='REPAIR', title='Bảo trì',
                starts_at=starts, ends_at=ends, status='SCHEDULED', created_by=owner.id))
            db.add(Payment(booking_id=booking.id, customer_id=customer.id, owner_id=owner.id,
                transaction_code='AI-PAY-001', amount=75, total_amount=250, deposit_amount=75,
                remaining_amount=175, paid_amount=75, payment_status='paid', payment_method='bank_transfer',
                payment_type='deposit', status='paid', escrow_status='held', paid_at=datetime.now(timezone.utc)))
            db.add(Booking(booking_code='AI-FEATURE-CANCEL', customer_id=customer.id, field_id=fields[0].id,
                time_slot_id=slots[0].id, booking_date=future + timedelta(days=1),
                start_time_snapshot=time(10), end_time_snapshot=time(11), price_snapshot=110,
                total_amount=110, status='cancelled_by_customer'))
            db.add(Payment(booking_id=booking.id, customer_id=customer.id, owner_id=owner.id,
                transaction_code='AI-REFUND-001', amount=25, total_amount=250, deposit_amount=75,
                remaining_amount=175, paid_amount=50, payment_status='refunded', payment_method='bank_transfer',
                payment_type='refund', status='refunded', escrow_status='refunded', refunded_at=datetime.now(timezone.utc)))
            db.commit()
            self.owner_id, self.customer_id = owner.id, customer.id
            self.available_pair = (fields[0].id, slots[0].id)
            self.booked_pair = (fields[1].id, slots[1].id)
            self.maintenance_pair = (fields[2].id, slots[2].id)
            self.booking_id, self.future = booking.id, future

        def override_db():
            with self.Session() as db:
                yield db
        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)
        self.customer_headers = self.login('feature-customer@test.local', 'Customer@123')
        self.owner_headers = self.login('feature-owner@test.local', 'Owner@123456')

    def tearDown(self):
        self.client.close(); app.dependency_overrides.clear(); Base.metadata.drop_all(self.engine)

    def login(self, email, password):
        response = self.client.post('/auth/login', json={'email': email, 'password': password})
        self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': f"Bearer {response.json()['access_token']}"}

    def request_body(self):
        return {'sport_type': 'tennis', 'booking_date': self.future.isoformat(),
                'start_time': '10:00', 'end_time': '11:00', 'max_price': 1000}

    def test_only_live_available_slot_is_returned_and_price_is_authoritative(self):
        provider = RankingProvider(self.available_pair)
        with patch('app.services.ai_feature_service.StructuredAIProvider', return_value=provider):
            response = self.client.post('/ai/recommend-slots', headers=self.customer_headers, json=self.request_body())
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(len(payload['recommendations']), 1)
        item = payload['recommendations'][0]
        self.assertEqual((item['court_id'], item['slot_id']), self.available_pair)
        self.assertEqual(item['price'], 150.0)  # weekend_price from DB, never AI output
        self.assertNotEqual((item['court_id'], item['slot_id']), self.booked_pair)
        self.assertNotEqual((item['court_id'], item['slot_id']), self.maintenance_pair)

    def test_ai_only_returns_available_slots(self):
        provider = RankingProvider(self.available_pair)
        with patch('app.services.ai_feature_service.StructuredAIProvider', return_value=provider):
            payload = self.client.post('/ai/recommend-slots', headers=self.customer_headers, json=self.request_body()).json()
        self.assertEqual([(item['court_id'], item['slot_id']) for item in payload['recommendations']], [self.available_pair])

    def test_ai_rejects_unknown_slot(self):
        provider = RankingProvider(invalid_only=True)
        with patch('app.services.ai_feature_service.StructuredAIProvider', return_value=provider):
            payload = self.client.post('/ai/recommend-slots', headers=self.customer_headers, json=self.request_body()).json()
        self.assertEqual(payload['recommendations'], [])

    def test_ai_rejects_fake_court(self):
        provider = RankingProvider((999999, self.available_pair[1]))
        with patch('app.services.ai_feature_service.StructuredAIProvider', return_value=provider):
            payload = self.client.post('/ai/recommend-slots', headers=self.customer_headers, json=self.request_body()).json()
        self.assertEqual(payload['recommendations'], [])

    def test_booked_slot_not_recommended(self):
        provider = RankingProvider(self.booked_pair)
        with patch('app.services.ai_feature_service.StructuredAIProvider', return_value=provider):
            payload = self.client.post('/ai/recommend-slots', headers=self.customer_headers, json=self.request_body()).json()
        self.assertEqual(payload['recommendations'], [])

    def test_maintenance_slot_not_recommended(self):
        provider = RankingProvider(self.maintenance_pair)
        with patch('app.services.ai_feature_service.StructuredAIProvider', return_value=provider):
            payload = self.client.post('/ai/recommend-slots', headers=self.customer_headers, json=self.request_body()).json()
        self.assertEqual(payload['recommendations'], [])

    def test_ai_does_not_change_price(self):
        provider = RankingProvider(self.available_pair)
        with patch('app.services.ai_feature_service.StructuredAIProvider', return_value=provider):
            item = self.client.post('/ai/recommend-slots', headers=self.customer_headers, json=self.request_body()).json()['recommendations'][0]
        self.assertEqual(item['price'], 150.0)

    def test_ai_slot_outside_input_is_filtered(self):
        provider = RankingProvider(invalid_only=True)
        with patch('app.services.ai_feature_service.StructuredAIProvider', return_value=provider):
            response = self.client.post('/ai/recommend-slots', headers=self.customer_headers, json=self.request_body())
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['recommendations'], [])
        self.assertEqual(response.json()['source'], 'ai_filtered')

    def test_no_available_slot_and_missing_or_invalid_input(self):
        with self.Session() as db:
            customer = db.get(User, self.customer_id)
            db.add(Booking(booking_code='AI-FEATURE-BLOCK-ALL', customer_id=customer.id,
                field_id=self.available_pair[0], time_slot_id=self.available_pair[1], booking_date=self.future,
                start_time_snapshot=time(10), end_time_snapshot=time(11), price_snapshot=150,
                total_amount=150, status='confirmed'))
            db.commit()
        response = self.client.post('/ai/recommend-slots', headers=self.customer_headers, json=self.request_body())
        self.assertEqual(response.json()['status'], 'NO_AVAILABLE_SLOT')
        missing = self.request_body(); missing.pop('booking_date')
        missing_response = self.client.post('/ai/recommend-slots', headers=self.customer_headers, json=missing)
        self.assertEqual(missing_response.status_code, 200)
        self.assertEqual(missing_response.json()['status'], 'NEED_MORE_DATA')
        invalid = self.request_body(); invalid.update({'start_time': '11:00', 'end_time': '10:00'})
        invalid_response = self.client.post('/ai/recommend-slots', headers=self.customer_headers, json=invalid)
        self.assertEqual(invalid_response.json()['status'], 'NEED_MORE_DATA')

    def test_no_available_slot(self):
        with self.Session() as db:
            db.add(Booking(booking_code='AI-NO-SLOT', customer_id=self.customer_id,
                field_id=self.available_pair[0], time_slot_id=self.available_pair[1], booking_date=self.future,
                start_time_snapshot=time(10), end_time_snapshot=time(11), price_snapshot=150,
                total_amount=150, status='confirmed'))
            db.commit()
        payload = self.client.post('/ai/recommend-slots', headers=self.customer_headers, json=self.request_body()).json()
        self.assertEqual(payload['status'], 'NO_AVAILABLE_SLOT')
        self.assertEqual(payload['recommendations'], [])

    def test_missing_date_requests_clarification(self):
        body = self.request_body(); body.pop('booking_date')
        payload = self.client.post('/ai/recommend-slots', headers=self.customer_headers, json=body).json()
        self.assertEqual(payload['status'], 'NEED_MORE_DATA')
        self.assertEqual(payload['missing_fields'], ['date'])

    def test_booking_message_fallback_preserves_database_facts(self):
        provider = RankingProvider()
        with patch('app.services.booking_message_service.OpenAIProvider', return_value=provider):
            response = self.client.post('/ai/generate-booking-message', headers=self.customer_headers,
                json={'booking_id': self.booking_id, 'event': 'OWNER_CONFIRMED'})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload['source'], 'fallback')
        self.assertIn('AI-FEATURE-001', payload['message'])
        self.assertIn(self.future.strftime('%d/%m/%Y'), payload['message'])
        self.assertIn('10:00-11:00', payload['message'])
        self.assertEqual(payload['booking_facts']['booking_code'], 'AI-FEATURE-001')
        self.assertEqual(payload['booking_facts']['amount'], 75.0)

    def booking_message(self, provider=None):
        with patch('app.services.booking_message_service.OpenAIProvider', return_value=provider or RankingProvider()):
            response = self.client.post('/ai/generate-booking-message', headers=self.customer_headers,
                json={'booking_id': self.booking_id, 'event': 'BOOKING_CONFIRMED'})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_booking_message_keeps_booking_code(self):
        payload = self.booking_message()
        self.assertEqual(payload['booking_facts']['booking_code'], 'AI-FEATURE-001')
        self.assertIn('AI-FEATURE-001', payload['message'])

    def test_booking_message_keeps_date(self):
        payload = self.booking_message()
        self.assertEqual(payload['booking_facts']['date'], self.future.isoformat())
        self.assertIn(self.future.strftime('%d/%m/%Y'), payload['message'])

    def test_booking_message_keeps_time(self):
        payload = self.booking_message()
        self.assertEqual(payload['booking_facts']['start_time'], '10:00:00')
        self.assertEqual(payload['booking_facts']['end_time'], '11:00:00')
        self.assertIn('10:00-11:00', payload['message'])

    def test_booking_message_keeps_amount(self):
        payload = self.booking_message()
        self.assertEqual(payload['booking_facts']['amount'], 75.0)
        self.assertEqual(payload['booking_facts']['deposit_amount'], 75.0)

    def test_booking_message_fallback_when_ai_fails(self):
        payload = self.booking_message(FailingProvider())
        self.assertEqual(payload['source'], 'fallback')
        self.assertIn('AI-FEATURE-001', payload['message'])

    def test_ai_provider_timeout_fallback(self):
        payload = self.booking_message(FailingProvider())
        self.assertEqual(payload['source'], 'fallback')

    def test_occupancy_and_low_peak_are_computed_before_ai(self):
        provider = RankingProvider()
        end = self.future + timedelta(days=1)
        with patch('app.services.ai_feature_service.StructuredAIProvider', return_value=provider):
            response = self.client.get(
                f'/ai/occupancy-summary?date_from={self.future}&date_to={end}', headers=self.owner_headers,
            )
        self.assertEqual(response.status_code, 200, response.text)
        analytics = response.json()['analytics']
        self.assertEqual(analytics['total_operating_hours'], 6.0)
        self.assertEqual(analytics['booked_hours'], 1.0)
        self.assertEqual(analytics['booking_count'], 1)
        self.assertAlmostEqual(analytics['occupancy_rate'], 16.67, places=2)
        self.assertEqual(analytics['revenue'], 50.0)
        self.assertEqual(analytics['cancellation_rate'], 50.0)
        self.assertTrue(analytics['low_peak_hours'])
        self.assertEqual(response.json()['label'], 'Gợi ý AI')

    def test_occupancy_ai_uses_calculated_data(self):
        provider = CapturingAnalyticsProvider()
        with patch('app.services.ai_feature_service.StructuredAIProvider', return_value=provider):
            payload = self.client.get(
                f'/ai/occupancy-summary?date_from={self.future}&date_to={self.future + timedelta(days=1)}',
                headers=self.owner_headers,
            ).json()
        self.assertIsNotNone(provider.analytics)
        self.assertEqual(provider.analytics['occupancy_rate'], payload['analytics']['occupancy_rate'])
        self.assertEqual(provider.analytics['revenue'], payload['analytics']['revenue'])

    def test_occupancy_summary(self):
        provider = RankingProvider()
        with patch('app.services.ai_feature_service.StructuredAIProvider', return_value=provider):
            payload = self.client.get(
                f'/ai/occupancy-summary?date_from={self.future}&date_to={self.future + timedelta(days=1)}',
                headers=self.owner_headers,
            ).json()
        self.assertEqual(payload['label'], 'Gợi ý AI')
        self.assertTrue(payload['summary'])
        self.assertEqual(payload['analytics']['total_available_hours'], 6.0)
        self.assertTrue(payload['analytics']['occupancy_by_court'])
        self.assertEqual(len(payload['analytics']['occupancy_by_day']), 2)
        self.assertTrue(payload['analytics']['occupancy_by_time'])

    def test_owner_assistant_routes_occupancy_insight(self):
        provider = RankingProvider()
        with patch('app.services.ai_feature_service.StructuredAIProvider', return_value=provider):
            response = self.client.post('/ai/assistant', headers=self.owner_headers,
                json={'message': 'Công suất sân tuần này thế nào?'})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload['intent'], 'OCCUPANCY_INSIGHT')
        self.assertIn('Gợi ý AI', payload['reply'])
        self.assertIn('không tự thay đổi giá', payload['reply'])

    def test_low_demand_hour_detection(self):
        provider = RankingProvider()
        with patch('app.services.ai_feature_service.StructuredAIProvider', return_value=provider):
            analytics = self.client.get(
                f'/ai/occupancy-summary?date_from={self.future}&date_to={self.future + timedelta(days=1)}',
                headers=self.owner_headers,
            ).json()['analytics']
        rates = [item['occupancy_rate'] for item in analytics['occupancy_by_court']]
        self.assertEqual(analytics['low_demand_hours'][0]['occupancy_rate'], min(rates))

    def test_peak_hour_detection(self):
        provider = RankingProvider()
        with patch('app.services.ai_feature_service.StructuredAIProvider', return_value=provider):
            analytics = self.client.get(
                f'/ai/occupancy-summary?date_from={self.future}&date_to={self.future + timedelta(days=1)}',
                headers=self.owner_headers,
            ).json()['analytics']
        slot_rates = [item['occupancy_rate'] for item in analytics['low_peak_hours']]
        self.assertEqual(analytics['peak_hours'][0]['occupancy_rate'], max(slot_rates))

    def test_ai_cannot_modify_pricing(self):
        with self.Session() as db:
            before = {item.id: float(item.price) for item in db.scalars(select(TimeSlot)).all()}
        with patch('app.services.ai_feature_service.StructuredAIProvider', return_value=PricingMutationProvider()):
            payload = self.client.get(
                f'/ai/occupancy-summary?date_from={self.future}&date_to={self.future + timedelta(days=1)}',
                headers=self.owner_headers,
            ).json()
        with self.Session() as db:
            after = {item.id: float(item.price) for item in db.scalars(select(TimeSlot)).all()}
        self.assertEqual(after, before)
        self.assertEqual(payload['promotion_suggestions'], [])

    def test_ai_does_not_invent_analytics(self):
        with patch('app.services.ai_feature_service.StructuredAIProvider', return_value=InventedAnalyticsProvider()):
            payload = self.client.get(
                f'/ai/occupancy-summary?date_from={self.future}&date_to={self.future + timedelta(days=1)}',
                headers=self.owner_headers,
            ).json()
        self.assertEqual(payload['source'], 'fallback')
        self.assertNotIn(999999, [item['slot_id'] for item in payload['peak_hours']])


if __name__ == '__main__':
    unittest.main()
