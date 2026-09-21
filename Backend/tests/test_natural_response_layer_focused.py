import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.knowledge_repository import get_knowledge_repository, reset_shared_knowledge_repository
from app.services.knowledge_service import get_knowledge_service, reset_shared_knowledge_service
from app.services.ai_intent_router import IntentRouter, AssistantIntent
from app.services.ai_assistant_service import AIAssistantService, AIRepository
from app.services.ai_domain_policy import ScopeClassification
from app.schemas.ai import AssistantMode


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


class NaturalResponseLayerFocusedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reset_shared_knowledge_service()
        reset_shared_knowledge_repository()
        cls.provider_patch = patch('app.services.ai_feature_service.StructuredAIProvider', return_value=AssistantScenarioMockProvider())
        cls.provider_patch.start()
        cls.client = TestClient(app)
        cls.context = cls.client.__enter__()
        cls.router = IntentRouter()
        cls.assistant = AIAssistantService(AIRepository(None))

    @classmethod
    def tearDownClass(cls):
        try:
            cls.client.__exit__(None, None, None)
        finally:
            cls.client.close()
            cls.provider_patch.stop()
            reset_shared_knowledge_service()
            reset_shared_knowledge_repository()

    def setUp(self):
        reset_shared_knowledge_service()
        reset_shared_knowledge_repository()

    # 1. Valid sports evidence -> correct response + valid source citation
    def test_01_valid_sports_evidence_response_and_source(self):
        query = "Đội nào vô địch World Cup 2022?"
        res = self.assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertIn("Argentina", res["reply"])
        # Must contain valid source attribution without fake citation
        self.assertTrue("FIFA" in res["reply"] or "Nguồn:" in res["reply"] or "https://" in res["reply"])

    # 2. Insufficient evidence -> no hallucination (honest refusal / acknowledgement)
    def test_02_insufficient_evidence_no_hallucination(self):
        # Query for non-existent local athlete / fact with no evidence in repository
        query = "Vận động viên Nguyễn Văn A môn bóng chuyền Thái Nguyên cao bao nhiêu mét?"
        res = self.assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        # Ensure system states lack of verified info and does NOT fabricate a specific number
        reply_lower = res["reply"].lower()
        self.assertTrue(
            "chưa có thông tin kiểm chứng" in reply_lower or 
            "chưa có dữ liệu" in reply_lower or 
            "chưa có thông tin" in reply_lower
        )
        self.assertNotIn("2m05", reply_lower)
        self.assertNotIn("1m95", reply_lower)

    # 3. Follow-up -> correct context & source preservation
    def test_03_followup_correct_context_and_source(self):
        # Turn 1: Ben Johns
        q1 = "Ben Johns là ai trong môn pickleball?"
        res1 = self.assistant.ask(q1, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res1["status"], "OK")
        self.assertIn("Ben Johns", res1["reply"])

        # Turn 2: Followup pronoun question
        q2 = "Anh ấy sinh năm bao nhiêu?"
        context = {
            "sports_entity": "Ben Johns",
            "active_entity": "Ben Johns",
            "sport_type": "pickleball",
            "last_intent": "SPORTS_KNOWLEDGE",
        }
        res2 = self.assistant.ask(q2, context=context, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res2["status"], "OK")
        self.assertIn("1999", res2["reply"])
        self.assertTrue("PPA" in res2["reply"] or "Nguồn:" in res2["reply"] or "nguồn" in res2["reply"].lower())

    # 4. Entity switching -> no evidence contamination
    def test_04_entity_switching_no_evidence_contamination(self):
        # Turn 1: Novak Djokovic in tennis
        res1 = self.assistant.ask("Novak Djokovic giành được bao nhiêu danh hiệu Grand Slam?", assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res1["status"], "OK")
        self.assertIn("24", res1["reply"])

        # Turn 2: Switch to Lebron James in basketball
        context = {
            "sports_entity": "Novak Djokovic",
            "active_entity": "Novak Djokovic",
            "sport_type": "tennis",
            "last_intent": "SPORTS_KNOWLEDGE",
        }
        res2 = self.assistant.ask("Còn LeBron James thi đấu môn gì?", context=context, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res2["status"], "OK")
        self.assertIn("bóng rổ", res2["reply"].lower())
        # Ensure tennis/Djokovic stats did NOT contaminate LeBron's response
        self.assertNotIn("grand slam", res2["reply"].lower())
        self.assertNotIn("24", res2["reply"])

    # 5. Business result -> backend is source of truth, no fabricated data
    def test_05_business_result_no_fabricated_data(self):
        # Request a business search for football venue
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
        # Ensure LLM does not hallucinate fake booking confirmation or phantom payment data
        reply = data.get('reply', '')
        self.assertNotIn('đã đặt sân thành công', reply.lower())
        self.assertNotIn('mã thanh toán sh', reply.lower())

    # 6. Out-of-scope -> natural redirect to SportHub without calling sports knowledge
    def test_06_out_of_scope_natural_redirect(self):
        query = "Hướng dẫn tôi nấu món phở bò truyền thống"
        res = self.assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OUT_OF_SCOPE")
        self.assertEqual(res["classification"], ScopeClassification.OUT_OF_SCOPE)
        self.assertTrue("ẩm thực" in res["reply"] or "món ăn" in res["reply"] or "nấu ăn" in res["reply"])
        self.assertTrue("SportHub" in res["reply"] or "thể thao" in res["reply"] or "sân" in res["reply"])
        # Ensure it does NOT talk about World Cup or tennis
        self.assertNotIn("World Cup", res["reply"])
        self.assertNotIn("Grand Slam", res["reply"])


if __name__ == "__main__":
    unittest.main()
