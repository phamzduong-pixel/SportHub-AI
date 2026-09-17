import unittest
from datetime import date
from unittest.mock import MagicMock

from app.services.ai_intent_router import (
    AssistantIntent,
    BUSINESS_INTENTS,
    IntentRouter,
    is_business_intent,
    is_supported_sport,
    SUPPORTED_SPORTS,
)
from app.services.ai_assistant_service import AIAssistantService, ScopeClassification
from app.repositories.ai_repository import AIRepository


class AIWebFlowSeparationTests(unittest.TestCase):
    """
    Focused test suite for AI-WEB-01:
    Separating Business Flow from Sports Knowledge Flow with deterministic sports scoping.
    """

    def setUp(self):
        self.router = IntentRouter()
        self.mock_repo = MagicMock(spec=AIRepository)
        self.mock_repo.db = MagicMock()
        self.service = AIAssistantService(repository=self.mock_repo)

    # ----------------------------------------------------
    # 1. Deterministic Supported Sports Scope Definition
    # ----------------------------------------------------
    def test_supported_sports_configuration(self):
        expected_sports = {'bóng đá', 'cầu lông', 'pickleball', 'tennis', 'bóng rổ', 'bóng chuyền'}
        self.assertEqual(SUPPORTED_SPORTS, expected_sports)

        for sp in ('football', 'bóng đá', 'badminton', 'cầu lông', 'pickleball', 'tennis', 'quần vợt', 'basketball', 'bóng rổ', 'volleyball', 'bóng chuyền'):
            self.assertTrue(is_supported_sport(sp), f"Sport '{sp}' should be recognized as supported")

        for unsp in ('golf', 'bơi lội', 'bi-a', 'bida', 'boxing', 'esports', 'bóng chày', 'rugby'):
            self.assertFalse(is_supported_sport(unsp), f"Sport '{unsp}' should NOT be recognized as supported")

    # ----------------------------------------------------
    # 2. Business Intent Bypasses Sports Knowledge
    # ----------------------------------------------------
    def test_business_intents_bypass_sports_knowledge(self):
        business_queries = [
            ("Tìm sân bóng đá ở Cầu Giấy", AssistantIntent.SEARCH_VENUE),
            ("Gợi ý sân cầu lông giá tốt ở Hà Nội", AssistantIntent.RECOMMEND_VENUE),
            ("Sân tennis còn trống tối nay 19h không?", AssistantIntent.CHECK_AVAILABILITY),
            ("Gợi ý khung giờ đá bóng rẻ hơn", AssistantIntent.RECOMMEND_SLOT),
            ("Địa chỉ sân bóng và bảng giá chi tiết", AssistantIntent.GET_VENUE_DETAIL),
            ("Tôi muốn đặt sân này", AssistantIntent.CREATE_BOOKING),
            ("Kiểm tra mã đặt sân SP12345", AssistantIntent.GET_BOOKING),
            ("Tôi muốn hủy lịch đặt sân", AssistantIntent.CANCEL_BOOKING),
            ("Đổi giờ đặt sân sang ngày mai", AssistantIntent.RESCHEDULE_BOOKING),
            ("Chính sách hoàn tiền khi hủy cọc", AssistantIntent.PAYMENT_SUPPORT),
            ("Đổi mật khẩu tài khoản", AssistantIntent.ACCOUNT_SUPPORT),
            ("Quy trình đăng ký làm chủ sân đối tác", AssistantIntent.PARTNER_APPLICATION_SUPPORT),
            ("Xem phân tích công suất giờ cao điểm", AssistantIntent.OCCUPANCY_INSIGHT),
            ("Ở sân có cho thuê vợt cầu lông không?", AssistantIntent.GET_PRODUCTS),
            ("Hướng dẫn cách tìm và đặt sân trên SportHub", AssistantIntent.SYSTEM_GUIDE),
        ]

        for query, expected_intent in business_queries:
            route = self.router.route(query)
            self.assertEqual(route.intent, expected_intent, f"Query '{query}' should route to {expected_intent}")
            self.assertTrue(is_business_intent(route.intent), f"Intent {route.intent} must be recognized as a business intent")
            self.assertNotEqual(route.intent, AssistantIntent.SPORTS_KNOWLEDGE)

    # ----------------------------------------------------
    # 3. Supported Sport Questions Route to SPORTS_KNOWLEDGE
    # ----------------------------------------------------
    def test_supported_sports_route_to_sports_knowledge(self):
        supported_sports_queries = [
            # Football (Bóng đá)
            "Messi là ai?",
            "Lịch sử CLB bóng đá Thái Nguyên T&T",
            "Hà Nội FC là đội nào?",
            "Luật việt vị trong bóng đá",
            # Badminton (Cầu lông)
            "Luật tính điểm trong môn cầu lông",
            "Phong trào cầu lông ở Thái Nguyên như thế nào?",
            "Vận động viên Nguyễn Thùy Linh là ai?",
            # Pickleball
            "Kích thước sân pickleball tiêu chuẩn là bao nhiêu?",
            "Trường ICTU có sân pickleball không?",
            # Tennis
            "Luật tie-break trong môn tennis là gì?",
            "Phong trào quần vợt ở Thái Nguyên thế nào?",
            # Basketball (Bóng rổ)
            "Saigon Heat thi đấu ở giải bóng rổ nào?",
            "Hanoi Buffaloes là đội bóng rổ nào?",
            "Luật ném bóng 3 điểm trong bóng rổ",
            # Volleyball (Bóng chuyền)
            "Chiều cao lưới bóng chuyền nam chuẩn quốc tế",
            "Đội tuyển bóng chuyền nam TP.HCM",
            # Multi-sport regional overviews
            "Ở Hà Nội có những môn thể thao nào?",
            "Ở Thái Nguyên ngoài bóng đá còn có môn gì?",
            "TP.HCM có những môn thể thao nào?",
        ]

        for query in supported_sports_queries:
            route = self.router.route(query)
            self.assertEqual(route.intent, AssistantIntent.SPORTS_KNOWLEDGE, f"Query '{query}' should route to SPORTS_KNOWLEDGE")

    # ----------------------------------------------------
    # 4. Unsupported Sports and Non-Sports Route to OUT_OF_SCOPE
    # ----------------------------------------------------
    def test_unsupported_and_non_sports_route_to_out_of_scope(self):
        out_of_scope_queries = [
            # Unsupported sports
            "Luật chơi môn golf là gì?",
            "Cách chơi bi-a 8 bóng thế nào?",
            "Kỷ lục bơi lội 100m thế giới là bao nhiêu?",
            "Võ thuật boxing có những hạng cân nào?",
            "Đội tuyển bóng chày vô địch thế giới",
            "Faker vô địch Liên Minh Huyền Thoại mấy lần?",
            "Giải đấu Valorant Champions tổ chức ở đâu?",
            # General non-sports questions
            "Python là ngôn ngữ lập trình gì?",
            "Hướng dẫn nấu món phở bò Hà Nội",
            "Thời tiết hôm nay ở Hà Nội như thế nào?",
            "Dân số TP.HCM hiện nay là bao nhiêu?",
            "Viết cho tôi một bài thơ tình",
            "Giá Bitcoin hôm nay bao nhiêu?",
        ]

        for query in out_of_scope_queries:
            route = self.router.route(query)
            self.assertEqual(route.intent, AssistantIntent.OUT_OF_SCOPE, f"Query '{query}' should route to OUT_OF_SCOPE")

    # ----------------------------------------------------
    # 5. Out of Scope Queries Never Trigger Database or Search
    # ----------------------------------------------------
    def test_out_of_scope_never_queries_database(self):
        query = "Thời tiết hôm nay ở Hà Nội thế nào?"
        res = self.service.ask(query)
        self.assertEqual(res["status"], "OUT_OF_SCOPE")
        self.assertEqual(res["classification"], ScopeClassification.OUT_OF_SCOPE.value)
        self.assertEqual(res["intent"], AssistantIntent.OUT_OF_SCOPE.value)
        self.mock_repo.search_venues.assert_not_called()
        self.mock_repo.count_venues.assert_not_called()

    # ----------------------------------------------------
    # 6. Existing Venue & Booking Queries Still Pass Unchanged
    # ----------------------------------------------------
    def test_existing_venue_and_booking_queries_pass(self):
        r1 = self.router.route("Tìm sân bóng đá 7 người ở Hà Nội ngày mai")
        self.assertEqual(r1.intent, AssistantIntent.SEARCH_VENUE)
        self.assertEqual(r1.entities.sport_type, "bóng đá")
        self.assertEqual(r1.entities.court_type, "7 người")
        self.assertEqual(r1.entities.location, "Hà Nội")

        r2 = self.router.route("Hủy sân mã SH9988")
        self.assertEqual(r2.intent, AssistantIntent.CANCEL_BOOKING)
        self.assertEqual(r2.entities.booking_code, "SH9988")

        r3 = self.router.route("Đăng ký làm chủ sân đối tác SportHub")
        self.assertEqual(r3.intent, AssistantIntent.PARTNER_APPLICATION_SUPPORT)


if __name__ == "__main__":
    unittest.main()
