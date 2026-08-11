from datetime import date
import unittest

from app.services.ai_assistant_service import AIAssistantService
from app.services.ai_intent_router import AssistantIntent, IntentRouter


class IntentRouterTests(unittest.TestCase):
    def setUp(self):
        self.router = IntentRouter()
        self.today = date(2026, 8, 10)

    def route(self, message, context=None):
        return self.router.route(message, context, today=self.today)

    def test_search_extracts_required_entities(self):
        result = self.route('Tìm sân cầu lông tối mai lúc 19h dưới 150k')
        self.assertEqual(result.intent, AssistantIntent.SEARCH_VENUE)
        self.assertGreaterEqual(result.confidence, 0.9)
        self.assertEqual(result.entities.sport_type, 'cầu lông')
        self.assertEqual(result.entities.date, '2026-08-11')
        self.assertEqual(result.entities.start_time, '19:00')
        self.assertEqual(result.entities.price_max, 150000)
        self.assertFalse(result.needs_clarification)

    def test_availability_uses_conversation_context(self):
        result = self.route('Sân này còn 19h không?', {
            'sport_type': 'cầu lông', 'booking_date': '2026-08-11', 'field_id': 12,
        })
        self.assertEqual(result.intent, AssistantIntent.CHECK_AVAILABILITY)
        self.assertTrue(result.is_follow_up)
        self.assertEqual(result.entities.date, '2026-08-11')
        self.assertEqual(result.entities.start_time, '19:00')
        self.assertFalse(result.needs_clarification)

    def test_booking_cancel_payment_and_account_intents(self):
        cases = (
            ('Booking SH123 của tôi thế nào?', AssistantIntent.GET_BOOKING, 'SH123'),
            ('Tôi muốn hủy sân', AssistantIntent.CANCEL_BOOKING, None),
            ('Đổi lịch booking SH-ABC123', AssistantIntent.RESCHEDULE_BOOKING, 'SH-ABC123'),
            ('Tiền cọc có được hoàn không?', AssistantIntent.PAYMENT_SUPPORT, None),
            ('Tôi muốn cập nhật hồ sơ', AssistantIntent.ACCOUNT_SUPPORT, None),
        )
        for message, intent, code in cases:
            with self.subTest(message=message):
                result = self.route(message)
                self.assertEqual(result.intent, intent)
                self.assertEqual(result.entities.booking_code, code)

    def test_recommend_detail_create_guide_and_greeting(self):
        cases = (
            ('Gợi ý sân bóng phù hợp ngày mai', AssistantIntent.RECOMMEND_VENUE),
            ('Địa chỉ và tiện ích sân này?', AssistantIntent.GET_VENUE_DETAIL),
            ('Tôi muốn đặt sân cầu lông ngày mai', AssistantIntent.CREATE_BOOKING),
            ('Hướng dẫn cách sử dụng SportHub', AssistantIntent.SYSTEM_GUIDE),
            ('Xin chào', AssistantIntent.GREETING),
        )
        for message, intent in cases:
            with self.subTest(message=message):
                self.assertEqual(self.route(message, {'field_id': 1}).intent, intent)

    def test_follow_up_unclear_and_out_of_scope(self):
        follow_up = self.route('Sân thứ 2', {'result_field_ids': [3, 7], 'last_intent': 'SEARCH_VENUE'})
        self.assertEqual(follow_up.intent, AssistantIntent.FOLLOW_UP)
        self.assertTrue(follow_up.is_follow_up)
        self.assertEqual(self.route('Bao nhiêu vậy?').intent, AssistantIntent.UNCLEAR)
        self.assertEqual(self.route('Python là gì?').intent, AssistantIntent.OUT_OF_SCOPE)
        self.assertEqual(self.route('Thịt chó ngon không?').intent, AssistantIntent.OUT_OF_SCOPE)

    def test_out_of_scope_service_never_queries_repository(self):
        class NoQueryRepository:
            def __init__(self):
                self.queries = 0

            def scope_for_user(self, _user):
                pass

            def __getattr__(self, _name):
                self.queries += 1
                raise AssertionError('OUT_OF_SCOPE không được query repository')

        repository = NoQueryRepository()
        payload = AIAssistantService(repository).ask('Python là gì?')
        self.assertEqual(payload['intent'], 'OUT_OF_SCOPE')
        self.assertEqual(payload['suggestions'], [])
        self.assertEqual(repository.queries, 0)


if __name__ == '__main__':
    unittest.main()
