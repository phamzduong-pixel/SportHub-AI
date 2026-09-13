from unittest.mock import MagicMock
import pytest
from app.services.ai_domain_policy import ScopeClassification
from app.services.ai_intent_router import AssistantIntent, IntentRouter
from app.services.ai_assistant_service import AIAssistantService


class TestAIDomainBoundary:
    @pytest.fixture(autouse=True)
    def setup_service(self):
        self.mock_repo = MagicMock()
        self.service = AIAssistantService(self.mock_repo)
        self.router = IntentRouter()

    # --- A. MANDATORY OUT_OF_SCOPE QUERIES (12 Cases) ---
    @pytest.mark.parametrize("query", [
        "cách nấu ăn",
        "công thức làm bánh",
        "thời tiết hôm nay thế nào?",
        "giải giúp bài toán",
        "viết code Python",
        "dịch giúp đoạn này sang tiếng Anh",
        "viết CV xin việc",
        "tin tức hôm nay có gì mới?",
        "Bitcoin hôm nay giá bao nhiêu?",
        "phim nào đang hot ngoài rạp?",
        "tư vấn tình cảm giúp tôi",
        "cách sửa máy tính",
    ])
    def test_mandatory_out_of_scope_rejection(self, query):
        route = self.router.route(query)
        assert route.intent == AssistantIntent.OUT_OF_SCOPE
        assert route.confidence >= 0.85

        res = self.service.ask(query)
        assert res["status"] == "OUT_OF_SCOPE"
        assert res["classification"] == ScopeClassification.OUT_OF_SCOPE.value
        assert res["intent"] == "OUT_OF_SCOPE"
        assert not res["needs_clarification"]
        assert res["suggestions"] == []
        assert "trợ lý chuyên biệt của SportHub AI" in res["reply"]
        assert "Tìm kiếm sân và kiểm tra lịch trống" in res["reply"]

    def test_out_of_scope_never_queries_repository(self):
        self.service.ask("Cách làm bánh pizza hải sản?")
        self.mock_repo.query_available_courts.assert_not_called()
        self.mock_repo.recommend_slots.assert_not_called()
        self.mock_repo.field_context.assert_not_called()

    # --- B. MANDATORY IN_SCOPE NATURAL QUERIES (10 Cases) ---
    @pytest.mark.parametrize("query, expected_intents", [
        ("tối nay có sân cầu lông nào không?", [AssistantIntent.CHECK_AVAILABILITY, AssistantIntent.SEARCH_VENUE]),
        ("kiếm giúp tôi sân bóng gần đây", [AssistantIntent.SEARCH_VENUE, AssistantIntent.CHECK_AVAILABILITY]),
        ("có sân nào rẻ không?", [AssistantIntent.SEARCH_VENUE, AssistantIntent.RECOMMEND_VENUE]),
        ("mình muốn tìm sân cầu lông khoảng 100k", [AssistantIntent.SEARCH_VENUE, AssistantIntent.CHECK_AVAILABILITY]),
        ("mai chơi tennis được không?", [AssistantIntent.CHECK_AVAILABILITY, AssistantIntent.SEARCH_VENUE]),
        ("cho tôi vài sân ngon", [AssistantIntent.RECOMMEND_VENUE, AssistantIntent.SEARCH_VENUE]),
        ("còn sân nào trống buổi tối?", [AssistantIntent.CHECK_AVAILABILITY, AssistantIntent.SEARCH_VENUE]),
        ("muốn thuê sân", [AssistantIntent.SEARCH_VENUE, AssistantIntent.CHECK_AVAILABILITY]),
        ("tìm sân gần Đại học Quốc gia", [AssistantIntent.SEARCH_VENUE, AssistantIntent.CHECK_AVAILABILITY]),
        ("sân bóng rổ nào có mái che?", [AssistantIntent.SEARCH_VENUE, AssistantIntent.CHECK_AVAILABILITY]),
    ])
    def test_mandatory_in_scope_acceptance(self, query, expected_intents):
        route = self.router.route(query)
        assert route.intent != AssistantIntent.OUT_OF_SCOPE, f"Query '{query}' was incorrectly classified as OUT_OF_SCOPE"
        assert route.intent in expected_intents

    # --- C. COMBINED QUERIES ---
    def test_combined_query_without_search_entities(self):
        query = "Trong lúc chờ sân thì chỉ tôi cách nấu gà?"
        route = self.router.route(query)
        assert route.intent == AssistantIntent.OUT_OF_SCOPE
        assert route.is_combined_out_of_scope

        res = self.service.ask(query)
        assert res["status"] == "OUT_OF_SCOPE"
        assert res["classification"] == ScopeClassification.OUT_OF_SCOPE.value
        assert "chỉ có thể hỗ trợ bạn tìm sân" in res["reply"]
        assert "Bạn có muốn tôi kiểm tra lại lịch sân hoặc gợi ý sân gần bạn không?" in res["reply"]

    def test_combined_query_with_venue_search_intent(self):
        query = "Tìm sân cầu lông tối nay ở Cầu Giấy và thời tiết hôm nay thế nào?"
        route = self.router.route(query)
        assert route.intent in (AssistantIntent.CHECK_AVAILABILITY, AssistantIntent.SEARCH_VENUE)
        assert route.is_combined_out_of_scope
        assert route.entities.sport_type == "cầu lông"

        self.mock_repo.query_available_courts.return_value = []
        res = self.service.ask(query)
        assert res["classification"] == ScopeClassification.IN_SCOPE.value
        assert "Lưu ý: SportHub AI chỉ hỗ trợ các dịch vụ sân thể thao" in res["reply"]

    # --- D. AMBIGUOUS / UNCLEAR QUERIES ---
    def test_ambiguous_queries_prompt_for_clarification(self):
        # "tôi muốn đặt"
        res1 = self.service.ask("tôi muốn đặt")
        assert res1["status"] == "NEED_MORE_DATA"
        assert res1["classification"] == ScopeClassification.UNCLEAR.value
        assert res1["needs_clarification"]
        assert "Bạn muốn đặt sân môn thể thao nào và ở khu vực nào ạ?" in res1["reply"]

        # "giá thế nào"
        res2 = self.service.ask("giá thế nào")
        assert res2["status"] == "NEED_MORE_DATA"
        assert res2["classification"] == ScopeClassification.UNCLEAR.value
        assert res2["needs_clarification"]
        assert "Bạn muốn tham khảo giá của sân nào hoặc môn thể thao nào?" in res2["reply"]

        # "còn không"
        res3 = self.service.ask("còn không")
        assert res3["status"] == "NEED_MORE_DATA"
        assert res3["classification"] == ScopeClassification.UNCLEAR.value
        assert res3["needs_clarification"]
        assert "Bạn muốn kiểm tra lịch trống của sân nào và vào thời gian nào?" in res3["reply"]

    # --- E. GREETINGS ---
    @pytest.mark.parametrize("greeting", [
        "chào bạn",
        "hello",
        "hi",
        "alo",
        "chào trợ lý",
    ])
    def test_greetings_friendly_and_domain_focused(self, greeting):
        route = self.router.route(greeting)
        assert route.intent == AssistantIntent.GREETING
        assert route.confidence >= 0.9

        res = self.service.ask(greeting)
        assert res["status"] == "OK"
        assert "Xin chào! Tôi là trợ lý chuyên biệt của SportHub AI." in res["reply"]
        assert "Bạn đang quan tâm đến môn thể thao nào?" in res["reply"]
