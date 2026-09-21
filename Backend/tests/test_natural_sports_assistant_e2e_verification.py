import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.knowledge_repository import get_knowledge_repository, reset_shared_knowledge_repository
from app.services.knowledge_service import get_knowledge_service, reset_shared_knowledge_service
from app.services.ai_intent_router import IntentRouter, AssistantIntent
from app.services.ai_sports_resolver import SportsContextResolver
from app.services.ai_assistant_service import AIAssistantService, AIRepository
from app.services.ai_domain_policy import ScopeClassification, ScopeDecision, ScopeDomain, ScopeRouter
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


class NaturalSportsAssistantE2EVerificationTests(unittest.TestCase):
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

    # =========================================================================
    # SCENARIO 1: Sports Knowledge (Athlete, Team, Competition, Rules, Achievements, Vietnam/Local, Source)
    # =========================================================================
    def test_scenario_01_sports_knowledge_athlete(self):
        # Athlete query
        res = self.assistant.ask("Nguyễn Thùy Linh sinh năm bao nhiêu?", assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertIn("1997", res["reply"])
        self.assertTrue("BWF" in res["reply"] or "Nguồn:" in res["reply"] or "nguồn" in res["reply"].lower())

    def test_scenario_01_sports_knowledge_team_club(self):
        # Team/Club query
        res = self.assistant.ask("Thái Nguyên T&T là đội bóng nào?", assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertIn("nữ", res["reply"].lower())
        self.assertTrue("VFF" in res["reply"] or "Nguồn:" in res["reply"] or "nguồn" in res["reply"].lower())

    def test_scenario_01_sports_knowledge_competition(self):
        # Competition query
        res = self.assistant.ask("Đội nào vô địch World Cup 2022?", assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertIn("Argentina", res["reply"])
        self.assertTrue("FIFA" in res["reply"] or "Nguồn:" in res["reply"] or "nguồn" in res["reply"].lower())

    def test_scenario_01_sports_knowledge_rules_scoring(self):
        # Rules/Scoring query
        res = self.assistant.ask("Khu vực Non-Volley Zone (Kitchen) trong pickleball có luật gì?", assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertTrue("volley" in res["reply"].lower() or "không được" in res["reply"].lower() or "chạm đất" in res["reply"].lower())
        self.assertTrue("USAP" in res["reply"] or "IFP" in res["reply"] or "Nguồn:" in res["reply"] or "nguồn" in res["reply"].lower())

    def test_scenario_01_sports_knowledge_achievement_history(self):
        # Achievement/History query
        res = self.assistant.ask("Novak Djokovic giành được bao nhiêu danh hiệu Grand Slam?", assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertIn("24", res["reply"])
        self.assertTrue("ITF" in res["reply"] or "ATP" in res["reply"] or "Nguồn:" in res["reply"] or "nguồn" in res["reply"].lower())

    def test_scenario_01_sports_knowledge_vietnam_local(self):
        # Vietnam/Local query
        res = self.assistant.ask("Trần Thị Thanh Thúy thi đấu ở vị trí nào trong đội tuyển bóng chuyền nữ Việt Nam?", assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertTrue("chủ công" in res["reply"].lower() or "ngoài nước" in res["reply"].lower() or "4t" in res["reply"].lower())
        self.assertTrue("VFV" in res["reply"] or "Nguồn:" in res["reply"] or "nguồn" in res["reply"].lower())

    # =========================================================================
    # SCENARIO 2: Follow-up (Context continuity: Athlete -> Achievements -> Competition)
    # =========================================================================
    def test_scenario_02_followup_continuity(self):
        # Turn 1: Athlete intro
        res1 = self.assistant.ask("Lionel Messi là ai?", assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res1["status"], "OK")
        self.assertIn("Argentina", res1["reply"])
        context_t1 = {
            "active_entity": "Lionel Messi",
            "sports_entity": "Lionel Messi",
            "sport_type": "bóng đá",
            "last_intent": "SPORTS_KNOWLEDGE",
        }

        # Turn 2: Follow-up pronoun achievement
        q2 = "Anh ấy đã đạt thành tích Quả bóng vàng như thế nào?"
        res2 = self.assistant.ask(q2, context=context_t1, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res2["status"], "OK")
        self.assertIn("8", res2["reply"])
        context_t2 = {
            "active_entity": "Lionel Messi",
            "sports_entity": "Lionel Messi",
            "sport_type": "bóng đá",
            "current_topic": "achievements",
            "last_intent": "SPORTS_KNOWLEDGE",
        }

        # Turn 3: Follow-up competition
        q3 = "Còn World Cup 2022 thì sao?"
        res3 = self.assistant.ask(q3, context=context_t2, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res3["status"], "OK")
        self.assertIn("vô địch", res3["reply"].lower())

    # =========================================================================
    # SCENARIO 3: Entity Switching (Entity A -> follow-up -> Entity B -> follow-up Entity B)
    # =========================================================================
    def test_scenario_03_entity_switching_no_contamination(self):
        # Turn 1: Entity A (Cristiano Ronaldo)
        res1 = self.assistant.ask("Cristiano Ronaldo sinh năm bao nhiêu?", assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res1["status"], "OK")
        self.assertIn("1985", res1["reply"])
        ctx_a = {"active_entity": "Cristiano Ronaldo", "sports_entity": "Cristiano Ronaldo", "sport_type": "bóng đá", "last_intent": "SPORTS_KNOWLEDGE"}

        # Turn 2: Follow-up Entity A
        res2 = self.assistant.ask("Anh ấy đang thi đấu cho CLB nào?", context=ctx_a, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res2["status"], "OK")
        self.assertIn("Al-Nassr", res2["reply"])

        # Turn 3: Switch to Entity B (Lionel Messi)
        res3 = self.assistant.ask("Còn Lionel Messi đang thi đấu cho CLB nào?", context=ctx_a, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res3["status"], "OK")
        self.assertIn("Inter Miami", res3["reply"])
        self.assertNotIn("Al-Nassr", res3["reply"])
        ctx_b = {"active_entity": "Lionel Messi", "sports_entity": "Lionel Messi", "sport_type": "bóng đá", "last_intent": "SPORTS_KNOWLEDGE"}

        # Turn 4: Follow-up Entity B
        res4 = self.assistant.ask("Anh ấy sinh năm bao nhiêu?", context=ctx_b, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res4["status"], "OK")
        self.assertIn("1987", res4["reply"])
        self.assertNotIn("1985", res4["reply"])

    # =========================================================================
    # SCENARIO 4: Sport Switching (Sport A -> question -> Sport B -> question -> back to Sport A)
    # =========================================================================
    def test_scenario_04_sport_switching_isolation(self):
        # Turn 1: Sport A (Tennis)
        res1 = self.assistant.ask("Novak Djokovic giành được bao nhiêu Grand Slam?", assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res1["status"], "OK")
        self.assertIn("24", res1["reply"])
        ctx_tennis = {"sport_type": "tennis", "active_entity": "Novak Djokovic", "last_intent": "SPORTS_KNOWLEDGE"}

        # Turn 2: Switch to Sport B (Bóng rổ)
        res2 = self.assistant.ask("Thời gian tấn công 24 giây trong bóng rổ hoạt động như thế nào?", context=ctx_tennis, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res2["status"], "OK")
        self.assertTrue("24 giây" in res2["reply"] or "bóng rổ" in res2["reply"].lower() or "FIBA" in res2["reply"] or "NBA" in res2["reply"])
        self.assertNotIn("Grand Slam", res2["reply"])
        ctx_bball = {"sport_type": "bóng rổ", "last_intent": "SPORTS_KNOWLEDGE"}

        # Turn 3: Switch back to Sport A (Tennis - rules)
        res3 = self.assistant.ask("Quy tắc tính điểm game và set trong tennis là gì?", context=ctx_bball, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res3["status"], "OK")
        self.assertIn("15", res3["reply"])
        self.assertIn("40", res3["reply"])
        self.assertNotIn("bóng rổ", res3["reply"].lower())

    # =========================================================================
    # SCENARIO 5: Business Switching (Sports Knowledge -> Venue Search -> Sports Knowledge)
    # =========================================================================
    def test_scenario_05_business_switching_flow(self):
        # Turn 1: Sports Knowledge
        res1 = self.assistant.ask("Kích thước sân pickleball chuẩn là bao nhiêu?", assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res1["status"], "OK")
        self.assertIn("13.41", res1["reply"])
        ctx_sk = {"sport_type": "pickleball", "last_intent": "SPORTS_KNOWLEDGE"}

        # Turn 2: Switch to Business Search
        turn2_q = "Tìm sân pickleball ở Cầu Giấy"
        route2 = self.router.route(turn2_q, context=ctx_sk)
        self.assertEqual(route2.intent, AssistantIntent.SEARCH_VENUE)
        self.assertEqual(route2.entities.sport_type, "pickleball")
        self.assertEqual(route2.entities.location, "Cầu Giấy")

        # Turn 3: Switch back to Sports Knowledge
        turn3_q = "VĐV Quang Dương đạt thứ hạng bao nhiêu trong làng pickleball?"
        route3 = self.router.route(turn3_q, context={"sport_type": "pickleball", "location": "Cầu Giấy", "last_intent": "SEARCH_VENUE"})
        self.assertEqual(route3.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        res3 = self.assistant.ask(turn3_q, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res3["status"], "OK")
        self.assertTrue("Quang Dương" in res3["reply"] or "PPA" in res3["reply"])

    # =========================================================================
    # SCENARIO 6: Out-of-Scope (Non-sports, non-SportHub query)
    # =========================================================================
    def test_scenario_06_out_of_scope_natural_redirect(self):
        query = "Cách nấu chè bưởi giòn ngon không bị đắng?"
        domain = ScopeRouter.classify_domain(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(domain, ScopeDomain.OUT_OF_SCOPE)

        res = self.assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OUT_OF_SCOPE")
        self.assertEqual(res["classification"], ScopeClassification.OUT_OF_SCOPE)
        self.assertTrue("ẩm thực" in res["reply"] or "món ăn" in res["reply"] or "nấu" in res["reply"])
        self.assertTrue("SportHub" in res["reply"] or "sân" in res["reply"] or "thể thao" in res["reply"])
        # No sports knowledge hallucination
        self.assertNotIn("FIFA", res["reply"])
        self.assertNotIn("Grand Slam", res["reply"])

    # =========================================================================
    # SCENARIO 7: Evidence Failure (Unverified entity, insufficient evidence, no fake source)
    # =========================================================================
    def test_scenario_07_evidence_failure_graceful_handling(self):
        query = "Vận động viên Nguyễn Hoàng ABC123 môn bóng rổ ghi bao nhiêu điểm trận chung kết 1970?"
        res = self.assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        reply_lower = res["reply"].lower()
        self.assertTrue(
            "chưa có thông tin kiểm chứng" in reply_lower or 
            "chưa có dữ liệu" in reply_lower or 
            "chưa có thông tin" in reply_lower
        )
        # Verify no fabricated citation URL or hallucinated score
        self.assertNotIn("https://fake-source", reply_lower)
        self.assertNotIn("100 điểm", reply_lower)


if __name__ == "__main__":
    unittest.main()
