import unittest
from unittest.mock import patch
from app.services.ai_sports_resolver import SportsContextResolver
from app.services.ai_intent_router import IntentRouter, AssistantIntent
from app.services.ai_assistant_service import AIAssistantService, AIRepository
from app.schemas.ai import AssistantMode


class AssistantMockRankingProvider:
    def generate_json(self, **kwargs):
        available = kwargs.get('system_data', {}).get('available_slots', [])
        return {'status': 'OK', 'recommendations': [
            {'court_id': item['court_id'], 'slot_id': item['slot_id'], 'reason': 'Phù hợp nhu cầu đã chọn.'}
            for item in available[:3]
        ]}


class NaturalModeContextSwitchingDeepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provider_patch = patch('app.services.ai_feature_service.StructuredAIProvider', return_value=AssistantMockRankingProvider())
        cls.provider_patch.start()
        cls.router = IntentRouter()
        cls.assistant = AIAssistantService(AIRepository(None))

    @classmethod
    def tearDownClass(cls):
        cls.provider_patch.stop()

    # ─────────────────────────────────────────────────────────────────
    # 1. Follow-up Forms
    # ─────────────────────────────────────────────────────────────────
    def test_followup_vay_con(self):
        # Turn 1: Ben Johns
        r1 = SportsContextResolver.resolve("Ben Johns là ai?")
        self.assertEqual(r1.active_entity, "Ben Johns")
        self.assertEqual(r1.sport, "pickleball")

        # Turn 2: "vậy còn danh hiệu của anh ấy?"
        ctx1 = {
            "active_entity": "Ben Johns",
            "entity_type": "athlete",
            "sport": "pickleball",
            "last_intent": "SPORTS_KNOWLEDGE",
        }
        r2 = SportsContextResolver.resolve("vậy còn danh hiệu của anh ấy?", context=ctx1)
        self.assertEqual(r2.active_entity, "Ben Johns")
        self.assertEqual(r2.sport, "pickleball")
        self.assertTrue(r2.is_follow_up)
        self.assertIn("Ben Johns", r2.rewritten_query)

    def test_followup_the_anh_ay_thi_sao(self):
        # Context with LeBron James
        ctx = {
            "active_entity": "LeBron James",
            "entity_type": "athlete",
            "sport": "bóng rổ",
            "last_intent": "SPORTS_KNOWLEDGE",
        }
        r = SportsContextResolver.resolve("thế anh ấy thì sao?", context=ctx)
        self.assertEqual(r.active_entity, "LeBron James")
        self.assertEqual(r.sport, "bóng rổ")
        self.assertTrue(r.is_follow_up)

    def test_followup_con_giai_do(self):
        # Context with V-League
        ctx = {
            "active_entity": "V.League 1",
            "entity_type": "competition",
            "competition": "V.League 1",
            "sport": "bóng đá",
            "last_intent": "SPORTS_KNOWLEDGE",
        }
        r = SportsContextResolver.resolve("còn giải đó tổ chức ở đâu?", context=ctx)
        self.assertEqual(r.competition, "V.League 1")
        self.assertTrue(r.is_follow_up)
        self.assertIn("V.League 1", r.rewritten_query)

    def test_followup_mon_nay_thi_sao(self):
        # Context with Volleyball
        ctx = {
            "sport": "bóng chuyền",
            "sport_type": "bóng chuyền",
            "last_intent": "SPORTS_KNOWLEDGE",
        }
        r = SportsContextResolver.resolve("Việt Nam có ai nổi bật ở môn này?", context=ctx)
        self.assertEqual(r.sport, "bóng chuyền")
        self.assertTrue(r.is_follow_up)
        self.assertIn("môn bóng chuyền", r.rewritten_query)

    def test_followup_o_viet_nam_thi_sao(self):
        # Context with Tennis
        ctx = {
            "sport": "tennis",
            "sport_type": "tennis",
            "last_intent": "SPORTS_KNOWLEDGE",
        }
        r = SportsContextResolver.resolve("ở Việt Nam thì sao?", context=ctx)
        self.assertEqual(r.sport, "tennis")
        self.assertEqual(r.location, "Việt Nam")
        self.assertTrue(r.is_follow_up)
        self.assertIn("tennis", r.rewritten_query)
        self.assertIn("Việt Nam", r.rewritten_query)

    # ─────────────────────────────────────────────────────────────────
    # 2. Entity Switching
    # ─────────────────────────────────────────────────────────────────
    def test_entity_switching_athlete_a_to_b(self):
        # Turn 1: Novak Djokovic
        ctx1 = {
            "active_entity": "Novak Djokovic",
            "entity_type": "athlete",
            "sport": "tennis",
            "last_intent": "SPORTS_KNOWLEDGE",
        }
        # Follow-up on Djokovic
        r_f1 = SportsContextResolver.resolve("ông ấy đã giành bao nhiêu Grand Slam?", context=ctx1)
        self.assertEqual(r_f1.active_entity, "Novak Djokovic")

        # Turn 2: Switch to Rafael Nadal
        r_switch = SportsContextResolver.resolve("Còn Rafael Nadal?", context=ctx1)
        self.assertEqual(r_switch.active_entity, "Rafael Nadal")
        self.assertEqual(r_switch.sport, "tennis")
        self.assertIn("Novak Djokovic", r_switch.recent_entities)

        # Turn 3: Follow-up on Nadal
        ctx2 = {
            "active_entity": "Rafael Nadal",
            "entity_type": "athlete",
            "sport": "tennis",
            "recent_entities": r_switch.recent_entities,
            "last_intent": "SPORTS_KNOWLEDGE",
        }
        r_f2 = SportsContextResolver.resolve("anh ấy sinh năm bao nhiêu?", context=ctx2)
        self.assertEqual(r_f2.active_entity, "Rafael Nadal")
        self.assertNotIn("Novak Djokovic", r_f2.rewritten_query)
        self.assertIn("Rafael Nadal", r_f2.rewritten_query)

    def test_sport_switching_a_to_b_to_a(self):
        # Sport A: Basketball
        ctx_bb = {
            "sport": "bóng rổ",
            "sport_type": "bóng rổ",
            "active_entity": "Stephen Curry",
            "entity_type": "athlete",
            "last_intent": "SPORTS_KNOWLEDGE",
        }
        # Switch to Sport B: Volleyball
        r_vb = SportsContextResolver.resolve("Còn bóng chuyền thì chiều cao lưới nam là bao nhiêu?", context=ctx_bb)
        self.assertEqual(r_vb.sport, "bóng chuyền")
        self.assertIsNone(r_vb.active_entity)  # Cleared athlete from prior sport!

        # Switch back to Sport A: Basketball
        ctx_vb = {
            "sport": "bóng chuyền",
            "sport_type": "bóng chuyền",
            "last_intent": "SPORTS_KNOWLEDGE",
        }
        r_bb_back = SportsContextResolver.resolve("Quay lại bóng rổ, thời gian tấn công là bao lâu?", context=ctx_vb)
        self.assertEqual(r_bb_back.sport, "bóng rổ")
        self.assertNotIn("bóng chuyền", r_bb_back.rewritten_query)

    # ─────────────────────────────────────────────────────────────────
    # 3. Topic Switching (Knowledge -> Business -> Knowledge)
    # ─────────────────────────────────────────────────────────────────
    def test_knowledge_to_business_to_knowledge_flow(self):
        # Turn 1: Sports Knowledge (Ronaldo World Cup)
        res1 = self.assistant.ask("Ronaldo đã vô địch World Cup chưa?", assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res1["status"], "OK")
        self.assertIn("chưa từng vô địch", res1["reply"])

        # Turn 2: Followup on achievements
        ctx1 = {
            "active_entity": "Cristiano Ronaldo",
            "entity_type": "athlete",
            "sport": "bóng đá",
            "last_intent": "SPORTS_KNOWLEDGE",
        }
        r_ach = SportsContextResolver.resolve("anh ấy đã giành Quả bóng vàng mấy lần?", context=ctx1)
        self.assertEqual(r_ach.active_entity, "Cristiano Ronaldo")
        self.assertEqual(r_ach.target_trophy, "Ballon d'Or")

        # Turn 3: User switches to Business: "Thôi tìm sân bóng lúc nãy."
        ctx2 = dict(ctx1)
        ctx2["last_search"] = {"sport_type": "bóng đá", "location": "Cầu Giấy"}
        ctx2["location"] = "Cầu Giấy"
        route_biz = self.router.route("Thôi tìm sân bóng lúc nãy.", context=ctx2)
        self.assertEqual(route_biz.intent, AssistantIntent.SEARCH_VENUE)
        self.assertEqual(route_biz.entities.sport_type, "bóng đá")

        # Turn 4: Return to sports knowledge: "Quay lại Ronaldo, còn C1 thì sao?"
        ctx3 = {
            "sport_type": "bóng đá",
            "location": "Cầu Giấy",
            "last_intent": "SEARCH_VENUE",
            "active_entity": "Cristiano Ronaldo",
            "recent_entities": ["Cristiano Ronaldo"],
        }
        r_know_back = SportsContextResolver.resolve("Quay lại Ronaldo, còn C1 thì sao?", context=ctx3)
        self.assertEqual(r_know_back.active_entity, "Cristiano Ronaldo")
        self.assertEqual(r_know_back.target_trophy, "UEFA Champions League")
        self.assertIn("Cristiano Ronaldo", r_know_back.rewritten_query)
        self.assertIn("UEFA Champions League", r_know_back.rewritten_query)

    # ─────────────────────────────────────────────────────────────────
    # 4. Query Rewrite & Context Priority
    # ─────────────────────────────────────────────────────────────────
    def test_query_rewrite_con_c1_alone(self):
        # Query "còn C1?" in context of Cristiano Ronaldo must rewrite with complete context
        ctx = {
            "active_entity": "Cristiano Ronaldo",
            "entity_type": "athlete",
            "sport": "bóng đá",
            "last_intent": "SPORTS_KNOWLEDGE",
        }
        r = SportsContextResolver.resolve("còn C1?", context=ctx)
        self.assertEqual(r.active_entity, "Cristiano Ronaldo")
        self.assertEqual(r.target_trophy, "UEFA Champions League")
        self.assertIn("Cristiano Ronaldo", r.rewritten_query)
        self.assertIn("UEFA Champions League", r.rewritten_query)

    def test_context_priority_new_entity_overrides_old(self):
        # When user explicitly mentions Anna Leigh Waters in query, it overrides Ben Johns
        ctx = {
            "active_entity": "Ben Johns",
            "entity_type": "athlete",
            "sport": "pickleball",
            "last_intent": "SPORTS_KNOWLEDGE",
        }
        r = SportsContextResolver.resolve("Anna Leigh Waters sinh năm bao nhiêu?", context=ctx)
        self.assertEqual(r.active_entity, "Anna Leigh Waters")
        self.assertEqual(r.sport, "pickleball")
        self.assertEqual(r.recent_entities[0], "Anna Leigh Waters")
        self.assertEqual(r.recent_entities[1], "Ben Johns")


if __name__ == '__main__':
    unittest.main()
