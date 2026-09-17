import unittest

from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.knowledge_retriever import KnowledgeRetriever
from app.services.knowledge_service import KnowledgeService
from app.services.ai_intent_router import IntentRouter, AssistantIntent


class ProvinceSportsKnowledgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = KnowledgeRepository()
        cls.retriever = KnowledgeRetriever(cls.repo)
        cls.service = KnowledgeService(cls.repo, cls.retriever)
        cls.router = IntentRouter()

    # ----------------------------------------------------
    # 1. THAI NGUYEN PROVINCE EXPANDED TESTS
    # ----------------------------------------------------
    def test_thai_nguyen_sports_beyond_football(self):
        query = "Ở Thái Nguyên ngoài bóng đá còn có môn gì?"
        route = self.router.route(query)
        self.assertEqual(route.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertIn("Thể thao Thái Nguyên", route.entities.sports_entities)

        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", entity="Thể thao Thái Nguyên")
        self.assertGreater(len(results), 0)
        entry = next((e for e, _ in results if e.id == "TN-SPT-040"), None)
        self.assertIsNotNone(entry)
        self.assertIn("Cầu lông", entry.content)
        self.assertIn("Pickleball", entry.content)
        self.assertIn("Bóng chuyền", entry.content)

    def test_thai_nguyen_badminton(self):
        query = "Thái Nguyên có cầu lông không?"
        route = self.router.route(query)
        self.assertEqual(route.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertIn("Cầu lông Thái Nguyên", route.entities.sports_entities)

        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", sport="cầu lông", entity="Cầu lông Thái Nguyên")
        self.assertGreater(len(results), 0)
        entry = next((e for e, _ in results if e.id == "TN-SPT-005"), None)
        self.assertIsNotNone(entry)
        self.assertIn("Giải Cầu lông các Câu lạc bộ tỉnh Thái Nguyên", entry.content)

    def test_thai_nguyen_football_teams(self):
        query = "Ở Thái Nguyên có những đội bóng đá nào?"
        route = self.router.route(query)
        self.assertEqual(route.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertIn("Bóng đá Thái Nguyên", route.entities.sports_entities)

        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", sport="bóng đá", entity="Bóng đá Thái Nguyên")
        self.assertGreater(len(results), 0)
        entry = next((e for e, _ in results if e.id == "TN-SPT-003"), None)
        self.assertIsNotNone(entry)
        self.assertIn("Thái Nguyên T&T", entry.content)
        self.assertIn("FC Thái Nguyên", entry.content)

    # ----------------------------------------------------
    # 2. HANOI SPORTS KNOWLEDGE TESTS
    # ----------------------------------------------------
    def test_hanoi_sports_overview(self):
        query = "Hà Nội có những môn thể thao nào?"
        route = self.router.route(query)
        self.assertEqual(route.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertIn("Thể thao Hà Nội", route.entities.sports_entities)

        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", entity="Thể thao Hà Nội")
        self.assertGreater(len(results), 0)
        entry = next((e for e, _ in results if e.id == "HN-SPT-001"), None)
        self.assertIsNotNone(entry)
        self.assertIn("Bóng đá", entry.content)
        self.assertIn("Bóng rổ", entry.content)
        self.assertIn("Võ thuật", entry.content)

    def test_hanoi_volleyball(self):
        query = "Ở Hà Nội có bóng chuyền không?"
        route = self.router.route(query)
        self.assertEqual(route.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertIn("Bóng chuyền Hà Nội", route.entities.sports_entities)

        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", sport="bóng chuyền", entity="Bóng chuyền Hà Nội")
        self.assertGreater(len(results), 0)
        entry = next((e for e, _ in results if e.id == "HN-SPT-004"), None)
        self.assertIsNotNone(entry)
        self.assertIn("bóng chuyền nam Hà Nội", entry.content)
        self.assertIn("bóng chuyền nữ Hà Nội", entry.content)

    def test_hanoi_university_sports(self):
        query = "Ở các trường đại học Hà Nội có những đội thể thao nào?"
        route = self.router.route(query)
        self.assertEqual(route.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertIn("Thể thao Đại học Hà Nội", route.entities.sports_entities)

        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", entity="Thể thao Đại học Hà Nội")
        self.assertGreater(len(results), 0)
        entry = next((e for e, _ in results if e.id == "HN-SPT-007"), None)
        self.assertIsNotNone(entry)
        self.assertIn("SV Cup", entry.content)
        self.assertIn("Đại học Sư phạm Hà Nội", entry.content)

    # ----------------------------------------------------
    # 3. TP. HỒ CHÍ MINH SPORTS KNOWLEDGE TESTS
    # ----------------------------------------------------
    def test_hcmc_basketball_clubs(self):
        query = "TP.HCM có những CLB bóng rổ nào?"
        route = self.router.route(query)
        self.assertEqual(route.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertIn("Bóng rổ TP.HCM", route.entities.sports_entities)

        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", sport="bóng rổ", entity="Bóng rổ TP.HCM")
        self.assertGreater(len(results), 0)
        entry = next((e for e, _ in results if e.id == "HCM-SPT-003"), None)
        self.assertIsNotNone(entry)
        self.assertIn("Saigon Heat", entry.content)
        self.assertIn("Ho Chi Minh City Wings", entry.content)

    def test_hcmc_sports_beyond_football(self):
        query = "Ngoài bóng đá thì TP.HCM còn có những môn gì?"
        route = self.router.route(query)
        self.assertEqual(route.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertIn("Thể thao TP.HCM", route.entities.sports_entities)

        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", entity="Thể thao TP.HCM")
        self.assertGreater(len(results), 0)
        entry = next((e for e, _ in results if e.id == "HCM-SPT-001"), None)
        self.assertIsNotNone(entry)
        self.assertIn("Bóng rổ", entry.content)
        self.assertIn("Bóng bàn", entry.content)
        self.assertIn("Cầu lông", entry.content)

    # ----------------------------------------------------
    # 4. MULTI-ENTITY (HÀ NỘI + TP.HCM) & ICTU TESTS
    # ----------------------------------------------------
    def test_ictu_multi_sports(self):
        query = "ICTU có những môn thể thao gì?"
        route = self.router.route(query)
        self.assertEqual(route.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertIn("Thể thao ICTU", route.entities.sports_entities)

        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", entity="Thể thao ICTU")
        self.assertGreater(len(results), 0)
        entry = next((e for e, _ in results if e.id == "TN-SPT-030"), None)
        self.assertIsNotNone(entry)
        self.assertIn("ICTU CUP", entry.content)
        self.assertIn("Pickleball", entry.content)

    def test_multi_province_query_hanoi_and_hcmc(self):
        query = "Hà Nội và TP.HCM có những môn thể thao nào được hệ thống biết?"
        route = self.router.route(query)
        self.assertEqual(route.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertIn("Thể thao Hà Nội", route.entities.sports_entities)
        self.assertIn("Thể thao TP.HCM", route.entities.sports_entities)

        results_hn = self.service.retrieve("Thể thao Hà Nội", intent="SPORTS_KNOWLEDGE", entity="Thể thao Hà Nội")
        results_hcm = self.service.retrieve("Thể thao TP.HCM", intent="SPORTS_KNOWLEDGE", entity="Thể thao TP.HCM")
        self.assertGreater(len(results_hn), 0)
        self.assertGreater(len(results_hcm), 0)

    # ----------------------------------------------------
    # 5. MULTI-TURN LOCATION CONTEXT TESTS
    # ----------------------------------------------------
    def test_multiturn_location_pronoun(self):
        # Turn 1: User asks about Thai Nguyen
        t1_query = "Thái Nguyên có những đội bóng nào?"
        t1_route = self.router.route(t1_query)
        self.assertIn("Bóng đá Thái Nguyên", t1_route.entities.sports_entities)
        context = {
            "last_intent": AssistantIntent.SPORTS_KNOWLEDGE.value,
            "sports_entities": t1_route.entities.sports_entities,
            "sports_entity": t1_route.entities.sports_entity,
            "sport_type": t1_route.entities.sport_type,
            "location": "Thái Nguyên",
        }

        # Turn 2: User asks "Tỉnh này có đội bóng chuyền không?"
        t2_query = "Tỉnh này có đội bóng chuyền không?"
        t2_route = self.router.route(t2_query, context=context)
        self.assertEqual(t2_route.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertIn("Bóng chuyền Thái Nguyên", t2_route.entities.sports_entities)
        self.assertEqual(t2_route.entities.sport_type, "bóng chuyền")

    def test_multiturn_other_sports_pronoun(self):
        # Turn 1: User asks about Hanoi
        t1_query = "Hà Nội FC là đội nào?"
        t1_route = self.router.route(t1_query)
        self.assertIn("Hà Nội FC", t1_route.entities.sports_entities)
        context = {
            "last_intent": AssistantIntent.SPORTS_KNOWLEDGE.value,
            "sports_entities": t1_route.entities.sports_entities,
            "sports_entity": "Hà Nội FC",
            "sport_type": "bóng đá",
            "location": "Hà Nội",
        }

        # Turn 2: User asks "Còn môn khác thì sao?"
        t2_query = "Còn môn khác thì sao?"
        t2_route = self.router.route(t2_query, context=context)
        self.assertEqual(t2_route.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertIn("Thể thao Hà Nội", t2_route.entities.sports_entities)


if __name__ == "__main__":
    unittest.main()
