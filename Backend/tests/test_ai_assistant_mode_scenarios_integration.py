import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.ai import AssistantMode
from app.services.ai_intent_router import AssistantIntent
from app.services.ai_domain_policy import ScopeClassification, ScopeDecision
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


class AIAssistantModeScenarioIntegrationTests(unittest.TestCase):
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

    # ==========================================
    # 1. NATURAL MODE SCENARIOS
    # ==========================================

    def test_scenario_01_natural_messi_sports_knowledge_grounded(self):
        """1. 'Messi là ai?' -> Sports Knowledge nếu thuộc supported scope và có evidence."""
        response = self.client.post('/ai/assistant', json={
            'message': 'Messi là ai?',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('classification'), 'IN_SCOPE')
        self.assertEqual(data.get('status'), 'OK')
        self.assertEqual(data.get('assistant_mode'), 'NATURAL')
        self.assertEqual(data.get('understood', {}).get('scope_decision'), 'SPORTS_KNOWLEDGE')
        reply = data.get('reply', '')
        self.assertTrue('Messi' in reply or 'Lionel Messi' in reply or 'tiền đạo' in reply or 'bóng đá' in reply)

    def test_scenario_02_natural_search_venue_business_flow(self):
        """2. 'Tìm sân bóng đá' -> SportHub business flow."""
        response = self.client.post('/ai/assistant', json={
            'message': 'Tìm sân bóng đá',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('classification'), 'IN_SCOPE')
        self.assertEqual(data.get('assistant_mode'), 'NATURAL')
        self.assertEqual(data.get('understood', {}).get('scope_decision'), 'SPORT_HUB_BUSINESS')
        self.assertEqual(data.get('understood', {}).get('sport_type'), 'bóng đá')

    def test_scenario_03_natural_sports_knowledge_missing_evidence_safe_fallback(self):
        """3. Sports Knowledge không có evidence -> safe fallback."""
        with patch('app.services.rag_guardrail.KnowledgeService.retrieve', return_value=[]):
            with patch('app.services.rag_guardrail.RAGGuardrail.retrieve_web_context', return_value=[]):
                response = self.client.post('/ai/assistant', json={
                    'message': 'Cầu thủ bóng đá UnknownUnverifiedPlayer123 thi đấu cho ai?',
                    'assistant_mode': 'NATURAL',
                })
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data.get('classification'), 'IN_SCOPE')
                self.assertEqual(data.get('status'), 'OK')
                reply = data.get('reply', '')
                self.assertIn('chưa có thông tin kiểm chứng', reply)

    def test_scenario_04_natural_out_of_scope_coding_query(self):
        """4. Câu hỏi ngoài: 'Viết cho tôi một chương trình Python' -> OUT_OF_SCOPE."""
        response = self.client.post('/ai/assistant', json={
            'message': 'Viết cho tôi một chương trình Python',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'OUT_OF_SCOPE')
        self.assertEqual(data.get('classification'), 'OUT_OF_SCOPE')
        self.assertEqual(data.get('understood', {}).get('scope_decision'), 'OUT_OF_SCOPE')

    # ==========================================
    # 2. PROFESSIONAL MODE SCENARIOS
    # ==========================================

    def test_scenario_05_professional_search_venue_business_flow(self):
        """5. 'Tìm sân bóng đá' -> SportHub business flow."""
        response = self.client.post('/ai/assistant', json={
            'message': 'Tìm sân bóng đá',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('classification'), 'IN_SCOPE')
        self.assertEqual(data.get('assistant_mode'), 'PROFESSIONAL')
        self.assertEqual(data.get('understood', {}).get('scope_decision'), 'SPORT_HUB_BUSINESS')
        self.assertEqual(data.get('understood', {}).get('sport_type'), 'bóng đá')

    def test_scenario_06_professional_check_slot_availability_db_flow(self):
        """6. 'Sân cầu lông còn trống lúc 19h?' -> SportHub DB/business flow."""
        response = self.client.post('/ai/assistant', json={
            'message': 'Sân cầu lông còn trống lúc 19h?',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('classification'), 'IN_SCOPE')
        self.assertEqual(data.get('assistant_mode'), 'PROFESSIONAL')
        self.assertEqual(data.get('understood', {}).get('scope_decision'), 'SPORT_HUB_BUSINESS')
        self.assertEqual(data.get('understood', {}).get('sport_type'), 'cầu lông')
        self.assertEqual(data.get('understood', {}).get('start_time'), '19:00')

    def test_scenario_07_professional_messi_controlled_refusal(self):
        """7. 'Messi là ai?' -> controlled refusal."""
        response = self.client.post('/ai/assistant', json={
            'message': 'Messi là ai?',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'OUT_OF_SCOPE')
        self.assertEqual(data.get('classification'), 'OUT_OF_SCOPE')
        self.assertEqual(data.get('assistant_mode'), 'PROFESSIONAL')
        reply = data.get('reply', '')
        self.assertIn('Chuyên nghiệp (Professional)', reply)
        self.assertIn('Tự nhiên (Natural)', reply)

    def test_scenario_08_professional_sports_comparison_controlled_refusal(self):
        """8. 'Ronaldo hay Messi giỏi hơn?' -> controlled refusal."""
        response = self.client.post('/ai/assistant', json={
            'message': 'Ronaldo hay Messi giỏi hơn?',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'OUT_OF_SCOPE')
        self.assertEqual(data.get('classification'), 'OUT_OF_SCOPE')
        reply = data.get('reply', '')
        self.assertIn('Chuyên nghiệp (Professional)', reply)

    @patch('app.services.rag_guardrail.RAGGuardrail.retrieve_web_context')
    @patch('app.services.rag_guardrail.KnowledgeService.retrieve')
    def test_scenario_09_professional_sports_knowledge_never_calls_rag_or_web(self, mock_retrieve: MagicMock, mock_web: MagicMock):
        """9. Professional Sports Knowledge -> không gọi Sports RAG/Web."""
        response = self.client.post('/ai/assistant', json={
            'message': 'Thông tin về đội tuyển bóng đá Việt Nam',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'OUT_OF_SCOPE')
        mock_retrieve.assert_not_called()
        mock_web.assert_not_called()

    # ==========================================
    # 3. MODE SWITCHING SCENARIOS
    # ==========================================

    def test_scenario_10_mode_switching_natural_to_professional_in_same_conversation(self):
        """10. Natural -> Professional trong cùng conversation."""
        # Turn 1: Natural mode
        res1 = self.client.post('/ai/assistant', json={
            'message': 'Nguyễn Quang Hải là ai?',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1.get('classification'), 'IN_SCOPE')
        understood1 = data1.get('understood', {})
        self.assertEqual(understood1.get('sports_entity'), 'Nguyễn Quang Hải')

        # Turn 2: Switch to Professional in same conversation
        res2 = self.client.post('/ai/assistant', json={
            'message': 'Còn anh ấy thì sao?',
            'assistant_mode': 'PROFESSIONAL',
            'context': understood1,
        })
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2.get('assistant_mode'), 'PROFESSIONAL')
        # Professional mode refuses / asks clarification for sports context
        self.assertNotIn('Quang Hải sinh ngày', data2.get('reply', ''))
        self.assertIsNone(data2.get('understood', {}).get('sports_entity'))

    def test_scenario_11_mode_switching_professional_to_natural_in_same_conversation(self):
        """11. Professional -> Natural trong cùng conversation."""
        # Turn 1: Professional mode business query
        res1 = self.client.post('/ai/assistant', json={
            'message': 'Tìm sân cầu lông ở Cầu Giấy',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        understood1 = data1.get('understood', {})
        self.assertEqual(understood1.get('sport_type'), 'cầu lông')
        self.assertEqual(understood1.get('location'), 'Cầu Giấy')

        # Turn 2: Switch to Natural mode with same business context
        res2 = self.client.post('/ai/assistant', json={
            'message': 'Tối mai có khung giờ nào trống?',
            'assistant_mode': 'NATURAL',
            'context': understood1,
        })
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2.get('classification'), 'IN_SCOPE')
        self.assertEqual(data2.get('assistant_mode'), 'NATURAL')
        self.assertEqual(data2.get('understood', {}).get('sport_type'), 'cầu lông')
        self.assertEqual(data2.get('understood', {}).get('location'), 'Cầu Giấy')

    def test_scenario_12_previous_mode_context_does_not_break_new_mode_policy(self):
        """12. Context của mode trước không làm sai policy của mode mới."""
        # Previous Natural context had sports entity
        dirty_context = {
            'sports_entity': 'Lionel Messi',
            'sports_entities': ['Lionel Messi'],
            'sport_type': 'bóng đá',
            'last_intent': 'SPORTS_KNOWLEDGE',
            'location': 'Thanh Xuân',
        }
        # In Professional mode, query a fresh business request
        response = self.client.post('/ai/assistant', json={
            'message': 'Tìm sân bóng đá tối nay',
            'assistant_mode': 'PROFESSIONAL',
            'context': dirty_context,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('classification'), 'IN_SCOPE')
        self.assertEqual(data.get('assistant_mode'), 'PROFESSIONAL')
        self.assertEqual(data.get('understood', {}).get('scope_decision'), 'SPORT_HUB_BUSINESS')
        # Sports entity was sanitized out
        self.assertIsNone(data.get('understood', {}).get('sports_entity'))

    # ==========================================
    # 4. GROUNDING SCENARIOS
    # ==========================================

    def test_scenario_13_sports_knowledge_evidence_grounded_response(self):
        """13. Sports Knowledge có evidence -> response grounded."""
        response = self.client.post('/ai/assistant', json={
            'message': 'Thái Nguyên T&T là đội bóng gì?',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('classification'), 'IN_SCOPE')
        reply = data.get('reply', '')
        self.assertTrue('Thái Nguyên T&T' in reply or 'bóng đá nữ' in reply or 'CLB' in reply)

    def test_scenario_14_sports_knowledge_no_evidence_no_hallucination(self):
        """14. Không có evidence -> không hallucinate."""
        with patch('app.services.rag_guardrail.KnowledgeService.retrieve', return_value=[]):
            with patch('app.services.rag_guardrail.RAGGuardrail.retrieve_web_context', return_value=[]):
                response = self.client.post('/ai/assistant', json={
                    'message': 'Cầu thủ bóng đá NonExistentPlayerXYZ sinh ngày bao nhiêu?',
                    'assistant_mode': 'NATURAL',
                })
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data.get('classification'), 'IN_SCOPE')
                self.assertIn('chưa có thông tin kiểm chứng', data.get('reply', ''))

    def test_scenario_15_business_data_strictly_grounded_from_db_and_internal_rag(self):
        """15. Business data -> lấy từ DB/RAG tương ứng."""
        # System Guide / Internal RAG
        res_guide = self.client.post('/ai/assistant', json={
            'message': 'Làm sao để đăng ký trở thành chủ sân?',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(res_guide.status_code, 200)
        data_guide = res_guide.json()
        self.assertEqual(data_guide.get('classification'), 'IN_SCOPE')
        self.assertEqual(data_guide.get('status'), 'OK')
        self.assertTrue('chủ sân' in data_guide.get('reply', '') or 'hồ sơ' in data_guide.get('reply', ''))


if __name__ == '__main__':
    unittest.main()
