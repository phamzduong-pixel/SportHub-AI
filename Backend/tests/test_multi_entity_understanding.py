import pytest
from app.services.ai_intent_router import IntentRouter, AssistantIntent
from app.services.ai_assistant_service import AIAssistantService, AIRepository


@pytest.fixture
def router():
    return IntentRouter()


@pytest.fixture
def assistant():
    return AIAssistantService(AIRepository(None))


def test_single_entity_ronaldo(router, assistant):
    # Validation 1: "Ronaldo là ai?" -> trả lời Ronaldo
    query = "Ronaldo là ai?"
    route = router.route(query)
    assert route.intent == AssistantIntent.SPORTS_KNOWLEDGE
    assert route.entities.sports_entity == "Cristiano Ronaldo"
    assert route.entities.sports_entities == ["Cristiano Ronaldo"]
    assert route.entities.sport_type == "bóng đá"

    res = assistant.ask(query)
    assert res["status"] == "OK"
    assert "Cristiano Ronaldo" in res["reply"]
    assert "Nguồn: FIFA" in res["reply"]
    assert res["understood"]["sports_entity"] == "Cristiano Ronaldo"
    assert res["understood"]["sports_entities"] == ["Cristiano Ronaldo"]


def test_single_entity_messi(router, assistant):
    # Validation 4: "Messi là ai?" -> behavior hiện tại không thay đổi
    query = "Messi là ai?"
    route = router.route(query)
    assert route.intent == AssistantIntent.SPORTS_KNOWLEDGE
    assert route.entities.sports_entity == "Lionel Messi"
    assert route.entities.sports_entities == ["Lionel Messi"]

    res = assistant.ask(query)
    assert res["status"] == "OK"
    assert "Lionel Messi" in res["reply"]
    assert "Nguồn: FIFA" in res["reply"]
    assert res["understood"]["sports_entity"] == "Lionel Messi"
    assert res["understood"]["sports_entities"] == ["Lionel Messi"]


def test_two_entities_messi_ronaldo(router, assistant):
    # Validation 2: "Messi và Ronaldo là ai?" -> trả lời cả Messi và Ronaldo
    query = "Messi và Ronaldo là ai?"
    route = router.route(query)
    assert route.intent == AssistantIntent.SPORTS_KNOWLEDGE
    assert route.entities.sports_entities == ["Lionel Messi", "Cristiano Ronaldo"]
    assert route.entities.sports_entity == "Lionel Messi"
    assert route.entities.sport_type == "bóng đá"

    res = assistant.ask(query)
    assert res["status"] == "OK"
    # Verify both entities are explicitly answered and formatted
    assert "**Lionel Messi**:" in res["reply"]
    assert "**Cristiano Ronaldo**:" in res["reply"]
    assert "Lionel Messi là siêu sao" in res["reply"]
    assert "Cristiano Ronaldo (CR7)" in res["reply"]
    assert res["understood"]["sports_entities"] == ["Lionel Messi", "Cristiano Ronaldo"]


def test_three_entities_messi_ronaldo_neymar(router, assistant):
    # Validation 3: "Messi, Ronaldo và Neymar là ai?" -> không bỏ sót entity
    query = "Messi, Ronaldo và Neymar là ai?"
    route = router.route(query)
    assert route.intent == AssistantIntent.SPORTS_KNOWLEDGE
    assert route.entities.sports_entities == ["Lionel Messi", "Cristiano Ronaldo", "Neymar"]
    assert route.entities.sports_entity == "Lionel Messi"
    assert route.entities.sport_type == "bóng đá"

    res = assistant.ask(query)
    assert res["status"] == "OK"
    assert "**Lionel Messi**:" in res["reply"]
    assert "**Cristiano Ronaldo**:" in res["reply"]
    assert "**Neymar**:" in res["reply"]
    assert "Inter Miami" in res["reply"] or "Lionel Messi là siêu sao" in res["reply"]
    assert "Al-Nassr" in res["reply"] or "Cristiano Ronaldo (CR7)" in res["reply"]
    assert "Al-Hilal" in res["reply"] or "Neymar (Neymar Jr)" in res["reply"]
    assert res["understood"]["sports_entities"] == ["Lionel Messi", "Cristiano Ronaldo", "Neymar"]


def test_multi_turn_multi_entity_followup(router, assistant):
    # Validation 5: Multi-turn context -> không regression
    turn1_query = "Messi và Ronaldo là ai?"
    turn1_res = assistant.ask(turn1_query)
    assert turn1_res["status"] == "OK"

    # Multi-turn follow up using plural pronoun
    turn2_query = "Họ đang thi đấu ở đâu?"
    context = turn1_res["understood"]
    turn2_route = router.route(turn2_query, context)
    assert turn2_route.intent == AssistantIntent.SPORTS_KNOWLEDGE
    assert turn2_route.entities.sports_entities == ["Lionel Messi", "Cristiano Ronaldo"]

    turn2_res = assistant.ask(turn2_query, context=context)
    assert turn2_res["status"] == "OK"
    assert "**Lionel Messi**:" in turn2_res["reply"]
    assert "**Cristiano Ronaldo**:" in turn2_res["reply"]
    assert "Inter Miami" in turn2_res["reply"]
    assert "Al-Nassr" in turn2_res["reply"]


def test_voice_transcript_multi_entity_equivalence(router, assistant):
    # Validation 6: Voice transcript -> xử lý giống text input
    voice_transcript = "messi và ronaldo là ai"
    route = router.route(voice_transcript)
    assert route.intent == AssistantIntent.SPORTS_KNOWLEDGE
    assert route.entities.sports_entities == ["Lionel Messi", "Cristiano Ronaldo"]

    res = assistant.ask(voice_transcript)
    assert res["status"] == "OK"
    assert "**Lionel Messi**:" in res["reply"]
    assert "**Cristiano Ronaldo**:" in res["reply"]


def test_multi_entity_venues(router):
    query = 'Sân "Chảo Lửa" và sân "Khu Nam" giá bao nhiêu?'
    route = router.route(query)
    assert route.intent in (AssistantIntent.GET_VENUE_DETAIL, AssistantIntent.SEARCH_VENUE)
    assert "chao lua" in route.entities.venue_names
    assert "khu nam" in route.entities.venue_names
    assert route.entities.venue_name == "chao lua"
