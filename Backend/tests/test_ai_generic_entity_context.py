import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.ai import AssistantMode
from app.repositories.knowledge_repository import reset_shared_knowledge_repository
from app.services.ai_sports_resolver import SportsContextResolver


class MultiTurnMockProvider:
    def generate_json(self, **kwargs):
        return {
            'status': 'OK',
            'recommendations': [],
        }


class AIGenericEntityContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reset_shared_knowledge_repository()
        cls.provider_patch = patch('app.services.ai_feature_service.StructuredAIProvider', return_value=MultiTurnMockProvider())
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
    # 1. GENERIC ALIAS & ENTITY NORMALIZATION TESTS
    # =========================================================================

    def test_football_aliases_cr7_messi_mbappe(self):
        # CR7 variants: CR7, Cr7, cr7, anh 7, anh bay
        for query in ('CR7 là ai?', 'Cr7 là ai?', 'cr7 là ai?'):
            res = self._ask(query)
            self.assertEqual(res['status'], 'OK')
            self.assertEqual(res['understood'].get('active_entity'), 'Cristiano Ronaldo')
            self.assertEqual(res['understood'].get('entity_type'), 'athlete')
            self.assertEqual(res['understood'].get('sport_type'), 'bóng đá')

        # Messi variants: M10, m10, anh 10, anh muoi
        for query in ('M10 là ai?', 'm10 là ai?'):
            res = self._ask(query)
            self.assertEqual(res['status'], 'OK')
            self.assertEqual(res['understood'].get('active_entity'), 'Lionel Messi')
            self.assertEqual(res['understood'].get('entity_type'), 'athlete')

        # Mbappé variants: Mbappé, mbappe, m3p
        for query in ('Mbappé là ai?', 'm3p là ai?'):
            res = self._ask(query)
            self.assertEqual(res['status'], 'OK')
            self.assertEqual(res['understood'].get('active_entity'), 'Kylian Mbappé')
            self.assertEqual(res['understood'].get('entity_type'), 'athlete')

    def test_other_sports_entity_resolution(self):
        # Badminton: Thùy Linh, Tiến Minh, Axelsen
        res_tl = self._ask('Thùy Linh là ai?')
        self.assertEqual(res_tl['status'], 'OK')
        self.assertEqual(res_tl['understood'].get('active_entity'), 'Nguyễn Thùy Linh')
        self.assertEqual(res_tl['understood'].get('sport_type'), 'cầu lông')

        res_tm = self._ask('Tiến Minh là ai?')
        self.assertEqual(res_tm['status'], 'OK')
        self.assertEqual(res_tm['understood'].get('active_entity'), 'Nguyễn Tiến Minh')
        self.assertEqual(res_tm['understood'].get('sport_type'), 'cầu lông')

        res_ax = self._ask('Axelsen là ai?')
        self.assertEqual(res_ax['status'], 'OK')
        self.assertEqual(res_ax['understood'].get('active_entity'), 'Viktor Axelsen')
        self.assertEqual(res_ax['understood'].get('sport_type'), 'cầu lông')

        # Tennis: Federer / FedEx, Nadal
        res_fed = self._ask('Federer là ai?')
        self.assertEqual(res_fed['status'], 'OK')
        self.assertEqual(res_fed['understood'].get('active_entity'), 'Roger Federer')
        self.assertEqual(res_fed['understood'].get('sport_type'), 'tennis')

        # Basketball: LeBron James / King James
        res_lbj = self._ask('LeBron James là ai?')
        self.assertEqual(res_lbj['status'], 'OK')
        self.assertEqual(res_lbj['understood'].get('active_entity'), 'LeBron James')
        self.assertEqual(res_lbj['understood'].get('sport_type'), 'bóng rổ')

        # Pickleball: Ben Johns / Vua pickleball
        res_bj = self._ask('Ben Johns là ai?')
        self.assertEqual(res_bj['status'], 'OK')
        self.assertEqual(res_bj['understood'].get('active_entity'), 'Ben Johns')
        self.assertEqual(res_bj['understood'].get('sport_type'), 'pickleball')

        # Volleyball: Bích Tuyền, 4T / Thanh Thúy
        res_bt = self._ask('Bích Tuyền là ai?')
        self.assertEqual(res_bt['status'], 'OK')
        self.assertEqual(res_bt['understood'].get('active_entity'), 'Nguyễn Thị Bích Tuyền')
        self.assertEqual(res_bt['understood'].get('sport_type'), 'bóng chuyền')

    # =========================================================================
    # 2. INDEPENDENT SPORT CONTEXT SWITCHING
    # =========================================================================

    def test_independent_sport_context_switch(self):
        # Step 1: Start with football (Messi)
        t1 = self._ask('Messi là ai?')
        self.assertEqual(t1['understood'].get('active_entity'), 'Lionel Messi')
        self.assertEqual(t1['understood'].get('sport_type'), 'bóng đá')
        ctx1 = t1['understood']

        # Step 2: Switch to badminton ("còn cầu lông?")
        t2 = self._ask('còn cầu lông?', context=ctx1)
        self.assertEqual(t2['status'], 'OK')
        self.assertEqual(t2['understood'].get('sport_type'), 'cầu lông')
        self.assertIn('Lionel Messi', t2['understood'].get('recent_entities', []))
        ctx2 = t2['understood']

        # Step 3: Deictic reference to badminton ("Việt Nam có ai nổi bật ở môn này?")
        t3 = self._ask('Việt Nam có ai nổi bật ở môn này?', context=ctx2)
        self.assertEqual(t3['status'], 'OK')
        self.assertEqual(t3['understood'].get('sport_type'), 'cầu lông')
        # Ensure answer includes badminton athletes, NOT football
        self.assertTrue('Thùy Linh' in t3['reply'] or 'Tiến Minh' in t3['reply'])
        self.assertNotIn('Quang Hải', t3['reply'])

    # =========================================================================
    # 3. INDEPENDENT LOCATION CONTEXT SWITCHING
    # =========================================================================

    def test_independent_location_context_flow(self):
        # Step 1: "Việt Nam có ai giỏi bóng đá?" -> sport=bóng đá, location=Việt Nam
        t1 = self._ask('Việt Nam có ai giỏi bóng đá?')
        self.assertEqual(t1['status'], 'OK')
        self.assertEqual(t1['understood'].get('sport_type'), 'bóng đá')
        self.assertEqual(t1['understood'].get('location'), 'Việt Nam')
        ctx1 = t1['understood']

        # Step 2: "Thái Nguyên thì sao?" -> keep sport=bóng đá, switch location=Thái Nguyên
        t2 = self._ask('Thái Nguyên thì sao?', context=ctx1)
        self.assertEqual(t2['status'], 'OK')
        self.assertEqual(t2['understood'].get('sport_type'), 'bóng đá')
        self.assertEqual(t2['understood'].get('location'), 'Thái Nguyên')
        self.assertTrue('Thái Nguyên T&T' in t2['reply'] or 'FC Thái Nguyên' in t2['reply'] or 'Thái Nguyên' in t2['reply'])
        ctx2 = t2['understood']

        # Step 3: "còn cầu lông?" -> switch sport=cầu lông, keep location=Thái Nguyên
        t3 = self._ask('còn cầu lông?', context=ctx2)
        self.assertEqual(t3['status'], 'OK')
        self.assertEqual(t3['understood'].get('sport_type'), 'cầu lông')
        self.assertEqual(t3['understood'].get('location'), 'Thái Nguyên')
        self.assertIn('cầu lông', t3['reply'].lower())
        ctx3 = t3['understood']

        # Step 4: "ở Hà Nội thì sao?" -> keep sport=cầu lông, switch location=Hà Nội
        t4 = self._ask('ở Hà Nội thì sao?', context=ctx3)
        self.assertEqual(t4['status'], 'OK')
        self.assertEqual(t4['understood'].get('sport_type'), 'cầu lông')
        self.assertEqual(t4['understood'].get('location'), 'Hà Nội')

    # =========================================================================
    # 4. GENERIC ENTITY SWITCHING (Ronaldo -> Messi -> Mbappé -> Ronaldo)
    # =========================================================================

    def test_generic_entity_switching_cycle(self):
        # 1. Ronaldo
        t1 = self._ask('CR7 là ai?')
        self.assertEqual(t1['understood'].get('active_entity'), 'Cristiano Ronaldo')
        ctx1 = t1['understood']

        # 2. Switch to Messi
        t2 = self._ask('còn Messi?', context=ctx1)
        self.assertEqual(t2['understood'].get('active_entity'), 'Lionel Messi')
        self.assertIn('Cristiano Ronaldo', t2['understood'].get('recent_entities', []))
        ctx2 = t2['understood']

        # 3. Switch to Mbappé
        t3 = self._ask('còn Mbappé?', context=ctx2)
        self.assertEqual(t3['understood'].get('active_entity'), 'Kylian Mbappé')
        self.assertIn('Lionel Messi', t3['understood'].get('recent_entities', []))
        ctx3 = t3['understood']

        # 4. Switch back to CR7 via "còn anh 7?"
        t4 = self._ask('còn anh 7?', context=ctx3)
        self.assertEqual(t4['understood'].get('active_entity'), 'Cristiano Ronaldo')
        self.assertIn('Kylian Mbappé', t4['understood'].get('recent_entities', []))

    # =========================================================================
    # 5. CROSS-SPORT ENTITY SWITCHING (Tiến Minh -> Thùy Linh -> Axelsen)
    # =========================================================================

    def test_badminton_entity_switching(self):
        # 1. Tiến Minh
        t1 = self._ask('Tiến Minh là ai?')
        self.assertEqual(t1['understood'].get('active_entity'), 'Nguyễn Tiến Minh')
        self.assertEqual(t1['understood'].get('sport_type'), 'cầu lông')
        ctx1 = t1['understood']

        # 2. Thùy Linh
        t2 = self._ask('còn Thùy Linh?', context=ctx1)
        self.assertEqual(t2['understood'].get('active_entity'), 'Nguyễn Thùy Linh')
        self.assertEqual(t2['understood'].get('sport_type'), 'cầu lông')
        self.assertIn('Nguyễn Tiến Minh', t2['understood'].get('recent_entities', []))
        ctx2 = t2['understood']

        # 3. Axelsen
        t3 = self._ask('còn Axelsen?', context=ctx2)
        self.assertEqual(t3['understood'].get('active_entity'), 'Viktor Axelsen')
        self.assertEqual(t3['understood'].get('sport_type'), 'cầu lông')
        self.assertIn('Nguyễn Thùy Linh', t3['understood'].get('recent_entities', []))

    # =========================================================================
    # 6. PROFESSIONAL MODE DISCIPLINE
    # =========================================================================

    def test_professional_mode_discipline(self):
        # Sports inquiry in professional mode -> OUT_OF_SCOPE
        res = self._ask('CR7 là ai?', mode=AssistantMode.PROFESSIONAL)
        self.assertEqual(res['status'], 'OUT_OF_SCOPE')
        self.assertEqual(res['classification'], 'OUT_OF_SCOPE')

        # Business booking query in professional mode -> IN_SCOPE
        res_biz = self._ask('Tìm sân bóng đá', mode=AssistantMode.PROFESSIONAL)
        self.assertIn(res_biz['status'], ('OK', 'NEED_MORE_DATA'))
        self.assertEqual(res_biz['classification'], 'IN_SCOPE')


if __name__ == '__main__':
    unittest.main()
