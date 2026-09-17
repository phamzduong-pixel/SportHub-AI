import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.knowledge_entry import KnowledgeEntry
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.knowledge_retriever import KnowledgeRetriever
from app.services.knowledge_service import KnowledgeService
from app.services.rag_guardrail import RAGGuardrail


class AssistantRankingProvider:
    def generate_json(self, **kwargs):
        available = kwargs.get('system_data', {}).get('available_slots', [])
        return {'status': 'OK', 'recommendations': [
            {'court_id': item['court_id'], 'slot_id': item['slot_id'], 'reason': 'Phù hợp nhu cầu đã chọn.'}
            for item in available[:3]
        ]}


class SportsKnowledgePipelineTests(unittest.TestCase):
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
    # 1. Query with Matching Evidence -> Grounded Answer
    # ----------------------------------------------------
    def test_query_with_evidence_answers_grounded(self):
        res = self.client.post('/ai/assistant', json={'message': 'Messi là ai?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SPORTS_KNOWLEDGE')
        self.assertEqual(data['classification'], 'IN_SCOPE')
        self.assertEqual(data['status'], 'OK')

        # Evidence validation
        self.assertIn('Lionel Messi', data['reply'])
        self.assertIn('Inter Miami', data['reply'])
        self.assertIn('World Cup 2022', data['reply'])

    # ----------------------------------------------------
    # 2. Query with No Evidence -> Fallback (No Hallucination)
    # ----------------------------------------------------
    def test_query_no_evidence_returns_fallback_no_hallucination(self):
        res = self.client.post('/ai/assistant', json={'message': 'Cầu thủ bóng đá FakePlayerXYZ999 đang đá cho đội nào?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SPORTS_KNOWLEDGE')
        self.assertIn('chưa có thông tin kiểm chứng', data['reply'])
        self.assertNotIn('Real Madrid', data['reply'])
        self.assertNotIn('Manchester United', data['reply'])

    # ----------------------------------------------------
    # 3. Low Relevance Evidence -> Guardrail Trigger Fallback
    # ----------------------------------------------------
    def test_low_relevance_evidence_triggers_fallback(self):
        # Query about sports rules not covered in the knowledge base (below threshold)
        res = self.client.post('/ai/assistant', json={'message': 'Luật thi đấu bóng rổ cho người khuyết tật quy định thế nào?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SPORTS_KNOWLEDGE')
        self.assertIn('chưa có thông tin kiểm chứng', data['reply'])

    # ----------------------------------------------------
    # 4. Multiple Candidates -> Select Most Relevant Evidence
    # ----------------------------------------------------
    def test_multiple_candidate_documents_selects_best_evidence(self):
        # Query specifically about club/team
        res_club = self.client.post('/ai/assistant', json={'message': 'Messi đang chơi cho đội nào?'})
        self.assertEqual(res_club.status_code, 200)
        data_club = res_club.json()
        self.assertEqual(data_club['intent'], 'SPORTS_KNOWLEDGE')
        self.assertIn('Inter Miami', data_club['reply'])
        self.assertIn('MLS', data_club['reply'])

        # Query specifically about bio
        res_bio = self.client.post('/ai/assistant', json={'message': 'Messi là ai?'})
        self.assertEqual(res_bio.status_code, 200)
        data_bio = res_bio.json()
        self.assertIn('8 Quả bóng vàng', data_bio['reply'])

    # ----------------------------------------------------
    # 5. Source Metadata Preserved and Displayed
    # ----------------------------------------------------
    def test_source_metadata_preserved_and_displayed(self):
        res = self.client.post('/ai/assistant', json={'message': 'Thái Nguyên T&T là đội bóng nào?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SPORTS_KNOWLEDGE')
        self.assertIn('Nguồn: Báo Thái Nguyên', data['reply'])
        self.assertIn('https://baothainguyen.vn', data['reply'])
        self.assertIn('cập nhật 2026-03-01', data['reply'])

    # ----------------------------------------------------
    # 6. Sports Knowledge Does Not Affect Business Intents
    # ----------------------------------------------------
    def test_sports_knowledge_does_not_affect_business_intents(self):
        # 1. Search venue
        res_search = self.client.post('/ai/assistant', json={'message': 'Tìm sân bóng đá ở Thái Nguyên'})
        self.assertEqual(res_search.status_code, 200)
        data_search = res_search.json()
        self.assertIn(data_search['intent'], ('SEARCH_VENUE', 'CHECK_AVAILABILITY'))
        self.assertNotEqual(data_search['intent'], 'SPORTS_KNOWLEDGE')

        # 2. Check availability
        res_avail = self.client.post('/ai/assistant', json={'message': 'Sân bóng đá ở Thái Nguyên còn trống tối nay?'})
        self.assertEqual(res_avail.status_code, 200)
        data_avail = res_avail.json()
        self.assertEqual(data_avail['intent'], 'CHECK_AVAILABILITY')
        self.assertEqual(data_avail['source'], 'live_backend')

        # 3. System Guide
        res_guide = self.client.post('/ai/assistant', json={'message': 'SportHub là gì?'})
        self.assertEqual(res_guide.status_code, 200)
        data_guide = res_guide.json()
        self.assertEqual(data_guide['intent'], 'SYSTEM_GUIDE')
        self.assertIn('SportHub', data_guide['reply'])


if __name__ == '__main__':
    unittest.main()
