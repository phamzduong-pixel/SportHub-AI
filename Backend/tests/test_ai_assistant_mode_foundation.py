import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.ai import AssistantMode, AssistantRequest, AssistantResponse
from app.services.ai_assistant_service import AIAssistantService
from app.repositories.ai_repository import AIRepository
from app.database.session import SessionLocal


class AssistantModeMockProvider:
    def generate_json(self, **kwargs):
        available = kwargs.get('system_data', {}).get('available_slots', [])
        return {
            'status': 'OK',
            'recommendations': [
                {'court_id': item['court_id'], 'slot_id': item['slot_id'], 'reason': 'Phù hợp nhu cầu.'}
                for item in available[:3]
            ],
        }


class AIAssistantModeFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provider_patch = patch('app.services.ai_feature_service.StructuredAIProvider', return_value=AssistantModeMockProvider())
        cls.provider_patch.start()
        cls.client = TestClient(app)
        cls.context = cls.client.__enter__()
        cls.db = SessionLocal()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        try:
            cls.client.__exit__(None, None, None)
        finally:
            cls.client.close()
            cls.provider_patch.stop()

    def test_schema_enums_and_defaults(self):
        req_default = AssistantRequest(message='Xin chào')
        self.assertIsNone(req_default.assistant_mode)

        req_pro = AssistantRequest(message='Xin chào', assistant_mode=AssistantMode.PROFESSIONAL)
        self.assertEqual(req_pro.assistant_mode, AssistantMode.PROFESSIONAL)

        res_default = AssistantResponse(
            reply='test',
            understood={},
            suggestions=[],
            classification='IN_SCOPE',
            confidence=1.0,
            entities={},
        )
        self.assertEqual(res_default.assistant_mode, AssistantMode.NATURAL)

    def test_default_mode_is_natural_via_api(self):
        response = self.client.post('/ai/assistant', json={'message': 'Xin chào'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('assistant_mode'), 'NATURAL')
        self.assertEqual(data.get('understood', {}).get('assistant_mode'), 'NATURAL')

    def test_natural_mode_passed_correctly_via_api(self):
        response = self.client.post('/ai/assistant', json={
            'message': 'Xin chào',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('assistant_mode'), 'NATURAL')
        self.assertEqual(data.get('understood', {}).get('assistant_mode'), 'NATURAL')

    def test_professional_mode_passed_correctly_via_api(self):
        response = self.client.post('/ai/assistant', json={
            'message': 'Xin chào',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('assistant_mode'), 'PROFESSIONAL')
        self.assertEqual(data.get('understood', {}).get('assistant_mode'), 'PROFESSIONAL')

    def test_mode_propagation_and_conversation_persistence(self):
        # 1. Create conversation with PROFESSIONAL mode
        first_resp = self.client.post('/ai/assistant', json={
            'message': 'Tìm sân cầu lông',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(first_resp.status_code, 200)
        first_data = first_resp.json()
        cid = first_data['conversation_id']
        self.assertEqual(first_data.get('assistant_mode'), 'PROFESSIONAL')

        # 2. Follow-up without explicit mode should inherit context snapshot
        followup_resp = self.client.post('/ai/assistant', json={
            'message': 'ở Cầu Giấy',
            'conversation_id': cid,
        })
        self.assertEqual(followup_resp.status_code, 200)
        followup_data = followup_resp.json()
        self.assertEqual(followup_data.get('conversation_id'), cid)
        # Context snapshot preserved assistant_mode in understood
        self.assertEqual(followup_data.get('understood', {}).get('assistant_mode'), 'PROFESSIONAL')

    def test_service_layer_direct_mode_handling(self):
        repo = AIRepository(self.db)
        service = AIAssistantService(repo)

        # 1. Default ask call
        res_default = service.ask('Xin chào')
        self.assertEqual(res_default.get('assistant_mode'), AssistantMode.NATURAL)
        self.assertEqual(res_default.get('understood', {}).get('assistant_mode'), 'NATURAL')

        # 2. Ask with Enum PROFESSIONAL
        res_pro = service.ask('Xin chào', assistant_mode=AssistantMode.PROFESSIONAL)
        self.assertEqual(res_pro.get('assistant_mode'), AssistantMode.PROFESSIONAL)
        self.assertEqual(res_pro.get('understood', {}).get('assistant_mode'), 'PROFESSIONAL')

        # 3. Ask with string 'PROFESSIONAL'
        res_str = service.ask('Xin chào', assistant_mode='PROFESSIONAL')
        self.assertEqual(res_str.get('assistant_mode'), AssistantMode.PROFESSIONAL)
        self.assertEqual(res_str.get('understood', {}).get('assistant_mode'), 'PROFESSIONAL')

    # =========================================================================
    # CP-07B Comprehensive E2E Flow Tests
    # =========================================================================
    def test_e2e_natural_mode_business_and_sports_knowledge(self):
        """Natural mode handles both SportHub business and grounded sports knowledge."""
        # 1. Business query
        resp_bus = self.client.post('/ai/assistant', json={
            'message': 'Tìm sân bóng đá tại Hà Nội tối nay',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(resp_bus.status_code, 200)
        data_bus = resp_bus.json()
        self.assertEqual(data_bus['assistant_mode'], 'NATURAL')
        self.assertEqual(data_bus['classification'], 'IN_SCOPE')

        # 2. Grounded sports knowledge
        resp_sports = self.client.post('/ai/assistant', json={
            'message': 'Messi hiện thi đấu cho CLB nào?',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(resp_sports.status_code, 200)
        data_sports = resp_sports.json()
        self.assertEqual(data_sports['assistant_mode'], 'NATURAL')
        self.assertEqual(data_sports['classification'], 'IN_SCOPE')
        self.assertIn('Inter Miami', data_sports['reply'])
        self.assertNotIn('Tôi chỉ hỗ trợ các thông tin và nghiệp vụ trực thuộc hệ thống SportHub', data_sports['reply'])

    def test_e2e_professional_mode_business_allowed_and_sports_refused(self):
        """Professional mode processes SportHub business and strictly refuses sports knowledge without RAG."""
        # 1. Business query -> ALLOWED
        resp_bus = self.client.post('/ai/assistant', json={
            'message': 'Tìm sân cầu lông quanh Cầu Giấy',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(resp_bus.status_code, 200)
        data_bus = resp_bus.json()
        self.assertEqual(data_bus['assistant_mode'], 'PROFESSIONAL')
        self.assertEqual(data_bus['classification'], 'IN_SCOPE')

        # 2. "Messi là ai?" -> CONTROLLED REFUSAL
        resp_messi = self.client.post('/ai/assistant', json={
            'message': 'Messi là ai?',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(resp_messi.status_code, 200)
        data_messi = resp_messi.json()
        self.assertEqual(data_messi['assistant_mode'], 'PROFESSIONAL')
        self.assertEqual(data_messi['classification'], 'OUT_OF_SCOPE')
        self.assertIn('chế độ Chuyên nghiệp', data_messi['reply'])
        self.assertIn('SportHub AI', data_messi['reply'])

        # 3. "Ronaldo hay Messi giỏi hơn?" -> CONTROLLED REFUSAL
        resp_comp = self.client.post('/ai/assistant', json={
            'message': 'Ronaldo hay Messi giỏi hơn?',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(resp_comp.status_code, 200)
        data_comp = resp_comp.json()
        self.assertEqual(data_comp['assistant_mode'], 'PROFESSIONAL')
        self.assertEqual(data_comp['classification'], 'OUT_OF_SCOPE')
        self.assertIn('chế độ Chuyên nghiệp', data_comp['reply'])

    def test_e2e_mode_switching_and_context_isolation(self):
        """Switching modes retains conversation history while enforcing mode scope rules."""
        # Step 1: NATURAL Mode - Turn 1 (Search venue)
        t1_resp = self.client.post('/ai/assistant', json={
            'message': 'Tìm sân bóng đá',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(t1_resp.status_code, 200)
        t1_data = t1_resp.json()
        cid = t1_data['conversation_id']
        self.assertEqual(t1_data['assistant_mode'], 'NATURAL')

        # Step 2: NATURAL Mode - Turn 2 (Sports query) -> ALLOWED
        t2_resp = self.client.post('/ai/assistant', json={
            'message': 'Messi hiện thi đấu cho CLB nào?',
            'conversation_id': cid,
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(t2_resp.status_code, 200)
        t2_data = t2_resp.json()
        self.assertEqual(t2_data['classification'], 'IN_SCOPE')
        self.assertIn('Inter Miami', t2_data['reply'])

        # Step 3: Switch to PROFESSIONAL Mode - Turn 3 (Sports query in same conversation) -> MUST BE BLOCKED
        t3_resp = self.client.post('/ai/assistant', json={
            'message': 'Messi là ai?',
            'conversation_id': cid,
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(t3_resp.status_code, 200)
        t3_data = t3_resp.json()
        self.assertEqual(t3_data['assistant_mode'], 'PROFESSIONAL')
        self.assertEqual(t3_data['classification'], 'OUT_OF_SCOPE')
        self.assertIn('chế độ Chuyên nghiệp', t3_data['reply'])

        # Step 4: Continue in PROFESSIONAL Mode - Turn 4 (Business query) -> MUST BE ALLOWED
        t4_resp = self.client.post('/ai/assistant', json={
            'message': 'Có sân nào giá dưới 600k không?',
            'conversation_id': cid,
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(t4_resp.status_code, 200)
        t4_data = t4_resp.json()
        self.assertEqual(t4_data['assistant_mode'], 'PROFESSIONAL')
        self.assertEqual(t4_data['classification'], 'IN_SCOPE')

        # Step 5: Switch back to NATURAL Mode - Turn 5 (Sports query) -> MUST BE ALLOWED
        t5_resp = self.client.post('/ai/assistant', json={
            'message': 'Nguyễn Thùy Linh là ai?',
            'conversation_id': cid,
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(t5_resp.status_code, 200)
        t5_data = t5_resp.json()
        self.assertEqual(t5_data['assistant_mode'], 'NATURAL')
        self.assertEqual(t5_data['classification'], 'IN_SCOPE')
        self.assertNotIn('chế độ Chuyên nghiệp', t5_data['reply'])


if __name__ == '__main__':
    unittest.main()
