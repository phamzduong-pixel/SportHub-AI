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


class SportsKnowledgeMultiTurnTests(unittest.TestCase):
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

    def test_multiturn_pronoun_followup_messi(self):
        """Turn 1: 'Messi là ai?' -> Turn 2: 'Anh ấy đang chơi cho đội nào?'"""
        # Turn 1
        res1 = self.client.post('/ai/assistant', json={'message': 'Messi là ai?'})
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1['intent'], 'SPORTS_KNOWLEDGE')
        self.assertEqual(data1['understood'].get('sports_entity'), 'Lionel Messi')
        conv_id = data1.get('conversation_id')
        self.assertIsNotNone(conv_id)

        # Turn 2: follow-up referencing 'Anh ấy'
        res2 = self.client.post('/ai/assistant', json={
            'message': 'Anh ấy đang chơi cho đội nào?',
            'conversation_id': conv_id,
            'context': data1['understood'],
        })
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2['intent'], 'SPORTS_KNOWLEDGE')
        self.assertEqual(data2['understood'].get('sports_entity'), 'Lionel Messi')
        self.assertIn('Inter Miami', data2['reply'])

    def test_multiturn_team_reference_followup_thai_nguyen(self):
        """Turn 1: 'Thái Nguyên T&T là đội bóng nào?' -> Turn 2: 'Đội này có thành tích gì nổi bật?'"""
        # Turn 1
        res1 = self.client.post('/ai/assistant', json={'message': 'Thái Nguyên T&T là đội bóng nào?'})
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1['intent'], 'SPORTS_KNOWLEDGE')
        self.assertEqual(data1['understood'].get('sports_entity'), 'Thái Nguyên T&T')
        conv_id = data1.get('conversation_id')

        # Turn 2: follow-up referencing 'Đội này'
        res2 = self.client.post('/ai/assistant', json={
            'message': 'Đội này có thành tích gì nổi bật?',
            'conversation_id': conv_id,
            'context': data1['understood'],
        })
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2['intent'], 'SPORTS_KNOWLEDGE')
        self.assertEqual(data2['understood'].get('sports_entity'), 'Thái Nguyên T&T')
        self.assertIn('Huy chương Đồng', data2['reply'])

    def test_multiturn_entity_switching(self):
        """Turn 1: 'Messi là ai?' -> Turn 2: 'Còn Quang Hải?'"""
        # Turn 1
        res1 = self.client.post('/ai/assistant', json={'message': 'Messi là ai?'})
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1['understood'].get('sports_entity'), 'Lionel Messi')
        conv_id = data1.get('conversation_id')

        # Turn 2: entity switch
        res2 = self.client.post('/ai/assistant', json={
            'message': 'Còn Quang Hải?',
            'conversation_id': conv_id,
            'context': data1['understood'],
        })
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2['intent'], 'SPORTS_KNOWLEDGE')
        self.assertEqual(data2['understood'].get('sports_entity'), 'Nguyễn Quang Hải')
        self.assertIn('Quang Hải', data2['reply'])
        self.assertIn('Công An Hà Nội', data2['reply'])

    def test_switch_from_sports_knowledge_to_business_intent(self):
        """Sports Knowledge -> Venue Search (Context Reset)"""
        # Turn 1: Sports Knowledge
        res1 = self.client.post('/ai/assistant', json={'message': 'Messi là ai?'})
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        conv_id = data1.get('conversation_id')

        # Turn 2: Search Venue
        res2 = self.client.post('/ai/assistant', json={
            'message': 'Tìm sân bóng đá ở Thái Nguyên',
            'conversation_id': conv_id,
            'context': data1['understood'],
        })
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertIn(data2['intent'], ('SEARCH_VENUE', 'CHECK_AVAILABILITY'))
        self.assertTrue(data2['context_reset'])
        self.assertEqual(data2['understood'].get('sport_type'), 'bóng đá')
        self.assertEqual(data2['understood'].get('location'), 'Thái Nguyên')

    def test_switch_from_business_intent_to_sports_knowledge(self):
        """Venue Search -> Sports Knowledge"""
        # Turn 1: Venue Search
        res1 = self.client.post('/ai/assistant', json={'message': 'Tìm sân bóng đá ở Thái Nguyên'})
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        conv_id = data1.get('conversation_id')

        # Turn 2: Sports Knowledge
        res2 = self.client.post('/ai/assistant', json={
            'message': 'Còn Ronaldo thì sao?',
            'conversation_id': conv_id,
            'context': data1['understood'],
        })
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2['intent'], 'SPORTS_KNOWLEDGE')
        self.assertEqual(data2['understood'].get('sports_entity'), 'Cristiano Ronaldo')
        self.assertIn('Cristiano Ronaldo', data2['reply'])

    def test_multiturn_persistence_and_restore(self):
        """Verify context persistence across database snapshot and conversation detail endpoint"""
        # Turn 1
        res1 = self.client.post('/ai/assistant', json={'message': 'Nguyễn Thùy Linh là ai?'})
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        conv_id = data1['conversation_id']

        # Check conversation detail endpoint
        res_detail = self.client.get(f'/ai/conversations/{conv_id}')
        self.assertEqual(res_detail.status_code, 200)
        detail = res_detail.json()
        self.assertEqual(detail['context_snapshot'].get('sports_entity'), 'Nguyễn Thùy Linh')
        self.assertEqual(detail['context_snapshot'].get('sport_type'), 'cầu lông')
        self.assertEqual(detail['context_snapshot'].get('last_intent'), 'SPORTS_KNOWLEDGE')

        # Turn 2: Restore without explicitly passing context in body (fallback to conv.context_snapshot)
        res2 = self.client.post('/ai/assistant', json={
            'message': 'Cô ấy đang thi đấu môn gì và thành tích ra sao?',
            'conversation_id': conv_id,
        })
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2['intent'], 'SPORTS_KNOWLEDGE')
        self.assertEqual(data2['understood'].get('sports_entity'), 'Nguyễn Thùy Linh')
        self.assertIn('Thùy Linh', data2['reply'])

    def test_multiturn_switch_from_messi_to_thai_nguyen_football(self):
        """Turn 1: 'Messi là ai?' -> Turn 2: 'Bóng đá ở Thái Nguyên có những đội nào?' (No reuse of Messi evidence)"""
        # Turn 1: Messi
        res1 = self.client.post('/ai/assistant', json={'message': 'Messi là ai?'})
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1['intent'], 'SPORTS_KNOWLEDGE')
        self.assertEqual(data1['understood'].get('sports_entity'), 'Lionel Messi')
        self.assertIn('Lionel Messi', data1['reply'])
        conv_id = data1.get('conversation_id')

        # Turn 2: Thai Nguyen football (must switch entity and evidence cleanly)
        res2 = self.client.post('/ai/assistant', json={
            'message': 'Bóng đá ở Thái Nguyên có những đội nào?',
            'conversation_id': conv_id,
            'context': data1['understood'],
        })
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2['intent'], 'SPORTS_KNOWLEDGE')
        self.assertEqual(data2['understood'].get('sports_entity'), 'Bóng đá Thái Nguyên')
        self.assertIn('Thái Nguyên T&T', data2['reply'])
        self.assertIn('FC Thái Nguyên', data2['reply'])
        self.assertNotIn('Lionel Messi', data2['reply'])


if __name__ == '__main__':
    unittest.main()
