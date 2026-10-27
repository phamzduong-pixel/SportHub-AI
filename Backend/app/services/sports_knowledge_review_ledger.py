"""Read-only, fail-closed verification for Sports Knowledge review decisions.

The ledger is deliberately not writable through the ordinary knowledge updater.
Entries are accepted only when their canonical JSON is authenticated with the
review HMAC key configured outside the repository. A hash/fingerprint identifies
the reviewed version; it is not itself evidence of rights.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from .sports_knowledge_policy import APPROVED_USES


REVIEW_HMAC_ENV = "SPORTS_KNOWLEDGE_REVIEW_HMAC_KEY"
_FINGERPRINT_FIELDS = (
    "id", "topic", "role", "intent", "sport", "entity", "question", "answer",
    "source_name", "source_url", "source_title", "source_version", "verified_at",
    "effective_from", "effective_to", "rule_set", "jurisdiction", "rights_status",
    "license", "rights_evidence_url", "rights_checked_at", "approved_uses",
    "authoring_type", "record_status",
)
_DECISION_FIELDS = frozenset({
    "decision_id", "record_id", "content_fingerprint", "purpose", "evidence_url",
    "evidence_revision", "reviewer", "decided_at", "reason", "decision",
    "supersedes", "signature",
})
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ReviewLedgerResult:
    status: str
    decisions: Mapping[tuple[str, str, str], Mapping[str, Any]]
    reason: str | None = None

    def authorizes(self, entry: Any, purpose: str) -> bool:
        """Return true only for a verified, current, purpose-specific allow."""
        if self.status != "valid" or purpose not in APPROVED_USES:
            return False
        record_id = _field(entry, "id")
        if not isinstance(record_id, str) or not record_id:
            return False
        decision = self.decisions.get((record_id, content_fingerprint(entry), purpose))
        return bool(decision and decision.get("decision") == "allow")


def _field(entry: Any, name: str) -> Any:
    if isinstance(entry, Mapping):
        return entry.get(name)
    return getattr(entry, name, None)


def content_fingerprint(entry: Any) -> str:
    """Fingerprint the reviewed claim, provenance, and use metadata version."""
    values: dict[str, Any] = {}
    for field in _FINGERPRINT_FIELDS:
        value = _field(entry, field)
        if field == "approved_uses" and value is not None:
            value = list(value) if isinstance(value, tuple) else value
        values[field] = value
    canonical = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical_decision(decision: Mapping[str, Any]) -> bytes:
    unsigned = {key: value for key, value in decision.items() if key != "signature"}
    return json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _default_ledger_path() -> Path:
    backend_root = Path(__file__).resolve().parents[2]
    return backend_root / "data" / "knowledge" / "sports_knowledge_rights" / "decisions.jsonl"


def load_review_ledger(
    path: str | os.PathLike[str] | None = None,
    *,
    verification_key: str | bytes | None = None,
) -> ReviewLedgerResult:
    """Load and authenticate the complete JSONL ledger; any defect denies all."""
    ledger_path = Path(path) if path is not None else _default_ledger_path()
    try:
        raw = ledger_path.read_bytes()
    except FileNotFoundError:
        return ReviewLedgerResult("missing", {}, "review ledger does not exist")
    except OSError as exc:
        return ReviewLedgerResult("invalid", {}, f"review ledger cannot be read: {exc}")

    if verification_key is None:
        verification_key = os.environ.get(REVIEW_HMAC_ENV)
    if isinstance(verification_key, str):
        key = verification_key.encode("utf-8")
    elif isinstance(verification_key, bytes):
        key = verification_key
    else:
        key = b""
    if len(key) < 32:
        return ReviewLedgerResult("unauthenticated", {}, "review verification key is absent or too short")
    if len(raw) > 10 * 1024 * 1024:
        return ReviewLedgerResult("invalid", {}, "review ledger exceeds the 10 MiB safety limit")

    latest: dict[tuple[str, str, str], dict[str, Any]] = {}
    seen_ids: set[str] = set()
    try:
        lines = raw.decode("utf-8").splitlines()
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict) or set(record) != _DECISION_FIELDS:
                raise ValueError(f"line {line_number}: decision fields do not match the contract")
            if any(not isinstance(record[field], str) or not record[field].strip() for field in (
                "decision_id", "record_id", "content_fingerprint", "purpose", "evidence_url",
                "evidence_revision", "reviewer", "decided_at", "reason", "decision", "signature",
            )):
                raise ValueError(f"line {line_number}: required text field is missing")
            if record["decision_id"] in seen_ids:
                raise ValueError(f"line {line_number}: duplicate decision_id")
            seen_ids.add(record["decision_id"])
            if not _HEX_64.fullmatch(record["content_fingerprint"]):
                raise ValueError(f"line {line_number}: content_fingerprint must be SHA-256 hex")
            if record["purpose"] not in APPROVED_USES:
                raise ValueError(f"line {line_number}: unsupported purpose")
            if record["decision"] not in {"allow", "deny"}:
                raise ValueError(f"line {line_number}: decision must be allow or deny")
            supersedes = record["supersedes"]
            if supersedes is not None and (not isinstance(supersedes, str) or not supersedes.strip()):
                raise ValueError(f"line {line_number}: supersedes must be a non-empty ID or null")
            parsed_time = datetime.fromisoformat(record["decided_at"].replace("Z", "+00:00"))
            if parsed_time.tzinfo is None:
                raise ValueError(f"line {line_number}: decided_at must include a timezone")
            parsed_url = urlparse(record["evidence_url"])
            if parsed_url.scheme not in {"https", "http"} or not parsed_url.netloc:
                raise ValueError(f"line {line_number}: evidence_url must be an absolute HTTP(S) URL")

            expected_signature = hmac.new(key, _canonical_decision(record), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected_signature, record["signature"].lower()):
                raise ValueError(f"line {line_number}: decision signature is invalid")

            decision_key = (record["record_id"], record["content_fingerprint"], record["purpose"])
            previous = latest.get(decision_key)
            expected_supersedes = previous["decision_id"] if previous else None
            if supersedes != expected_supersedes:
                raise ValueError(f"line {line_number}: supersedes does not identify the prior decision")
            latest[decision_key] = record
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return ReviewLedgerResult("invalid", {}, str(exc))

    return ReviewLedgerResult("valid", latest)
