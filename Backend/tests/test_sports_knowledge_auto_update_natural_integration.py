import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.knowledge_entry import KnowledgeEntry
from app.repositories.knowledge_repository import get_knowledge_repository, reset_shared_knowledge_repository
from app.services.knowledge_service import get_knowledge_service, reset_shared_knowledge_service
from app.services.knowledge_update_service import KnowledgeUpdateService
from app.services.sports_web_retriever import SportsWebEvidence


class AssistantScenarioMockProvider:
    def generate_json(self, **kwargs):
        available = kwargs.get('system_data', {}).get('available_slots', [])
        return {
            'status': 'OK',
            'recommendations': [
                {'court_id': item['court_id'], 'slot_id': item['slot_id'], 'reason': 'Phù hợp nhu cầu.'}
                for item in available[:3]
            ],
        }


class SportsKnowledgeAutoUpdateNaturalIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provider_patch = patch('app.services.ai_feature_service.StructuredAIProvider', return_value=AssistantScenarioMockProvider())
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

    def setUp(self):
        # Reset shared instances to clean state for each test
        reset_shared_knowledge_service()
        reset_shared_knowledge_repository()
        self.repo = get_knowledge_repository()
        self.knowledge_service = get_knowledge_service()
        self.update_service = KnowledgeUpdateService(
            repository=self.repo,
            retriever=self.knowledge_service.retriever,
        )

    def tearDown(self):
        reset_shared_knowledge_service()
        reset_shared_knowledge_repository()

    # 1. New Knowledge Update -> Re-index -> Natural Assistant Retrieval
    def test_new_knowledge_update_and_natural_assistant_retrieval(self):
        """
        Flow:
        1. Query Natural Assistant for unverified fact -> Safe fallback.
        2. Web Update pipeline inserts new verified sports fact and incrementally indexes it.
        3. Query Natural Assistant again -> Returns grounded answer with evidence and source citations.
        4. Query Professional Assistant -> Strictly refused.
        """
        query_text = "Phong trào Pickleball sinh viên ICTU phát triển thế nào?"

        # Step 1: Before update -> Safe fallback
        with patch('app.services.rag_guardrail.RAGGuardrail.retrieve_web_context', return_value=[]):
            res_before = self.client.post('/ai/assistant', json={
                'message': query_text,
                'assistant_mode': 'NATURAL',
            })
            self.assertEqual(res_before.status_code, 200)
            data_before = res_before.json()
            self.assertEqual(data_before.get('classification'), 'IN_SCOPE')
            self.assertIn('chưa có thông tin kiểm chứng', data_before.get('reply', ''))

        # Step 2: Web update arrives from approved source
        web_items = [
            {
                "url": "https://baothainguyen.vn/the-thao/pickleball-sinh-vien-ictu-2026",
                "title": "Pickleball ICTU",
                "snippet": "CLB Pickleball sinh viên ICTU vừa thành lập đã thu hút hơn 200 sinh viên tham gia tập luyện đều đặn hàng tuần.",
                "sport": "pickleball",
                "entity": "Pickleball ICTU",
                "topic": "community",
                "published_date": "2026-09-01",
            }
        ]

        summary = self.update_service.update_knowledge_pipeline(web_items)
        self.assertEqual(summary.inserted, 1)
        self.assertEqual(summary.accepted, 1)

        # Step 3: Natural Assistant query AFTER update -> Grounds in the newly indexed knowledge
        with patch('app.services.rag_guardrail.RAGGuardrail.retrieve_web_context', return_value=[]):
            res_after = self.client.post('/ai/assistant', json={
                'message': query_text,
                'assistant_mode': 'NATURAL',
            })
            self.assertEqual(res_after.status_code, 200)
            data_after = res_after.json()
            self.assertEqual(data_after.get('classification'), 'IN_SCOPE')
            reply_after = data_after.get('reply', '')
            self.assertIn('200 sinh viên', reply_after)
            self.assertTrue('Báo Thái Nguyên' in reply_after or 'baothainguyen.vn' in reply_after)

        # Step 4: Professional Assistant query -> Controlled refusal, no access to sports knowledge
        res_pro = self.client.post('/ai/assistant', json={
            'message': query_text,
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(res_pro.status_code, 200)
        data_pro = res_pro.json()
        self.assertEqual(data_pro.get('status'), 'OUT_OF_SCOPE')
        self.assertIn('Chuyên nghiệp (Professional)', data_pro.get('reply', ''))

    # 2. Existing Knowledge Update -> Returns NEW content (not stale content)
    def test_existing_knowledge_update_returns_new_content_not_old(self):
        """
        Scenario:
        1. Seed older knowledge entry (e.g. Endrick playing for Palmeiras).
        2. Web Update updates the entry to Real Madrid.
        3. Query Natural Assistant -> Returns Real Madrid, not Palmeiras.
        """
        old_entry = KnowledgeEntry(
            id="AUTO-FB-ENDRICK-GEN",
            topic="current_club",
            role="CUSTOMER,OWNER,SYSTEM_ADMIN",
            intent="SPORTS_KNOWLEDGE",
            sport="bóng đá",
            entity="Endrick",
            question="Cầu thủ Endrick hiện đang thi đấu cho CLB nào?",
            answer="Cầu thủ Endrick trước đây thi đấu cho câu lạc bộ Palmeiras tại giải VĐQG Brazil.",
            source="Báo Thái Nguyên (https://baothainguyen.vn/the-thao/endrick-old)",
            source_name="Báo Thái Nguyên",
            source_url="https://baothainguyen.vn/the-thao/endrick-old",
            collected_at="2023-01-01",
            priority=2,
            classification="static",
        )
        self.knowledge_service.index_entry(old_entry)

        # Update with new fact
        update_items = [
            {
                "url": "https://baothainguyen.vn/the-thao/endrick-real-madrid-2026",
                "title": "Endrick - Real Madrid",
                "snippet": "Cầu thủ bóng đá Endrick hiện đang thi đấu chính thức cho câu lạc bộ Real Madrid tại giải La Liga Tây Ban Nha.",
                "sport": "bóng đá",
                "entity": "Endrick",
                "topic": "current_club",
                "published_date": "2026-08-20",
            }
        ]

        summary = self.update_service.update_knowledge_pipeline(update_items)
        self.assertEqual(summary.updated, 1)

        # Natural Assistant Query
        with patch('app.services.rag_guardrail.RAGGuardrail.retrieve_web_context', return_value=[]):
            response = self.client.post('/ai/assistant', json={
                'message': 'Cầu thủ bóng đá Endrick hiện đang thi đấu cho CLB nào?',
                'assistant_mode': 'NATURAL',
            })
            self.assertEqual(response.status_code, 200)
            data = response.json()
            reply = data.get('reply', '')
            # Must return Real Madrid, not stale Palmeiras
            self.assertIn('Real Madrid', reply)
            self.assertNotIn('Palmeiras', reply)
            # Provenance preserved
            self.assertTrue('Báo Thái Nguyên' in reply or 'baothainguyen.vn' in reply)

    # 3. Provenance & Citations Preserved in Natural Mode Response
    def test_metadata_and_provenance_preserved_in_natural_response(self):
        """
        Verify that provenance (source name, URL, timestamp) is attached as citation in Natural response.
        """
        evidence = SportsWebEvidence(
            url="https://vff.org.vn/giai-bong-da-nu-quoc-gia-2026",
            title="Giải Bóng đá Nữ Quốc gia",
            source_name="Liên đoàn Bóng đá Việt Nam (VFF)",
            domain="vff.org.vn",
            snippet="Giải bóng đá Nữ Vô địch Quốc gia 2026 chính thức khởi tranh với sự tham gia của 8 đội bóng xuất sắc.",
            sport="bóng đá",
            published_date="2026-09-05",
            relevance_score=0.96,
            is_confirmed=True,
        )

        summary = self.update_service.update_from_web_evidence([evidence])
        self.assertEqual(summary.inserted, 1)

        with patch('app.services.rag_guardrail.RAGGuardrail.retrieve_web_context', return_value=[]):
            res = self.client.post('/ai/assistant', json={
                'message': 'Giải bóng đá Nữ Quốc gia là gì?',
                'assistant_mode': 'NATURAL',
            })
            self.assertEqual(res.status_code, 200)
            data = res.json()
            reply = data.get('reply', '')
            self.assertIn('8 đội bóng', reply)
            self.assertTrue('VFF' in reply or 'vff.org.vn' in reply)


if __name__ == '__main__':
    unittest.main()
