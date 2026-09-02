from datetime import date, datetime, time, timedelta
import unittest
from unittest.mock import MagicMock, patch

from app.models.field import Booking, Field
from app.models.time_slot import TimeSlot
from app.models.user import User
from app.schemas.ai import BookingMessageEvent, SlotRecommendationRequest
from app.services.ai_feature_service import AIFeatureService
from app.services.ai_provider import AIProviderError
from app.services.booking_message_service import BookingMessageService


class FakeMockDB:
    def __init__(self):
        self.bind = None

    def execute(self, *args, **kwargs):
        return self

    def scalar(self, *args, **kwargs):
        return None

    def scalars(self, *args, **kwargs):
        mock_result = MagicMock()
        mock_result.all.return_value = []
        return mock_result


class AIGenAIEvaluationTests(unittest.TestCase):
    def test_task1_rank_available_slots_strict_grounding(self):
        """Kiểm tra task 1: AI chỉ được chọn slot có trong available_slots, loại bỏ slot bịa đặt."""
        mock_db = FakeMockDB()
        service = AIFeatureService(mock_db)

        # Mock availability returning 2 valid court-slot pairs
        field1 = Field(id=1, name='Sân A', sport_type='bóng đá', capacity=10, base_price=200000, location='Hà Nội')
        slot1 = TimeSlot(id=101, field_id=1, name='Ca 18h', start_time=time(18, 0), end_time=time(19, 30), price=200000, is_active=True, created_at=datetime.now(), updated_at=datetime.now())
        field2 = Field(id=2, name='Sân B', sport_type='bóng đá', capacity=10, base_price=220000, location='Hà Nội')
        slot2 = TimeSlot(id=102, field_id=2, name='Ca 19h30', start_time=time(19, 30), end_time=time(21, 0), price=220000, is_active=True, created_at=datetime.now(), updated_at=datetime.now())

        service.availability = MagicMock()
        service.availability.available_pairs.return_value = [(field1, slot1), (field2, slot2)]

        # Mock LLM provider trying to return 1 valid slot and 1 hallucinated slot (court_id=999, slot_id=9999)
        mock_provider = MagicMock()
        mock_provider.generate_json.return_value = {
            'status': 'OK',
            'recommendations': [
                {'court_id': 1, 'slot_id': 101, 'reason': 'Slot chuẩn giờ.'},
                {'court_id': 999, 'slot_id': 9999, 'reason': 'Slot bịa đặt không tồn tại trong backend.'}
            ]
        }
        service.provider = mock_provider

        req = SlotRecommendationRequest(sport_type='bóng đá', booking_date=date.today() + timedelta(days=1))
        result = service.recommend_slots(req)

        self.assertEqual(result['status'], 'OK')
        # Guardrail must filter out the hallucinated slot, leaving only 1 validated slot
        self.assertEqual(len(result['recommendations']), 1)
        self.assertEqual(result['recommendations'][0]['court_id'], 1)
        self.assertEqual(result['recommendations'][0]['slot_id'], 101)
        self.assertEqual(result['source'], 'ai_validated')

    def test_task1_fallback_when_llm_fails(self):
        """Kiểm tra task 1: Fallback deterministic an toàn khi OpenAI API gặp lỗi."""
        mock_db = FakeMockDB()
        service = AIFeatureService(mock_db)

        field1 = Field(id=1, name='Sân A', sport_type='bóng đá', capacity=10, base_price=200000, location='Hà Nội')
        slot1 = TimeSlot(id=101, field_id=1, name='Ca 18h', start_time=time(18, 0), end_time=time(19, 30), price=200000, is_active=True, created_at=datetime.now(), updated_at=datetime.now())
        service.availability = MagicMock()
        service.availability.available_pairs.return_value = [(field1, slot1)]

        mock_provider = MagicMock()
        mock_provider.generate_json.side_effect = AIProviderError('OpenAI timeout')
        service.provider = mock_provider

        req = SlotRecommendationRequest(sport_type='bóng đá', booking_date=date.today() + timedelta(days=1))
        result = service.recommend_slots(req)

        self.assertEqual(result['status'], 'OK')
        self.assertEqual(result['source'], 'fallback')
        self.assertEqual(len(result['recommendations']), 1)
        self.assertEqual(result['recommendations'][0]['court_id'], 1)

    def test_task2_occupancy_promotions_prevents_hallucinated_metrics(self):
        """Kiểm tra task 2: AI tóm tắt công suất không được bịa số liệu hay tự ý áp dụng đổi giá DB."""
        mock_db = FakeMockDB()
        service = AIFeatureService(mock_db)

        analytics_data = {
            'occupancy_rate': 45.5,
            'booked_hours': 10.0,
            'total_operating_hours': 22.0,
            'peak_hours': [{'slot_id': 10, 'field_name': 'Sân 1', 'start_time': '18:00', 'end_time': '20:00'}],
            'low_demand_hours': [{'slot_id': 20, 'field_name': 'Sân 1', 'start_time': '08:00', 'end_time': '10:00'}]
        }

        with patch('app.services.analytics_service.AnalyticsService.occupancy', return_value=analytics_data):
            # Test case: LLM attempts to return numbers in qualitative summary
            mock_provider = MagicMock()
            mock_provider.generate_json.return_value = {
                'summary': 'Công suất đạt 99% rất cao',  # contains numbers -> must trigger validation error and fallback!
                'peak_slot_ids': [10],
                'low_demand_slot_ids': [20],
                'promotions': [{'slot_id': 20, 'suggestion': 'Giảm giá buổi sáng'}]
            }
            service.provider = mock_provider

            user = User(id=1, role='OWNER', full_name='Chủ Sân')
            res = service.occupancy_summary(user, date.today() - timedelta(days=7), date.today(), 1)
            # Must safely fallback because AI violated strict rules
            self.assertEqual(res['source'], 'fallback')

    def test_task3_write_booking_message_locks_business_facts(self):
        """Kiểm tra task 3: Khóa cứng sự thật nghiệp vụ, AI chỉ viết lời chào/kết an toàn."""
        mock_db = FakeMockDB()
        service = BookingMessageService(mock_db)

        mock_booking = MagicMock()
        mock_booking.id = 100
        mock_booking.booking_code = 'SH-123456'
        mock_booking.field_name = 'Sân Bóng Đá 1'
        mock_booking.facility_name = 'Cơ Sở Hoàng Gia'
        mock_booking.booking_date = date.today() + timedelta(days=1)
        mock_booking.start_time_snapshot = time(18, 0)
        mock_booking.end_time_snapshot = time(19, 30)
        mock_booking.total_amount = 300000
        mock_booking.paid_amount = 100000
        mock_booking.deposit_amount = 100000
        mock_booking.refund_amount = 0
        mock_booking.status = 'confirmed'
        mock_booking.payment_status = 'deposit_paid'

        with patch('app.services.booking_service.BookingService.get_for_user', return_value=mock_booking):
            mock_provider = MagicMock()
            mock_provider.generate_json.return_value = {
                'lead': 'Kính chào quý khách,',
                'closing': 'Chúc bạn có trận đấu vui vẻ!'
            }
            service.provider = mock_provider

            user = User(id=2, role='CUSTOMER', full_name='Khách Hàng')
            req = MagicMock()
            req.booking_id = 100
            req.event = BookingMessageEvent.BOOKING_CONFIRMED

            res = service.generate(req, user)
            self.assertEqual(res['source'], 'ai_validated')
            self.assertIn('Kính chào quý khách', res['message'])
            self.assertIn('SH-123456', res['message'])
            self.assertIn('100.000', res['message'])
            self.assertIn('Chúc bạn có trận đấu vui vẻ', res['message'])


if __name__ == '__main__':
    unittest.main()
