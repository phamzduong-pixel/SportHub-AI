import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.knowledge_service import KnowledgeService


class AssistantRankingProvider:
    def generate_json(self, **kwargs):
        available = kwargs.get('system_data', {}).get('available_slots', [])
        return {'status': 'OK', 'recommendations': [
            {'court_id': item['court_id'], 'slot_id': item['slot_id'], 'reason': 'Phù hợp nhu cầu đã chọn.'}
            for item in available[:3]
        ]}


class SportsKnowledgeValidationTests(unittest.TestCase):
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

    def test_query_messi(self):
        res = self.client.post('/ai/assistant', json={'message': 'Messi là ai?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SPORTS_KNOWLEDGE')
        self.assertEqual(data['classification'], 'IN_SCOPE')
        self.assertIn('Lionel Messi', data['reply'])
        self.assertIn('Quả bóng vàng', data['reply'])
        self.assertIn('FIFA', data['reply'])

    def test_query_ronaldo(self):
        res = self.client.post('/ai/assistant', json={'message': 'Ronaldo là ai?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SPORTS_KNOWLEDGE')
        self.assertEqual(data['classification'], 'IN_SCOPE')
        self.assertIn('Cristiano Ronaldo', data['reply'])
        self.assertIn('Bồ Đào Nha', data['reply'])
        self.assertIn('Al-Nassr', data['reply'])

    def test_query_doi_tuyen_viet_nam(self):
        res = self.client.post('/ai/assistant', json={'message': 'Đội tuyển Việt Nam?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SPORTS_KNOWLEDGE')
        self.assertEqual(data['classification'], 'IN_SCOPE')
        self.assertIn('Đội tuyển bóng đá nam quốc gia Việt Nam', data['reply'])
        self.assertIn('AFF Cup', data['reply'])
        self.assertIn('VFF', data['reply'])

    def test_query_bong_da_thai_nguyen_co_nhung_doi_nao(self):
        res = self.client.post('/ai/assistant', json={'message': 'Bóng đá Thái Nguyên có những đội nào?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SPORTS_KNOWLEDGE')
        self.assertEqual(data['classification'], 'IN_SCOPE')
        self.assertIn('Thái Nguyên T&T', data['reply'])
        self.assertIn('FC Thái Nguyên', data['reply'])
        self.assertIn('Báo Thái Nguyên', data['reply'])

    def test_query_thai_nguyen_tt_club(self):
        res = self.client.post('/ai/assistant', json={'message': 'Thái Nguyên T&T là đội bóng nào?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SPORTS_KNOWLEDGE')
        self.assertIn('Thái Nguyên T&T', data['reply'])
        self.assertIn('bóng đá nữ chuyên nghiệp', data['reply'])

    def test_query_san_van_dong_thai_nguyen(self):
        res = self.client.post('/ai/assistant', json={'message': 'Sân vận động Thái Nguyên ở đâu và quy mô thế nào?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SPORTS_KNOWLEDGE')
        self.assertIn('Sân vận động Thái Nguyên', data['reply'])
        self.assertIn('22.000 chỗ ngồi', data['reply'])

    def test_query_volleyball_vietnam_women(self):
        res = self.client.post('/ai/assistant', json={'message': 'Đội tuyển bóng chuyền nữ Việt Nam?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SPORTS_KNOWLEDGE')
        self.assertIn('Đội tuyển bóng chuyền nữ Việt Nam', data['reply'])
        self.assertIn('AVC Challenge Cup', data['reply'])

    def test_query_vleague(self):
        res = self.client.post('/ai/assistant', json={'message': 'V-League là giải đấu gì?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SPORTS_KNOWLEDGE')
        self.assertIn('Giải Bóng đá Vô địch Quốc gia', data['reply'])
        self.assertIn('VPF', data['reply'])

    def test_query_badminton_court_dimensions(self):
        res = self.client.post('/ai/assistant', json={'message': 'Kích thước sân cầu lông tiêu chuẩn là bao nhiêu?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SPORTS_KNOWLEDGE')
        self.assertIn('13.40m', data['reply'])
        self.assertIn('BWF', data['reply'])


    def test_query_bong_da_nam_thai_nguyen(self):
        res = self.client.post('/ai/assistant', json={'message': 'Bóng đá nam Thái Nguyên có những đội nào và hoạt động ra sao?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SPORTS_KNOWLEDGE')
        self.assertIn('Bóng đá nam Thái Nguyên', data['reply'])
        self.assertIn('FC Thái Nguyên', data['reply'])
        self.assertIn('HPL/VSC', data['reply'])

    def test_query_bong_da_nu_thai_nguyen(self):
        res = self.client.post('/ai/assistant', json={'message': 'Đội bóng đá nữ Thái Nguyên là đội nào?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SPORTS_KNOWLEDGE')
        self.assertIn('Thái Nguyên T&T', data['reply'])
        self.assertIn('nữ chuyên nghiệp', data['reply'])

    def test_query_thai_nguyen_unanswerable_safe_fallback(self):
        """Query with Thai Nguyen keyword but unanswerable question must trigger safe fallback, not wrong evidence."""
        res = self.client.post('/ai/assistant', json={'message': 'Câu lạc bộ bóng đá Thái Nguyên được thành lập khi nào?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SPORTS_KNOWLEDGE')
        # Must return safe fallback without hallucinating or defaulting to Thai Nguyen T&T evidence
        self.assertIn('chưa có thông tin kiểm chứng', data['reply'])

    def test_query_thai_nguyen_pickleball(self):
        res = self.client.post('/ai/assistant', json={'message': 'Phong trào pickleball tại Thái Nguyên hiện nay ra sao?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SPORTS_KNOWLEDGE')
        self.assertIn('Pickleball', data['reply'])
        self.assertIn('Thái Nguyên', data['reply'])
        self.assertNotIn('Thái Nguyên T&T', data['reply'])

    def test_query_thai_nguyen_cau_long(self):
        res = self.client.post('/ai/assistant', json={'message': 'Phong trào cầu lông ở Thái Nguyên phát triển như thế nào?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SPORTS_KNOWLEDGE')
        self.assertIn('cầu lông', data['reply'].lower())
        self.assertIn('Sông Công', data['reply'])
        self.assertNotIn('Thái Nguyên T&T', data['reply'])


if __name__ == '__main__':
    unittest.main()

