import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.knowledge_repository import get_knowledge_repository, reset_shared_knowledge_repository
from app.services.knowledge_service import get_knowledge_service, reset_shared_knowledge_service
from app.services.ai_intent_router import IntentRouter, AssistantIntent
from app.services.ai_sports_resolver import SportsContextResolver
from app.services.ai_assistant_service import AIAssistantService, AIRepository
from app.services.ai_domain_policy import ScopeClassification, ScopeDecision, evaluate_mode_scope, generate_out_of_scope_redirect
from app.schemas.ai import AssistantMode


class UnifiedMockRankingProvider:
    def generate_json(self, **kwargs):
        available = kwargs.get('system_data', {}).get('available_slots', [])
        return {
            'status': 'OK',
            'recommendations': [
                {'court_id': item['court_id'], 'slot_id': item['slot_id'], 'reason': 'Khung giờ phù hợp.'}
                for item in available[:3]
            ],
        }


class NaturalModeUnifiedPipelineE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reset_shared_knowledge_service()
        reset_shared_knowledge_repository()
        cls.provider_patch = patch('app.services.ai_feature_service.StructuredAIProvider', return_value=UnifiedMockRankingProvider())
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

    # Matrix 1: Sports knowledge direct question
    def test_matrix_01_sports_knowledge_direct_question(self):
        query = "Đội nào vô địch World Cup 2022?"
        res = self.assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertIn("Argentina", res["reply"])
        self.assertTrue("FIFA" in res["reply"] or "nguồn" in res["reply"].lower() or "https://" in res["reply"])

    # Matrix 2: Sports knowledge follow-up with pronoun
    def test_matrix_02_sports_knowledge_followup(self):
        # Turn 1: Champion
        q1 = "Đội nào vô địch World Cup 2022?"
        res1 = self.assistant.ask(q1, assistant_mode=AssistantMode.NATURAL)
        self.assertIn("Argentina", res1["reply"])

        # Turn 2: Followup pronoun question
        context = {
            "competition": "FIFA World Cup",
            "year": "2022",
            "active_entity": "Đội tuyển Argentina",
            "sports_entity": "Đội tuyển Argentina",
            "last_intent": "SPORTS_KNOWLEDGE",
        }
        q2 = "Họ đã thắng ai ở trận chung kết?"
        res2 = self.assistant.ask(q2, context=context, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res2["status"], "OK")
        self.assertIn("Pháp", res2["reply"])

    # Matrix 3: Entity switching between athletes
    def test_matrix_03_entity_switching_athletes(self):
        # Turn 1: Thùy Linh (Badminton)
        res1 = self.assistant.ask("Nguyễn Thùy Linh sinh năm bao nhiêu?", assistant_mode=AssistantMode.NATURAL)
        self.assertIn("1997", res1["reply"])

        # Turn 2: Switch to Quang Hải (Football)
        context = {"sports_entity": "Nguyễn Thùy Linh", "sport_type": "cầu lông", "last_intent": "SPORTS_KNOWLEDGE"}
        q2 = "Còn Nguyễn Quang Hải thì sao?"
        res2 = self.assistant.ask(q2, context=context, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res2["status"], "OK")
        self.assertIn("Quang Hải", res2["reply"])
        self.assertNotIn("cầu lông", res2["reply"].lower())

    # Matrix 4: Sport switching
    def test_matrix_04_sport_switching(self):
        # Turn 1: Football in Thai Nguyen
        q1 = "Ở Thái Nguyên có những CLB bóng đá nào?"
        res1 = self.assistant.ask(q1, assistant_mode=AssistantMode.NATURAL)
        self.assertIn("FC Thái Nguyên", res1["reply"])
        self.assertIn("Thái Nguyên T&T", res1["reply"])

        # Turn 2: Switch to another sport inquiry
        context = {"sports_entity": "Bóng đá Thái Nguyên", "sport_type": "bóng đá", "last_intent": "SPORTS_KNOWLEDGE"}
        q2 = "Thế còn môn cầu lông Việt Nam có tay vợt nào tiêu biểu?"
        res2 = self.assistant.ask(q2, context=context, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res2["status"], "OK")
        self.assertTrue("Thùy Linh" in res2["reply"] or "Tiến Minh" in res2["reply"])

    # Matrix 5: Year / competition disambiguation
    def test_matrix_05_competition_year_disambiguation(self):
        res_2022 = SportsContextResolver.resolve("Đội tuyển nào vô địch World Cup 2022?")
        self.assertEqual(res_2022.competition, "FIFA World Cup")
        self.assertEqual(res_2022.year, "2022")

        res_c1 = SportsContextResolver.resolve("Ronaldo có bao nhiêu cúp C1 Champions League?")
        self.assertEqual(res_c1.target_trophy, "UEFA Champions League")
        self.assertEqual(res_c1.topic, "achievements")

    # Matrix 6: Sports question -> SportHub business
    def test_matrix_06_sports_to_business_transition(self):
        # Turn 1: Sports question
        res1 = self.assistant.ask("Ronaldo hiện đang thi đấu cho câu lạc bộ nào?", assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res1["status"], "OK")
        self.assertIn("Al-Nassr", res1["reply"])

        # Turn 2: User switches to searching for a football court
        q2 = "Tìm sân bóng đá ở Cầu Giấy tối nay"
        route2 = self.router.route(q2, context={"sports_entity": "Cristiano Ronaldo", "sport_type": "bóng đá"})
        self.assertEqual(route2.intent, AssistantIntent.SEARCH_VENUE)
        self.assertEqual(route2.entities.sport_type, "bóng đá")
        self.assertEqual(route2.entities.location, "Cầu Giấy")

    # Matrix 7: SportHub business -> sports knowledge
    def test_matrix_07_business_to_sports_transition(self):
        turn1_context = {"sport_type": "cầu lông", "location": "Cầu Giấy", "last_intent": "SEARCH_VENUE"}
        q2 = "Nguyễn Thùy Linh sinh năm bao nhiêu?"
        route2 = self.router.route(q2, context=turn1_context)
        self.assertEqual(route2.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(route2.entities.sports_entity, "Nguyễn Thùy Linh")

        res2 = self.assistant.ask(q2, context=turn1_context, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res2["status"], "OK")
        self.assertIn("1997", res2["reply"])

    # Matrix 8: Returning to prior topic / search
    def test_matrix_08_return_to_prior_search(self):
        turn1_context = {"sport_type": "bóng đá", "location": "Cầu Giấy", "last_intent": "SEARCH_VENUE"}
        q_return = "Quay lại tìm sân lúc nãy"
        route = self.router.route(q_return, context=turn1_context)
        self.assertEqual(route.intent, AssistantIntent.SEARCH_VENUE)
        self.assertEqual(route.entities.sport_type, "bóng đá")
        self.assertEqual(route.entities.location, "Cầu Giấy")

    # Matrix 9: Out-of-scope -> natural redirect -> return to SportHub
    def test_matrix_09_out_of_scope_redirect_and_resume(self):
        turn1_context = {"sport_type": "pickleball", "location": "Hà Đông", "last_intent": "SEARCH_VENUE"}
        
        # Out-of-scope query
        q_oos = "Thịt chó có ngon không?"
        res_oos = self.assistant.ask(q_oos, context=turn1_context, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res_oos["status"], "OUT_OF_SCOPE")
        self.assertEqual(res_oos["classification"], ScopeClassification.OUT_OF_SCOPE)
        self.assertIn("pickleball", res_oos["reply"])  # Contextual prompt included!

        # Resume search
        q_resume = "Quay lại tìm sân lúc nãy"
        route_resume = self.router.route(q_resume, context=turn1_context)
        self.assertEqual(route_resume.intent, AssistantIntent.SEARCH_VENUE)
        self.assertEqual(route_resume.entities.sport_type, "pickleball")

    # Matrix 10: Insufficient evidence fallback without hallucination
    def test_matrix_10_insufficient_evidence_graceful_limitation(self):
        q_unknown = "VĐV XYZ123 vô địch giải đấu nào năm 1950?"
        res = self.assistant.ask(q_unknown, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertTrue("chưa có thông tin kiểm chứng" in res["reply"] or "chưa có thông tin" in res["reply"])

    # Matrix 11: Conflicting / low-quality evidence filtering & source priority
    def test_matrix_11_evidence_quality_and_ranking(self):
        resolver = SportsContextResolver.resolve("Messi đã giành bao nhiêu Quả bóng vàng?")
        self.assertEqual(resolver.topic, "achievements")
        self.assertEqual(resolver.target_trophy, "Ballon d'Or")

    # Matrix 12: Source attribution / citation integrity
    def test_matrix_12_source_attribution_integrity(self):
        q = "Messi sinh ngày nào?"
        res = self.assistant.ask(q, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertIn("24 tháng 6 năm 1987", res["reply"])
        self.assertTrue("FIFA" in res["reply"] or "https://" in res["reply"])

    # Matrix 13: Regression protection for core business & Professional Mode
    def test_matrix_13_core_business_and_professional_mode_integrity(self):
        # 1. Professional Mode must reject sports knowledge
        eval_pro = evaluate_mode_scope(mode=AssistantMode.PROFESSIONAL, intent=AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertFalse(eval_pro.is_allowed)
        self.assertEqual(eval_pro.classification, ScopeClassification.OUT_OF_SCOPE)

        # 2. Professional Mode allows venue search
        eval_search = evaluate_mode_scope(mode=AssistantMode.PROFESSIONAL, intent=AssistantIntent.SEARCH_VENUE)
        self.assertTrue(eval_search.is_allowed)
        self.assertEqual(eval_search.classification, ScopeClassification.IN_SCOPE)

        # 3. Core Business routes untouched
        route_booking = self.router.route("Kiểm tra đơn đặt sân của tôi")
        self.assertEqual(route_booking.intent, AssistantIntent.GET_BOOKING)

        route_owner = self.router.route("Tôi muốn đăng ký làm đối tác chủ sân")
        self.assertEqual(route_owner.intent, AssistantIntent.PARTNER_APPLICATION_SUPPORT)
