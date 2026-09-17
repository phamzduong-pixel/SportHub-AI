import unittest

from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.knowledge_retriever import KnowledgeRetriever
from app.services.knowledge_service import KnowledgeService
from app.services.ai_intent_router import IntentRouter, AssistantIntent


class ThaiNguyenICTUFootballKnowledgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = KnowledgeRepository()
        cls.retriever = KnowledgeRetriever(cls.repo)
        cls.service = KnowledgeService(cls.repo, cls.retriever)
        cls.router = IntentRouter()

    # ----------------------------------------------------
    # 1. INTENT ROUTING & ENTITY EXTRACTION
    # ----------------------------------------------------
    def test_intent_router_recognizes_ictu_football_queries(self):
        test_queries = [
            ("ICTU có đội bóng đá không?", "Bóng đá ICTU"),
            ("Đội bóng ICTU tên gì vậy?", "Bóng đá ICTU"),
            ("Trường CNTT và Truyền thông Thái Nguyên có đội bóng đá sinh viên không?", "Bóng đá ICTU"),
            ("Đội bóng sinh viên ICTU từng thi đấu ở đâu?", "Bóng đá ICTU"),
            ("ICTU CUP là giải gì?", "ICTU CUP"),
            ("ICTU CUP 2024 có bao nhiêu đội?", "ICTU CUP"),
            ("Khoa CNTT ICTU có đá bóng không?", "Khoa CNTT ICTU"),
            ("ICTU có bóng đá nữ không?", "Bóng đá ICTU"),
            ("Ở Thái Nguyên có những đội bóng sinh viên nào?", "Bóng đá ICTU"),
        ]

        for query, expected_entity in test_queries:
            route = self.router.route(query)
            self.assertEqual(route.intent, AssistantIntent.SPORTS_KNOWLEDGE, f"Query '{query}' should be SPORTS_KNOWLEDGE")
            self.assertEqual(route.entities.sport_type, "bóng đá", f"Query '{query}' should detect sport as 'bóng đá'")
            self.assertIn(expected_entity, route.entities.sports_entities, f"Query '{query}' should extract entity '{expected_entity}'")

    # ----------------------------------------------------
    # 2. KNOWLEDGE RETRIEVAL FOR ALL REQUIRED QUESTIONS
    # ----------------------------------------------------
    def test_retrieve_ictu_team_existence_and_identity(self):
        query = "ICTU có đội bóng đá không?"
        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", sport="bóng đá", entity="Bóng đá ICTU")
        self.assertGreater(len(results), 0)
        top_entry, score = results[0]
        self.assertIn("ICTU", top_entry.content)
        self.assertIn("đội tuyển bóng đá nam sinh viên ICTU", top_entry.content)
        self.assertIn("https://ictu.edu.vn", top_entry.source_url)
        self.assertGreaterEqual(score, 0.60)

    def test_retrieve_ictu_competition_history_and_con_minh(self):
        query = "Đội bóng sinh viên ICTU từng thi đấu ở đâu?"
        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", sport="bóng đá", entity="Bóng đá ICTU")
        self.assertGreater(len(results), 0)
        top_entry, score = results[0]
        self.assertIn("Côn Minh", top_entry.content)
        self.assertIn("2019", top_entry.content)
        self.assertIn("https://ictu.edu.vn/dau-an-con-minh/", top_entry.source_url)

    def test_retrieve_ictu_cup_tournament_info(self):
        query = "ICTU CUP 2024 có bao nhiêu đội?"
        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", sport="bóng đá", entity="ICTU CUP")
        self.assertGreater(len(results), 0)
        top_entry, score = results[0]
        self.assertEqual(top_entry.id, "TN-SPT-022")
        self.assertIn("8 đội", top_entry.content)
        self.assertIn("4 đội nam và 4 đội nữ", top_entry.content)
        self.assertIn("sân bóng cỏ nhân tạo ICTU", top_entry.content)
        self.assertIn("https://ictu.edu.vn/khoi-tranh-giai-bong-da-sinh-vien-ictu-cup-2024/", top_entry.source_url)

    def test_retrieve_fit_ictu_football_match(self):
        query = "Khoa CNTT ICTU có đá bóng không?"
        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", sport="bóng đá", entity="Khoa CNTT ICTU")
        self.assertGreater(len(results), 0)
        top_entry, score = results[0]
        self.assertEqual(top_entry.id, "TN-SPT-024")
        self.assertIn("HNUE", top_entry.content)
        self.assertIn("28/12/2025", top_entry.content)
        self.assertIn("fit.ictu.edu.vn", top_entry.source_url)

    def test_retrieve_ictu_women_football(self):
        query = "ICTU có bóng đá nữ không?"
        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", sport="bóng đá", entity="Bóng đá ICTU")
        self.assertGreater(len(results), 0)
        matching_entry = next((e for e, _ in results if "bóng đá nữ" in e.topic.lower() or "bóng đá nữ" in e.content.lower()), None)
        self.assertIsNotNone(matching_entry)
        self.assertIn("4 đội bóng đá nữ", matching_entry.content)

    def test_retrieve_fet_ictu_football(self):
        query = "Khoa Kỹ thuật và Công nghệ ICTU có giải bóng đá không?"
        route = self.router.route(query)
        self.assertIn("Khoa Kỹ thuật và Công nghệ ICTU", route.entities.sports_entities)
        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", sport="bóng đá", entity="Khoa Kỹ thuật và Công nghệ ICTU")
        self.assertGreater(len(results), 0)
        top_entry, score = results[0]
        self.assertEqual(top_entry.id, "TN-SPT-025")
        self.assertIn("FET", top_entry.content)
        self.assertIn("fet.ictu.edu.vn", top_entry.source_url)

    # ----------------------------------------------------
    # 3. DIFFERENTIATION TESTS
    # ----------------------------------------------------
    def test_differentiation_ictu_vs_thai_nguyen_tt(self):
        query = "ICTU với Thái Nguyên T&T có phải cùng một đội không?"
        route = self.router.route(query)
        self.assertIn("Bóng đá ICTU", route.entities.sports_entities)
        self.assertIn("Thái Nguyên T&T", route.entities.sports_entities)
        
        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", sport="bóng đá")
        self.assertGreater(len(results), 0)
        diff_entry = next((e for e, _ in results if e.id == "TN-SPT-026"), None)
        self.assertIsNotNone(diff_entry)
        self.assertIn("hoàn toàn khác nhau", diff_entry.content)
        self.assertIn("Thái Nguyên T&T là Câu lạc bộ bóng đá nữ chuyên nghiệp", diff_entry.content)
        self.assertIn("bóng đá sinh viên", diff_entry.content)

    def test_differentiation_ictu_vs_fc_thai_nguyen(self):
        query = "Đội bóng ICTU và FC Thái Nguyên khác nhau thế nào?"
        route = self.router.route(query)
        self.assertIn("Bóng đá ICTU", route.entities.sports_entities)
        self.assertIn("Bóng đá nam Thái Nguyên", route.entities.sports_entities)

        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", sport="bóng đá")
        self.assertGreater(len(results), 0)
        diff_entry = next((e for e, _ in results if e.id == "TN-SPT-027"), None)
        self.assertIsNotNone(diff_entry)
        self.assertIn("hoàn toàn khác nhau", diff_entry.content)
        self.assertIn("FC Thái Nguyên", diff_entry.content)
        self.assertIn("đại diện chính thức cho tỉnh Thái Nguyên", diff_entry.content)

    def test_thai_nguyen_student_teams_grounding(self):
        query = "Ở Thái Nguyên có những đội bóng sinh viên nào?"
        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", sport="bóng đá", entity="Bóng đá ICTU")
        self.assertGreater(len(results), 0)
        entry = next((e for e, _ in results if e.id == "TN-SPT-028"), None)
        self.assertIsNotNone(entry)
        self.assertIn("ICTU", entry.content)
        self.assertIn("Côn Minh 2019", entry.content)
        self.assertIn("không suy đoán các trường chưa có nguồn kiểm chứng", entry.content)

    # ----------------------------------------------------
    # 4. MULTI-SPORT ICTU TESTS
    # ----------------------------------------------------
    def test_ictu_multi_sports_overview(self):
        query = "ICTU có những môn thể thao gì?"
        route = self.router.route(query)
        self.assertEqual(route.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertIn("Thể thao ICTU", route.entities.sports_entities)

        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", entity="Thể thao ICTU")
        self.assertGreater(len(results), 0)
        entry = next((e for e, _ in results if e.id == "TN-SPT-030"), None)
        self.assertIsNotNone(entry)
        self.assertIn("Bóng đá", entry.content)
        self.assertIn("Cầu lông", entry.content)
        self.assertIn("Bóng bàn", entry.content)
        self.assertIn("Bóng chuyền", entry.content)
        self.assertIn("Pickleball", entry.content)
        self.assertIn("Quản lý Thể thao số & E-Sports", entry.content)

    def test_ictu_sports_beyond_football(self):
        query = "Ngoài bóng đá trường ICTU còn chơi môn nào?"
        route = self.router.route(query)
        self.assertEqual(route.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertIn("Thể thao ICTU", route.entities.sports_entities)

        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", entity="Thể thao ICTU")
        self.assertGreater(len(results), 0)
        entry = next((e for e, _ in results if e.id == "TN-SPT-030"), None)
        self.assertIsNotNone(entry)
        self.assertIn("Cầu lông", entry.content)
        self.assertIn("Pickleball", entry.content)

    def test_ictu_badminton_retrieval(self):
        query = "ICTU có cầu lông không?"
        route = self.router.route(query)
        self.assertEqual(route.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertIn("Cầu lông ICTU", route.entities.sports_entities)

        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", sport="cầu lông", entity="Cầu lông ICTU")
        self.assertGreater(len(results), 0)
        entry = next((e for e, _ in results if e.id == "TN-SPT-031"), None)
        self.assertIsNotNone(entry)
        self.assertIn("Giải Cầu lông viên chức", entry.content)
        self.assertIn("FISU", entry.content)

    def test_ictu_volleyball_retrieval(self):
        query = "Trường CNTT Thái Nguyên có bóng chuyền không?"
        route = self.router.route(query)
        self.assertEqual(route.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertIn("Bóng chuyền ICTU", route.entities.sports_entities)

        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", sport="bóng chuyền", entity="Bóng chuyền ICTU")
        self.assertGreater(len(results), 0)
        entry = next((e for e, _ in results if e.id == "TN-SPT-032"), None)
        self.assertIsNotNone(entry)
        self.assertIn("bóng chuyền hơi", entry.content)
        self.assertIn("lưu học sinh", entry.content)

    def test_ictu_table_tennis_retrieval(self):
        query = "ICTU có bóng bàn không?"
        route = self.router.route(query)
        self.assertEqual(route.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertIn("Bóng bàn ICTU", route.entities.sports_entities)

        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", sport="bóng bàn", entity="Bóng bàn ICTU")
        self.assertGreater(len(results), 0)
        entry = next((e for e, _ in results if e.id == "TN-SPT-033"), None)
        self.assertIsNotNone(entry)
        self.assertIn("Bóng bàn", entry.content)
        self.assertIn("FISU", entry.content)

    def test_ictu_pickleball_retrieval(self):
        query = "Sinh viên ICTU có chơi pickleball không?"
        route = self.router.route(query)
        self.assertEqual(route.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertIn("Pickleball ICTU", route.entities.sports_entities)

        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", sport="pickleball", entity="Pickleball ICTU")
        self.assertGreater(len(results), 0)
        entry = next((e for e, _ in results if e.id == "TN-SPT-034"), None)
        self.assertIsNotNone(entry)
        self.assertIn("Sân Pickleball 1", entry.content)
        self.assertIn("Việt Nam – Lào năm 2025", entry.content)

    def test_ictu_sports_clubs_grounding(self):
        query = "Ở ICTU có những CLB thể thao nào?"
        route = self.router.route(query)
        self.assertEqual(route.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertIn("Thể thao ICTU", route.entities.sports_entities)

        results = self.service.retrieve(query, intent="SPORTS_KNOWLEDGE", entity="Thể thao ICTU")
        self.assertGreater(len(results), 0)
        entry = next((e for e, _ in results if e.id == "TN-SPT-035"), None)
        self.assertIsNotNone(entry)
        self.assertIn("đội tuyển trường", entry.content)
        self.assertIn("CLB E-Sports", entry.content)
        self.assertIn("không phải các CLB thể thao chuyên nghiệp độc lập", entry.content)


if __name__ == "__main__":
    unittest.main()

