from app.services.ai_intent_router import AssistantIntent, IntentRouter


def _sports_context(entity: str) -> dict:
    return {
        'last_intent': AssistantIntent.SPORTS_KNOWLEDGE.value,
        'active_entity': entity,
        'sports_entity': entity,
        'sport_type': 'bóng đá',
        'entity_type': 'athlete',
    }


def test_explicit_aliases_have_priority_over_previous_entity():
    router = IntentRouter()
    context = _sports_context('Cristiano Ronaldo')

    assert router.route('anh bảy là ai?').entities.active_entity == 'Cristiano Ronaldo'
    assert router.route('anh 7 là ai?').entities.active_entity == 'Cristiano Ronaldo'
    assert router.route('anh 10 là ai?', context).entities.active_entity == 'Lionel Messi'
    assert router.route('CR7 là ai?', context).entities.active_entity == 'Cristiano Ronaldo'
    assert router.route('m3p là ai?', context).entities.active_entity == 'Kylian Mbappé'


def test_unknown_explicit_name_does_not_inherit_previous_entity():
    router = IntentRouter()
    context = _sports_context('Cristiano Ronaldo')

    for query in (
        'biết anh Dương là ai không?',
        'anh Dương đang chơi môn gì?',
        'Dương là ai?',
    ):
        route = router.route(query, context)
        assert route.entities.active_entity is None
        assert route.entities.sports_entity is None
        assert route.entities.explicit_entity_mention is True
        assert route.context_reset is True


def test_pronoun_follow_up_inherits_previous_entity():
    router = IntentRouter()
    first = router.route('anh 7 là ai?')
    context = first.entities.__dict__ | {'last_intent': first.intent.value}
    route = router.route(
        'anh ấy đang chơi cho đội nào?',
        context,
    )

    assert route.entities.active_entity == 'Cristiano Ronaldo'
    assert route.entities.sports_entity == 'Cristiano Ronaldo'
    assert route.entities.explicit_entity_mention is False


def test_unknown_name_switches_away_from_messi_too():
    route = IntentRouter().route('anh Dương là ai?', _sports_context('Lionel Messi'))

    assert route.entities.active_entity is None
    assert route.entities.sports_entity is None
    assert route.context_reset is True
