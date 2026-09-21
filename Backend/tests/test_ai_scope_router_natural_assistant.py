import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.ai import AssistantMode
from app.repositories.knowledge_repository import reset_shared_knowledge_repository
from app.services.ai_domain_policy import ScopeDomain, ScopeRouter


class MockAIProvider:
    def generate_json(self, **kwargs):
        return {
            'status': 'OK',
            'recommendations': [],
        }


class AIScopeRouterNaturalAssistantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reset_shared_knowledge_repository()
        cls.provider_patch = patch('app.services.ai_feature_service.StructuredAIProvider', return_value=MockAIProvider())
        cls.llm_gen_patch = patch('app.services.llm_sports_processor.LLMSportsQueryProcessor.generate_grounded_response', return_value=None)
        cls.llm_und_patch = patch('app.services.llm_sports_processor.LLMSportsQueryProcessor.understand_query', return_value=None)
        cls.web_patch = patch('app.services.rag_guardrail.RAGGuardrail.retrieve_web_context', return_value=[])
        cls.provider_patch.start()
        cls.llm_gen_patch.start()
        cls.llm_und_patch.start()
        cls.web_patch.start()
        cls.client = TestClient(app)
        cls.context = cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.client.__exit__(None, None, None)
        finally:
            cls.client.close()
            cls.web_patch.stop()
            cls.llm_und_patch.stop()
            cls.llm_gen_patch.stop()
            cls.provider_patch.stop()

    def _ask(self, message: str, context: dict | None = None, mode: AssistantMode = AssistantMode.NATURAL) -> dict:
        payload = {
            'message': message,
            'context': context or {},
            'assistant_mode': mode.value,
        }
        res = self.client.post('/ai/assistant', json=payload)
        self.assertEqual(res.status_code, 200)
        return res.json()

    # =========================================================================
    # 1. SCOPE ROUTER DOMAIN CLASSIFICATION TESTS
    # =========================================================================

    def test_scope_router_direct_classification(self):
        # 1. SPORTHUB_BUSINESS
        self.assertEqual(
            ScopeRouter.classify_domain("Tìm sân cầu lông ở Cầu Giấy"),
            ScopeDomain.SPORTHUB_BUSINESS,
        )
        self.assertEqual(
            ScopeRouter.classify_domain("Tôi muốn đăng ký làm chủ sân"),
            ScopeDomain.SPORTHUB_BUSINESS,
        )
        self.assertEqual(
            ScopeRouter.classify_domain("Kiểm tra lịch đặt SH-123"),
            ScopeDomain.SPORTHUB_BUSINESS,
        )

        # 2. SPORTS_KNOWLEDGE
        self.assertEqual(
            ScopeRouter.classify_domain("CR7 là ai?"),
            ScopeDomain.SPORTS_KNOWLEDGE,
        )
        self.assertEqual(
            ScopeRouter.classify_domain("Đội nào vô địch World Cup 2026?"),
            ScopeDomain.SPORTS_KNOWLEDGE,
        )
        self.assertEqual(
            ScopeRouter.classify_domain("Kích thước sân bóng rổ tiêu chuẩn là bao nhiêu?"),
            ScopeDomain.SPORTS_KNOWLEDGE,
        )

        # 3. CONVERSATIONAL_FOLLOWUP (with prior context)
        ctx = {'active_entity': 'Cristiano Ronaldo', 'sport_type': 'bóng đá'}
        self.assertEqual(
            ScopeRouter.classify_domain("vậy anh ấy có World Cup chưa?", context=ctx),
            ScopeDomain.CONVERSATIONAL_FOLLOWUP,
        )
        self.assertEqual(
            ScopeRouter.classify_domain("còn Messi?", context=ctx),
            ScopeDomain.CONVERSATIONAL_FOLLOWUP,
        )
        self.assertEqual(
            ScopeRouter.classify_domain("Thôi tìm sân bóng lúc nãy.", context=ctx),
            ScopeDomain.CONVERSATIONAL_FOLLOWUP,
        )

        # 4. OUT_OF_SCOPE
        self.assertEqual(
            ScopeRouter.classify_domain("Hướng dẫn làm bánh bông lan"),
            ScopeDomain.OUT_OF_SCOPE,
        )
        self.assertEqual(
            ScopeRouter.classify_domain("Thời tiết Hà Nội hôm nay thế nào?"),
            ScopeDomain.OUT_OF_SCOPE,
        )
        self.assertEqual(
            ScopeRouter.classify_domain("Viết code Python tính Fibonacci"),
            ScopeDomain.OUT_OF_SCOPE,
        )
        # In professional mode, sports knowledge is classified as OUT_OF_SCOPE
        self.assertEqual(
            ScopeRouter.classify_domain("CR7 là ai?", assistant_mode=AssistantMode.PROFESSIONAL),
            ScopeDomain.OUT_OF_SCOPE,
        )

    # =========================================================================
    # 2. FULL MULTI-TURN CONTEXT SWITCHING CHAIN
    #    (Business -> CR7 -> WC -> Messi -> WC -> Return to Business)
    # =========================================================================

    def test_full_context_switching_chain(self):
        # Step 1: Business Request (Find badminton court in Cầu Giấy)
        t1 = self._ask("Tìm sân cầu lông ở Cầu Giấy")
        self.assertIn(t1['status'], ('OK', 'NEED_MORE_DATA', 'NO_RESULT'))
        self.assertEqual(t1['understood'].get('sport_type'), 'cầu lông')
        self.assertEqual(t1['understood'].get('location'), 'Cầu Giấy')
        self.assertIsNotNone(t1['understood'].get('business_context'))
        ctx1 = t1['understood']

        # Step 2: Switch to Sports Knowledge ("Cr7 là ai?")
        t2 = self._ask("Cr7 là ai?", context=ctx1)
        self.assertEqual(t2['status'], 'OK')
        self.assertEqual(t2['understood'].get('active_entity'), 'Cristiano Ronaldo')
        self.assertEqual(t2['understood'].get('sport_type'), 'bóng đá')
        self.assertIn("Cristiano Ronaldo", t2['reply'])
        # Business context is preserved in state
        self.assertIsNotNone(t2['understood'].get('business_context'))
        ctx2 = t2['understood']

        # Step 3: Follow-up on CR7 ("Anh ấy có World Cup chưa?")
        t3 = self._ask("Anh ấy có World Cup chưa?", context=ctx2)
        self.assertEqual(t3['status'], 'OK')
        self.assertEqual(t3['understood'].get('active_entity'), 'Cristiano Ronaldo')
        self.assertEqual(t3['understood'].get('current_topic'), 'achievements')
        self.assertTrue("World Cup" in t3['reply'] and ("chưa từng" in t3['reply'] or "bán kết" in t3['reply']))
        ctx3 = t3['understood']

        # Step 4: Switch Entity to Messi ("Còn Messi?")
        t4 = self._ask("Còn Messi?", context=ctx3)
        self.assertEqual(t4['status'], 'OK')
        self.assertEqual(t4['understood'].get('active_entity'), 'Lionel Messi')
        self.assertIn('Cristiano Ronaldo', t4['understood'].get('recent_entities', []))
        self.assertIn("Lionel Messi", t4['reply'])
        ctx4 = t4['understood']

        # Step 5: Follow-up on Messi ("Anh ấy có World Cup chưa?")
        t5 = self._ask("Anh ấy có World Cup chưa?", context=ctx4)
        self.assertEqual(t5['status'], 'OK')
        self.assertEqual(t5['understood'].get('active_entity'), 'Lionel Messi')
        self.assertEqual(t5['understood'].get('current_topic'), 'achievements')
        self.assertTrue("2022" in t5['reply'] and "vô địch" in t5['reply'])
        ctx5 = t5['understood']

        # Step 6: Return to Business context ("Thôi tìm sân lúc nãy.")
        t6 = self._ask("Thôi tìm sân lúc nãy.", context=ctx5)
        self.assertIn(t6['status'], ('OK', 'NEED_MORE_DATA', 'NO_RESULT'))
        # Restored venue search results/criteria
        self.assertIn(t6['intent'], ('SEARCH_VENUE', 'RECOMMEND_VENUE', 'CHECK_AVAILABILITY'))
        self.assertEqual(t6['understood'].get('sport_type'), 'cầu lông')
        self.assertEqual(t6['understood'].get('location'), 'Cầu Giấy')

    # =========================================================================
    # 3. GENERIC SPORTS KNOWLEDGE QUERIES
    # =========================================================================

    def test_generic_sports_knowledge_queries(self):
        # 1. World Cup 2022 champion
        t_wc = self._ask("Đội nào vô địch World Cup 2022?")
        self.assertEqual(t_wc['status'], 'OK')
        self.assertEqual(t_wc['understood'].get('sport_type'), 'bóng đá')

        # 2. Club location / country
        t_club = self._ask("Thái Nguyên T&T là đội nào?")
        self.assertEqual(t_club['status'], 'OK')
        self.assertEqual(t_club['understood'].get('active_entity'), 'Thái Nguyên T&T')
        self.assertEqual(t_club['understood'].get('location'), 'Thái Nguyên')

        # 3. Badminton athlete
        t_bm = self._ask("Nguyễn Thùy Linh là ai?")
        self.assertEqual(t_bm['status'], 'OK')
        self.assertEqual(t_bm['understood'].get('active_entity'), 'Nguyễn Thùy Linh')
        self.assertEqual(t_bm['understood'].get('sport_type'), 'cầu lông')

    # =========================================================================
    # 4. OUT OF SCOPE GUARDRAILS & REDIRECTS
    # =========================================================================

    def test_out_of_scope_rejection_and_redirect(self):
        res_cooking = self._ask("Công thức làm bánh chưng")
        self.assertEqual(res_cooking['status'], 'OUT_OF_SCOPE')
        self.assertEqual(res_cooking['classification'], 'OUT_OF_SCOPE')
        self.assertIn("SportHub", res_cooking['reply'])

        res_code = self._ask("Viết code Python kết nối database")
        self.assertEqual(res_code['status'], 'OUT_OF_SCOPE')
        self.assertEqual(res_code['classification'], 'OUT_OF_SCOPE')

        res_weather = self._ask("Thời tiết ngày mai ở Đà Nẵng")
        self.assertEqual(res_weather['status'], 'OUT_OF_SCOPE')
        self.assertEqual(res_weather['classification'], 'OUT_OF_SCOPE')


if __name__ == '__main__':
    unittest.main()
