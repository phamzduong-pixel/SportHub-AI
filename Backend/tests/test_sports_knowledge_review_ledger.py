from __future__ import annotations

import hashlib
import hmac
import json
from types import SimpleNamespace

from app.services.sports_knowledge_review_ledger import (
    ReviewLedgerResult,
    content_fingerprint,
    load_review_ledger,
)
from app.services.sports_knowledge_policy import PolicyOutcome
from app.services.sports_knowledge_policy_enforcement import evaluate_reviewed_knowledge_use


TEST_KEY = "synthetic-test-ledger-key-32-bytes-minimum"


def _entry():
    return SimpleNamespace(
        id="SYNTHETIC-RULE-1",
        topic="rules",
        role="CUSTOMER",
        intent="SPORTS_KNOWLEDGE",
        sport="tennis",
        entity="tennis",
        question="What is a synthetic tennis rule?",
        answer="Synthetic test claim only.",
        source_name="Synthetic test source",
        source_url="https://example.test/synthetic-rules",
        source_title=None,
        source_version="fixture-v1",
        verified_at=None,
        effective_from=None,
        effective_to=None,
        rule_set=None,
        jurisdiction=None,
        rights_status="approved",
        license="synthetic-test-license",
        rights_evidence_url="https://example.test/synthetic-license",
        rights_checked_at="2026-01-01",
        approved_uses=("retrieve_internal",),
        authoring_type="synthetic_test",
        record_status="active",
        collected_at="2026-01-01",
    )


def _signed_deny(entry):
    record = {
        "decision_id": "synthetic-denial-1",
        "record_id": entry.id,
        "content_fingerprint": content_fingerprint(entry),
        "purpose": "retrieve_internal",
        "evidence_url": "https://example.test/synthetic-rights-evidence",
        "evidence_revision": "fixture-rev-1",
        "reviewer": "synthetic test reviewer",
        "decided_at": "2026-01-01T00:00:00+00:00",
        "reason": "Synthetic denial fixture; no production rights decision.",
        "decision": "deny",
        "supersedes": None,
    }
    payload = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    record["signature"] = hmac.new(TEST_KEY.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return record


def test_missing_ledger_does_not_authorize_any_use(tmp_path):
    result = load_review_ledger(tmp_path / "missing.jsonl", verification_key=TEST_KEY)

    assert result.status == "missing"
    assert not result.authorizes(_entry(), "retrieve_internal")

    decision = evaluate_reviewed_knowledge_use(_entry(), "retrieve_internal", result)
    assert decision.outcome == PolicyOutcome.REVIEW


def test_malformed_or_incomplete_ledger_fails_closed(tmp_path):
    ledger = tmp_path / "decisions.jsonl"
    ledger.write_text('{"decision_id":\n', encoding="utf-8")
    malformed = load_review_ledger(ledger, verification_key=TEST_KEY)
    assert malformed.status == "invalid"
    assert not malformed.authorizes(_entry(), "retrieve_internal")

    ledger.write_text(json.dumps({"decision_id": "incomplete"}) + "\n", encoding="utf-8")
    incomplete = load_review_ledger(ledger, verification_key=TEST_KEY)
    assert incomplete.status == "invalid"
    assert not incomplete.authorizes(_entry(), "retrieve_internal")


def test_unsigned_allow_claim_and_missing_verification_key_fail_closed(tmp_path):
    entry = _entry()
    record = _signed_deny(entry)
    record["decision"] = "allow"
    # Deliberately retain the denial signature to model an untrusted payload edit.
    path = tmp_path / "decisions.jsonl"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    unsigned_allow = load_review_ledger(path, verification_key=TEST_KEY)
    no_key = load_review_ledger(path, verification_key="")

    assert unsigned_allow.status == "invalid"
    assert no_key.status == "unauthenticated"
    assert not unsigned_allow.authorizes(entry, "retrieve_internal")
    assert not no_key.authorizes(entry, "retrieve_internal")


def test_signed_denial_is_accepted_but_content_change_has_no_matching_decision(tmp_path):
    entry = _entry()
    path = tmp_path / "decisions.jsonl"
    path.write_text(json.dumps(_signed_deny(entry), ensure_ascii=False) + "\n", encoding="utf-8")

    result = load_review_ledger(path, verification_key=TEST_KEY)
    changed = _entry()
    changed.answer = "Changed claim with the same synthetic record ID."

    assert result.status == "valid"
    assert not result.authorizes(entry, "retrieve_internal")
    assert not result.authorizes(changed, "retrieve_internal")
    assert (entry.id, content_fingerprint(entry), "retrieve_internal") in result.decisions
    assert (changed.id, content_fingerprint(changed), "retrieve_internal") not in result.decisions
    assert content_fingerprint(entry) != content_fingerprint(changed)

    policy_decision = evaluate_reviewed_knowledge_use(entry, "retrieve_internal", result)
    assert policy_decision.outcome == PolicyOutcome.REVIEW


def test_review_ledger_result_without_verified_status_is_never_authoritative():
    entry = _entry()
    result = ReviewLedgerResult("invalid", {(entry.id, content_fingerprint(entry), "retrieve_internal"): {"decision": "allow"}})

    assert not result.authorizes(entry, "retrieve_internal")
