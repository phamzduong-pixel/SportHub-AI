import pytest
from app.services.ai_intent_router import IntentRouter, AssistantIntent
from app.services.ai_assistant_service import AIAssistantService, AIRepository
from app.services.ai_domain_policy import ScopeClassification, generate_out_of_scope_redirect
from app.schemas.ai import AssistantMode


@pytest.fixture
def router():
    return IntentRouter()


@pytest.fixture
def assistant():
    return AIAssistantService(AIRepository(None))


def test_out_of_scope_food_redirect(router, assistant):
    # Case: "Thịt chó có ngon không?"
    query = "Thịt chó có ngon không?"
    route = router.route(query)
    assert route.intent == AssistantIntent.OUT_OF_SCOPE

    res = assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
    assert res["status"] == "OUT_OF_SCOPE"
    assert res["classification"] == ScopeClassification.OUT_OF_SCOPE
    assert "ẩm thực" in res["reply"] or "món ăn" in res["reply"]
    assert "SportHub" in res["reply"] or "sân" in res["reply"]


def test_out_of_scope_technical_repair_redirect(router, assistant):
    # Case: "Cách sửa xe máy?"
    query = "Cách sửa xe máy?"
    route = router.route(query)
    assert route.intent == AssistantIntent.OUT_OF_SCOPE

    res = assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
    assert res["status"] == "OUT_OF_SCOPE"
    assert res["classification"] == ScopeClassification.OUT_OF_SCOPE
    assert "sửa chữa" in res["reply"] or "kỹ thuật" in res["reply"]
    assert "sân thể thao" in res["reply"] or "SportHub" in res["reply"]


def test_out_of_scope_finance_stock_redirect(router, assistant):
    # Case: "Viết cho tôi một bài về chứng khoán?"
    query = "Viết cho tôi một bài về chứng khoán?"
    route = router.route(query)
    assert route.intent == AssistantIntent.OUT_OF_SCOPE

    res = assistant.ask(query, assistant_mode=AssistantMode.NATURAL)
    assert res["status"] == "OUT_OF_SCOPE"
    assert res["classification"] == ScopeClassification.OUT_OF_SCOPE
    assert "tài chính" in res["reply"] or "chứng khoán" in res["reply"]
    assert "SportHub" in res["reply"] or "sân" in res["reply"]


def test_out_of_scope_non_repetitive_redirects(assistant):
    # Ensure food, repair, and finance queries receive customized natural redirects
    res_food = assistant.ask("Thịt chó có ngon không?", assistant_mode=AssistantMode.NATURAL)
    res_tech = assistant.ask("Cách sửa xe máy?", assistant_mode=AssistantMode.NATURAL)
    res_fin = assistant.ask("Viết cho tôi một bài về chứng khoán?", assistant_mode=AssistantMode.NATURAL)

    assert res_food["reply"] != res_tech["reply"]
    assert res_tech["reply"] != res_fin["reply"]


def test_transition_sports_knowledge_to_business(router, assistant):
    # Turn 1: Sports knowledge inquiry
    res1 = assistant.ask("Ronaldo hiện đang thi đấu cho câu lạc bộ nào?", assistant_mode=AssistantMode.NATURAL)
    assert res1["status"] == "OK"
    assert "Al-Nassr" in res1["reply"]

    # Turn 2: User switches to SportHub Business (venue search)
    turn2_query = "Tìm sân bóng đá gần đây"
    route2 = router.route(turn2_query, context={"sports_entity": "Cristiano Ronaldo", "sport_type": "bóng đá"})
    assert route2.intent == AssistantIntent.SEARCH_VENUE
    assert route2.entities.sport_type == "bóng đá"


def test_transition_business_to_sports_knowledge(router, assistant):
    # Turn 1: User searching for badminton courts
    turn1_context = {"sport_type": "cầu lông", "location": "Cầu Giấy", "last_intent": "SEARCH_VENUE"}
    
    # Turn 2: User asks a sports knowledge question
    turn2_query = "Nguyễn Thùy Linh sinh năm bao nhiêu?"
    route2 = router.route(turn2_query, context=turn1_context)
    assert route2.intent == AssistantIntent.SPORTS_KNOWLEDGE
    assert route2.entities.sports_entity == "Nguyễn Thùy Linh"

    res2 = assistant.ask(turn2_query, context=turn1_context, assistant_mode=AssistantMode.NATURAL)
    assert res2["status"] == "OK"
    assert "1997" in res2["reply"]
    assert "Nguồn:" in res2["reply"] or "nguồn" in res2["reply"].lower()


def test_out_of_scope_middle_conversation_and_return(router, assistant):
    # Turn 1: Business search for tennis
    turn1_context = {"sport_type": "tennis", "location": "Thanh Xuân", "last_intent": "SEARCH_VENUE"}

    # Turn 2: Out of scope question
    turn2_query = "Thịt chó có ngon không?"
    res2 = assistant.ask(turn2_query, context=turn1_context, assistant_mode=AssistantMode.NATURAL)
    assert res2["status"] == "OUT_OF_SCOPE"
    assert "tennis" in res2["reply"]  # Context-aware redirect mentions tennis!

    # Turn 3: User returns to previous search
    turn3_query = "Quay lại tìm sân lúc nãy"
    route3 = router.route(turn3_query, context=turn1_context)
    assert route3.intent == AssistantIntent.SEARCH_VENUE
    assert route3.entities.sport_type == "tennis"
    assert route3.entities.location == "Thanh Xuân"


def test_pronoun_and_entity_followup_knowledge(router, assistant):
    # Turn 1: Identity of Thai Nguyen T&T
    turn1_query = "Thái Nguyên T&T là đội nào?"
    res1 = assistant.ask(turn1_query, assistant_mode=AssistantMode.NATURAL)
    assert res1["status"] == "OK"
    assert "bóng đá nữ" in res1["reply"]

    # Turn 2: Followup pronoun question
    turn2_query = "Đội này có những cầu thủ nào nổi bật?"
    route2 = router.route(turn2_query, context={"sports_entity": "Thái Nguyên T&T", "active_entity": "Thái Nguyên T&T", "last_intent": "SPORTS_KNOWLEDGE"})
    assert route2.intent == AssistantIntent.SPORTS_KNOWLEDGE
    assert route2.entities.sports_entity == "Thái Nguyên T&T"
