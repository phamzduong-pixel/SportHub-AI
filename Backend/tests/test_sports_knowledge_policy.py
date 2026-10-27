from __future__ import annotations

import pytest
from types import SimpleNamespace

from app.services.sports_knowledge_policy import (
    APPROVED_USES,
    LEGACY_APPROVED_USE_VALUES,
    KnowledgeUseDecision,
    MetadataState,
    PolicyOutcome,
    assess_metadata_field,
    citation_deduplication_key,
    evaluate_knowledge_policy,
    evaluate_knowledge_use,
    filter_knowledge_evidence,
)
from app.services.llm_sports_processor import LLMSportsQueryProcessor
from app.services.ai_assistant_service import _sports_knowledge_conversation_history


METADATA_FIELDS = (
    "source_title",
    "source_version",
    "verified_at",
    "effective_from",
    "effective_to",
    "rule_set",
    "jurisdiction",
    "rights_status",
    "license",
    "rights_evidence_url",
    "rights_checked_at",
    "approved_uses",
    "authoring_type",
    "record_status",
)


def _approved(*uses: str) -> dict[str, object]:
    return {
        "rights_status": "approved",
        "approved_uses": tuple(uses),
        "record_status": "active",
    }


@pytest.mark.parametrize(
    ("rights_status", "uses", "expected"),
    [
        ("approved", ("retrieve_internal",), PolicyOutcome.ALLOWED),
        ("reference_only", ("retrieve_internal",), PolicyOutcome.DENIED),
        ("pending_review", ("retrieve_internal",), PolicyOutcome.REVIEW),
        ("restricted", ("retrieve_internal",), PolicyOutcome.DENIED),
    ],
)
def test_rights_status_matrix_for_internal_retrieval(rights_status, uses, expected) -> None:
    decision = evaluate_knowledge_use(
        {"rights_status": rights_status, "approved_uses": uses, "record_status": "active"},
        "retrieve_internal",
    )

    assert decision.outcome == expected
    assert decision.usable is (expected == PolicyOutcome.ALLOWED)


@pytest.mark.parametrize("purpose", sorted(APPROVED_USES))
def test_approved_allows_only_each_explicitly_listed_purpose(purpose: str) -> None:
    decision = evaluate_knowledge_use(_approved(purpose), purpose)

    assert decision.outcome == PolicyOutcome.ALLOWED
    assert decision.rights_authorized


@pytest.mark.parametrize(
    ("approved_purpose", "requested_purpose"),
    [
        (approved_purpose, requested_purpose)
        for approved_purpose in sorted(APPROVED_USES)
        for requested_purpose in sorted(APPROVED_USES)
        if approved_purpose != requested_purpose
    ],
)
def test_approved_denies_every_unlisted_purpose(
    approved_purpose: str,
    requested_purpose: str,
) -> None:
    decision = evaluate_knowledge_use(_approved(approved_purpose), requested_purpose)

    assert decision.outcome == PolicyOutcome.DENIED
    assert not decision.usable


@pytest.mark.parametrize(
    ("rights_status", "purpose", "expected"),
    [
        ("reference_only", purpose, PolicyOutcome.ALLOWED if purpose == "display_citation" else PolicyOutcome.DENIED)
        for purpose in sorted(APPROVED_USES)
    ]
    + [
        (rights_status, purpose, expected)
        for rights_status, expected in (
            ("pending_review", PolicyOutcome.REVIEW),
            ("restricted", PolicyOutcome.DENIED),
        )
        for purpose in sorted(APPROVED_USES)
    ],
)
def test_non_approved_rights_statuses_across_all_purposes(
    rights_status: str,
    purpose: str,
    expected: PolicyOutcome,
) -> None:
    decision = evaluate_knowledge_use(
        {
            "rights_status": rights_status,
            "approved_uses": tuple(sorted(APPROVED_USES)),
            "record_status": "active",
        },
        purpose,
    )

    assert decision.outcome == expected
    assert decision.usable is (expected == PolicyOutcome.ALLOWED)


def test_approved_without_uses_or_with_empty_tuple_does_not_grant_use() -> None:
    missing = evaluate_knowledge_use(
        {"rights_status": "approved", "approved_uses": None, "record_status": "active"},
        "retrieve_internal",
    )
    empty = evaluate_knowledge_use(
        {"rights_status": "approved", "approved_uses": (), "record_status": "active"},
        "retrieve_internal",
    )

    assert missing.outcome == PolicyOutcome.REVIEW
    assert empty.outcome == PolicyOutcome.DENIED


@pytest.mark.parametrize("value", sorted(LEGACY_APPROVED_USE_VALUES))
def test_legacy_approved_uses_are_preserved_but_unresolved(value: str) -> None:
    assessment = assess_metadata_field({"approved_uses": (value,)}, "approved_uses")
    decision = evaluate_knowledge_use(
        {"rights_status": "approved", "approved_uses": (value,), "record_status": "active"},
        "retrieve_internal",
    )

    assert assessment.state == MetadataState.UNRESOLVED
    assert assessment.raw_value == (value,)
    assert value in (assessment.reason or "")
    assert decision.outcome == PolicyOutcome.REVIEW


def test_internal_retrieval_does_not_imply_external_llm_prompt() -> None:
    decision = evaluate_knowledge_use(_approved("retrieve_internal"), "prompt_llm_external")

    assert decision.outcome == PolicyOutcome.DENIED


def test_answer_display_does_not_imply_verbatim_quote_or_redistribution() -> None:
    metadata = _approved("display_answer")

    assert evaluate_knowledge_use(metadata, "quote_excerpt").outcome == PolicyOutcome.DENIED
    assert evaluate_knowledge_use(metadata, "redistribute").outcome == PolicyOutcome.DENIED


@pytest.mark.parametrize(
    ("uses", "expected"),
    [
        (("display_citation",), PolicyOutcome.ALLOWED),
        ((), PolicyOutcome.DENIED),
        (("retrieve_internal",), PolicyOutcome.DENIED),
        (None, PolicyOutcome.REVIEW),
    ],
)
def test_reference_only_can_show_citation_only_when_explicitly_allowed(uses, expected) -> None:
    decision = evaluate_knowledge_use(
        {"rights_status": "reference_only", "approved_uses": uses, "record_status": "active"},
        "display_citation",
    )

    assert decision.outcome == expected


@pytest.mark.parametrize(
    ("record_status", "expected"),
    [
        ("active", PolicyOutcome.ALLOWED),
        ("draft", PolicyOutcome.DENIED),
        ("conflicted", PolicyOutcome.REVIEW),
        ("superseded", PolicyOutcome.DENIED),
        ("withdrawn", PolicyOutcome.DENIED),
    ],
)
def test_record_status_matrix(record_status: str, expected: PolicyOutcome) -> None:
    decision = evaluate_knowledge_use(
        {"rights_status": "approved", "approved_uses": ("retrieve_internal",), "record_status": record_status},
        "retrieve_internal",
    )

    assert decision.outcome == expected


def test_missing_record_status_requires_review_even_with_approved_rights() -> None:
    decision = evaluate_knowledge_use(
        {"rights_status": "approved", "approved_uses": ("retrieve_internal",)},
        "retrieve_internal",
    )

    assert decision.outcome == PolicyOutcome.REVIEW


def test_missing_and_partial_metadata_are_not_implicitly_approved() -> None:
    legacy = {field: None for field in METADATA_FIELDS}
    before = dict(legacy)
    legacy_decision = evaluate_knowledge_use(legacy, "retrieve_internal")
    partial_decision = evaluate_knowledge_use(
        {**legacy, "source_title": "Official rules"},
        "retrieve_internal",
    )

    assert legacy_decision.outcome == PolicyOutcome.REVIEW
    assert partial_decision.outcome == PolicyOutcome.REVIEW
    assert legacy == before
    assert legacy["rights_status"] is None
    assert legacy["verified_at"] is None


def test_missing_valid_and_invalid_status_metadata_are_distinct() -> None:
    missing_rights = assess_metadata_field({}, "rights_status")
    valid_rights = assess_metadata_field({"rights_status": " APPROVED "}, "rights_status")
    invalid_rights = assess_metadata_field({"rights_status": "approved_by_default"}, "rights_status")
    missing_record = assess_metadata_field({}, "record_status")
    invalid_record = assess_metadata_field({"record_status": "current"}, "record_status")

    assert missing_rights.state == MetadataState.MISSING
    assert valid_rights.state == MetadataState.VALID
    assert valid_rights.value == "approved"
    assert invalid_rights.state == MetadataState.INVALID
    assert missing_record.state == MetadataState.MISSING
    assert invalid_record.state == MetadataState.INVALID


def test_explicit_legacy_id_is_required_and_partial_metadata_is_not_legacy() -> None:
    metadata = {field: None for field in METADATA_FIELDS}
    no_marker = evaluate_knowledge_use(metadata, "retrieve_internal", record_id="OLD-1")
    marked = evaluate_knowledge_use(
        metadata,
        "retrieve_internal",
        record_id="OLD-1",
        legacy_record_ids={"OLD-1"},
    )
    partial = evaluate_knowledge_use(
        {**metadata, "source_title": "A title"},
        "retrieve_internal",
        record_id="OLD-1",
        legacy_record_ids={"OLD-1"},
    )

    assert no_marker.outcome == PolicyOutcome.REVIEW
    assert marked.outcome == PolicyOutcome.LEGACY_COMPATIBILITY
    assert marked.usable
    assert not marked.rights_authorized
    assert partial.outcome == PolicyOutcome.REVIEW


def test_legacy_marker_never_authorizes_external_llm_prompt() -> None:
    legacy = {field: None for field in METADATA_FIELDS}
    internal = evaluate_knowledge_use(
        legacy,
        "retrieve_internal",
        record_id="OLD-2",
        legacy_record_ids={"OLD-2"},
    )
    external = evaluate_knowledge_use(
        legacy,
        "prompt_llm_external",
        record_id="OLD-2",
        legacy_record_ids={"OLD-2"},
    )

    assert internal.outcome == PolicyOutcome.LEGACY_COMPATIBILITY
    assert internal.usable
    assert not internal.rights_authorized
    assert external.outcome == PolicyOutcome.REVIEW
    assert not external.usable
    assert not external.rights_authorized


def test_policy_assesses_retrieval_and_external_prompt_independently() -> None:
    metadata = _approved("retrieve_internal")
    policy = evaluate_knowledge_policy(metadata)

    assert policy.retrieval.outcome == PolicyOutcome.ALLOWED
    assert policy.internal_retrieval_allowed
    assert policy.external_prompt.outcome == PolicyOutcome.DENIED
    assert not policy.external_prompt_authorized


def test_legacy_policy_allows_internal_transition_but_requires_review_for_llm() -> None:
    metadata = {field: None for field in METADATA_FIELDS}
    policy = evaluate_knowledge_policy(
        metadata,
        record_id="OLD-3",
        legacy_record_ids={"OLD-3"},
    )

    assert policy.retrieval.outcome == PolicyOutcome.LEGACY_COMPATIBILITY
    assert policy.internal_retrieval_allowed
    assert policy.external_prompt.outcome == PolicyOutcome.REVIEW
    assert not policy.external_prompt_authorized


@pytest.mark.parametrize(
    "metadata",
    [
        {"rights_status": "unrecognized", "approved_uses": ("retrieve_internal",), "record_status": "active"},
        {"rights_status": "approved", "approved_uses": ["retrieve_internal"], "record_status": "active"},
        {"rights_status": "approved", "approved_uses": ("retrieve_internal",), "record_status": "unknown"},
        {"rights_status": "approved", "approved_uses": ("invented_use",), "record_status": "active"},
        {"rights_status": "approved", "approved_uses": ("",), "record_status": "active"},
        {"rights_status": "approved", "approved_uses": ("retrieve,internal",), "record_status": "active"},
        {"rights_status": "approved", "approved_uses": ("retrieve_internal",), "record_status": "active", "verified_at": "2026-2-3"},
        {"rights_status": 1, "approved_uses": ("retrieve_internal",), "record_status": "active"},
    ],
)
def test_malformed_metadata_is_invalid_not_missing_or_approved(metadata) -> None:
    decision = evaluate_knowledge_use(
        metadata,
        "retrieve_internal",
        record_id="OLD-INVALID",
        legacy_record_ids={"OLD-INVALID"},
    )

    assert decision.outcome == PolicyOutcome.INVALID
    assert not decision.usable
    assert not decision.rights_authorized


def test_unknown_requested_purpose_is_invalid() -> None:
    decision = evaluate_knowledge_use(_approved("retrieve_internal"), "share_everywhere")

    assert decision.outcome == PolicyOutcome.INVALID


def test_citation_key_keeps_distinct_urls_for_same_source_name() -> None:
    first = citation_deduplication_key("Federation", "https://example.test/rules/2025")
    second = citation_deduplication_key("Federation", "https://example.test/rules/2026")
    duplicate = citation_deduplication_key(" Federation ", "https://example.test/rules/2025 ")

    assert first != second
    assert first == duplicate


def test_citation_key_without_url_uses_record_identity_or_declines_to_deduplicate() -> None:
    first = citation_deduplication_key("Federation", None, record_id="RULE-001")
    second = citation_deduplication_key("Federation", "", record_id="RULE-002")

    assert first == ("federation", "record:rule-001")
    assert second == ("federation", "record:rule-002")
    assert citation_deduplication_key("Federation", None) is None


def test_citation_identity_does_not_change_use_eligibility() -> None:
    metadata = _approved("retrieve_internal")
    before = evaluate_knowledge_use(metadata, "retrieve_internal")
    citation_deduplication_key("Federation", "https://example.test/a")
    citation_deduplication_key("Federation", "https://example.test/b")
    after = evaluate_knowledge_use(metadata, "retrieve_internal")

    assert before == after
    assert isinstance(before, KnowledgeUseDecision)


def test_runtime_evidence_filter_keeps_each_permission_separate() -> None:
    record = SimpleNamespace(
        id="KB-APPROVED-1",
        rights_status="approved",
        approved_uses=("retrieve_internal",),
        record_status="active",
        collected_at=None,
    )
    retrieved = filter_knowledge_evidence([(record, 0.92)], "retrieve_internal")
    prompt = filter_knowledge_evidence(retrieved, "prompt_llm_external")
    display = filter_knowledge_evidence(retrieved, "display_answer")

    assert retrieved == [(record, 0.92)]
    assert prompt == []
    assert display == []


def test_runtime_evidence_filter_blocks_legacy_review_invalid_and_non_active_records() -> None:
    legacy = SimpleNamespace(id="OLD-1")
    review = SimpleNamespace(
        id="REVIEW-1", rights_status="pending_review",
        approved_uses=("retrieve_internal",), record_status="active",
    )
    invalid = SimpleNamespace(
        id="INVALID-1", rights_status="approved_by_default",
        approved_uses=("retrieve_internal",), record_status="active",
    )
    draft = SimpleNamespace(
        id="DRAFT-1", rights_status="approved",
        approved_uses=("retrieve_internal",), record_status="draft",
    )
    evidence = [(entry, 0.9) for entry in (legacy, review, invalid, draft)]

    assert filter_knowledge_evidence(evidence, "retrieve_internal") == []


def test_runtime_evidence_filter_requires_display_permission_before_prompt() -> None:
    record = SimpleNamespace(
        id="KB-PROMPT-ONLY",
        rights_status="approved",
        approved_uses=("retrieve_internal", "prompt_llm_external"),
        record_status="active",
    )
    retrieved = filter_knowledge_evidence([(record, 0.9)], "retrieve_internal")
    display = filter_knowledge_evidence(retrieved, "display_answer")
    prompt = filter_knowledge_evidence(display, "prompt_llm_external")

    assert retrieved == [(record, 0.9)]
    assert display == []
    assert prompt == []


def test_runtime_evidence_filter_allows_only_complete_prompt_permissions() -> None:
    record = SimpleNamespace(
        id="KB-FULL-1",
        rights_status="approved",
        approved_uses=("retrieve_internal", "prompt_llm_external", "display_answer", "display_citation"),
        record_status="active",
        source_name="Federation",
        source_url="https://example.test/rules",
    )
    retrieved = filter_knowledge_evidence([(record, 0.9)], "retrieve_internal")
    display = filter_knowledge_evidence(retrieved, "display_answer")
    prompt = filter_knowledge_evidence(display, "prompt_llm_external")
    citations = filter_knowledge_evidence(prompt, "display_citation")

    assert retrieved == display == prompt == citations == [(record, 0.9)]


def test_sports_citation_scope_keeps_distinct_urls_without_changing_default_scope() -> None:
    processor = object.__new__(LLMSportsQueryProcessor)
    records = [
        (SimpleNamespace(id="RULE-1", source_name="Federation", source_url="https://example.test/a"), 1.0),
        (SimpleNamespace(id="RULE-2", source_name="Federation", source_url="https://example.test/b"), 0.9),
        (SimpleNamespace(id="RULE-3", source_name="Federation", source_url="https://example.test/a"), 0.8),
    ]

    sports_citations = processor._extract_citations(records, citation_scope="sports_knowledge")
    default_citations = processor._extract_citations(records)

    assert [item["source_url"] for item in sports_citations] == [
        "https://example.test/a", "https://example.test/b",
    ]
    assert len(default_citations) == 1


def test_sports_knowledge_prompt_history_keeps_dialogue_without_current_turn() -> None:
    history = [
        {"role": "user", "content": "Messi là ai?"},
        {"role": "assistant", "content": "Dữ kiện từ record chưa rõ quyền."},
        {"role": "user", "content": "Còn danh hiệu thì sao?"},
    ]

    assert _sports_knowledge_conversation_history(history, "Còn danh hiệu thì sao?") == history[:2]
