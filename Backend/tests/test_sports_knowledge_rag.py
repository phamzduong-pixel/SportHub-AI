import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.knowledge_retriever import KnowledgeRetriever
from app.services.knowledge_service import KnowledgeService


class AssistantRankingProvider:
    def generate_json(self, **kwargs):
        available = kwargs.get('system_data', {}).get('available_slots', [])
        return {'status': 'OK', 'recommendations': [
            {'court_id': item['court_id'], 'slot_id': item['slot_id'], 'reason': 'Phù hợp nhu cầu đã chọn.'}
            for item in available[:3]
        ]}


class SportsKnowledgeRAGTests(unittest.TestCase):
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

    # ----------------------------------------------------
    # 1. SPORTS SCOPE WHITELIST & ROUTING
    # ----------------------------------------------------
    def test_sports_knowledge_supported_football_messi(self):
        res = self.client.post('/ai/assistant', json={'message': 'Messi là ai?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SPORTS_KNOWLEDGE')
        self.assertEqual(data['classification'], 'IN_SCOPE')
        self.assertIn('Lionel Messi', data['reply'])
        self.assertIn('Argentina', data['reply'])
        self.assertIn('Nguồn: FIFA', data['reply'])

    def test_sports_knowledge_thai_nguyen_tt(self):
        res = self.client.post('/ai/assistant', json={'message': 'Thái Nguyên T&T là đội bóng nào?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SPORTS_KNOWLEDGE')
        self.assertIn('Thái Nguyên T&T', data['reply'])
        self.assertIn('Thái Nguyên', data['reply'])
        self.assertIn('Nguồn: Báo Thái Nguyên', data['reply'])

    def test_sports_knowledge_supported_badminton_thuy_linh(self):
        res = self.client.post('/ai/assistant', json={'message': 'Nguyễn Thùy Linh là ai?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SPORTS_KNOWLEDGE')
        self.assertIn('Nguyễn Thùy Linh', data['reply'])
        self.assertIn('tay vợt nữ số 1 Việt Nam', data['reply'])

    def test_sports_knowledge_unsupported_sport_golf_rejected(self):
        res = self.client.post('/ai/assistant', json={'message': 'Luật chơi môn golf thế nào?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'OUT_OF_SCOPE')
        self.assertEqual(data['classification'], 'OUT_OF_SCOPE')

    def test_sports_knowledge_unsupported_sport_f1_rejected(self):
        res = self.client.post('/ai/assistant', json={'message': 'Lewis Hamilton đang đua xe cho đội nào?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'OUT_OF_SCOPE')

    def test_sports_knowledge_unsupported_sport_baseball_rejected(self):
        res = self.client.post('/ai/assistant', json={'message': 'Luật chơi bóng chày là gì?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'OUT_OF_SCOPE')

    # ----------------------------------------------------
    # 2. ANTI-HALLUCINATION & RELEVANCE GATE
    # ----------------------------------------------------
    def test_sports_knowledge_anti_hallucination_fallback(self):
        res = self.client.post('/ai/assistant', json={'message': 'Cầu thủ bóng đá JohnDoe12345 thi đấu ở đâu?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SPORTS_KNOWLEDGE')
        self.assertIn('chưa có thông tin kiểm chứng', data['reply'])

    # ----------------------------------------------------
    # 3. FOLLOW-UP CONVERSATION
    # ----------------------------------------------------
    def test_sports_knowledge_followup_pronoun_and_entity_switch(self):
        # Turn 1: Messi
        first = self.client.post('/ai/assistant', json={'message': 'Messi là ai?'}).json()
        self.assertEqual(first['intent'], 'SPORTS_KNOWLEDGE')
        self.assertEqual(first['understood']['sports_entity'], 'Lionel Messi')

        # Turn 2: "Anh ấy đang chơi cho đội nào?" (Pronoun resolution)
        followup1 = self.client.post('/ai/assistant', json={
            'message': 'Anh ấy đang chơi cho đội nào?',
            'context': first['understood'],
        }).json()
        self.assertEqual(followup1['intent'], 'SPORTS_KNOWLEDGE')
        self.assertIn('Inter Miami', followup1['reply'])

        # Turn 3: "Còn Quang Hải?" (Entity switch)
        followup2 = self.client.post('/ai/assistant', json={
            'message': 'Còn Quang Hải?',
            'context': followup1['understood'],
        }).json()
        self.assertEqual(followup2['intent'], 'SPORTS_KNOWLEDGE')
        self.assertIn('Quang Hải', followup2['reply'])

        # Turn 4: "Đội Thái Nguyên thì sao?" (Local entity switch)
        followup3 = self.client.post('/ai/assistant', json={
            'message': 'Đội Thái Nguyên thì sao?',
            'context': followup2['understood'],
        }).json()
        self.assertEqual(followup3['intent'], 'SPORTS_KNOWLEDGE')
        self.assertIn('Thái Nguyên', followup3['reply'])

    # ----------------------------------------------------
    # 4. REGRESSION SAFETY (Preserve Existing Business)
    # ----------------------------------------------------
    def test_venue_search_is_not_intercepted_by_sports_knowledge(self):
        res = self.client.post('/ai/assistant', json={'message': 'Tìm sân bóng đá ở Thái Nguyên'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn(data['intent'], ('SEARCH_VENUE', 'CHECK_AVAILABILITY'))
        self.assertNotEqual(data['intent'], 'SPORTS_KNOWLEDGE')

    def test_system_guide_is_not_affected(self):
        res = self.client.post('/ai/assistant', json={'message': 'SportHub là gì?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SYSTEM_GUIDE')
        self.assertIn('SportHub', data['reply'])


if __name__ == '__main__':
    unittest.main()
