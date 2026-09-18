import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.ai import AssistantMode
from app.services.ai_intent_router import AssistantIntent, IntentRouter


class NaturalConversationMockProvider:
    def generate_json(self, **kwargs):
        return {
            'status': 'OK',
            'recommendations': [],
        }


class AINaturalConversationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provider_patch = patch('app.services.ai_feature_service.StructuredAIProvider', return_value=NaturalConversationMockProvider())
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

    # ==========================================
    # 1. GROUP 1: GREETINGS / CHÀO HỎI / XÃ GIAO
    # ==========================================

    def test_greetings_natural_mode(self):
        greetings = [
            "hello",
            "hi",
            "chào bạn",
            "xin chào",
            "chào buổi sáng",
            "hey",
            "alo",
            "chào bạn nhé",
            "hello SportHub",
            "hi bạn",
        ]
        for query in greetings:
            with self.subTest(query=query):
                route = self.router.route(query)
                self.assertEqual(route.intent, AssistantIntent.GREETING)

                res = self.client.post('/ai/assistant', json={
                    'message': query,
                    'assistant_mode': 'NATURAL',
                })
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertEqual(data.get('status'), 'OK')
                self.assertEqual(data.get('classification'), 'IN_SCOPE')
                self.assertNotIn('chỉ hỗ trợ nghiệp vụ', data.get('reply', ''))
                self.assertIn('SportHub', data.get('reply', ''))

    def test_greetings_professional_mode(self):
        res = self.client.post('/ai/assistant', json={
            'message': 'Xin chào',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get('status'), 'OK')
        self.assertIn('Trợ lý Nghiệp vụ SportHub AI', data.get('reply', ''))

    # ==========================================
    # 2. GROUP 2: AI IDENTITY & CAPABILITY
    # ==========================================

    def test_ai_identity_natural_mode(self):
        identity_queries = [
            "Bạn là ai?",
            "Bạn tên gì?",
            "Bạn là AI gì?",
            "Trợ lý này là ai?",
            "Ai tạo ra bạn?",
        ]
        for query in identity_queries:
            with self.subTest(query=query):
                route = self.router.route(query)
                self.assertEqual(route.intent, AssistantIntent.AI_IDENTITY)

                res = self.client.post('/ai/assistant', json={
                    'message': query,
                    'assistant_mode': 'NATURAL',
                })
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertEqual(data.get('status'), 'OK')
                self.assertEqual(data.get('classification'), 'IN_SCOPE')
                self.assertIn('SportHub AI', data.get('reply', ''))
                self.assertNotIn('chỉ hỗ trợ nghiệp vụ', data.get('reply', ''))

    def test_ai_capability_natural_mode(self):
        capability_queries = [
            "Bạn có thể làm gì?",
            "Bạn giúp được gì?",
            "Trợ lý này dùng để làm gì?",
            "Bạn làm được những việc gì?",
            "Chức năng của bạn là gì?",
        ]
        for query in capability_queries:
            with self.subTest(query=query):
                route = self.router.route(query)
                self.assertEqual(route.intent, AssistantIntent.AI_CAPABILITY)

                res = self.client.post('/ai/assistant', json={
                    'message': query,
                    'assistant_mode': 'NATURAL',
                })
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertEqual(data.get('status'), 'OK')
                self.assertEqual(data.get('classification'), 'IN_SCOPE')
                reply = data.get('reply', '')
                self.assertTrue('Tìm và gợi ý sân' in reply or 'đặt sân' in reply)
                self.assertNotIn('chỉ hỗ trợ nghiệp vụ', reply)

    def test_ai_identity_and_capability_professional_mode(self):
        res_id = self.client.post('/ai/assistant', json={
            'message': 'Bạn là ai?',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(res_id.status_code, 200)
        self.assertIn('Trợ lý Nghiệp vụ SportHub AI', res_id.json().get('reply', ''))

        res_cap = self.client.post('/ai/assistant', json={
            'message': 'Bạn có thể làm gì?',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(res_cap.status_code, 200)
        self.assertIn('nghiệp vụ', res_cap.json().get('reply', ''))

    # ==========================================
    # 3. GROUP 3: THANKS & GOODBYE
    # ==========================================

    def test_thanks_and_acknowledgment(self):
        thanks_queries = [
            "cảm ơn",
            "cảm ơn bạn",
            "cảm ơn nhiều nhé",
            "thank you",
            "thanks",
            "ok",
            "được rồi",
            "okie",
            "đã hiểu",
        ]
        for query in thanks_queries:
            with self.subTest(query=query):
                route = self.router.route(query)
                self.assertEqual(route.intent, AssistantIntent.THANKS)

                res = self.client.post('/ai/assistant', json={
                    'message': query,
                    'assistant_mode': 'NATURAL',
                })
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertEqual(data.get('status'), 'OK')
                self.assertEqual(data.get('classification'), 'IN_SCOPE')
                self.assertNotIn('chỉ hỗ trợ nghiệp vụ', data.get('reply', ''))

    def test_goodbye(self):
        goodbye_queries = [
            "bye",
            "tạm biệt",
            "tạm biệt bạn",
            "hẹn gặp lại",
            "chào tạm biệt",
            "chúc ngủ ngon",
        ]
        for query in goodbye_queries:
            with self.subTest(query=query):
                route = self.router.route(query)
                self.assertEqual(route.intent, AssistantIntent.GOODBYE)

                res = self.client.post('/ai/assistant', json={
                    'message': query,
                    'assistant_mode': 'NATURAL',
                })
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertEqual(data.get('status'), 'OK')
                self.assertEqual(data.get('classification'), 'IN_SCOPE')
                self.assertNotIn('chỉ hỗ trợ nghiệp vụ', data.get('reply', ''))

    # ==========================================
    # 4. GROUP 4: CASUAL CHIT-CHAT & SMALL TALK
    # ==========================================

    def test_casual_queries_natural_mode(self):
        casual_queries = [
            "hôm nay bạn thế nào?",
            "bạn khỏe không?",
            "bạn ổn không?",
            "hay quá",
            "tuyệt vời",
            "được đó",
            "tốt lắm",
            "đỉnh quá",
        ]
        for query in casual_queries:
            with self.subTest(query=query):
                route = self.router.route(query)
                self.assertEqual(route.intent, AssistantIntent.CASUAL)

                res = self.client.post('/ai/assistant', json={
                    'message': query,
                    'assistant_mode': 'NATURAL',
                })
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertEqual(data.get('status'), 'OK')
                self.assertEqual(data.get('classification'), 'IN_SCOPE')
                self.assertNotIn('chỉ hỗ trợ nghiệp vụ', data.get('reply', ''))

    # ==========================================
    # 5. GROUP 5: NONSENSE, SPAM & ABUSIVE INPUT
    # ==========================================

    def test_nonsense_and_spam(self):
        nonsense_inputs = [
            "asdfghjkl",
            "zzzzzz",
            "11111111",
            "qwertyuiop",
            "test test test test",
        ]
        for query in nonsense_inputs:
            with self.subTest(query=query):
                route = self.router.route(query)
                self.assertEqual(route.intent, AssistantIntent.NONSENSE)

                res = self.client.post('/ai/assistant', json={
                    'message': query,
                    'assistant_mode': 'NATURAL',
                })
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertEqual(data.get('status'), 'OUT_OF_SCOPE')
                self.assertIn('chưa hiểu', data.get('reply', ''))

    def test_abusive_input(self):
        abusive_inputs = [
            "dcm",
            "địt mẹ mày",
            "đồ ngu ngốc",
            "ngu vcl",
        ]
        for query in abusive_inputs:
            with self.subTest(query=query):
                route = self.router.route(query)
                self.assertEqual(route.intent, AssistantIntent.ABUSIVE)

                res = self.client.post('/ai/assistant', json={
                    'message': query,
                    'assistant_mode': 'NATURAL',
                })
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertEqual(data.get('status'), 'OUT_OF_SCOPE')
                self.assertIn('lịch sự và tôn trọng', data.get('reply', ''))

    # ==========================================
    # 6. REGRESSION: SPORTS KNOWLEDGE & BUSINESS FLOWS
    # ==========================================

    def test_sports_knowledge_not_intercepted_by_identity(self):
        # Athlete identity inquiries must still go to SPORTS_KNOWLEDGE
        route1 = self.router.route("Messi là ai?")
        self.assertEqual(route1.intent, AssistantIntent.SPORTS_KNOWLEDGE)

        route2 = self.router.route("Quang Hải là ai?")
        self.assertEqual(route2.intent, AssistantIntent.SPORTS_KNOWLEDGE)

        route3 = self.router.route("Sân vận động Thái Nguyên ở đâu?")
        self.assertEqual(route3.intent, AssistantIntent.SPORTS_KNOWLEDGE)

    def test_business_search_with_greeting(self):
        # "chào bạn, tìm giúp tôi sân bóng" -> SEARCH_VENUE
        route = self.router.route("Chào bạn, tìm giúp tôi sân bóng đá ở Cầu Giấy")
        self.assertIn(route.intent, (AssistantIntent.SEARCH_VENUE, AssistantIntent.CHECK_AVAILABILITY))
        self.assertEqual(route.entities.sport_type, 'bóng đá')
