from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.api.routes.ai import _resolve_assistant_context, _should_include_assistant_history
from app.schemas.ai import AssistantMode
from app.services.ai_assistant_service import AIAssistantService, BACKGROUND_VOLATILE_WARNING, SearchCriteria
from app.services.ai_intent_router import AssistantIntent, IntentEntities, IntentRoute
from app.services.ai_intent_router import IntentRouter
from app.services.ai_domain_policy import PROFESSIONAL_SPORTS_KNOWLEDGE_REFUSAL
from app.services.sports_knowledge_review_ledger import ReviewLedgerResult


class _Guardrail:
    def __init__(self, evidence, error=None):
        self.evidence = evidence
        self.error = error
        self.retrieve_calls = 0

    def retrieve_context(self, *args, **kwargs):
        self.retrieve_calls += 1
        if self.error:
            raise self.error
        return self.evidence

    @staticmethod
    def evaluate_freshness_and_sufficiency(*args, **kwargs):
        return SimpleNamespace(needs_fresh_web=False)


class _Processor:
    def __init__(self, grounded=None, generation_status='unavailable'):
        self.grounded = grounded
        self.last_generation_status = generation_status
        self.prompt_evidence = None
        self.prompt_history = None
        self.generation_kwargs = None
        self.understanding_history = None
        self.generation_calls = 0

    def understand_query(self, query, *, conversation_messages=None, context=None):
        self.understanding_history = conversation_messages
        return None

    def generate_grounded_response(self, query, evidence_entries, **kwargs):
        self.generation_calls += 1
        self.prompt_evidence = evidence_entries
        self.prompt_history = kwargs.get("conversation_messages")
        self.generation_kwargs = kwargs
        return self.grounded


def _service(evidence, processor, sport='tennis', context=None, retrieval_error=None):
    route = IntentRoute(
        intent=AssistantIntent.SPORTS_KNOWLEDGE,
        confidence=1.0,
        entities=IntentEntities(sport_type=sport),
    )
    repository = SimpleNamespace(scope_for_user=lambda _user: None)
    service = AIAssistantService(
        repository, current_user=None,
        guardrail=_Guardrail(evidence, error=retrieval_error),
    )
    service._assistant_mode = AssistantMode.NATURAL
    service._active_route = route
    service._mode_evaluation = None
    service._conversation_context = context or {
        "conversation_messages": [
            {"role": "user", "content": "Tennis có luật giao bóng nào?"},
            {"role": "assistant", "content": "Nội dung cũ có nguồn chưa rõ."},
        ]
    }
    return service, route


def _entry(*uses):
    return SimpleNamespace(
        id="TENNIS-RULE-001",
        sport="tennis",
        entity="tennis",
        topic="rules",
        question="Luật giao bóng tennis là gì?",
        answer="Người giao bóng phải đứng sau vạch cuối sân.",
        source="official_rules",
        source_name="Federation",
        source_url="https://example.test/tennis-rules",
        collected_at="2026-01-01",
        rights_status="approved",
        approved_uses=tuple(uses),
        record_status="active",
    )


def test_record_without_display_answer_permission_never_leaks_through_local_rag():
    entry = _entry("retrieve_internal")
    processor = _Processor(SimpleNamespace(answer="Tennis có quy tắc giao bóng riêng.", citations=[]))
    service, route = _service([(entry, 0.9)], processor)

    with patch("app.services.ai_assistant_service.get_llm_sports_processor", return_value=processor):
        response = service._answer_sports_knowledge("Luật giao bóng tennis là gì?", route)

    assert processor.generation_calls == 1
    assert processor.prompt_evidence == []
    assert "Người giao bóng" not in response["reply"]
    assert "Federation" not in response["reply"]


def test_missing_review_ledger_blocks_local_rag_claim_and_citation():
    entry = _entry(
        "retrieve_internal", "prompt_llm_external", "display_answer", "display_citation",
    )
    processor = _Processor(SimpleNamespace(answer="Tennis có quy tắc giao bóng riêng.", citations=[]))
    service, route = _service([(entry, 0.99)], processor)

    with patch("app.services.ai_assistant_service.load_review_ledger", return_value=ReviewLedgerResult("missing", {})), \
         patch("app.services.ai_assistant_service.get_llm_sports_processor", return_value=processor):
        response = service._answer_sports_knowledge("Luật giao bóng tennis là gì?", route)

    assert processor.generation_calls == 1
    assert processor.prompt_evidence == []
    assert "Người giao bóng" not in response["reply"]
    assert "Nguồn: Federation" not in response["reply"]


def test_reference_only_record_does_not_leak_claim_or_citation_into_answer():
    entry = _entry("display_citation")
    entry.rights_status = "reference_only"
    processor = _Processor(SimpleNamespace(answer="Tennis có quy tắc giao bóng riêng.", citations=[]))
    service, route = _service([(entry, 0.9)], processor)

    with patch("app.services.ai_assistant_service.load_review_ledger", return_value=_TestReviewLedger()), \
         patch("app.services.ai_assistant_service.get_llm_sports_processor", return_value=processor):
        response = service._answer_sports_knowledge("Luật giao bóng tennis là gì?", route)

    assert processor.generation_calls == 1
    assert processor.prompt_evidence == []
    assert "Người giao bóng" not in response["reply"]
    assert "Nguồn: Federation" not in response["reply"]


def test_natural_mode_sends_authorized_evidence_and_keeps_dialogue_as_context():
    entry = _entry(
        "retrieve_internal", "prompt_llm_external", "display_answer", "display_citation",
    )
    grounded = SimpleNamespace(
        answer="Người giao bóng phải đứng sau vạch cuối sân.",
        citations=[{
            "source_name": "Federation",
            "source_url": "https://example.test/tennis-rules",
            "collected_at": "2026-01-01",
            "record_id": entry.id,
        }],
    )
    processor = _Processor(grounded)
    service, route = _service([(entry, 0.9)], processor)

    with patch("app.services.ai_assistant_service.load_review_ledger", return_value=_TestReviewLedger()), \
         patch("app.services.ai_assistant_service.get_llm_sports_processor", return_value=processor):
        response = service._answer_sports_knowledge("Luật giao bóng tennis là gì?", route)

    assert processor.generation_calls == 1
    assert processor.prompt_evidence == [(entry, 0.9)]
    assert processor.prompt_history == service._conversation_context["conversation_messages"]
    assert "Người giao bóng" in response["reply"]
    assert "Nguồn: Federation, https://example.test/tennis-rules" in response["reply"]


def test_natural_mode_suppresses_citation_without_display_citation_permission():
    entry = _entry("retrieve_internal", "prompt_llm_external", "display_answer")
    grounded = SimpleNamespace(
        answer="Câu trả lời dựa trên bản ghi.",
        citations=[{
            "source_name": "Federation",
            "source_url": entry.source_url,
            "collected_at": entry.collected_at,
            "record_id": entry.id,
        }],
    )
    processor = _Processor(grounded)
    service, route = _service([(entry, 0.9)], processor)

    with patch("app.services.ai_assistant_service.load_review_ledger", return_value=_TestReviewLedger()), \
         patch("app.services.ai_assistant_service.get_llm_sports_processor", return_value=processor):
        response = service._answer_sports_knowledge("Luật giao bóng tennis là gì?", route)

    assert "Câu trả lời dựa trên bản ghi." in response["reply"]
    assert "Nguồn: Federation" not in response["reply"]


def test_deterministic_answer_can_cite_without_external_prompt_permission():
    entry = _entry("retrieve_internal", "display_answer", "display_citation")
    processor = _Processor()
    service, route = _service([(entry, 0.9)], processor)

    with patch("app.services.ai_assistant_service.load_review_ledger", return_value=_TestReviewLedger()), \
         patch("app.services.ai_assistant_service.get_llm_sports_processor", return_value=processor):
        response = service._answer_sports_knowledge("Luật giao bóng tennis là gì?", route)

    assert processor.generation_calls == 0
    assert "Người giao bóng" in response["reply"]
    assert "https://example.test/tennis-rules" in response["reply"]


def test_local_answer_requires_display_answer_and_citation_permission_is_independent():
    entry = _entry("retrieve_internal", "display_answer")
    processor = _Processor()
    service, route = _service([(entry, 0.9)], processor)

    with patch("app.services.ai_assistant_service.load_review_ledger", return_value=_TestReviewLedger()), \
         patch("app.services.ai_assistant_service.get_llm_sports_processor", return_value=processor):
        response = service._answer_sports_knowledge("Luật giao bóng tennis là gì?", route)

    assert processor.generation_calls == 0
    assert "Người giao bóng" in response["reply"]
    assert "Nguồn:" not in response["reply"]


def test_no_local_evidence_allows_cautious_general_answer_for_stable_rule_question():
    processor = _Processor(SimpleNamespace(answer="Một cách chơi an toàn là bắt đầu bằng các luật cơ bản và luyện kỹ thuật phù hợp."))
    service, route = _service([], processor)

    with patch("app.services.ai_assistant_service.get_llm_sports_processor", return_value=processor):
        response = service._answer_sports_knowledge("Luật giao bóng tennis là gì?", route)

    assert processor.generation_calls == 1
    assert processor.prompt_evidence == []
    assert processor.generation_kwargs["allow_general_knowledge"] is True
    assert "chưa có nguồn" not in response["reply"].lower()
    assert "Nguồn:" not in response["reply"]
    assert response["understood"]["current_topic"] == "rules"


def test_record_or_medal_question_without_evidence_uses_warned_model_background():
    processor = _Processor(SimpleNamespace(answer="Thành tích này có thể thay đổi theo giải đấu.", citations=[]))
    service, route = _service([], processor, sport="cầu lông")

    with patch("app.services.ai_assistant_service.get_llm_sports_processor", return_value=processor):
        response = service._answer_sports_knowledge("Cầu lông ai có nhiều huy chương vàng nhất?", route)

    assert processor.generation_calls == 1
    assert processor.prompt_evidence == []
    assert response["reply"].endswith(BACKGROUND_VOLATILE_WARNING)
    assert "Nguồn:" not in response["reply"]


def test_followup_without_local_evidence_keeps_previous_topic_and_new_sport():
    processor = _Processor()
    context = {
        "last_intent": "SPORTS_KNOWLEDGE",
        "sport_type": "cầu lông",
        "current_topic": "achievements",
        "conversation_messages": [
            {"role": "user", "content": "Cầu lông ai có nhiều huy chương vàng nhất?"},
            {"role": "assistant", "content": "Nguồn cũ chưa được xác minh."},
        ],
    }
    service, route = _service([], processor, sport="bóng đá", context=context)

    with patch("app.services.ai_assistant_service.get_llm_sports_processor", return_value=processor):
        response = service._answer_sports_knowledge("Còn môn bóng đá?", route)

    assert processor.generation_calls == 1
    assert processor.generation_kwargs["target_topic"] == "achievements"
    assert processor.generation_kwargs["target_entity"] is None
    assert response["understood"]["current_topic"] == "achievements"
    assert response["understood"]["sport_type"] == "bóng đá"


def test_policy_blocked_candidate_is_not_reintroduced_by_local_rag():
    processor = _Processor(SimpleNamespace(answer="Có thể giải thích nguyên tắc giao bóng tennis từ kiến thức chung.", citations=[]))
    entry = _entry("retrieve_internal")
    service, route = _service([(entry, 0.9)], processor)

    with patch("app.services.ai_assistant_service.get_llm_sports_processor", return_value=processor):
        response = service._answer_sports_knowledge("Luật giao bóng tennis là gì?", route)

    assert processor.generation_calls == 1
    assert processor.prompt_evidence == []
    assert "Người giao bóng" not in response["reply"]
    assert "Nguồn: Federation" not in response["reply"]


def test_ictu_deterministic_requery_cannot_bypass_missing_review_ledger():
    entry = _entry("retrieve_internal", "display_answer", "display_citation")
    entry.id = "TN-SPT-022"
    entry.entity = "ICTU CUP"
    entry.topic = "competition"
    entry.question = "ICTU CUP là giải gì?"
    entry.answer = "Nội dung giả lập không được phép dùng nếu thiếu review ledger."
    processor = _Processor()
    service, route = _service([(entry, 0.9)], processor)
    ledger = ReviewLedgerResult("missing", {})

    response = service._answer_sports_knowledge_deterministic(
        "ICTU CUP 2024 là gì?", route, SearchCriteria(), "CUSTOMER", "bóng đá",
        ["ICTU CUP"], {"ICTU CUP": [(entry, 0.9)]}, service.guardrail, ledger,
    )

    assert "Nội dung giả lập" not in response["reply"]
    assert "Nguồn: Federation" not in response["reply"]


def test_retrieval_error_falls_back_to_general_knowledge_model():
    processor = _Processor(SimpleNamespace(answer="Luật giao bóng tennis quy định vị trí giao bóng và thứ tự thực hiện.", citations=[]))
    service, route = _service([], processor, retrieval_error=RuntimeError("offline retrieval failure"))

    with patch("app.services.ai_assistant_service.get_llm_sports_processor", return_value=processor):
        response = service._answer_sports_knowledge("Luật giao bóng tennis là gì?", route)

    assert response["status"] == "OK"
    assert response["reply"] == "Luật giao bóng tennis quy định vị trí giao bóng và thứ tự thực hiện."
    assert processor.generation_calls == 1
    assert processor.prompt_evidence == []
    assert processor.generation_kwargs["allow_general_knowledge"] is True


def test_provider_failure_is_distinct_from_missing_local_data(caplog):
    processor = _Processor(generation_status='failed')
    service, route = _service([], processor)

    with caplog.at_level("INFO", logger="app.services.ai_assistant_service"), \
         patch("app.services.ai_assistant_service.get_llm_sports_processor", return_value=processor):
        response = service._answer_sports_knowledge("Luật giao bóng tennis là gì?", route)

    assert processor.generation_calls == 1
    assert response["status"] == "ERROR"
    assert "chưa thể hoàn tất câu trả lời" in response["reply"]
    assert any("decision=GEMINI_PROVIDER_FAILED" in record.message for record in caplog.records)


def test_context_dependent_followup_without_context_requests_clarification():
    assert AIAssistantService._natural_ambiguous_query("Còn môn bóng đá?", {}) is True
    assert AIAssistantService._natural_ambiguous_query(
        "Còn môn bóng đá?", {"current_topic": "achievements"},
    ) is False


def test_explicit_empty_context_resets_old_snapshot_but_omitted_context_reuses_it():
    snapshot = {"active_entity": "old entity", "current_topic": "rules"}

    assert _resolve_assistant_context({}, snapshot) == {}
    assert _resolve_assistant_context(None, snapshot) == snapshot
    assert _resolve_assistant_context({"active_entity": "new entity"}, snapshot) == {
        "active_entity": "new entity",
    }
    assert _should_include_assistant_history({}) is False
    assert _should_include_assistant_history(None) is True
    assert _should_include_assistant_history({"active_entity": "current entity"}) is True


def test_professional_sports_knowledge_guard_returns_before_retrieval_or_lookup():
    service = object.__new__(AIAssistantService)
    service._assistant_mode = AssistantMode.PROFESSIONAL
    service.current_user = None
    service._conversation_context = {}
    route = IntentRoute(
        intent=AssistantIntent.SPORTS_KNOWLEDGE,
        confidence=1.0,
        entities=IntentEntities(sport_type="tennis"),
    )
    service._active_route = route
    service._mode_evaluation = None

    class _ForbiddenGuardrail:
        def retrieve_context(self, *args, **kwargs):
            raise AssertionError("Professional Mode must not call sports retrieval")

    service.guardrail = _ForbiddenGuardrail()
    with patch("app.services.ai_assistant_service.lookup_world_cup_query", side_effect=AssertionError("lookup called")):
        response = service._answer_sports_knowledge("Tennis Grand Slam?", route)

    assert response["reply"] == PROFESSIONAL_SPORTS_KNOWLEDGE_REFUSAL
    assert response["status"] == "OUT_OF_SCOPE"


def test_professional_ask_does_not_enter_natural_sports_model_or_lookup():
    processor = _Processor()
    service, _ = _service([], processor, sport="bóng đá")
    with patch("app.services.ai_assistant_service.get_llm_sports_processor", side_effect=AssertionError("Natural sports model called")), \
         patch("app.services.ai_assistant_service.lookup_world_cup_query", side_effect=AssertionError("World Cup lookup called")):
        response = service.ask("Messi là ai?", assistant_mode=AssistantMode.PROFESSIONAL)

    assert response["status"] == "OUT_OF_SCOPE"
    assert service.guardrail.retrieve_calls == 0


class _TestReviewLedger:
    """Non-persistent stub for exercising downstream behavior under test authorization."""
    status = "valid"

    @staticmethod
    def authorizes(entry, purpose):
        return True


@pytest.mark.parametrize("query", ["messi là ai", "Bạn biết Messi là ai không?"])
def test_basic_athlete_identity_does_not_expose_record_without_rights(query, caplog):
    blocked = _entry()
    blocked.entity = "Lionel Messi"
    blocked.sport = "bóng đá"
    blocked.topic = "identity"
    blocked.question = "Messi là ai?"
    blocked.answer = "Lionel Messi là cầu thủ bóng đá người Argentina, từng vô địch World Cup 2022."
    blocked.rights_status = None
    blocked.approved_uses = None
    blocked.record_status = None
    processor = _Processor(SimpleNamespace(
        answer="Messi là một cầu thủ bóng đá người Argentina.", citations=[],
    ))
    service, _ = _service(
        [(blocked, 0.99)], processor, sport="bóng đá",
        context={"conversation_messages": [{"role": "user", "content": query}]},
    )
    route = IntentRouter().route(query)

    with caplog.at_level("INFO", logger="app.services.ai_assistant_service"), \
         patch("app.services.ai_assistant_service.load_review_ledger", return_value=ReviewLedgerResult("missing", {})), \
         patch("app.services.ai_assistant_service.get_llm_sports_processor", return_value=processor):
        response = service._answer_sports_knowledge(query, route)

    assert response["status"] == "OK"
    assert "một cầu thủ bóng đá người Argentina" in response["reply"]
    assert "từng vô địch World Cup 2022" not in response["reply"]
    assert "Nguồn: Federation" not in response["reply"]
    assert processor.generation_calls == 1
    assert processor.prompt_evidence == []
    assert not any("decision=LOCAL_RAG" in record.message for record in caplog.records)
    assert response["understood"]["active_entity"] == "Lionel Messi"
    assert response["understood"]["entity_type"] == "athlete"


def test_approved_athlete_record_takes_precedence_over_model_background():
    entry = _entry(
        "retrieve_internal", "prompt_llm_external", "display_answer", "display_citation",
    )
    entry.entity = "Lionel Messi"
    entry.sport = "bóng đá"
    entry.topic = "identity"
    entry.question = "Messi là ai?"
    entry.answer = "Lionel Messi là cầu thủ bóng đá được mô tả trong bản ghi đã duyệt."
    processor = _Processor(SimpleNamespace(answer=entry.answer, citations=[]))
    service, _ = _service([(entry, 0.99)], processor, sport="bóng đá")
    route = IntentRouter().route("messi là ai")

    with patch("app.services.ai_assistant_service.load_review_ledger", return_value=_TestReviewLedger()), \
         patch("app.services.ai_assistant_service.get_llm_sports_processor", return_value=processor):
        response = service._answer_sports_knowledge("messi là ai", route)

    assert processor.generation_calls == 1
    assert processor.prompt_evidence == [(entry, 0.99)]
    assert entry.answer in response["reply"]


def test_messi_world_cup_followup_keeps_athlete_and_dialogue_context():
    blocked = _entry()
    blocked.entity = "Lionel Messi"
    blocked.sport = "bóng đá"
    blocked.topic = "achievements"
    blocked.answer = "Lionel Messi đã vô địch FIFA World Cup 2022 cùng Argentina."
    blocked.rights_status = None
    blocked.approved_uses = None
    blocked.record_status = None
    processor = _Processor(SimpleNamespace(
        answer="Messi cùng Argentina vô địch FIFA World Cup 2022.", citations=[],
    ))
    service, _ = _service(
        [(blocked, 0.99)], processor, sport="bóng đá",
        context={"conversation_messages": [{"role": "user", "content": "messi là ai"}]},
    )
    with patch("app.services.ai_assistant_service.load_review_ledger", return_value=ReviewLedgerResult("missing", {})), \
         patch("app.services.ai_assistant_service.get_llm_sports_processor", return_value=processor):
        first = service.ask(
            "messi là ai", assistant_mode=AssistantMode.NATURAL,
            context={"conversation_messages": [{"role": "user", "content": "messi là ai"}]},
        )
        assert first["understood"]["active_entity"] == "Lionel Messi"
        assert first["understood"]["entity_type"] == "athlete"

        second_query = "vậy messi đã vô địch wc nào chưa"
        second_context = {
            **first["understood"],
            "conversation_messages": [
                {"role": "user", "content": "messi là ai"},
                {"role": "assistant", "content": first["reply"]},
                {"role": "user", "content": second_query},
            ],
        }
        with patch("app.services.ai_assistant_service.lookup_world_cup_query", side_effect=AssertionError("Finals lookup must not answer an athlete question")):
            second = service.ask(second_query, assistant_mode=AssistantMode.NATURAL, context=second_context)

        assert "World Cup 2022" in second["reply"]
        assert second["understood"]["active_entity"] == "Lionel Messi"
        assert second["understood"]["current_topic"] == "achievements"
        assert processor.generation_calls == 2
        assert processor.prompt_evidence == []

        third_query = "tôi chỉ hỏi messi"
        third_context = {
            **second["understood"],
            "conversation_messages": [
                {"role": "user", "content": "messi là ai"},
                {"role": "assistant", "content": first["reply"]},
                {"role": "user", "content": second_query},
                {"role": "assistant", "content": second["reply"]},
                {"role": "user", "content": third_query},
            ],
        }
        third = service.ask(third_query, assistant_mode=AssistantMode.NATURAL, context=third_context)

    assert "Messi" in third["reply"]
    assert "2022" in third["reply"]
    assert third["understood"]["active_entity"] == "Lionel Messi"
    assert processor.generation_calls == 3
    assert processor.prompt_evidence == []
    assert "Nguồn: Federation" not in third["reply"]


def test_world_cup_pronoun_followup_keeps_previous_athlete():
    processor = _Processor(SimpleNamespace(
        answer="Messi đã vô địch World Cup 2022 cùng Argentina.", citations=[],
    ))
    prior = {
        "last_intent": "SPORTS_KNOWLEDGE",
        "active_entity": "Lionel Messi",
        "sports_entity": "Lionel Messi",
        "sport_type": "bóng đá",
        "entity_type": "athlete",
        "current_topic": "identity",
        "conversation_messages": [
            {"role": "user", "content": "Messi là ai?"},
            {"role": "assistant", "content": "Messi là một cầu thủ bóng đá."},
            {"role": "user", "content": "anh ấy đã vô địch wc chưa?"},
        ],
    }
    service, _ = _service([], processor, sport="bóng đá", context=prior)
    route = IntentRouter().route("anh ấy đã vô địch wc chưa?", prior)
    service._active_route = route

    assert route.entities.athlete == "Lionel Messi"
    assert route.entities.active_entity == "Lionel Messi"
    with patch("app.services.ai_assistant_service.get_llm_sports_processor", return_value=processor), \
         patch("app.services.ai_assistant_service.lookup_world_cup_query", side_effect=AssertionError("Finals lookup must not answer an athlete question")):
        response = service._answer_sports_knowledge("anh ấy đã vô địch wc chưa?", route)

    assert "2022" in response["reply"]
    assert processor.prompt_evidence == []
    assert processor.prompt_history[-1] == prior["conversation_messages"][1]


def test_current_club_question_uses_cautious_model_without_unverified_record(caplog):
    blocked = _entry()
    blocked.entity = "Lionel Messi"
    blocked.sport = "bóng đá"
    blocked.topic = "current_club"
    blocked.question = "Messi hiện thi đấu cho CLB nào?"
    blocked.answer = "CLB chưa được kiểm chứng."
    blocked.rights_status = None
    blocked.approved_uses = None
    blocked.record_status = None
    processor = _Processor(SimpleNamespace(
        answer="Messi có thể đang chơi cho một CLB ở Mỹ.\nNguồn: https://example.test/unsupported",
        citations=[{"source_name": "Nguồn giả", "source_url": "https://example.test/unsupported"}],
    ))
    service, _ = _service([(blocked, 0.99)], processor, sport="bóng đá")

    with caplog.at_level("INFO", logger="app.services.ai_assistant_service"), \
         patch("app.services.ai_assistant_service.load_review_ledger", return_value=ReviewLedgerResult("missing", {})), \
         patch("app.services.ai_assistant_service.get_llm_sports_processor", return_value=processor):
        response = service.ask(
            "Messi hiện thi đấu cho CLB nào?",
            assistant_mode=AssistantMode.NATURAL,
        )

    assert "Messi có thể đang chơi cho một CLB ở Mỹ." in response["reply"]
    assert BACKGROUND_VOLATILE_WARNING in response["reply"]
    assert "CLB chưa được kiểm chứng" not in response["reply"]
    assert "Nguồn: Federation" not in response["reply"]
    assert "https://example.test/unsupported" not in response["reply"]
    assert processor.generation_calls == 1
    assert processor.prompt_evidence == []
    assert any("decision=BACKGROUND_VOLATILE_WARNED" in record.message for record in caplog.records)


@pytest.mark.parametrize("query", [
    "Tỷ số trận đang diễn ra?",
    "Kết quả bóng đá hôm nay là gì?",
    "Lịch thi đấu bóng đá sắp tới thế nào?",
])
def test_realtime_sports_question_without_evidence_uses_model_without_inventing_live_data(query, caplog):
    processor = _Processor(SimpleNamespace(answer="Mình không có dữ liệu trực tiếp để xác nhận tỷ số hiện tại.", citations=[]))
    service, _ = _service([], processor, sport="bóng đá")
    route = IntentRoute(
        intent=AssistantIntent.SPORTS_KNOWLEDGE,
        confidence=1.0,
        entities=IntentEntities(sport_type="bóng đá"),
    )
    service._active_route = route

    with caplog.at_level("INFO", logger="app.services.ai_assistant_service"), \
         patch("app.services.ai_assistant_service.get_llm_sports_processor", return_value=processor):
        response = service._answer_sports_knowledge(query, route)

    assert processor.generation_calls == 1
    assert processor.prompt_evidence == []
    assert processor.generation_kwargs["allow_general_knowledge"] is True
    assert processor.generation_kwargs["background_level"] == "realtime"
    assert "không có dữ liệu trực tiếp" in response["reply"]
    assert any("decision=BACKGROUND_REALTIME" in record.message for record in caplog.records)


def test_routed_realtime_sports_question_uses_natural_model_response():
    query = "Kết quả bóng đá hôm nay là gì?"
    processor = _Processor(SimpleNamespace(answer="Không được dùng.", citations=[]))
    service, _ = _service([], processor, sport="bóng đá")

    with patch("app.services.ai_assistant_service.get_llm_sports_processor", return_value=processor):
        response = service.ask(query, assistant_mode=AssistantMode.NATURAL)

    assert response["intent"] == AssistantIntent.SPORTS_KNOWLEDGE.value
    assert response["status"] == "OK"
    assert processor.generation_calls == 1
    assert response["reply"] == "Không được dùng."


def test_background_without_gemini_returns_generation_error_not_evidence_refusal(caplog):
    processor = _Processor(generation_status="unavailable")
    service, _ = _service([], processor, sport="bóng đá")
    route = IntentRouter().route("Messi hiện thi đấu cho CLB nào?")
    service._active_route = route

    with caplog.at_level("INFO", logger="app.services.ai_assistant_service"), \
         patch("app.services.ai_assistant_service.get_llm_sports_processor", return_value=processor):
        response = service._answer_sports_knowledge("Messi hiện thi đấu cho CLB nào?", route)

    assert processor.generation_calls == 1
    assert processor.prompt_evidence == []
    assert "chưa có thông tin kiểm chứng" not in response["reply"]
    assert "chưa thể hoàn tất câu trả lời" in response["reply"]
    assert BACKGROUND_VOLATILE_WARNING not in response["reply"]
    assert any("decision=GEMINI_UNAVAILABLE" in record.message for record in caplog.records)
