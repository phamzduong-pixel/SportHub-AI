import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.ai import AssistantMode
from app.services.ai_intent_router import AssistantIntent, IntentRouter
from app.services.ai_sports_resolver import SportsContextResolver


class NaturalMockProvider:
    def generate_json(self, **kwargs):
        return {
            'status': 'OK',
            'recommendations': [],
        }


class AINaturalContextEntityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provider_patch = patch('app.services.ai_feature_service.StructuredAIProvider', return_value=NaturalMockProvider())
        cls.provider_patch.start()
        cls.client = TestClient(app)
        cls.context = cls.client.__enter__()
        cls.router = IntentRouter()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.client.__exit__(None, None, None)
        finally:
            cls.client.close()
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
    # 1. REQUIREMENT 1: ALIAS / NATURAL WAYS OF ASKING
    # =========================================================================

    def test_alias_natural_ways_of_asking(self):
        queries = [
            "Môn thể thao đá bóng, anh bảy là ai?",
            "Môn thể thao đá bóng, anh 7 là ai?",
            "Anh 7 trong bóng đá là ai?",
            "Trong môn đá bóng, anh bảy là ai?",
            "CR7 trong bóng đá là ai?",
        ]
        for q in queries:
            with self.subTest(query=q):
                data = self._ask(q, mode=AssistantMode.NATURAL)
                self.assertEqual(data['status'], 'OK')
                self.assertEqual(data['classification'], 'IN_SCOPE')
                self.assertIn('Cristiano Ronaldo', data['reply'])
                self.assertEqual(data['understood'].get('sport_type'), 'bóng đá')
                self.assertIn('Cristiano Ronaldo', data['understood'].get('sports_entities', []))

    # =========================================================================
    # 2. REQUIREMENT 2: CONVERSATION CONTEXT & FOLLOW-UP RESOLUTION
    # =========================================================================

    def test_conversation_context_followup_resolution(self):
        # Turn 1: Ask about Anh 7 in football
        turn1 = self._ask("Anh 7 trong bóng đá là ai?", mode=AssistantMode.NATURAL)
        self.assertIn('Cristiano Ronaldo', turn1['reply'])
        ctx = turn1['understood']

        # Turn 2: Follow-up asking about "anh 10" using previous context
        followups = [
            "Còn anh 10 là ai?",
            "Thế còn anh 10?",
            "Vậy anh 10 là ai?",
            "Còn anh mười thì sao?",
        ]
        for fq in followups:
            with self.subTest(followup=fq):
                turn2 = self._ask(fq, context=ctx, mode=AssistantMode.NATURAL)
                self.assertEqual(turn2['status'], 'OK')
                self.assertEqual(turn2['classification'], 'IN_SCOPE')
                self.assertIn('Lionel Messi', turn2['reply'])
                self.assertEqual(turn2['understood'].get('sport_type'), 'bóng đá')
                self.assertIn('Lionel Messi', turn2['understood'].get('sports_entities', []))

    # =========================================================================
    # 3. REQUIREMENT 3: MULTI-SPORT SLANG / NICKNAMES / NUMBER WORDS
    # =========================================================================

    def test_tennis_nicknames(self):
        tennis_queries = [
            ("Trong tennis, Tàu tốc hành là ai?", "Roger Federer"),
            ("Môn tennis, ai là Vua đất nện?", "Rafael Nadal"),
            ("Trong quần vợt, Nole là ai?", "Novak Djokovic"),
        ]
        for q, expected_name in tennis_queries:
            with self.subTest(query=q):
                data = self._ask(q, mode=AssistantMode.NATURAL)
                self.assertEqual(data['status'], 'OK')
                self.assertIn(expected_name, data['reply'])
                self.assertEqual(data['understood'].get('sport_type'), 'tennis')

    def test_badminton_nicknames(self):
        badminton_queries = [
            ("Trong cầu lông, Super Dan là ai?", "Lin Dan"),
            ("Hoa khôi cầu lông Việt Nam là ai?", "Nguyễn Thùy Linh"),
            ("Tượng đài cầu lông Việt Nam Tiến Minh", "Nguyễn Tiến Minh"),
        ]
        for q, expected_name in badminton_queries:
            with self.subTest(query=q):
                data = self._ask(q, mode=AssistantMode.NATURAL)
                self.assertEqual(data['status'], 'OK')
                self.assertIn(expected_name, data['reply'])
                self.assertEqual(data['understood'].get('sport_type'), 'cầu lông')

    def test_volleyball_nicknames(self):
        volleyball_queries = [
            ("Trong bóng chuyền, Khủng long Bích Tuyền là ai?", "Nguyễn Thị Bích Tuyền"),
            ("Chủ công 4T của bóng chuyền nữ Việt Nam là ai?", "Trần Thị Thanh Thúy"),
        ]
        for q, expected_name in volleyball_queries:
            with self.subTest(query=q):
                data = self._ask(q, mode=AssistantMode.NATURAL)
                self.assertEqual(data['status'], 'OK')
                self.assertIn(expected_name, data['reply'])
                self.assertEqual(data['understood'].get('sport_type'), 'bóng chuyền')

    def test_basketball_nicknames(self):
        basketball_queries = [
            ("Trong bóng rổ, Nhà vua King James là ai?", "LeBron James"),
            ("Bếp trưởng Chef Curry chơi môn bóng rổ là ai?", "Stephen Curry"),
        ]
        for q, expected_name in basketball_queries:
            with self.subTest(query=q):
                data = self._ask(q, mode=AssistantMode.NATURAL)
                self.assertEqual(data['status'], 'OK')
                self.assertIn(expected_name, data['reply'])
                self.assertEqual(data['understood'].get('sport_type'), 'bóng rổ')

    def test_pickleball_nicknames(self):
        pickleball_queries = [
            ("Vua Pickleball Ben Johns là ai?", "Ben Johns"),
            ("Nữ hoàng Pickleball Anna Leigh Waters là ai?", "Anna Leigh Waters"),
        ]
        for q, expected_name in pickleball_queries:
            with self.subTest(query=q):
                data = self._ask(q, mode=AssistantMode.NATURAL)
                self.assertEqual(data['status'], 'OK')
                self.assertIn(expected_name, data['reply'])
                self.assertEqual(data['understood'].get('sport_type'), 'pickleball')

    # =========================================================================
    # 4. REQUIREMENT 4: AMBIGUOUS / CONTEXT-LESS QUERIES (CONDITIONAL HANDLING)
    # =========================================================================

    def test_ambiguous_bare_nickname_conditional_handling(self):
        bare_queries = [
            ("anh 7 là ai?", "Cristiano Ronaldo"),
            ("anh bảy là ai?", "Cristiano Ronaldo"),
            ("anh 10 là ai?", "Lionel Messi"),
            ("anh mười là ai?", "Lionel Messi"),
            ("Tàu tốc hành là ai?", "Roger Federer"),
            ("Vua đất nện là ai?", "Rafael Nadal"),
        ]
        for q, expected_entity in bare_queries:
            with self.subTest(query=q):
                data = self._ask(q, mode=AssistantMode.NATURAL)
                self.assertEqual(data['status'], 'OK')
                self.assertEqual(data['classification'], 'IN_SCOPE')
                self.assertIn(expected_entity, data['reply'])

    # =========================================================================
    # 5. REQUIREMENT 5: SPORTS MEME / HUMOR / TEASING
    # =========================================================================

    def test_sports_meme_and_humor(self):
        meme_queries = [
            "Đấng Maguire gánh team",
            "Chúa tể Maguire hài hước",
            "Lakaka tấu hài",
        ]
        for q in meme_queries:
            with self.subTest(query=q):
                data = self._ask(q, mode=AssistantMode.NATURAL)
                self.assertEqual(data['status'], 'OK')
                self.assertEqual(data['classification'], 'IN_SCOPE')
                self.assertTrue(any(k in data['reply'] for k in ('Harry Maguire', 'Romelu Lukaku', 'Maguire', 'Lukaku')))

    # =========================================================================
    # 6. PROFESSIONAL MODE DISCIPLINE & REGRESSIONS
    # =========================================================================

    def test_professional_mode_strict_discipline(self):
        sports_questions = [
            "Anh 7 trong bóng đá là ai?",
            "Môn thể thao đá bóng, anh bảy là ai?",
            "Còn anh 10 là ai?",
            "Tàu tốc hành là ai?",
            "Đấng Maguire gánh team",
        ]
        for q in sports_questions:
            with self.subTest(query=q):
                data = self._ask(q, mode=AssistantMode.PROFESSIONAL)
                self.assertEqual(data['status'], 'OUT_OF_SCOPE')
                self.assertEqual(data['classification'], 'OUT_OF_SCOPE')
                self.assertIn('Chuyên nghiệp (Professional)', data['reply'])
                self.assertNotIn('Cristiano Ronaldo', data['reply'])

    def test_sporthub_business_flow_not_broken_in_natural_mode(self):
        # Booking / venue inquiries should still route properly
        biz_queries = [
            "Tìm sân cầu lông tại Thái Nguyên",
            "Có sân bóng đá nào còn trống tối nay không?",
            "Đặt sân bóng đá tại Thái Nguyên lúc 19h",
        ]
        for q in biz_queries:
            with self.subTest(query=q):
                data = self._ask(q, mode=AssistantMode.NATURAL)
                self.assertIn(data['status'], ('OK', 'NEED_MORE_DATA', 'NO_RESULT', 'NO_AVAILABLE_SLOT'))
                self.assertEqual(data['classification'], 'IN_SCOPE')

    def test_abusive_and_nonsense_in_natural_mode(self):
        abusive_res = self._ask("dcm bot ngu vl", mode=AssistantMode.NATURAL)
        self.assertEqual(abusive_res['status'], 'OUT_OF_SCOPE')
        self.assertIn('lịch sự và tôn trọng', abusive_res['reply'])

        nonsense_res = self._ask("asdfghjklqwerty", mode=AssistantMode.NATURAL)
        self.assertEqual(nonsense_res['status'], 'OUT_OF_SCOPE')
        self.assertIn('chưa hiểu được', nonsense_res['reply'])


if __name__ == '__main__':
    unittest.main()
