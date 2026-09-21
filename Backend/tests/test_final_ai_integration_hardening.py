import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.knowledge_entry import KnowledgeEntry
from app.repositories.knowledge_repository import get_knowledge_repository, reset_shared_knowledge_repository
from app.services.knowledge_service import get_knowledge_service, reset_shared_knowledge_service
from app.services.knowledge_update_service import KnowledgeUpdateService
from app.services.sports_web_retriever import SportsWebEvidence


class HardeningMockProvider:
    def generate_json(self, **kwargs):
        available = kwargs.get('system_data', {}).get('available_slots', [])
        return {
            'status': 'OK',
            'recommendations': [
                {'court_id': item['court_id'], 'slot_id': item['slot_id'], 'reason': 'Phù hợp yêu cầu.'}
                for item in available[:3]
            ],
        }


class FinalAIIntegrationHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provider_patch = patch('app.services.ai_feature_service.StructuredAIProvider', return_value=HardeningMockProvider())
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

    # 1. Focused End-to-End Test for NATURAL Mode
    def test_final_hardening_natural_e2e(self):
        """
        NATURAL Mode comprehensive end-to-end flow:
        - SportHub business allowed
        - Supported sports knowledge grounded with evidence
        - Time-sensitive query using Approved Web
        - Missing evidence fallback
        - Auto-update new knowledge retrieval with citation
        - Out-of-scope refusal
        """
        # 1.1 SportHub business search
        res_biz = self.client.post('/ai/assistant', json={
            'message': 'Tìm sân bóng đá tại Cầu Giấy',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(res_biz.status_code, 200)
        data_biz = res_biz.json()
        self.assertEqual(data_biz.get('classification'), 'IN_SCOPE')
        self.assertEqual(data_biz.get('understood', {}).get('scope_decision'), 'SPORT_HUB_BUSINESS')
        self.assertNotIn('Chuyên nghiệp (Professional)', data_biz.get('reply', ''))

        # 1.2 Supported sports knowledge with evidence
        res_spt = self.client.post('/ai/assistant', json={
            'message': 'Messi là ai?',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(res_spt.status_code, 200)
        data_spt = res_spt.json()
        self.assertEqual(data_spt.get('classification'), 'IN_SCOPE')
        self.assertEqual(data_spt.get('understood', {}).get('scope_decision'), 'SPORTS_KNOWLEDGE')
        self.assertIn('Lionel Messi', data_spt.get('reply', ''))

        # 1.3 Time-sensitive query with mocked approved web evidence
        mock_web_item = SportsWebEvidence(
            url="https://baothainguyen.vn/the-thao/giai-dau-moi-2026",
            title="Giải đấu Thái Nguyên 2026",
            source_name="Báo Thái Nguyên",
            domain="baothainguyen.vn",
            snippet="Giải vô địch bóng đá phong trào Thái Nguyên 2026 quy tụ 16 đội bóng tham gia tranh tài từ ngày 15/10/2026.",
            sport="bóng đá",
            published_date="2026-09-18",
            relevance_score=0.95,
            is_confirmed=True,
        )
        with patch('app.services.sports_web_retriever.SportsWebRetriever.retrieve_evidence', return_value=[mock_web_item]):
            res_time = self.client.post('/ai/assistant', json={
                'message': 'Kết quả mới nhất của giải đấu bóng đá phong trào Thái Nguyên 2026?',
                'assistant_mode': 'NATURAL',
            })
            self.assertEqual(res_time.status_code, 200)
            data_time = res_time.json()
            self.assertEqual(data_time.get('classification'), 'IN_SCOPE')
            self.assertIn('16 đội bóng', data_time.get('reply', ''))
            self.assertTrue('Báo Thái Nguyên' in data_time.get('reply', '') or 'baothainguyen.vn' in data_time.get('reply', ''))

        # 1.4 Missing evidence -> Safe fallback
        with patch('app.services.rag_guardrail.RAGGuardrail.retrieve_web_context', return_value=[]):
            res_flb = self.client.post('/ai/assistant', json={
                'message': 'Cầu thủ bóng đá Zyxw Vuivui là ai?',
                'assistant_mode': 'NATURAL',
            })
            self.assertEqual(res_flb.status_code, 200)
            data_flb = res_flb.json()
            self.assertEqual(data_flb.get('classification'), 'IN_SCOPE')
            self.assertIn('chưa có thông tin kiểm chứng', data_flb.get('reply', ''))

        # 1.5 Auto-update pipeline -> Incremental re-index -> Natural retrieval
        update_items = [{
            "url": "https://vff.org.vn/the-thao/clb-moi-2026",
            "title": "CLB Tân Binh VFF 2026",
            "snippet": "CLB Tân Binh VFF 2026 vừa chính thức đăng ký tham gia giải hạng Nhì Quốc gia với 25 cầu thủ.",
            "sport": "bóng đá",
            "entity": "CLB Tân Binh VFF 2026",
            "topic": "identity",
            "published_date": "2026-09-18",
        }]
        summary = self.update_service.update_knowledge_pipeline(update_items)
        self.assertEqual(summary.inserted, 1)

        with patch('app.services.rag_guardrail.RAGGuardrail.retrieve_web_context', return_value=[]):
            res_new_spt = self.client.post('/ai/assistant', json={
                'message': 'CLB Tân Binh VFF 2026 là ai?',
                'assistant_mode': 'NATURAL',
            })
            self.assertEqual(res_new_spt.status_code, 200)
            data_new_spt = res_new_spt.json()
            self.assertIn('25 cầu thủ', data_new_spt.get('reply', ''))
            self.assertTrue('VFF' in data_new_spt.get('reply', '') or 'vff.org.vn' in data_new_spt.get('reply', ''))

        # 1.6 Out of scope refusal
        res_out = self.client.post('/ai/assistant', json={
            'message': 'Hãy viết code Python để crawl web',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(res_out.status_code, 200)
        self.assertEqual(res_out.json().get('status'), 'OUT_OF_SCOPE')

    # 2. Focused End-to-End Test for PROFESSIONAL Mode
    def test_final_hardening_professional_e2e(self):
        """
        PROFESSIONAL Mode comprehensive end-to-end flow:
        - SportHub business DB allowed
        - SportHub internal static guide allowed
        - Sports terms in business context allowed
        - Sports knowledge strictly blocked (formal refusal)
        - External sports web blocked
        - Auto-updated sports knowledge strictly blocked
        """
        # 2.1 SportHub business DB search
        res_biz = self.client.post('/ai/assistant', json={
            'message': 'Tìm sân bóng đá tại Hà Nội',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(res_biz.status_code, 200)
        data_biz = res_biz.json()
        self.assertEqual(data_biz.get('classification'), 'IN_SCOPE')
        self.assertEqual(data_biz.get('understood', {}).get('scope_decision'), 'SPORT_HUB_BUSINESS')
        self.assertNotIn('Chuyên nghiệp (Professional)', data_biz.get('reply', ''))

        # 2.2 SportHub internal static guide
        res_guide = self.client.post('/ai/assistant', json={
            'message': 'Làm thế nào để đăng ký làm chủ sân đối tác trên SportHub?',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(res_guide.status_code, 200)
        data_guide = res_guide.json()
        self.assertEqual(data_guide.get('understood', {}).get('scope_decision'), 'SPORT_HUB_BUSINESS')
        self.assertIn('đối tác', data_guide.get('reply', ''))

        # 2.3 Sports terms with business goal allowed
        res_term = self.client.post('/ai/assistant', json={
            'message': 'Tôi muốn đặt sân pickleball vào 19h tối mai',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(res_term.status_code, 200)
        data_term = res_term.json()
        self.assertEqual(data_term.get('understood', {}).get('scope_decision'), 'SPORT_HUB_BUSINESS')
        self.assertNotIn('Chuyên nghiệp (Professional)', data_term.get('reply', ''))

        # 2.4 Pure sports knowledge strictly blocked with formal refusal
        res_spt = self.client.post('/ai/assistant', json={
            'message': 'Messi là ai?',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(res_spt.status_code, 200)
        data_spt = res_spt.json()
        self.assertEqual(data_spt.get('status'), 'OUT_OF_SCOPE')
        self.assertEqual(data_spt.get('understood', {}).get('scope_decision'), 'SPORTS_KNOWLEDGE')
        self.assertIn('Chuyên nghiệp (Professional)', data_spt.get('reply', ''))
        self.assertIn('Tự nhiên (Natural)', data_spt.get('reply', ''))
        self.assertNotIn('Lionel Messi là cầu thủ', data_spt.get('reply', ''))

        # 2.5 External Sports Web blocked in Professional mode
        with patch('app.services.sports_web_retriever.SportsWebRetriever.retrieve_evidence') as mock_web:
            res_web = self.client.post('/ai/assistant', json={
                'message': 'Kết quả trận bóng đá mới nhất của Real Madrid?',
                'assistant_mode': 'PROFESSIONAL',
            })
            self.assertEqual(res_web.status_code, 200)
            mock_web.assert_not_called()
            self.assertIn('Chuyên nghiệp (Professional)', res_web.json().get('reply', ''))

        # 2.6 Auto-updated sports fact is strictly blocked in Professional mode
        update_items = [{
            "url": "https://vff.org.vn/the-thao/tin-tuyen-thu-2026",
            "title": "Tuyển thủ Quốc Gia 2026",
            "snippet": "Danh sách tập trung Đội tuyển Quốc gia năm 2026 gồm 30 cầu thủ xuất sắc.",
            "sport": "bóng đá",
            "entity": "Đội tuyển Quốc gia 2026",
            "topic": "identity",
            "published_date": "2026-09-18",
        }]
        self.update_service.update_knowledge_pipeline(update_items)

        res_new_pro = self.client.post('/ai/assistant', json={
            'message': 'Đội tuyển Quốc gia 2026 có bao nhiêu cầu thủ?',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(res_new_pro.status_code, 200)
        data_new_pro = res_new_pro.json()
        self.assertEqual(data_new_pro.get('status'), 'OUT_OF_SCOPE')
        self.assertIn('Chuyên nghiệp (Professional)', data_new_pro.get('reply', ''))
        self.assertNotIn('30 cầu thủ', data_new_pro.get('reply', ''))

    # 3. Focused Mode Isolation & Switching in Single Conversation
    def test_final_hardening_mode_switching_and_isolation(self):
        """
        Verify mode context isolation:
        - Turn 1: NATURAL mode asks sports question -> Answered.
        - Turn 2: Switch to PROFESSIONAL mode -> Follow-up athlete pronoun query -> Refused (no leakage).
        - Turn 3: PROFESSIONAL mode asks business venue query -> Answered with business flow.
        - Turn 4: Switch to NATURAL mode -> Sports knowledge query -> Answered normally.
        """
        # Turn 1: Natural mode sports query
        turn1 = self.client.post('/ai/assistant', json={
            'message': 'Messi là ai?',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(turn1.status_code, 200)
        data1 = turn1.json()
        self.assertIn('Lionel Messi', data1.get('reply', ''))
        ctx1 = data1.get('understood', {})

        # Turn 2: Switch to Professional mode, asking follow-up about athlete
        turn2 = self.client.post('/ai/assistant', json={
            'message': 'Anh ấy sinh năm bao nhiêu?',
            'assistant_mode': 'PROFESSIONAL',
            'context': ctx1,
        })
        self.assertEqual(turn2.status_code, 200)
        data2 = turn2.json()
        self.assertEqual(data2.get('status'), 'OUT_OF_SCOPE')
        self.assertIn('Chuyên nghiệp (Professional)', data2.get('reply', ''))
        self.assertNotIn('1987', data2.get('reply', ''))

        # Turn 3: In Professional mode, asking SportHub business query
        turn3 = self.client.post('/ai/assistant', json={
            'message': 'Tìm sân bóng đá tại Hà Nội',
            'assistant_mode': 'PROFESSIONAL',
            'context': data2.get('understood', {}),
        })
        self.assertEqual(turn3.status_code, 200)
        data3 = turn3.json()
        self.assertEqual(data3.get('understood', {}).get('scope_decision'), 'SPORT_HUB_BUSINESS')
        self.assertNotIn('Chuyên nghiệp (Professional)', data3.get('reply', ''))

        # Turn 4: Switch back to Natural mode, asking sports query
        turn4 = self.client.post('/ai/assistant', json={
            'message': 'Nguyễn Quang Hải sinh năm bao nhiêu?',
            'assistant_mode': 'NATURAL',
            'context': data3.get('understood', {}),
        })
        self.assertEqual(turn4.status_code, 200)
        data4 = turn4.json()
        self.assertEqual(data4.get('understood', {}).get('scope_decision'), 'SPORTS_KNOWLEDGE')
        self.assertIn('1997', data4.get('reply', ''))


if __name__ == '__main__':
    unittest.main()
