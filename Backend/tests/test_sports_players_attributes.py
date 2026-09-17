import unittest
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.knowledge_retriever import KnowledgeRetriever
from app.services.knowledge_service import KnowledgeService
from app.services.ai_intent_router import IntentRouter, AssistantIntent
from app.services.ai_assistant_service import AIAssistantService, AIRepository


class SportsPlayersAttributesTests(unittest.TestCase):
    def setUp(self):
        self.repo = KnowledgeRepository()
        self.retriever = KnowledgeRetriever(self.repo)
        self.service = KnowledgeService(self.repo, self.retriever)
        self.router = IntentRouter()

    # ----------------------------------------------------
    # 1. SPECIFIC TOPICS RETRIEVAL (birth_date, birth_place, current_club, career, status, achievements)
    # ----------------------------------------------------
    def test_messi_birth_date_topic(self):
        results = self.service.retrieve("Messi sinh ngày nào?", intent="SPORTS_KNOWLEDGE", entity="Lionel Messi")
        self.assertGreater(len(results), 0)
        top_entry, score = results[0]
        self.assertEqual(top_entry.entity, "Lionel Messi")
        self.assertEqual(top_entry.topic, "birth_date")
        self.assertIn("24 tháng 6 năm 1987", top_entry.answer)
        self.assertEqual(top_entry.source_name, "FIFA")

    def test_messi_birth_place_topic(self):
        results = self.service.retrieve("Messi sinh ở đâu?", intent="SPORTS_KNOWLEDGE", entity="Lionel Messi")
        self.assertGreater(len(results), 0)
        top_entry, score = results[0]
        self.assertEqual(top_entry.entity, "Lionel Messi")
        self.assertEqual(top_entry.topic, "birth_place")
        self.assertIn("Rosario", top_entry.answer)

    def test_messi_current_club_topic(self):
        results = self.service.retrieve("Messi hiện thi đấu cho CLB nào?", intent="SPORTS_KNOWLEDGE", entity="Lionel Messi")
        self.assertGreater(len(results), 0)
        top_entry, score = results[0]
        self.assertEqual(top_entry.entity, "Lionel Messi")
        self.assertEqual(top_entry.topic, "current_club")
        self.assertIn("Inter Miami CF", top_entry.answer)

    def test_messi_career_topic(self):
        results = self.service.retrieve("Quá trình thi đấu của Messi?", intent="SPORTS_KNOWLEDGE", entity="Lionel Messi")
        self.assertGreater(len(results), 0)
        top_entry, score = results[0]
        self.assertEqual(top_entry.entity, "Lionel Messi")
        self.assertEqual(top_entry.topic, "career")
        self.assertIn("Barcelona", top_entry.answer)

    def test_messi_status_topic(self):
        results = self.service.retrieve("Messi đã giải nghệ chưa?", intent="SPORTS_KNOWLEDGE", entity="Lionel Messi")
        self.assertGreater(len(results), 0)
        top_entry, score = results[0]
        self.assertEqual(top_entry.entity, "Lionel Messi")
        self.assertEqual(top_entry.topic, "status")
        self.assertIn("chưa giải nghệ", top_entry.answer)

    def test_messi_achievements_topic(self):
        results = self.service.retrieve("Thành tích nổi bật của Messi?", intent="SPORTS_KNOWLEDGE", entity="Lionel Messi")
        self.assertGreater(len(results), 0)
        top_entry, score = results[0]
        self.assertEqual(top_entry.entity, "Lionel Messi")
        self.assertEqual(top_entry.topic, "achievements")
        self.assertIn("8 Quả bóng vàng", top_entry.answer)

    # ----------------------------------------------------
    # 2. OTHER MVP PLAYERS ATTRIBUTES (Ronaldo, Quang Hải, Tiến Linh, Hoàng Đức, Thùy Linh, Tiến Minh, Axelsen)
    # ----------------------------------------------------
    def test_ronaldo_attributes(self):
        res_bd = self.service.retrieve("Ronaldo sinh ngày nào?", intent="SPORTS_KNOWLEDGE", entity="Cristiano Ronaldo")
        self.assertGreater(len(res_bd), 0)
        self.assertIn("5 tháng 2 năm 1985", res_bd[0][0].answer)

        res_club = self.service.retrieve("Ronaldo đang chơi cho đội nào?", intent="SPORTS_KNOWLEDGE", entity="Cristiano Ronaldo")
        self.assertGreater(len(res_club), 0)
        self.assertIn("Al-Nassr", res_club[0][0].answer)

    def test_quang_hai_attributes(self):
        res_club = self.service.retrieve("Quang Hải hiện thi đấu cho CLB nào?", intent="SPORTS_KNOWLEDGE", entity="Nguyễn Quang Hải")
        self.assertGreater(len(res_club), 0)
        self.assertIn("Công An Hà Nội", res_club[0][0].answer)

    def test_tien_linh_attributes(self):
        res_bd = self.service.retrieve("Tiến Linh sinh ngày nào?", intent="SPORTS_KNOWLEDGE", entity="Nguyễn Tiến Linh")
        self.assertGreater(len(res_bd), 0)
        self.assertIn("20 tháng 10 năm 1997", res_bd[0][0].answer)

    def test_hoang_duc_attributes(self):
        res_club = self.service.retrieve("Hoàng Đức hiện đang chơi cho CLB nào?", intent="SPORTS_KNOWLEDGE", entity="Nguyễn Hoàng Đức")
        self.assertGreater(len(res_club), 0)
        self.assertIn("Phù Đổng Ninh Bình", res_club[0][0].answer)

    def test_thuy_linh_badminton(self):
        res_bd = self.service.retrieve("Thùy Linh sinh ngày nào?", intent="SPORTS_KNOWLEDGE", sport="cầu lông", entity="Nguyễn Thùy Linh")
        self.assertGreater(len(res_bd), 0)
        self.assertIn("19 tháng 5 năm 1997", res_bd[0][0].answer)

    def test_tien_minh_badminton(self):
        res_car = self.service.retrieve("Quá trình thi đấu của Tiến Minh?", intent="SPORTS_KNOWLEDGE", sport="cầu lông", entity="Nguyễn Tiến Minh")
        self.assertGreater(len(res_car), 0)
        self.assertIn("4 kỳ Olympic", res_car[0][0].answer)

    def test_axelsen_badminton(self):
        res_bp = self.service.retrieve("Axelsen sinh ở đâu?", intent="SPORTS_KNOWLEDGE", sport="cầu lông", entity="Viktor Axelsen")
        self.assertGreater(len(res_bp), 0)
        self.assertIn("Odense, Đan Mạch", res_bp[0][0].answer)

    # ----------------------------------------------------
    # 3. MULTI-TURN FOLLOW-UP & PRONOUN RESOLUTION
    # ----------------------------------------------------
    def test_multiturn_player_attribute_followup(self):
        ai_service = AIAssistantService(AIRepository(None))

        # Turn 1
        r1 = ai_service.ask("Messi là ai?")
        self.assertIn("Lionel Messi", r1['reply'])

        context_t1 = r1['understood']

        # Turn 2: "Anh ấy sinh ngày nào?"
        r2 = ai_service.ask("Anh ấy sinh ngày nào?", context=context_t1)
        self.assertIn("24 tháng 6 năm 1987", r2['reply'])
        self.assertEqual(r2['understood']['sports_entity'], "Lionel Messi")

        context_t2 = r2['understood']

        # Turn 3: "Anh ấy đang chơi cho đội nào?"
        r3 = ai_service.ask("Anh ấy đang chơi cho đội nào?", context=context_t2)
        self.assertIn("Inter Miami CF", r3['reply'])
        self.assertEqual(r3['understood']['sports_entity'], "Lionel Messi")

    # ----------------------------------------------------
    # 4. ENTITY SWITCHING
    # ----------------------------------------------------
    def test_entity_switching_messi_to_ronaldo(self):
        ai_service = AIAssistantService(AIRepository(None))

        # Turn 1: "Messi sinh ngày nào?"
        r1 = ai_service.ask("Messi sinh ngày nào?")
        self.assertIn("24 tháng 6 năm 1987", r1['reply'])
        context_t1 = r1['understood']

        # Turn 2: "Còn Ronaldo?" -> switches entity to Cristiano Ronaldo
        r2 = ai_service.ask("Còn Ronaldo?", context=context_t1)
        self.assertIn("Cristiano Ronaldo", r2['reply'])
        self.assertEqual(r2['understood']['sports_entity'], "Cristiano Ronaldo")

        context_t2 = r2['understood']

        # Turn 3: "Anh ấy sinh ngày nào?" -> uses Cristiano Ronaldo
        r3 = ai_service.ask("Anh ấy sinh ngày nào?", context=context_t2)
        self.assertIn("5 tháng 2 năm 1985", r3['reply'])
        self.assertEqual(r3['understood']['sports_entity'], "Cristiano Ronaldo")

    # ----------------------------------------------------
    # 5. NO-EVIDENCE SAFE FALLBACK
    # ----------------------------------------------------
    def test_unanswerable_attribute_safe_fallback(self):
        ai_service = AIAssistantService(AIRepository(None))

        # Query about an unverified detail
        r = ai_service.ask("Messi bị mấy thẻ vàng năm 2012?")
        self.assertIn("chưa có thông tin kiểm chứng", r['reply'])
        self.assertEqual(r['status'], 'OK')
        self.assertEqual(r['understood']['sports_entity'], "Lionel Messi")

    # ----------------------------------------------------
    # 6. MULTI-ATTRIBUTE RAG TESTS
    # ----------------------------------------------------
    def test_quang_hai_multi_attribute(self):
        ai_service = AIAssistantService(AIRepository(None))
        q = "Quang Hải là ai, sinh vào ngày nào, quê ở đâu, đang đá cho câu lạc bộ nào?"
        r = ai_service.ask(q)
        reply = r['reply']
        self.assertIn("xuất sắc nhất", reply)
        self.assertIn("12 tháng 4 năm 1997", reply)
        self.assertIn("Đông Anh", reply)
        self.assertIn("Công An Hà Nội", reply)

    def test_messi_multi_attribute(self):
        ai_service = AIAssistantService(AIRepository(None))
        q = "Messi sinh ngày nào và đang thi đấu cho CLB nào?"
        r = ai_service.ask(q)
        reply = r['reply']
        self.assertIn("24 tháng 6 năm 1987", reply)
        self.assertIn("Inter Miami CF", reply)

    def test_ronaldo_multi_attribute(self):
        ai_service = AIAssistantService(AIRepository(None))
        q = "Ronaldo là ai và hiện đang thi đấu ở đâu?"
        r = ai_service.ask(q)
        reply = r['reply']
        self.assertIn("tiền đạo huyền thoại", reply)
        self.assertIn("Al-Nassr", reply)

    def test_missing_attribute_reporting(self):
        ai_service = AIAssistantService(AIRepository(None))
        q = "Quang Hải là ai và chiều cao bao nhiêu?"
        r = ai_service.ask(q)
        reply = r['reply']
        self.assertIn("xuất sắc nhất", reply)
        self.assertIn("chưa có thông tin kiểm chứng về chiều cao", reply)


if __name__ == '__main__':
    unittest.main()

