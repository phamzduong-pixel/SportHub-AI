"""Policy evaluation and evidence filtering for sports knowledge usage."""

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any


RIGHTS_STATUSES = frozenset({"approved", "reference_only", "pending_review", "restricted"})
RECORD_STATUSES = frozenset({"active", "draft", "conflicted", "superseded", "withdrawn"})
APPROVED_USES = frozenset({
    "store_local",
    "retrieve_internal",
    "prompt_llm_external",
    "display_answer",
    "display_citation",
    "quote_excerpt",
    "redistribute",
})
# These identifiers occur in the existing writer/parser contract and tests.
# Their meaning does not map safely to the proposed policy purposes.
LEGACY_APPROVED_USE_VALUES = frozenset({"local_storage", "commercial_use", "reference"})

_OPTIONAL_METADATA_FIELDS = (
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
_DATE_FIELDS = ("collected_at", "verified_at", "effective_from", "effective_to", "rights_checked_at")
_METADATA_FIELDS = (*_OPTIONAL_METADATA_FIELDS, "collected_at")

# Explicitly marks the existing Natural Mode behavior being retained for
# already-identified legacy records during the transition. This outcome is not
# a rights grant and must not be used for new imports.
_LEGACY_RUNTIME_USES = frozenset({
    "retrieve_internal",
    "display_answer",
    "display_citation",
})


class PolicyOutcome(str, Enum):
    ALLOWED = "allowed"
    LEGACY_COMPATIBILITY = "legacy_compatibility"
    REVIEW = "review"
    DENIED = "denied"
    INVALID = "invalid"


class MetadataState(str, Enum):
    MISSING = "missing"
    VALID = "valid"
    INVALID = "invalid"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class MetadataFieldAssessment:
    state: MetadataState
    value: Any = None
    raw_value: Any = None
    reason: str | None = None


@dataclass(frozen=True)
class KnowledgeUseDecision:
    outcome: PolicyOutcome
    reason: str

    @property
    def usable(self) -> bool:
        """Whether the proposed transition policy would permit this runtime use."""
        return self.outcome in (PolicyOutcome.ALLOWED, PolicyOutcome.LEGACY_COMPATIBILITY)

    @property
    def rights_authorized(self) -> bool:
        """Legacy compatibility preserves behavior without asserting rights."""
        return self.outcome == PolicyOutcome.ALLOWED


@dataclass(frozen=True)
class KnowledgePolicyAssessment:
    retrieval: KnowledgeUseDecision
    external_prompt: KnowledgeUseDecision

    @property
    def internal_retrieval_allowed(self) -> bool:
        return self.retrieval.usable

    @property
    def external_prompt_authorized(self) -> bool:
        return self.external_prompt.outcome == PolicyOutcome.ALLOWED and self.external_prompt.rights_authorized


def assess_metadata_field(metadata: Mapping[str, Any], field: str) -> MetadataFieldAssessment:
    """Classify one stored field without converting missing or legacy values to approval."""
    if not isinstance(metadata, Mapping):
        return MetadataFieldAssessment(MetadataState.INVALID, reason="metadata must be a mapping")
    if field not in _METADATA_FIELDS:
        return MetadataFieldAssessment(MetadataState.INVALID, reason=f"unknown metadata field: {field}")

    raw_value = metadata.get(field)
    if raw_value is None:
        return MetadataFieldAssessment(MetadataState.MISSING, raw_value=raw_value)

    if field == "approved_uses":
        if not isinstance(raw_value, tuple) or any(not isinstance(item, str) for item in raw_value):
            return MetadataFieldAssessment(
                MetadataState.INVALID,
                raw_value=raw_value,
                reason="approved_uses must be a tuple of strings or None",
            )
        uses = tuple(item.strip().lower() for item in raw_value)
        if any(not item or "," in item or item == "[]" for item in uses):
            return MetadataFieldAssessment(
                MetadataState.INVALID,
                raw_value=raw_value,
                reason="approved_uses contains an empty or invalid item",
            )
        unresolved = tuple(item for item in uses if item in LEGACY_APPROVED_USE_VALUES)
        unknown = tuple(item for item in uses if item not in APPROVED_USES and item not in LEGACY_APPROVED_USE_VALUES)
        if unknown:
            return MetadataFieldAssessment(
                MetadataState.INVALID,
                raw_value=raw_value,
                reason=f"unknown approved_uses: {', '.join(sorted(set(unknown)))}",
            )
        if unresolved:
            return MetadataFieldAssessment(
                MetadataState.UNRESOLVED,
                raw_value=raw_value,
                reason=f"legacy approved_uses are not mapped to permissions: {', '.join(sorted(set(unresolved)))}",
            )
        return MetadataFieldAssessment(MetadataState.VALID, value=uses, raw_value=raw_value)

    if not isinstance(raw_value, str):
        return MetadataFieldAssessment(
            MetadataState.INVALID,
            raw_value=raw_value,
            reason=f"{field} must be a string or None",
        )
    normalized = raw_value.strip()
    if not normalized:
        return MetadataFieldAssessment(MetadataState.MISSING, raw_value=raw_value)

    if field in ("rights_status", "record_status"):
        normalized = normalized.lower()
        allowed = RIGHTS_STATUSES if field == "rights_status" else RECORD_STATUSES
        if normalized not in allowed:
            return MetadataFieldAssessment(
                MetadataState.INVALID,
                raw_value=raw_value,
                reason=f"invalid {field}: {raw_value}",
            )

    if field in _DATE_FIELDS:
        try:
            parsed = date.fromisoformat(normalized)
        except ValueError:
            return MetadataFieldAssessment(
                MetadataState.INVALID,
                raw_value=raw_value,
                reason=f"{field} must use YYYY-MM-DD",
            )
        if parsed.isoformat() != normalized:
            return MetadataFieldAssessment(
                MetadataState.INVALID,
                raw_value=raw_value,
                reason=f"{field} must use YYYY-MM-DD",
            )

    return MetadataFieldAssessment(MetadataState.VALID, value=normalized, raw_value=raw_value)


def _assess_metadata(metadata: Mapping[str, Any]) -> dict[str, MetadataFieldAssessment]:
    return {field: assess_metadata_field(metadata, field) for field in _METADATA_FIELDS}


def _legacy_marker_matches(
    record_id: str | None,
    legacy_record_ids: Collection[str] | None,
) -> tuple[bool, str | None]:
    if record_id is not None and not isinstance(record_id, str):
        return False, "record_id must be a string or None"
    if legacy_record_ids is None:
        return False, None
    if isinstance(legacy_record_ids, (str, bytes)) or not isinstance(legacy_record_ids, Collection):
        return False, "legacy_record_ids must be an explicit collection of record IDs"
    if any(not isinstance(item, str) for item in legacy_record_ids):
        return False, "legacy_record_ids may contain only strings"
    return bool(record_id and record_id in legacy_record_ids), None


def evaluate_knowledge_use(
    metadata: Mapping[str, Any],
    purpose: str,
    *,
    record_id: str | None = None,
    legacy_record_ids: Collection[str] | None = None,
) -> KnowledgeUseDecision:
    """Evaluate one purpose without modifying metadata or changing runtime behavior.

    Legacy compatibility requires both a record ID and an explicit curated ID
    collection. Missing metadata alone never marks a record as legacy. No such
    allowlist is currently shipped by this module.
    """
    if not isinstance(metadata, Mapping):
        return KnowledgeUseDecision(PolicyOutcome.INVALID, "metadata must be a mapping")
    if not isinstance(purpose, str):
        return KnowledgeUseDecision(PolicyOutcome.INVALID, "purpose must be a string")
    requested = purpose.strip().lower()
    if requested not in APPROVED_USES:
        return KnowledgeUseDecision(PolicyOutcome.INVALID, f"unknown purpose: {purpose}")

    assessments = _assess_metadata(metadata)
    invalid_fields = [
        f"{field}: {assessment.reason}"
        for field, assessment in assessments.items()
        if assessment.state == MetadataState.INVALID
    ]
    if invalid_fields:
        return KnowledgeUseDecision(PolicyOutcome.INVALID, "; ".join(invalid_fields))

    unresolved_uses = assessments["approved_uses"]
    if unresolved_uses.state == MetadataState.UNRESOLVED:
        return KnowledgeUseDecision(PolicyOutcome.REVIEW, unresolved_uses.reason or "approved_uses is unresolved")

    legacy_match, marker_error = _legacy_marker_matches(record_id, legacy_record_ids)
    if marker_error:
        return KnowledgeUseDecision(PolicyOutcome.INVALID, marker_error)

    all_new_metadata_missing = all(
        assessments[field].state == MetadataState.MISSING for field in _OPTIONAL_METADATA_FIELDS
    )
    if all_new_metadata_missing:
        if legacy_match and requested in _LEGACY_RUNTIME_USES:
            return KnowledgeUseDecision(
                PolicyOutcome.LEGACY_COMPATIBILITY,
                "explicitly allowlisted legacy record; preserves internal behavior without inferring rights",
            )
        if legacy_match and requested == "prompt_llm_external":
            return KnowledgeUseDecision(
                PolicyOutcome.REVIEW,
                "legacy compatibility does not authorize sending record content to an external LLM",
            )
        reason = "missing rights and record metadata"
        if legacy_match:
            reason = f"explicitly allowlisted legacy record has no permission for {requested}"
        return KnowledgeUseDecision(PolicyOutcome.REVIEW, reason)

    record_status_assessment = assessments["record_status"]
    if record_status_assessment.state == MetadataState.MISSING:
        return KnowledgeUseDecision(PolicyOutcome.REVIEW, "record_status is missing")
    record_status = record_status_assessment.value
    if record_status == "conflicted":
        return KnowledgeUseDecision(PolicyOutcome.REVIEW, "conflicted record requires review")
    if record_status != "active":
        return KnowledgeUseDecision(PolicyOutcome.DENIED, f"record_status={record_status} is not usable")

    rights_status_assessment = assessments["rights_status"]
    if rights_status_assessment.state == MetadataState.MISSING:
        return KnowledgeUseDecision(PolicyOutcome.REVIEW, "rights_status is missing")
    rights_status = rights_status_assessment.value
    if rights_status == "restricted":
        return KnowledgeUseDecision(PolicyOutcome.DENIED, "rights_status=restricted")
    if rights_status == "pending_review":
        return KnowledgeUseDecision(PolicyOutcome.REVIEW, "rights_status=pending_review")

    uses_assessment = assessments["approved_uses"]
    if uses_assessment.state == MetadataState.MISSING:
        return KnowledgeUseDecision(PolicyOutcome.REVIEW, "approved_uses is missing")
    uses = uses_assessment.value
    if requested not in uses:
        return KnowledgeUseDecision(PolicyOutcome.DENIED, f"purpose {requested} is not listed in approved_uses")

    if rights_status == "reference_only" and requested != "display_citation":
        return KnowledgeUseDecision(
            PolicyOutcome.DENIED,
            "reference_only permits citation display only when that purpose is explicitly listed",
        )

    return KnowledgeUseDecision(PolicyOutcome.ALLOWED, "rights status, record status, and purpose permit this use")


def evaluate_knowledge_policy(
    metadata: Mapping[str, Any],
    *,
    record_id: str | None = None,
    legacy_record_ids: Collection[str] | None = None,
) -> KnowledgePolicyAssessment:
    """Return independent decisions for internal retrieval and external prompts."""
    return KnowledgePolicyAssessment(
        retrieval=evaluate_knowledge_use(
            metadata,
            "retrieve_internal",
            record_id=record_id,
            legacy_record_ids=legacy_record_ids,
        ),
        external_prompt=evaluate_knowledge_use(
            metadata,
            "prompt_llm_external",
            record_id=record_id,
            legacy_record_ids=legacy_record_ids,
        ),
    )


def filter_knowledge_evidence(evidence_entries: Any, purpose: str) -> list[tuple[Any, Any]]:
    """Keep only records explicitly allowed for one purpose.

    Legacy compatibility is intentionally not inferred here: callers cannot
    provide a legacy allowlist, so missing metadata remains REVIEW. Existing
    ``(record, score)`` retrieval pairs retain their score; bare records are
    normalized to a neutral score for callers that already selected them.
    """
    if evidence_entries is None:
        return []

    try:
        iterator = iter(evidence_entries)
    except TypeError:
        return []

    allowed: list[tuple[Any, Any]] = []
    for item in iterator:
        if isinstance(item, tuple) and len(item) == 2:
            entry, score = item
        else:
            entry, score = item, 1.0

        if isinstance(entry, Mapping):
            metadata = {field: entry.get(field) for field in _METADATA_FIELDS}
            record_id = entry.get("id")
        else:
            metadata = {field: getattr(entry, field, None) for field in _METADATA_FIELDS}
            record_id = getattr(entry, "id", None)

        decision = evaluate_knowledge_use(metadata, purpose, record_id=record_id)
        if decision.outcome == PolicyOutcome.ALLOWED:
            allowed.append((entry, score))
    return allowed


def citation_deduplication_key(
    source_name: str | None,
    source_url: str | None,
    *,
    record_id: str | None = None,
) -> tuple[str, str] | None:
    """Build a citation key without merging different URLs under one source name.

    When URL is absent, a record ID keeps otherwise indistinguishable citations
    separate. ``None`` means there is not enough provenance for safe deduplication.
    """
    name = source_name.strip().casefold() if isinstance(source_name, str) else ""
    url = source_url.strip() if isinstance(source_url, str) else ""
    if url:
        return name, url
    identifier = record_id.strip().casefold() if isinstance(record_id, str) else ""
    if name and identifier:
        return name, f"record:{identifier}"
    return None
