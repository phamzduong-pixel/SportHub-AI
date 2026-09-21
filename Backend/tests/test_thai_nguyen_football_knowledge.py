import pytest
from app.services.ai_intent_router import IntentRouter, AssistantIntent
from app.services.ai_assistant_service import AIAssistantService, AIRepository


@pytest.fixture
def router():
    return IntentRouter()


@pytest.fixture
def assistant():
    return AIAssistantService(AIRepository(None))


def test_thai_nguyen_which_clubs(router, assistant):
    # Test 1: "Ở Thái Nguyên có những CLB bóng đá nào?"
    query = "Ở Thái Nguyên có những CLB bóng đá nào?"
    route = router.route(query)
    assert route.intent == AssistantIntent.SPORTS_KNOWLEDGE
    assert route.entities.sports_entity == "Bóng đá Thái Nguyên"

    res = assistant.ask(query)
    assert res["status"] == "OK"
    assert "FC Thái Nguyên" in res["reply"]
    assert "Thái Nguyên T&T" in res["reply"]
    assert "Báo Thanh Niên" in res["reply"] or "https://thanhnien.vn" in res["reply"]


def test_thai_nguyen_how_many_pro_clubs(router, assistant):
    # Test 2: "Ở Thái Nguyên có bao nhiêu CLB bóng đá chuyên nghiệp?"
    query = "Ở Thái Nguyên có bao nhiêu CLB bóng đá chuyên nghiệp?"
    route = router.route(query)
    assert route.intent == AssistantIntent.SPORTS_KNOWLEDGE

    res = assistant.ask(query)
    assert res["status"] == "OK"
    assert "FC Thái Nguyên" in res["reply"]
    assert "Thái Nguyên T&T" in res["reply"]
    assert "Báo và Phát thanh, truyền hình Thái Nguyên" in res["reply"] or "https://baothainguyen.vn" in res["reply"]


def test_thai_nguyen_how_many_clubs_scope(router, assistant):
    # Test: "Ở Thái Nguyên có bao nhiêu câu lạc bộ đá bóng?"
    query = "Ở Thái Nguyên có bao nhiêu câu lạc bộ đá bóng?"
    route = router.route(query)
    assert route.intent == AssistantIntent.SPORTS_KNOWLEDGE

    res = assistant.ask(query)
    assert res["status"] == "OK"
    assert "FC Thái Nguyên" in res["reply"]
    assert "Thái Nguyên T&T" in res["reply"]
    assert "phong trào" in res["reply"]


def test_thai_nguyen_men_club(router, assistant):
    # Test 3: "CLB bóng đá nam Thái Nguyên là đội nào?"
    query = "CLB bóng đá nam Thái Nguyên là đội nào?"
    route = router.route(query)
    assert route.intent == AssistantIntent.SPORTS_KNOWLEDGE
    assert route.entities.sports_entity == "Bóng đá nam Thái Nguyên"

    res = assistant.ask(query)
    assert res["status"] == "OK"
    assert "FC Thái Nguyên" in res["reply"] or "Câu lạc bộ Bóng đá Thái Nguyên" in res["reply"]
    assert "https://baothainguyen.vn" in res["reply"]


def test_thai_nguyen_tt_identity(router, assistant):
    # Test 4: "Thái Nguyên T&T là đội nào?"
    query = "Thái Nguyên T&T là đội nào?"
    route = router.route(query)
    assert route.intent == AssistantIntent.SPORTS_KNOWLEDGE
    assert route.entities.sports_entity == "Thái Nguyên T&T"

    res = assistant.ask(query)
    assert res["status"] == "OK"
    assert "bóng đá nữ" in res["reply"]
    assert "Thái Nguyên T&T" in res["reply"]
    assert "https://thanhnien.vn" in res["reply"] or "Báo Thanh Niên" in res["reply"]


def test_thai_nguyen_has_women_football(router, assistant):
    # Test 5: "Thái Nguyên có bóng đá nữ không?"
    query = "Thái Nguyên có bóng đá nữ không?"
    route = router.route(query)
    assert route.intent == AssistantIntent.SPORTS_KNOWLEDGE

    res = assistant.ask(query)
    assert res["status"] == "OK"
    assert "Thái Nguyên T&T" in res["reply"]
    assert "bóng đá nữ" in res["reply"]


def test_no_regression_multi_entity_messi_ronaldo(router, assistant):
    # Test 6: "Messi và Ronaldo là ai?" -> đảm bảo không regression với multi-entity
    query = "Messi và Ronaldo là ai?"
    route = router.route(query)
    assert route.intent == AssistantIntent.SPORTS_KNOWLEDGE
    assert route.entities.sports_entities == ["Lionel Messi", "Cristiano Ronaldo"]

    res = assistant.ask(query)
    assert res["status"] == "OK"
    assert "**Lionel Messi**:" in res["reply"]
    assert "**Cristiano Ronaldo**:" in res["reply"]


def test_no_regression_venue_search(router):
    # Test 7: Các câu hỏi sân bóng/booking hiện tại -> không regression
    query = "tìm sân bóng đá gần đây"
    route = router.route(query)
    assert route.intent == AssistantIntent.SEARCH_VENUE
    assert route.entities.sport_type == "bóng đá"
