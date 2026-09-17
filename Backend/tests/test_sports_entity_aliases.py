import unittest
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.knowledge_retriever import KnowledgeRetriever
from app.services.knowledge_service import KnowledgeService
from app.services.ai_intent_router import IntentRouter
from app.services.ai_assistant_service import AIAssistantService, AIRepository


class EntityAliasRetrieverTests(unittest.TestCase):
    """Test alias / short-name / no-diacritics entity resolution at the retriever level."""

    def setUp(self):
        self.repo = KnowledgeRepository()
        self.retriever = KnowledgeRetriever(self.repo)
        self.service = KnowledgeService(self.repo, self.retriever)

    # ----------------------------------------------------------------
    # 1. FULL NAME (canonical) — baseline sanity
    # ----------------------------------------------------------------
    def test_full_name_lionel_messi(self):
        results = self.service.retrieve("Lionel Messi là ai?", intent="SPORTS_KNOWLEDGE")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0].entity, "Lionel Messi")

    def test_full_name_cristiano_ronaldo(self):
        results = self.service.retrieve("Cristiano Ronaldo là ai?", intent="SPORTS_KNOWLEDGE")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0].entity, "Cristiano Ronaldo")

    def test_full_name_nguyen_quang_hai(self):
        results = self.service.retrieve("Nguyễn Quang Hải là ai?", intent="SPORTS_KNOWLEDGE")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0].entity, "Nguyễn Quang Hải")

    def test_full_name_nguyen_tien_linh(self):
        results = self.service.retrieve("Nguyễn Tiến Linh là ai?", intent="SPORTS_KNOWLEDGE")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0].entity, "Nguyễn Tiến Linh")

    def test_full_name_viktor_axelsen(self):
        results = self.service.retrieve("Viktor Axelsen là ai?", intent="SPORTS_KNOWLEDGE")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0].entity, "Viktor Axelsen")

    # ----------------------------------------------------------------
    # 2. SHORT NAME / NICKNAME (alias)
    # ----------------------------------------------------------------
    def test_short_name_messi(self):
        results = self.service.retrieve("Messi là ai?", intent="SPORTS_KNOWLEDGE")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0].entity, "Lionel Messi")

    def test_alias_leo_messi(self):
        results = self.service.retrieve("Leo Messi là ai?", intent="SPORTS_KNOWLEDGE")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0].entity, "Lionel Messi")

    def test_alias_cr7(self):
        results = self.service.retrieve("CR7 là ai?", intent="SPORTS_KNOWLEDGE")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0].entity, "Cristiano Ronaldo")

    def test_alias_cristiano(self):
        results = self.service.retrieve("Cristiano sinh ở đâu?", intent="SPORTS_KNOWLEDGE")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0].entity, "Cristiano Ronaldo")
        self.assertEqual(results[0][0].topic, "birth_place")

    def test_short_name_ronaldo(self):
        results = self.service.retrieve("Ronaldo sinh ngày nào?", intent="SPORTS_KNOWLEDGE")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0].entity, "Cristiano Ronaldo")
        self.assertEqual(results[0][0].topic, "birth_date")

    def test_short_name_quang_hai(self):
        """Short Vietnamese name without diacritics should resolve."""
        results = self.service.retrieve("Quang Hải đang chơi cho đội nào?", intent="SPORTS_KNOWLEDGE")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0].entity, "Nguyễn Quang Hải")
        self.assertEqual(results[0][0].topic, "current_club")

    def test_short_name_tien_linh(self):
        results = self.service.retrieve("Tiến Linh sinh ngày nào?", intent="SPORTS_KNOWLEDGE")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0].entity, "Nguyễn Tiến Linh")

    def test_short_name_hoang_duc(self):
        results = self.service.retrieve("Hoàng Đức đang thi đấu cho CLB nào?", intent="SPORTS_KNOWLEDGE")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0].entity, "Nguyễn Hoàng Đức")

    def test_short_name_thuy_linh(self):
        results = self.service.retrieve("Thùy Linh là ai?", intent="SPORTS_KNOWLEDGE")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0].entity, "Nguyễn Thùy Linh")

    def test_short_name_tien_minh(self):
        results = self.service.retrieve("Tiến Minh là ai?", intent="SPORTS_KNOWLEDGE")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0].entity, "Nguyễn Tiến Minh")

    def test_short_name_axelsen(self):
        results = self.service.retrieve("Axelsen thành tích gì nổi bật?", intent="SPORTS_KNOWLEDGE")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0].entity, "Viktor Axelsen")

    # ----------------------------------------------------------------
    # 3. VIETNAMESE NO-DIACRITICS (tiếng Việt không dấu)
    # ----------------------------------------------------------------
    def test_no_diacritics_quang_hai(self):
        results = self.service.retrieve("Quang Hai la ai?", intent="SPORTS_KNOWLEDGE")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0].entity, "Nguyễn Quang Hải")

    def test_no_diacritics_tien_linh(self):
        results = self.service.retrieve("Tien Linh dang choi cho doi nao?", intent="SPORTS_KNOWLEDGE")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0].entity, "Nguyễn Tiến Linh")

    def test_no_diacritics_hoang_duc(self):
        results = self.service.retrieve("Hoang Duc la ai?", intent="SPORTS_KNOWLEDGE")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0].entity, "Nguyễn Hoàng Đức")

    def test_no_diacritics_thuy_linh(self):
        results = self.service.retrieve("Thuy Linh la ai?", intent="SPORTS_KNOWLEDGE")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0].entity, "Nguyễn Thùy Linh")

    def test_no_diacritics_tien_minh(self):
        results = self.service.retrieve("Tien Minh thi dau cho doi nao?", intent="SPORTS_KNOWLEDGE")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0].entity, "Nguyễn Tiến Minh")

    # ----------------------------------------------------------------
    # 4. ALIAS + TOPIC ATTRIBUTE combination
    # ----------------------------------------------------------------
    def test_alias_leo_messi_birth_date(self):
        results = self.service.retrieve("Leo Messi sinh ngày nào?", intent="SPORTS_KNOWLEDGE")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0].entity, "Lionel Messi")
        self.assertEqual(results[0][0].topic, "birth_date")
        self.assertIn("24 tháng 6 năm 1987", results[0][0].answer)

    def test_alias_cr7_achievements(self):
        results = self.service.retrieve("CR7 có thành tích gì nổi bật?", intent="SPORTS_KNOWLEDGE")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0].entity, "Cristiano Ronaldo")
        self.assertEqual(results[0][0].topic, "achievements")

    def test_alias_cr7_current_club(self):
        results = self.service.retrieve("CR7 đang chơi cho đội nào?", intent="SPORTS_KNOWLEDGE")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][0].entity, "Cristiano Ronaldo")
        self.assertEqual(results[0][0].topic, "current_club")


class EntityAliasRouterTests(unittest.TestCase):
    """Test that the intent router resolves aliases to the correct canonical entity."""

    def setUp(self):
        self.router = IntentRouter()

    def _route(self, query: str, context: dict = None):
        return self.router.route(query, context or {})

    def test_router_leo_messi(self):
        route = self._route("Leo Messi là ai?")
        self.assertEqual(route.entities.sports_entity, "Lionel Messi")

    def test_router_cr7(self):
        route = self._route("CR7 sinh ngày nào?")
        self.assertEqual(route.entities.sports_entity, "Cristiano Ronaldo")

    def test_router_cristiano(self):
        route = self._route("Cristiano sinh ở đâu?")
        self.assertEqual(route.entities.sports_entity, "Cristiano Ronaldo")

    def test_router_la_pulga(self):
        route = self._route("La Pulga là ai?")
        self.assertEqual(route.entities.sports_entity, "Lionel Messi")

    def test_router_quang_hai(self):
        route = self._route("Quang Hải đang chơi cho đội nào?")
        self.assertEqual(route.entities.sports_entity, "Nguyễn Quang Hải")

    def test_router_tien_linh(self):
        route = self._route("Tiến Linh sinh ở đâu?")
        self.assertEqual(route.entities.sports_entity, "Nguyễn Tiến Linh")


class EntityAliasEndToEndTests(unittest.TestCase):
    """End-to-end tests via AIAssistantService.ask() for alias-based queries."""

    def test_leo_messi_e2e(self):
        ai = AIAssistantService(AIRepository(None))
        r = ai.ask("Leo Messi là ai?")
        self.assertIn("Lionel Messi", r['reply'])
        self.assertEqual(r['understood']['sports_entity'], "Lionel Messi")

    def test_cr7_birth_date_e2e(self):
        ai = AIAssistantService(AIRepository(None))
        r = ai.ask("CR7 sinh ngày nào?")
        self.assertIn("5 tháng 2 năm 1985", r['reply'])
        self.assertEqual(r['understood']['sports_entity'], "Cristiano Ronaldo")

    def test_quang_hai_no_diacritics_e2e(self):
        ai = AIAssistantService(AIRepository(None))
        r = ai.ask("Quang Hai la ai?")
        self.assertIn("Quang Hải", r['reply'])

    def test_tien_linh_short_e2e(self):
        ai = AIAssistantService(AIRepository(None))
        r = ai.ask("Tiến Linh sinh ngày nào?")
        self.assertIn("20 tháng 10 năm 1997", r['reply'])

    def test_axelsen_no_diacritics_e2e(self):
        ai = AIAssistantService(AIRepository(None))
        r = ai.ask("Axelsen la ai?")
        self.assertIn("Viktor Axelsen", r['reply'])


if __name__ == '__main__':
    unittest.main()
