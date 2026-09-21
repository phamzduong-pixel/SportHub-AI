import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.knowledge_repository import get_knowledge_repository, reset_shared_knowledge_repository
from app.services.ai_sports_resolver import SportsContextResolver
from app.services.knowledge_retriever import KnowledgeRetriever


class AssistantRankingProvider:
    def generate_json(self, **kwargs):
        available = kwargs.get('system_data', {}).get('available_slots', [])
        return {'status': 'OK', 'recommendations': [
            {'court_id': item['court_id'], 'slot_id': item['slot_id'], 'reason': 'Phù hợp nhu cầu đã chọn.'}
            for item in available[:3]
        ]}


class SportsRetrievalPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reset_shared_knowledge_repository()
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
            reset_shared_knowledge_repository()

    def test_query_rewrite_and_tournament_resolution(self):
        """Test Query Understanding & Rewrite for tournament champions and follow-up matches."""
        # 1. Direct tournament champion question
        res1 = SportsContextResolver.resolve("Đội nào vô địch World Cup 2022?")
        self.assertEqual(res1.competition, "FIFA World Cup")
        self.assertEqual(res1.year, "2022")
        self.assertIn("FIFA World Cup 2022", res1.rewritten_query)

        # 2. Multi-turn follow-up: 'Họ thắng ai?'
        context = {
            'competition': 'FIFA World Cup',
            'year': '2022',
            'active_entity': 'Đội tuyển Argentina',
            'last_intent': 'SPORTS_KNOWLEDGE',
        }
        res2 = SportsContextResolver.resolve("Họ thắng ai?", context=context)
        self.assertTrue(res2.is_follow_up)
        self.assertEqual(res2.topic, "match_result")
        self.assertIn("Argentina", res2.rewritten_query)
        self.assertIn("FIFA World Cup 2022", res2.rewritten_query)

    def test_entity_correctness_and_boundary_isolation(self):
        """Retrieval must strictly isolate entities and avoid leaking irrelevant players."""
        repo = get_knowledge_repository()
        retriever = KnowledgeRetriever(repository=repo)

        # Query specifically for Messi
        results_messi = retriever.retrieve("Lionel Messi có World Cup chưa?", entity="Lionel Messi")
        self.assertTrue(len(results_messi) > 0)
        for entry, score in results_messi:
            self.assertEqual(entry.entity, "Lionel Messi")

        # Query specifically for Cristiano Ronaldo
        results_cr7 = retriever.retrieve("Cristiano Ronaldo có World Cup chưa?", entity="Cristiano Ronaldo")
        self.assertTrue(len(results_cr7) > 0)
        for entry, score in results_cr7:
            self.assertEqual(entry.entity, "Cristiano Ronaldo")

    def test_e2e_tournament_and_match_followup_pipeline(self):
        """E2E Turn 1: 'Đội nào vô địch World Cup 2022?' -> Turn 2: 'Họ thắng ai?'"""
        # Turn 1: Tournament champion
        res1 = self.client.post('/ai/assistant', json={'message': 'Đội nào vô địch World Cup 2022?'})
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1['intent'], 'SPORTS_KNOWLEDGE')
        self.assertIn('Argentina', data1['reply'])
        self.assertIn('Nguồn: FIFA', data1['reply'])
        conv_id = data1.get('conversation_id')

        # Turn 2: Follow-up match result ('Họ thắng ai?')
        res2 = self.client.post('/ai/assistant', json={
            'message': 'Họ thắng ai?',
            'conversation_id': conv_id,
            'context': data1['understood'],
        })
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2['intent'], 'SPORTS_KNOWLEDGE')
        self.assertIn('Pháp', data2['reply'])
        self.assertIn('Nguồn: FIFA', data2['reply'])

    def test_e2e_host_location_and_top_scorer_queries(self):
        """Test tournament host location and player statistics retrieval."""
        # Host location for WC 2026
        res1 = self.client.post('/ai/assistant', json={'message': 'World Cup 2026 được tổ chức ở đâu?'})
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1['intent'], 'SPORTS_KNOWLEDGE')
        self.assertTrue(any(loc in data1['reply'] for loc in ('Mỹ', 'Hoa Kỳ', 'Canada', 'Mexico')))

        # Top scorer for WC 2022
        res2 = self.client.post('/ai/assistant', json={'message': 'Vua phá lưới World Cup 2022 là ai?'})
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2['intent'], 'SPORTS_KNOWLEDGE')
        self.assertIn('Mbappé', data2['reply'])

    def test_insufficient_evidence_fallback_no_hallucination(self):
        """When asking for unknown/unverified sports stats, system gracefully declines without hallucinating."""
        res = self.client.post('/ai/assistant', json={'message': 'VĐV XYZ123 vô địch giải đấu nào năm 1950?'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'SPORTS_KNOWLEDGE')
        self.assertIn('chưa có thông tin kiểm chứng', data['reply'])

    def test_entity_switching_and_source_attribution_integrity(self):
        """Switching from Football (Messi) to Badminton (Nguyễn Thùy Linh) has zero cross-contamination."""
        # Turn 1: Messi
        res1 = self.client.post('/ai/assistant', json={'message': 'Messi sinh ngày nào?'})
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertIn('24 tháng 6 năm 1987', data1['reply'])
        self.assertIn('Nguồn:', data1['reply'])
        conv_id = data1.get('conversation_id')

        # Turn 2: Switch to Thuy Linh
        res2 = self.client.post('/ai/assistant', json={
            'message': 'Còn Nguyễn Thùy Linh sinh ở đâu?',
            'conversation_id': conv_id,
            'context': data1['understood'],
        })
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2['understood'].get('sports_entity'), 'Nguyễn Thùy Linh')
        self.assertIn('Phú Thọ', data2['reply'])
        self.assertNotIn('Messi', data2['reply'])
        self.assertNotIn('Argentina', data2['reply'])


if __name__ == '__main__':
    unittest.main()
