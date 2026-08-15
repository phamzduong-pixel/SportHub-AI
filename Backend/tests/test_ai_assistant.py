from datetime import date, timedelta
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class AssistantRankingProvider:
    def generate_json(self, **kwargs):
        available = kwargs['system_data']['available_slots']
        return {'status': 'OK', 'recommendations': [
            {'court_id': item['court_id'], 'slot_id': item['slot_id'], 'reason': 'Phù hợp nhu cầu đã chọn.'}
            for item in available[:3]
        ]}


class AIAssistantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provider_patch = patch('app.services.ai_feature_service.StructuredAIProvider', return_value=AssistantRankingProvider())
        cls.provider_patch.start()
        cls.client = TestClient(app)
        cls.context = cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.client.__exit__(None, None, None)
        finally:
            cls.client.close()
            cls.provider_patch.stop()

    def test_customer_search_uses_live_available_inventory(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        response = self.client.post('/ai/assistant', json={'message': f'Ngày {tomorrow} còn sân cầu lông dưới 250.000đ nào?'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['source'], 'live_backend')
        self.assertEqual(payload['intent'], 'CHECK_AVAILABILITY')
        self.assertGreaterEqual(payload['confidence'], 0.9)
        self.assertEqual(payload['entities']['sport_type'], 'cầu lông')
        self.assertEqual(payload['entities']['price_max'], 250000)
        self.assertTrue(payload['suggestions'])
        self.assertTrue(all(item['sport_type'] == 'cầu lông' for item in payload['suggestions']))
        self.assertTrue(all(item['price'] <= 250000 for item in payload['suggestions']))

    def test_extracts_people_weekday_and_time_range(self):
        response = self.client.post('/ai/assistant', json={'message': 'Tìm sân bóng cho 10 người từ 18 giờ đến 20 giờ sáng Chủ nhật'})
        self.assertEqual(response.status_code, 200)
        understood = response.json()['understood']
        self.assertEqual(understood['sport_type'], 'bóng đá')
        self.assertEqual(understood['people'], 10)
        self.assertEqual(understood['start_time'], '18:00')
        self.assertEqual(understood['end_time'], '20:00')

    def test_returns_nearest_slot_when_requested_time_is_not_available(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        response = self.client.post('/ai/assistant', json={'message': f'Tìm sân pickleball lúc 13 giờ ngày {tomorrow}'})
        self.assertEqual(response.status_code, 200)
        suggestions = response.json()['suggestions']
        self.assertTrue(suggestions)
        self.assertTrue(suggestions[0]['is_nearest_alternative'])

    def test_assistant_never_creates_booking(self):
        before = self.client.get('/bookings').status_code
        response = self.client.post('/ai/assistant', json={'message': 'Đặt giúp tôi sân cầu lông tối nay'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/bookings').status_code, before)

    def test_asks_for_missing_date_instead_of_guessing(self):
        response = self.client.post('/ai/assistant', json={'message': 'Tìm sân cầu lông giá rẻ'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['needs_clarification'])
        self.assertEqual(payload['understood']['sport_type'], 'cầu lông')
        self.assertIsNone(payload['understood']['booking_date'])
        self.assertEqual(payload['suggestions'], [])
        self.assertEqual(payload['status'], 'NEED_MORE_DATA')
        self.assertEqual(payload['missing_fields'], ['date'])

    def test_understands_natural_tomorrow_time_and_duration(self):
        response = self.client.post('/ai/assistant', json={'message': 'Tìm sân cầu lông 8 giờ sáng mai chơi 2 tiếng'})
        self.assertEqual(response.status_code, 200)
        understood = response.json()['understood']
        self.assertEqual(understood['booking_date'], (date.today() + timedelta(days=1)).isoformat())
        self.assertEqual(understood['start_time'], '08:00')
        self.assertEqual(understood['end_time'], '10:00')
        self.assertEqual(understood['duration_minutes'], 120)

    def test_rejects_unrelated_request(self):
        response = self.client.post('/ai/assistant', json={'message': 'Hãy viết cho tôi một bài thơ'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['intent'], 'OUT_OF_SCOPE')
        self.assertEqual(payload['classification'], 'OUT_OF_SCOPE')
        self.assertFalse(payload['needs_clarification'])
        self.assertEqual(payload['suggestions'], [])

    def test_marks_ambiguous_request_unclear(self):
        response = self.client.post('/ai/assistant', json={'message': 'Bao nhiêu vậy?'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['classification'], 'UNCLEAR')
        self.assertEqual(payload['intent'], 'UNCLEAR')
        self.assertTrue(payload['needs_clarification'])

    def test_does_not_answer_general_knowledge_even_with_question_wording(self):
        response = self.client.post('/ai/assistant', json={'message': 'Python là gì và dùng để làm gì?'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['classification'], 'OUT_OF_SCOPE')
        self.assertIn('trợ lý chuyên biệt', payload['reply'])

    def test_private_booking_data_requires_login(self):
        response = self.client.post('/ai/assistant', json={'message': 'Trạng thái booking của tôi thế nào?'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['classification'], 'IN_SCOPE')
        self.assertEqual(payload['intent'], 'GET_BOOKING')
        self.assertIn('đăng nhập', payload['reply'])

    def test_general_payment_workflow_does_not_require_private_data(self):
        response = self.client.post('/ai/assistant', json={'message': 'Quy trình đặt cọc và thanh toán thế nào?'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['classification'], 'IN_SCOPE')
        self.assertEqual(payload['intent'], 'PAYMENT_SUPPORT')
        self.assertIn('tự xác nhận booking', payload['reply'])

    def test_follow_up_can_reference_second_result_deterministically(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        first = self.client.post('/ai/assistant', json={'message': f'Tìm sân cầu lông ngày {tomorrow}'}).json()
        if len(first['suggestions']) < 2:
            self.skipTest('Dữ liệu kiểm thử không có đủ hai kết quả')
        second = first['suggestions'][1]
        follow_up = self.client.post('/ai/assistant', json={
            'message': 'Sân thứ 2 giá bao nhiêu?',
            'context': first['understood'],
        }).json()
        self.assertEqual(follow_up['classification'], 'IN_SCOPE')
        self.assertEqual(follow_up['understood']['field_id'], second['field_id'])
        self.assertEqual(follow_up['understood']['time_slot_id'], second['time_slot_id'])
        self.assertEqual(follow_up['intent'], 'GET_VENUE_DETAIL')
        self.assertEqual(follow_up['suggestions'], [])
        self.assertIn(second['court_name'], follow_up['reply'])

    def test_limits_live_results_and_marks_availability(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        response = self.client.post('/ai/assistant', json={'message': f'Tìm sân cầu lông ngày {tomorrow}'})
        self.assertEqual(response.status_code, 200)
        suggestions = response.json()['suggestions']
        self.assertLessEqual(len(suggestions), 5)
        self.assertTrue(all(item['availability_status'] == 'available' for item in suggestions))

    def test_follow_up_uses_previous_extracted_context(self):
        first = self.client.post('/ai/assistant', json={'message': 'Tìm sân cầu lông'}).json()
        response = self.client.post('/ai/assistant', json={
            'message': '8 giờ sáng mai',
            'context': first['understood'],
        })
        self.assertEqual(response.status_code, 200)
        understood = response.json()['understood']
        self.assertEqual(understood['sport_type'], 'cầu lông')
        self.assertEqual(understood['start_time'], '08:00')

    def test_requested_football_phrase_returns_or_clarifies_then_searches(self):
        first = self.client.post('/ai/assistant', json={
            'message': 'tìm cho tôi một sân đá bóng lúc 8 giờ sáng, nếu không có hãy gợi ý giờ khác',
        })
        self.assertEqual(first.status_code, 200)
        first_payload = first.json()
        self.assertEqual(first_payload['understood']['sport_type'], 'bóng đá')
        self.assertEqual(first_payload['understood']['start_time'], '08:00')
        self.assertTrue(first_payload['needs_clarification'])

        follow_up = self.client.post('/ai/assistant', json={
            'message': 'ngày mai',
            'context': first_payload['understood'],
        })
        self.assertEqual(follow_up.status_code, 200)
        payload = follow_up.json()
        self.assertFalse(payload['needs_clarification'])
        self.assertTrue(payload['reply'])


if __name__ == '__main__':
    unittest.main()
