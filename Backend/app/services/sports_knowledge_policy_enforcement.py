"""Natural Mode Sports Knowledge policy plus authenticated review enforcement."""

from __future__ import annotations

from typing import Any

from .sports_knowledge_policy import (
    KnowledgeUseDecision,
    PolicyOutcome,
    evaluate_knowledge_use,
)
from .sports_knowledge_review_ledger import ReviewLedgerResult


def evaluate_reviewed_knowledge_use(
    entry: Any,
    purpose: str,
    review_ledger: ReviewLedgerResult,
) -> KnowledgeUseDecision:
    """Require both valid record metadata and a signed, current per-use decision."""
    if isinstance(entry, dict):
        metadata = entry
        record_id = entry.get("id")
    else:
        metadata = {
            "source_title": getattr(entry, "source_title", None),
            "source_version": getattr(entry, "source_version", None),
            "verified_at": getattr(entry, "verified_at", None),
            "effective_from": getattr(entry, "effective_from", None),
            "effective_to": getattr(entry, "effective_to", None),
            "rule_set": getattr(entry, "rule_set", None),
            "jurisdiction": getattr(entry, "jurisdiction", None),
            "rights_status": getattr(entry, "rights_status", None),
            "license": getattr(entry, "license", None),
            "rights_evidence_url": getattr(entry, "rights_evidence_url", None),
            "rights_checked_at": getattr(entry, "rights_checked_at", None),
            "approved_uses": getattr(entry, "approved_uses", None),
            "authoring_type": getattr(entry, "authoring_type", None),
            "record_status": getattr(entry, "record_status", None),
            "collected_at": getattr(entry, "collected_at", None),
        }
        record_id = getattr(entry, "id", None)

    metadata_decision = evaluate_knowledge_use(metadata, purpose, record_id=record_id)
    if metadata_decision.outcome != PolicyOutcome.ALLOWED:
        return metadata_decision

    if review_ledger is None or review_ledger.status != "valid":
        return KnowledgeUseDecision(PolicyOutcome.REVIEW, "authenticated review ledger is unavailable")
    if not review_ledger.authorizes(entry, purpose):
        return KnowledgeUseDecision(
            PolicyOutcome.REVIEW,
            "no authenticated review decision matches this record version and purpose",
        )
    return metadata_decision


def filter_reviewed_knowledge_evidence(
    evidence_entries: Any,
    purpose: str,
    review_ledger: ReviewLedgerResult,
) -> list[tuple[Any, Any]]:
    """Filter evidence for one use; never treats citation as a rights grant."""
    if evidence_entries is None:
        return []
    try:
        items = iter(evidence_entries)
    except TypeError:
        return []

    accepted: list[tuple[Any, Any]] = []
    for item in items:
        if isinstance(item, tuple) and len(item) == 2:
            entry, score = item
        else:
            entry, score = item, 1.0
        if evaluate_reviewed_knowledge_use(entry, purpose, review_ledger).outcome == PolicyOutcome.ALLOWED:
            accepted.append((entry, score))
    return accepted


def reviewed_use_is_allowed(entry: Any, purpose: str, review_ledger: ReviewLedgerResult) -> bool:
    return evaluate_reviewed_knowledge_use(entry, purpose, review_ledger).outcome == PolicyOutcome.ALLOWED
