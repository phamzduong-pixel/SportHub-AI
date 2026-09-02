from datetime import date, datetime, time, timedelta
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.field import Field
from app.models.time_slot import TimeSlot


class AssistantRankingProvider:
    def generate_json(self, **kwargs):
        available = kwargs['system_data']['available_slots']
        return {'status': 'OK', 'recommendations': [
            {'court_id': item['court_id'], 'slot_id': item['slot_id'], 'reason': 'Phù hợp nhu cầu.'}
            for item in available[:3]
        ]}


class AIContextFollowUpTests(unittest.TestCase):
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

    def test_multi_turn_select_second_court(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        context = {
            'sport_type': 'bóng đá',
            'booking_date': tomorrow,
            'result_field_ids': [10, 20, 30],
            'result_time_slot_ids': [101, 102, 103],
            'result_prices': [200000, 250000, 300000],
            'reference_price': 250000,
            'last_intent': 'SEARCH_VENUE'
        }
        with patch('app.repositories.ai_repository.AIRepository.field_context') as mock_court:
            mock_field = Field(id=20, name='Sân Số 2 An Phú', sport_type='bóng đá', capacity=10, base_price=250000, location='Cầu Giấy, Hà Nội', amenities=['Đèn chiếu sáng', 'Bãi xe'])
            mock_court.return_value = mock_field
            with patch('app.repositories.ai_repository.AIRepository.inventory', return_value=[(mock_field, TimeSlot(id=102, field_id=20, name='Ca 19h', start_time=time(19, 0), end_time=time(20, 30), price=250000, is_active=True, created_at=datetime.now(), updated_at=datetime.now()))]):
                response = self.client.post('/ai/assistant', json={'message': 'sân thứ 2 giá bao nhiêu', 'context': context})
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertIn('Sân Số 2 An Phú', data['reply'])
                self.assertIn('250.000', data['reply'])

    def test_multi_turn_cheaper_follow_up(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        context = {
            'sport_type': 'cầu lông',
            'booking_date': tomorrow,
            'reference_price': 150000,
            'result_field_ids': [1, 2],
            'last_intent': 'RECOMMEND_SLOT'
        }
        with patch('app.repositories.booking_repository.BookingRepository.availability') as mock_avail:
            mock_field = Field(id=1, name='Sân Cầu Lông A', sport_type='cầu lông', capacity=4, base_price=100000, location='Hà Nội', facility_id=1)
            mock_slot = TimeSlot(id=101, field_id=1, name='Ca sáng rẻ', start_time=time(8, 0), end_time=time(9, 0), price=100000, is_active=True, created_at=datetime.now(), updated_at=datetime.now())
            mock_avail.return_value = ([mock_field], [mock_slot], [], [], [])

            response = self.client.post('/ai/assistant', json={'message': 'có sân nào rẻ hơn không', 'context': context})
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['status'], 'OK')
            self.assertGreaterEqual(len(data['suggestions']), 1)
            self.assertEqual(data['suggestions'][0]['price'], 100000)

    def test_switch_sport_clears_old_context(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        context = {
            'sport_type': 'bóng đá',
            'location': 'Cầu Giấy',
            'booking_date': tomorrow,
            'result_field_ids': [1, 2],
            'last_intent': 'SEARCH_VENUE'
        }
        with patch('app.repositories.ai_repository.AIRepository.search_venues') as mock_search:
            mock_field = Field(id=5, name='Sân Tennis Ba Đình', sport_type='tennis', capacity=4, base_price=200000, location='Ba Đình, Hà Nội')
            mock_search.return_value = [mock_field]

            response = self.client.post('/ai/assistant', json={'message': 'tìm sân tennis ở Ba Đình', 'context': context})
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['understood']['sport_type'], 'tennis')
            self.assertEqual(data['understood']['location'], 'Ba Đình')
            self.assertTrue(data['context_reset'])


if __name__ == '__main__':
    unittest.main()
