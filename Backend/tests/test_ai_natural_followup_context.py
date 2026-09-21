import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.ai import AssistantMode
from app.repositories.knowledge_repository import reset_shared_knowledge_repository
from app.services.ai_sports_resolver import SportsContextResolver


class MockAIProvider:
    def generate_json(self, **kwargs):
        return {
            'status': 'OK',
            'recommendations': [],
        }


class AINaturalFollowupContextTests(unittest.TestCase):
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
    # 1. CHAIN 1: ENTITY -> WC -> C1 -> BALLON D'OR (CR7 Chain)
    # =========================================================================

    def test_chain_cr7_trophies_followup(self):
        # Turn 1: "Cr7 là ai?"
        t1 = self._ask("Cr7 là ai?")
        self.assertEqual(t1['status'], 'OK')
        self.assertEqual(t1['understood'].get('active_entity'), 'Cristiano Ronaldo')
        self.assertEqual(t1['understood'].get('sport_type'), 'bóng đá')
        self.assertIn("Cristiano Ronaldo", t1['reply'])
        ctx1 = t1['understood']

        # Turn 2: "vậy cr7 có cup WC chưa?"
        t2 = self._ask("vậy cr7 có cup WC chưa?", context=ctx1)
        self.assertEqual(t2['status'], 'OK')
        self.assertEqual(t2['understood'].get('active_entity'), 'Cristiano Ronaldo')
        self.assertEqual(t2['understood'].get('current_topic'), 'achievements')
        # Ensure answer specifically addresses World Cup
        self.assertIn("World Cup", t2['reply'])
        self.assertTrue("chưa từng vô địch" in t2['reply'] or "bán kết" in t2['reply'])
        ctx2 = t2['understood']

        # Turn 3: "còn C1?"
        t3 = self._ask("còn C1?", context=ctx2)
        self.assertEqual(t3['status'], 'OK')
        self.assertEqual(t3['understood'].get('active_entity'), 'Cristiano Ronaldo')
        self.assertEqual(t3['understood'].get('current_topic'), 'achievements')
        # Ensure answer specifically addresses Champions League (5 titles)
        self.assertTrue("5 lần vô địch" in t3['reply'] or "Champions League" in t3['reply'] or "C1" in t3['reply'])
        ctx3 = t3['understood']

        # Turn 4: "anh ấy có mấy quả?" (referring to Ballon d'Or)
        t4 = self._ask("anh ấy có mấy quả?", context=ctx3)
        self.assertEqual(t4['status'], 'OK')
        self.assertEqual(t4['understood'].get('active_entity'), 'Cristiano Ronaldo')
        self.assertTrue("5 Quả bóng vàng" in t4['reply'] or "Ballon d'Or" in t4['reply'])

    # =========================================================================
    # 2. CHAIN 2: ENTITY SWITCH (CR7 -> Messi -> Mbappé) & CLUB / STATUS
    # =========================================================================

    def test_chain_entity_switch_messi_mbappe(self):
        # Start with CR7
        t1 = self._ask("CR7 là ai?")
        ctx1 = t1['understood']

        # Turn 2: Switch to Messi via "còn Messi?"
        t2 = self._ask("còn Messi?", context=ctx1)
        self.assertEqual(t2['understood'].get('active_entity'), 'Lionel Messi')
        self.assertIn('Cristiano Ronaldo', t2['understood'].get('recent_entities', []))
        self.assertIn("Lionel Messi", t2['reply'])
        ctx2 = t2['understood']

        # Turn 3: "ông này đá ở đâu?" -> current_club of Messi
        t3 = self._ask("ông này đá ở đâu?", context=ctx2)
        self.assertEqual(t3['status'], 'OK')
        self.assertEqual(t3['understood'].get('active_entity'), 'Lionel Messi')
        self.assertEqual(t3['understood'].get('current_topic'), 'current_club')
        self.assertIn("Inter Miami", t3['reply'])
        ctx3 = t3['understood']

        # Turn 4: "còn Mbappé?" -> switch to Kylian Mbappé
        t4 = self._ask("còn Mbappé?", context=ctx3)
        self.assertEqual(t4['status'], 'OK')
        self.assertEqual(t4['understood'].get('active_entity'), 'Kylian Mbappé')
        self.assertIn('Lionel Messi', t4['understood'].get('recent_entities', []))

    # =========================================================================
    # 3. CHAIN 3: BADMINTON (Sport -> Thùy Linh -> Tiến Minh -> Axelsen)
    # =========================================================================

    def test_chain_badminton_athletes_followup(self):
        # Turn 1: "cầu lông Việt Nam có ai nổi bật?"
        t1 = self._ask("cầu lông Việt Nam có ai nổi bật?")
        self.assertEqual(t1['status'], 'OK')
        self.assertEqual(t1['understood'].get('sport_type'), 'cầu lông')
        ctx1 = t1['understood']

        # Turn 2: "Thùy Linh là ai?"
        t2 = self._ask("Thùy Linh là ai?", context=ctx1)
        self.assertEqual(t2['status'], 'OK')
        self.assertEqual(t2['understood'].get('active_entity'), 'Nguyễn Thùy Linh')
        self.assertEqual(t2['understood'].get('sport_type'), 'cầu lông')
        self.assertIn("Nguyễn Thùy Linh", t2['reply'])
        ctx2 = t2['understood']

        # Turn 3: "cô ấy có thành tích gì?"
        t3 = self._ask("cô ấy có thành tích gì?", context=ctx2)
        self.assertEqual(t3['status'], 'OK')
        self.assertEqual(t3['understood'].get('active_entity'), 'Nguyễn Thùy Linh')
        self.assertEqual(t3['understood'].get('current_topic'), 'achievements')
        self.assertTrue("Vietnam Open" in t3['reply'] or "Olympic" in t3['reply'] or "BWF" in t3['reply'])
        ctx3 = t3['understood']

        # Turn 4: "còn Tiến Minh?"
        t4 = self._ask("còn Tiến Minh?", context=ctx3)
        self.assertEqual(t4['status'], 'OK')
        self.assertEqual(t4['understood'].get('active_entity'), 'Nguyễn Tiến Minh')
        self.assertEqual(t4['understood'].get('sport_type'), 'cầu lông')
        self.assertIn('Nguyễn Thùy Linh', t4['understood'].get('recent_entities', []))
        self.assertIn("Nguyễn Tiến Minh", t4['reply'])
        ctx4 = t4['understood']

        # Turn 5: "ông ấy giải nghệ chưa?"
        t5 = self._ask("ông ấy giải nghệ chưa?", context=ctx4)
        self.assertEqual(t5['status'], 'OK')
        self.assertEqual(t5['understood'].get('active_entity'), 'Nguyễn Tiến Minh')
        self.assertEqual(t5['understood'].get('current_topic'), 'status')
        self.assertTrue("huấn luyện" in t5['reply'] or "TP.HCM" in t5['reply'] or "phong trào" in t5['reply'])
        ctx5 = t5['understood']

        # Turn 6: "còn Axelsen?"
        t6 = self._ask("còn Axelsen?", context=ctx5)
        self.assertEqual(t6['status'], 'OK')
        self.assertEqual(t6['understood'].get('active_entity'), 'Viktor Axelsen')
        self.assertEqual(t6['understood'].get('sport_type'), 'cầu lông')
        self.assertIn("Viktor Axelsen", t6['reply'])

    # =========================================================================
    # 4. CHAIN 4: THÁI NGUYÊN (Overview -> Football -> Athletes -> Badminton)
    # =========================================================================

    def test_chain_thai_nguyen_sports_followup(self):
        # Turn 1: "Thái Nguyên có những môn thể thao nào?"
        t1 = self._ask("Thái Nguyên có những môn thể thao nào?")
        self.assertEqual(t1['status'], 'OK')
        self.assertEqual(t1['understood'].get('location'), 'Thái Nguyên')
        self.assertTrue("Bóng đá" in t1['reply'] and "Cầu lông" in t1['reply'])
        ctx1 = t1['understood']

        # Turn 2: "ở đó có bóng đá không?"
        t2 = self._ask("ở đó có bóng đá không?", context=ctx1)
        self.assertEqual(t2['status'], 'OK')
        self.assertEqual(t2['understood'].get('location'), 'Thái Nguyên')
        self.assertEqual(t2['understood'].get('sport_type'), 'bóng đá')
        self.assertTrue("Thái Nguyên T&T" in t2['reply'] or "FC Thái Nguyên" in t2['reply'])
        ctx2 = t2['understood']

        # Turn 3: "Thái Nguyên có ai không?" (asking for athletes in Thai Nguyen football)
        t3 = self._ask("Thái Nguyên có ai không?", context=ctx2)
        self.assertEqual(t3['status'], 'OK')
        self.assertEqual(t3['understood'].get('location'), 'Thái Nguyên')
        self.assertEqual(t3['understood'].get('sport_type'), 'bóng đá')
        self.assertTrue("Kim Thanh" in t3['reply'] or "Bích Thùy" in t3['reply'] or "Thái Nguyên T&T" in t3['reply'])
        ctx3 = t3['understood']

        # Turn 4: "còn cầu lông?"
        t4 = self._ask("còn cầu lông?", context=ctx3)
        self.assertEqual(t4['status'], 'OK')
        self.assertEqual(t4['understood'].get('location'), 'Thái Nguyên')
        self.assertEqual(t4['understood'].get('sport_type'), 'cầu lông')
        self.assertIn("cầu lông", t4['reply'].lower())

    # =========================================================================
    # 5. CHAIN 5: LOCATION SWITCHING FLOW (Vietnam -> Thai Nguyen -> Hanoi -> HCMC)
    # =========================================================================

    def test_chain_location_switching_flow(self):
        # Turn 1: "Việt Nam có ai giỏi bóng đá?"
        t1 = self._ask("Việt Nam có ai giỏi bóng đá?")
        self.assertEqual(t1['understood'].get('sport_type'), 'bóng đá')
        self.assertEqual(t1['understood'].get('location'), 'Việt Nam')
        ctx1 = t1['understood']

        # Turn 2: "Thái Nguyên thì sao?"
        t2 = self._ask("Thái Nguyên thì sao?", context=ctx1)
        self.assertEqual(t2['understood'].get('sport_type'), 'bóng đá')
        self.assertEqual(t2['understood'].get('location'), 'Thái Nguyên')
        ctx2 = t2['understood']

        # Turn 3: "ở Hà Nội thì sao?"
        t3 = self._ask("ở Hà Nội thì sao?", context=ctx2)
        self.assertEqual(t3['understood'].get('sport_type'), 'bóng đá')
        self.assertEqual(t3['understood'].get('location'), 'Hà Nội')
        ctx3 = t3['understood']

        # Turn 4: "còn TP.HCM?"
        t4 = self._ask("còn TP.HCM?", context=ctx3)
        self.assertEqual(t4['understood'].get('sport_type'), 'bóng đá')
        self.assertEqual(t4['understood'].get('location'), 'TP.HCM')
        ctx4 = t4['understood']

        # Turn 5: "còn bóng rổ?" (switch sport to basketball at TP.HCM)
        t5 = self._ask("còn bóng rổ?", context=ctx4)
        self.assertEqual(t5['understood'].get('sport_type'), 'bóng rổ')
        self.assertEqual(t5['understood'].get('location'), 'TP.HCM')
        self.assertTrue("Saigon Heat" in t5['reply'] or "bóng rổ" in t5['reply'].lower())

    # =========================================================================
    # 6. PROFESSIONAL MODE ZERO REGRESSION
    # =========================================================================

    def test_professional_mode_remains_strictly_business(self):
        # In professional mode, sports inquiries are rejected
        res = self._ask("vậy cr7 có cup WC chưa?", mode=AssistantMode.PROFESSIONAL)
        self.assertEqual(res['status'], 'OUT_OF_SCOPE')
        self.assertEqual(res['classification'], 'OUT_OF_SCOPE')


if __name__ == '__main__':
    unittest.main()
