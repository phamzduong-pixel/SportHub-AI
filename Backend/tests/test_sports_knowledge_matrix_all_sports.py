"""Comprehensive Sports Knowledge Retrieval Matrix Test across all 6 supported sports.

Tests each query group:
- rules / scoring
- court / equipment
- athlete
- team / club
- competition
- achievement / history
- Vietnam / local
- follow-up
- entity switching
- year/time-specific query
- source attribution
"""

import unittest
from app.repositories.knowledge_repository import get_knowledge_repository, reset_shared_knowledge_repository
from app.services.knowledge_service import get_knowledge_service, reset_shared_knowledge_service
from app.services.ai_intent_router import IntentRouter, AssistantIntent
from app.services.ai_sports_resolver import SportsContextResolver
from app.services.ai_assistant_service import AIAssistantService, AIRepository
from app.schemas.ai import AssistantMode


class SportsKnowledgeMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reset_shared_knowledge_service()
        reset_shared_knowledge_repository()
        cls.router = IntentRouter()
        cls.assistant = AIAssistantService(AIRepository(None))

    def setUp(self):
        reset_shared_knowledge_service()
        reset_shared_knowledge_repository()

    # ─────────────────────────────────────────────────────────────────────────
    # 1. TENNIS TESTS
    # ─────────────────────────────────────────────────────────────────────────
    def test_tennis_rules_scoring(self):
        query = "Cách tính điểm trong một ván đấu tennis và loạt tie-break như thế nào?"
        res = self.assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertIn("15", res["reply"])
        self.assertIn("40", res["reply"])
        self.assertTrue("ITF" in res["reply"] or "https://" in res["reply"] or "nguồn" in res["reply"].lower())

    def test_tennis_court_equipment(self):
        query = "Kích thước sân tennis tiêu chuẩn đánh đơn và đánh đôi là bao nhiêu?"
        res = self.assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertIn("23.77", res["reply"])
        self.assertIn("8.23", res["reply"])
        self.assertTrue("ITF" in res["reply"] or "itftennis.com" in res["reply"])

    def test_tennis_athlete_djokovic(self):
        query = "Novak Djokovic sinh năm bao nhiêu và đến từ quốc gia nào?"
        res = self.assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertIn("1987", res["reply"])
        self.assertIn("Serbia", res["reply"])
        self.assertTrue("ATP" in res["reply"] or "atptour.com" in res["reply"])

    def test_tennis_competition_grand_slam(self):
        query = "Có bao nhiêu giải Grand Slam trong môn tennis và gồm những giải nào?"
        res = self.assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertTrue("Wimbledon" in res["reply"] or "Australian Open" in res["reply"] or "Roland Garros" in res["reply"])

    def test_tennis_vietnam_local(self):
        query = "Tay vợt Lý Hoàng Nam của Việt Nam có những thành tích nổi bật nào?"
        res = self.assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertTrue("Wimbledon" in res["reply"] or "SEA Games" in res["reply"] or "VTF" in res["reply"])

    # ─────────────────────────────────────────────────────────────────────────
    # 2. PICKLEBALL TESTS
    # ─────────────────────────────────────────────────────────────────────────
    def test_pickleball_rules_kitchen(self):
        query = "Vùng Non-Volley Zone hay Kitchen trong pickleball có quy định như thế nào?"
        res = self.assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertTrue("7 feet" in res["reply"] or "2.13" in res["reply"] or "volley" in res["reply"].lower() or "kitchen" in res["reply"].lower())
        self.assertTrue("USA Pickleball" in res["reply"] or "usapickleball.org" in res["reply"])

    def test_pickleball_court_equipment(self):
        query = "Kích thước sân pickleball tiêu chuẩn và chiều cao lưới là bao nhiêu?"
        res = self.assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertTrue("13.41" in res["reply"] or "44 feet" in res["reply"] or "6.10" in res["reply"])
        self.assertTrue("34 inch" in res["reply"] or "36 inch" in res["reply"] or "0.86" in res["reply"] or "0.91" in res["reply"])

    def test_pickleball_athlete_ben_johns(self):
        query = "Ben Johns là ai và có thành tích gì trong môn pickleball?"
        res = self.assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertTrue("Mỹ" in res["reply"] or "PPA" in res["reply"] or "Triple Crown" in res["reply"])
        self.assertTrue("ppatour.com" in res["reply"] or "PPA Tour" in res["reply"])

    def test_pickleball_vietnam_quang_duong(self):
        query = "VĐV Quang Dương trong môn pickleball là ai và có gì nổi bật?"
        res = self.assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertTrue("2006" in res["reply"] or "gốc Việt" in res["reply"] or "PPA" in res["reply"])

    # ─────────────────────────────────────────────────────────────────────────
    # 3. BASKETBALL TESTS
    # ─────────────────────────────────────────────────────────────────────────
    def test_basketball_rules_shotclock(self):
        query = "Trong luật bóng rổ FIBA, luật 24 giây và 8 giây quy định thế nào?"
        res = self.assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertIn("24", res["reply"])
        self.assertIn("8", res["reply"])
        self.assertTrue("FIBA" in res["reply"] or "fiba.basketball" in res["reply"])

    def test_basketball_court_dimensions(self):
        query = "Kích thước sân bóng rổ tiêu chuẩn FIBA và chiều cao vành rổ là bao nhiêu?"
        res = self.assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertIn("28m", res["reply"].replace(" ", ""))
        self.assertIn("15m", res["reply"].replace(" ", ""))
        self.assertIn("3.05", res["reply"])

    def test_basketball_athlete_lebron_curry(self):
        query = "LeBron James sinh năm bao nhiêu và hiện thi đấu cho đội nào?"
        res = self.assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertIn("1984", res["reply"])
        self.assertIn("Los Angeles Lakers", res["reply"])
        self.assertTrue("NBA" in res["reply"] or "nba.com" in res["reply"])

    def test_basketball_competition_nba(self):
        query = "Giải bóng rổ NBA gồm bao nhiêu đội và thể thức thi đấu như thế nào?"
        res = self.assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertIn("30", res["reply"])
        self.assertTrue("Eastern" in res["reply"] or "Western" in res["reply"] or "NBA Finals" in res["reply"])

    # ─────────────────────────────────────────────────────────────────────────
    # 4. VOLLEYBALL TESTS
    # ─────────────────────────────────────────────────────────────────────────
    def test_volleyball_rules_libero(self):
        query = "Vị trí Libero trong bóng chuyền có nhiệm vụ và những hạn chế gì?"
        res = self.assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertTrue("phòng thủ" in res["reply"].lower() or "chắn bóng" in res["reply"].lower() or "tấn công" in res["reply"].lower())
        self.assertTrue("FIVB" in res["reply"] or "fivb.com" in res["reply"])

    def test_volleyball_court_net_height(self):
        query = "Kích thước sân bóng chuyền và chiều cao lưới nam nữ chuẩn FIVB là bao nhiêu?"
        res = self.assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertIn("18m", res["reply"].replace(" ", ""))
        self.assertIn("9m", res["reply"].replace(" ", ""))
        self.assertIn("2.43", res["reply"])
        self.assertIn("2.24", res["reply"])

    def test_volleyball_vietnam_athletes(self):
        query = "Nguyễn Thị Bích Tuyền sinh năm bao nhiêu và thi đấu cho CLB bóng chuyền nào?"
        res = self.assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertIn("2000", res["reply"])
        self.assertTrue("LPBank Ninh Bình" in res["reply"] or "Ninh Bình" in res["reply"])

    def test_volleyball_thanh_thuy(self):
        query = "Trần Thị Thanh Thúy sinh năm bao nhiêu và quê ở đâu?"
        res = self.assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertIn("1997", res["reply"])
        self.assertTrue("Bình Dương" in res["reply"] or "Việt Nam" in res["reply"])

    # ─────────────────────────────────────────────────────────────────────────
    # 5. MULTI-TURN, ENTITY SWITCHING & FOLLOW-UP TESTS
    # ─────────────────────────────────────────────────────────────────────────
    def test_followup_and_entity_switching_across_sports(self):
        # Step 1: Basketball LeBron
        r1 = self.assistant.ask("LeBron James sinh năm bao nhiêu?", assistant_mode=AssistantMode.NATURAL)
        self.assertIn("1984", r1["reply"])

        # Step 2: Followup pronoun for LeBron
        ctx1 = {"sports_entity": "LeBron James", "sport_type": "bóng rổ", "last_intent": "SPORTS_KNOWLEDGE"}
        r2 = self.assistant.ask("Anh ấy đang thi đấu cho đội nào?", context=ctx1, assistant_mode=AssistantMode.NATURAL)
        self.assertIn("Los Angeles Lakers", r2["reply"])

        # Step 3: Switch to Curry
        ctx2 = {"sports_entity": "LeBron James", "sport_type": "bóng rổ", "last_intent": "SPORTS_KNOWLEDGE"}
        r3 = self.assistant.ask("Còn Stephen Curry thì sao?", context=ctx2, assistant_mode=AssistantMode.NATURAL)
        self.assertTrue("Curry" in r3["reply"] or "Golden State Warriors" in r3["reply"])

        # Step 4: Switch to Tennis Djokovic
        ctx3 = {"sports_entity": "Stephen Curry", "sport_type": "bóng rổ", "last_intent": "SPORTS_KNOWLEDGE"}
        r4 = self.assistant.ask("Thế còn Novak Djokovic trong môn tennis?", context=ctx3, assistant_mode=AssistantMode.NATURAL)
        self.assertIn("Djokovic", r4["reply"])
        self.assertIn("Serbia", r4["reply"])

    def test_insufficient_evidence_limitation(self):
        query = "VĐV John Doe 123456 vô địch giải đấu nào năm 1920?"
        res = self.assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
        self.assertEqual(res["status"], "OK")
        self.assertTrue("chưa có thông tin" in res["reply"] or "chưa có dữ liệu" in res["reply"] or "không có thông tin" in res["reply"])


if __name__ == "__main__":
    unittest.main()
