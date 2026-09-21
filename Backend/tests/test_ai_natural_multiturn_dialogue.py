import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.ai import AssistantMode
from app.repositories.knowledge_repository import reset_shared_knowledge_repository


class MultiTurnMockProvider:
    def generate_json(self, **kwargs):
        return {
            'status': 'OK',
            'recommendations': [],
        }


class AINaturalMultiTurnDialogueTests(unittest.TestCase):
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
    # 1. CORE MULTI-TURN CONVERSATION SCENARIO (CR7 -> WC -> C1 -> Ballon d'Or -> Messi -> WC -> Club)
    # =========================================================================

    def test_full_multiturn_sports_dialogue_flow(self):
        # Turn 1: 'Cr7 là ai?'
        t1 = self._ask('Cr7 là ai?')
        self.assertEqual(t1['status'], 'OK')
        self.assertEqual(t1['classification'], 'IN_SCOPE')
        self.assertIn('Cristiano Ronaldo', t1['reply'])
        self.assertEqual(t1['understood'].get('active_entity'), 'Cristiano Ronaldo')
        self.assertEqual(t1['understood'].get('sport_type'), 'bóng đá')
        ctx1 = t1['understood']

        # Turn 2: 'vậy cr7 có cup WC chưa?'
        t2 = self._ask('vậy cr7 có cup WC chưa?', context=ctx1)
        self.assertEqual(t2['status'], 'OK')
        self.assertEqual(t2['classification'], 'IN_SCOPE')
        self.assertIn('World Cup', t2['reply'])
        self.assertTrue(
            'chưa từng vô địch' in t2['reply'] or 'bán kết' in t2['reply'] or '2006' in t2['reply'] or 'Euro 2016' in t2['reply']
        )
        self.assertEqual(t2['understood'].get('active_entity'), 'Cristiano Ronaldo')
        ctx2 = t2['understood']

        # Turn 3: 'còn C1?'
        t3 = self._ask('còn C1?', context=ctx2)
        self.assertEqual(t3['status'], 'OK')
        self.assertEqual(t3['classification'], 'IN_SCOPE')
        self.assertTrue('5' in t3['reply'] or 'Champions League' in t3['reply'])
        self.assertEqual(t3['understood'].get('active_entity'), 'Cristiano Ronaldo')
        ctx3 = t3['understood']

        # Turn 4: 'anh ấy có mấy quả bóng vàng?'
        t4 = self._ask('anh ấy có mấy quả bóng vàng?', context=ctx3)
        self.assertEqual(t4['status'], 'OK')
        self.assertEqual(t4['classification'], 'IN_SCOPE')
        self.assertTrue('5 Quả bóng vàng' in t4['reply'] or '5' in t4['reply'])
        self.assertEqual(t4['understood'].get('active_entity'), 'Cristiano Ronaldo')
        ctx4 = t4['understood']

        # Turn 5: 'còn Messi?' -> switch entity to Lionel Messi
        t5 = self._ask('còn Messi?', context=ctx4)
        self.assertEqual(t5['status'], 'OK')
        self.assertEqual(t5['classification'], 'IN_SCOPE')
        self.assertIn('Lionel Messi', t5['reply'])
        self.assertEqual(t5['understood'].get('active_entity'), 'Lionel Messi')
        self.assertEqual(t5['understood'].get('sport_type'), 'bóng đá')
        self.assertIn('Cristiano Ronaldo', t5['understood'].get('recent_entities', []))
        ctx5 = t5['understood']

        # Turn 6: 'anh ấy có World Cup chưa?' -> uses Lionel Messi
        t6 = self._ask('anh ấy có World Cup chưa?', context=ctx5)
        self.assertEqual(t6['status'], 'OK')
        self.assertEqual(t6['classification'], 'IN_SCOPE')
        self.assertTrue('World Cup 2022' in t6['reply'] or 'vô địch' in t6['reply'])
        self.assertEqual(t6['understood'].get('active_entity'), 'Lionel Messi')
        ctx6 = t6['understood']

        # Turn 7: 'anh ấy đang đá cho đội nào?' -> uses Lionel Messi
        t7 = self._ask('anh ấy đang đá cho đội nào?', context=ctx6)
        self.assertEqual(t7['status'], 'OK')
        self.assertEqual(t7['classification'], 'IN_SCOPE')
        self.assertIn('Inter Miami CF', t7['reply'])
        self.assertEqual(t7['understood'].get('active_entity'), 'Lionel Messi')

    # =========================================================================
    # 2. ADDITIONAL TEST CASES: NICKNAMES & WORDS FOR NUMBERS
    # =========================================================================

    def test_anh_7_and_anh_bay(self):
        res1 = self._ask('anh 7 là ai?')
        self.assertEqual(res1['status'], 'OK')
        self.assertIn('Cristiano Ronaldo', res1['reply'])
        self.assertEqual(res1['understood'].get('active_entity'), 'Cristiano Ronaldo')

        res2 = self._ask('môn thể thao đá bóng, anh bảy là ai?')
        self.assertEqual(res2['status'], 'OK')
        self.assertIn('Cristiano Ronaldo', res2['reply'])
        self.assertEqual(res2['understood'].get('active_entity'), 'Cristiano Ronaldo')
        self.assertEqual(res2['understood'].get('sport_type'), 'bóng đá')

    def test_pronoun_ong_nay_da_o_dau(self):
        # Start with Messi
        t1 = self._ask('Messi là ai?')
        ctx1 = t1['understood']

        # Follow up: 'ông này đá ở đâu?'
        t2 = self._ask('ông này đá ở đâu?', context=ctx1)
        self.assertEqual(t2['status'], 'OK')
        self.assertIn('Inter Miami', t2['reply'])
        self.assertEqual(t2['understood'].get('active_entity'), 'Lionel Messi')

    # =========================================================================
    # 3. BACKWARD COMPATIBILITY: PROFESSIONAL MODE
    # =========================================================================

    def test_professional_mode_remains_strictly_in_scope(self):
        res = self._ask('Cr7 là ai?', mode=AssistantMode.PROFESSIONAL)
        self.assertEqual(res['status'], 'OUT_OF_SCOPE')
        self.assertIn('Chuyên nghiệp (Professional)', res['reply'])

        res2 = self._ask('vậy cr7 có cup WC chưa?', mode=AssistantMode.PROFESSIONAL)
        self.assertEqual(res2['status'], 'OUT_OF_SCOPE')
        self.assertIn('Chuyên nghiệp (Professional)', res2['reply'])


if __name__ == '__main__':
    unittest.main()
