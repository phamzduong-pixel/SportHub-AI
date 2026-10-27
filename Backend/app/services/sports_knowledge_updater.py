import os
import re
import tempfile
from dataclasses import dataclass, replace
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ..models.knowledge_entry import KnowledgeEntry
from ..repositories.knowledge_repository import KnowledgeRepository
from .ai_intent_router import is_supported_sport, normalize_text
from .sports_web_retriever import (
    DEFAULT_SPORTS_SOURCE_WHITELIST,
    OFFICIAL_SOURCE_DOMAINS,
    RUMOR_PATTERNS,
    SportsWebEvidence,
    SportsWebRetriever,
)
from .sports_knowledge_review_ledger import load_review_ledger
from .sports_knowledge_policy import PolicyOutcome
from .sports_knowledge_policy_enforcement import evaluate_reviewed_knowledge_use


_AUTO_UPDATED_KNOWLEDGE_COLUMNS = (
    "ID", "Topic", "Role", "Intent", "Sport", "Entity", "Question", "Answer",
    "Source_Name", "Source_URL", "Collected_At", "Priority", "Classification",
    "Source_Title", "Source_Version", "Verified_At", "Effective_From", "Effective_To",
    "Rule_Set", "Jurisdiction", "Rights_Status", "License", "Rights_Evidence_URL",
    "Rights_Checked_At", "Approved_Uses", "Authoring_Type", "Record_Status",
)

_RIGHTS_STATUSES = {"approved", "reference_only", "pending_review", "restricted"}
_RECORD_STATUSES = {"active", "draft", "conflicted", "superseded", "withdrawn"}
_METADATA_STRING_FIELDS = (
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
    "authoring_type",
    "record_status",
)
_METADATA_DATE_FIELDS = (
    "collected_at",
    "verified_at",
    "effective_from",
    "effective_to",
    "rights_checked_at",
)
_METADATA_UPDATE_FIELDS = _METADATA_STRING_FIELDS + ("approved_uses", "collected_at")
_REVIEW_CONTROLLED_FACT_FIELDS = (
    "verified_at",
    "rights_status",
    "license",
    "rights_evidence_url",
    "rights_checked_at",
    "approved_uses",
    "record_status",
)
_REVIEW_BOUND_ENTRY_FIELDS = _REVIEW_CONTROLLED_FACT_FIELDS


class FactValidationStatus(str, Enum):
    VALID = "VALID"
    REJECTED_OUT_OF_SCOPE_SPORT = "REJECTED_OUT_OF_SCOPE_SPORT"
    REJECTED_UNAPPROVED_SOURCE = "REJECTED_UNAPPROVED_SOURCE"
    REJECTED_RUMOR = "REJECTED_RUMOR"
    REJECTED_INCOMPLETE_PROVENANCE = "REJECTED_INCOMPLETE_PROVENANCE"
    REJECTED_LOW_RELIABILITY = "REJECTED_LOW_RELIABILITY"


class KnowledgeUpdateAction(str, Enum):
    INSERTED = "INSERTED"
    UPDATED = "UPDATED"
    DUPLICATE_SKIPPED = "DUPLICATE_SKIPPED"
    CONFLICT_REJECTED = "CONFLICT_REJECTED"
    REJECTED = "REJECTED"


@dataclass
class ExtractedSportsFact:
    sport: str
    entity: str
    topic: str
    question: str
    answer: str
    source_name: str
    source_url: str
    collected_at: str
    priority: int = 2
    classification: str = "static"
    role: str = "CUSTOMER,OWNER,SYSTEM_ADMIN"
    intent: str = "SPORTS_KNOWLEDGE"
    is_confirmed: bool = True
    reliability_score: float = 0.9
    # None (or a blank string) means no update. No implicit rights grant or
    # metadata clearing is supported by this fact-extraction contract.
    source_title: Optional[str] = None
    source_version: Optional[str] = None
    verified_at: Optional[str] = None
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    rule_set: Optional[str] = None
    jurisdiction: Optional[str] = None
    rights_status: Optional[str] = None
    license: Optional[str] = None
    rights_evidence_url: Optional[str] = None
    rights_checked_at: Optional[str] = None
    approved_uses: Optional[Tuple[str, ...]] = None
    authoring_type: Optional[str] = None
    record_status: Optional[str] = None


@dataclass
class FactValidationResult:
    is_valid: bool
    status: FactValidationStatus
    reason: str
    fact: Optional[ExtractedSportsFact] = None


@dataclass
class KnowledgeUpdateResult:
    action: KnowledgeUpdateAction
    entry_id: Optional[str]
    message: str
    entry: Optional[KnowledgeEntry] = None
    previous_entry: Optional[KnowledgeEntry] = None
    is_indexed: bool = False


class SportsKnowledgeUpdater:
    """
    Automated Sports Knowledge Update Pipeline:
    Approved Web Evidence -> Fact Extraction -> Validation -> Knowledge Update / Upsert.
    """

    MINIMUM_RELIABILITY_THRESHOLD = 0.75
    MIN_ANSWER_LENGTH = 10
    MIN_QUESTION_LENGTH = 5

    def __init__(
        self,
        repository: Optional[KnowledgeRepository] = None,
        retriever: Optional[SportsWebRetriever] = None,
        knowledge_retriever: Optional[Any] = None,
        review_ledger: Optional[Any] = None,
    ):
        self.repository = repository or KnowledgeRepository()
        self.retriever = retriever or SportsWebRetriever()
        self.knowledge_retriever = knowledge_retriever
        self.review_ledger = review_ledger if review_ledger is not None else load_review_ledger()

    # 1. Fact Extraction Layer
    def extract_fact_from_evidence(
        self,
        evidence: SportsWebEvidence,
        topic: str = "general",
        question: Optional[str] = None,
        sport: Optional[str] = None,
        entity: Optional[str] = None,
    ) -> ExtractedSportsFact:
        """Extract a structured fact from SportsWebEvidence."""
        resolved_sport = sport or evidence.sport or "bóng đá"
        resolved_entity = entity or evidence.title.split("-")[0].strip()
        resolved_question = question or f"Thông tin về {resolved_entity} ({topic})?"
        resolved_date = evidence.published_date or datetime.now().strftime("%Y-%m-%d")

        return ExtractedSportsFact(
            sport=resolved_sport,
            entity=resolved_entity,
            topic=topic,
            question=resolved_question,
            answer=evidence.snippet.strip(),
            source_name=evidence.source_name,
            source_url=evidence.url,
            collected_at=resolved_date,
            priority=1 if evidence.domain in OFFICIAL_SOURCE_DOMAINS else 2,
            is_confirmed=evidence.is_confirmed and not evidence.is_rumor,
            reliability_score=evidence.relevance_score or 0.9,
        )

    def extract_facts_from_raw_web_item(
        self,
        item: Dict[str, Any],
        sport: Optional[str] = None,
        entity: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> ExtractedSportsFact:
        """Standardize raw web scraper / API payload into ExtractedSportsFact."""
        url = item.get("url", "")
        title = item.get("title", "")
        content = item.get("content") or item.get("snippet") or item.get("answer") or ""
        source_name = item.get("source_name")
        if not source_name and url:
            _, resolved_name = self.retriever.is_whitelisted(url)
            source_name = resolved_name or "Approved Web"

        resolved_sport = item.get("sport") or sport or "bóng đá"
        resolved_entity = item.get("entity") or entity or (title.split("-")[0].strip() if title else "Thể thao")
        resolved_topic = item.get("topic") or topic or "general"
        resolved_question = item.get("question") or f"Thông tin về {resolved_entity} ({resolved_topic})?"
        resolved_date = item.get("published_date") or item.get("collected_at") or datetime.now().strftime("%Y-%m-%d")
        is_rumor = self.retriever.is_rumor_or_unconfirmed(f"{title} {content}")

        return ExtractedSportsFact(
            sport=resolved_sport,
            entity=resolved_entity,
            topic=resolved_topic,
            question=resolved_question,
            answer=content.strip(),
            source_name=source_name or "Approved Web",
            source_url=url,
            collected_at=resolved_date,
            priority=1 if self._is_official_url(url) else 2,
            is_confirmed=not is_rumor,
            reliability_score=float(item.get("reliability_score", 0.9)),
        )

    # 2. Validation Layer
    def validate_fact(self, fact: ExtractedSportsFact) -> FactValidationResult:
        """
        Comprehensive validation of extracted sports fact before knowledge persistence:
        1. Sport scope (must be one of 6 supported sports).
        2. Source whitelist (must be approved domain).
        3. Rumor / speculation rejection.
        4. Complete provenance (source_url, source_name, entity, sport, collected_at).
        5. Minimum reliability threshold.
        """
        # A. Sport scope validation
        if not fact.sport or not is_supported_sport(fact.sport):
            return FactValidationResult(
                is_valid=False,
                status=FactValidationStatus.REJECTED_OUT_OF_SCOPE_SPORT,
                reason=f"Sport '{fact.sport}' is outside SportHub's 6 supported sports.",
                fact=fact,
            )

        # B. Approved Source Whitelist
        if not fact.source_url:
            return FactValidationResult(
                is_valid=False,
                status=FactValidationStatus.REJECTED_INCOMPLETE_PROVENANCE,
                reason="Missing required source_url.",
                fact=fact,
            )

        whitelisted, official_name = self.retriever.is_whitelisted(fact.source_url)
        if not whitelisted:
            return FactValidationResult(
                is_valid=False,
                status=FactValidationStatus.REJECTED_UNAPPROVED_SOURCE,
                reason=f"Source URL '{fact.source_url}' is not in the approved sports whitelist.",
                fact=fact,
            )

        # C. Rumor detection
        if not fact.is_confirmed or self.retriever.is_rumor_or_unconfirmed(fact.answer):
            return FactValidationResult(
                is_valid=False,
                status=FactValidationStatus.REJECTED_RUMOR,
                reason="Content contains unverified speculation or rumor patterns.",
                fact=fact,
            )

        # D. Provenance completeness & content sanity
        if not fact.entity or not fact.entity.strip():
            return FactValidationResult(
                is_valid=False,
                status=FactValidationStatus.REJECTED_INCOMPLETE_PROVENANCE,
                reason="Missing required entity name.",
                fact=fact,
            )

        if not fact.collected_at:
            return FactValidationResult(
                is_valid=False,
                status=FactValidationStatus.REJECTED_INCOMPLETE_PROVENANCE,
                reason="Missing required collected_at timestamp.",
                fact=fact,
            )

        if len(fact.answer.strip()) < self.MIN_ANSWER_LENGTH:
            return FactValidationResult(
                is_valid=False,
                status=FactValidationStatus.REJECTED_INCOMPLETE_PROVENANCE,
                reason=f"Answer content length ({len(fact.answer.strip())}) is too short.",
                fact=fact,
            )

        # E. Reliability score
        if fact.reliability_score < self.MINIMUM_RELIABILITY_THRESHOLD:
            return FactValidationResult(
                is_valid=False,
                status=FactValidationStatus.REJECTED_LOW_RELIABILITY,
                reason=f"Reliability score ({fact.reliability_score:.2f}) is below threshold ({self.MINIMUM_RELIABILITY_THRESHOLD:.2f}).",
                fact=fact,
            )

        return FactValidationResult(
            is_valid=True,
            status=FactValidationStatus.VALID,
            reason="Fact passed all validation criteria.",
            fact=fact,
        )

    # 3. Knowledge Update / Upsert Layer
    def apply_fact_update(
        self,
        fact: ExtractedSportsFact,
        persist_markdown: bool = False,
    ) -> KnowledgeUpdateResult:
        """
        Apply validated fact to Knowledge Base:
        - Detect duplicate -> DUPLICATE_SKIPPED
        - Detect conflict -> CONFLICT_REJECTED (if unverified / lower priority)
        - If existing changed -> UPDATED
        - If new -> INSERTED
        """
        validation = self.validate_fact(fact)
        if not validation.is_valid:
            return KnowledgeUpdateResult(
                action=KnowledgeUpdateAction.REJECTED,
                entry_id=None,
                message=f"Validation failed: {validation.reason}",
                is_indexed=False,
            )

        try:
            self._validate_fact_metadata(fact)
        except (TypeError, ValueError) as exc:
            return KnowledgeUpdateResult(
                action=KnowledgeUpdateAction.REJECTED,
                entry_id=None,
                message=f"Metadata validation failed: {exc}",
                is_indexed=False,
            )

        caller_review_fields = [
            field for field in _REVIEW_CONTROLLED_FACT_FIELDS
            if (value := getattr(fact, field)) is not None
            and (not isinstance(value, str) or value.strip())
        ]
        if caller_review_fields:
            return KnowledgeUpdateResult(
                action=KnowledgeUpdateAction.REJECTED,
                entry_id=None,
                message=(
                    "Ordinary updater cannot set reviewer-controlled metadata: "
                    + ", ".join(caller_review_fields)
                ),
                is_indexed=False,
            )

        existing_entries = self.repository.list_entries()
        matched_entry = self._find_matching_entry(fact, existing_entries)

        def apply_metadata(entry: KnowledgeEntry) -> None:
            for field in _METADATA_STRING_FIELDS + ("approved_uses",):
                if field in _REVIEW_CONTROLLED_FACT_FIELDS:
                    continue
                value = getattr(fact, field)
                if value is not None and (not isinstance(value, str) or value.strip()):
                    setattr(entry, field, value)

        def persist_or_reject(entry: KnowledgeEntry) -> Optional[KnowledgeUpdateResult]:
            try:
                # Validate even for an in-memory update, before mutating the index.
                normalized_metadata = self._validate_metadata(entry)
                for field in ("rights_status", "record_status", "approved_uses"):
                    setattr(entry, field, normalized_metadata[field])
                try:
                    store_local_decision = evaluate_reviewed_knowledge_use(
                        entry,
                        "store_local",
                        self.review_ledger,
                    )
                    store_local_authorized = store_local_decision.outcome == PolicyOutcome.ALLOWED
                except Exception:
                    store_local_authorized = False
                if not store_local_authorized:
                    return KnowledgeUpdateResult(
                        action=KnowledgeUpdateAction.REJECTED,
                        entry_id=entry.id,
                        message=(
                            "Sports Knowledge storage requires valid approved metadata "
                            "and an authenticated store_local review decision for this exact record version."
                        ),
                        entry=None,
                        is_indexed=False,
                    )
                if persist_markdown:
                    self._persist_entry_to_markdown(entry)
            except (OSError, TypeError, ValueError) as exc:
                return KnowledgeUpdateResult(
                    action=KnowledgeUpdateAction.REJECTED,
                    entry_id=entry.id,
                    message=f"Knowledge update was not applied: {exc}",
                    entry=matched_entry,
                    is_indexed=False,
                )
            return None

        if matched_entry:
            # Check for exact duplicate content
            if self._is_identical_content(matched_entry.answer, fact.answer):
                candidate = replace(matched_entry)
                apply_metadata(candidate)
                if fact.collected_at and (not matched_entry.collected_at or fact.collected_at > matched_entry.collected_at):
                    candidate.collected_at = fact.collected_at
                rejected = persist_or_reject(candidate) if candidate != matched_entry else None
                if rejected:
                    return rejected
                metadata_changed = any(
                    getattr(candidate, field) != getattr(matched_entry, field)
                    for field in _METADATA_UPDATE_FIELDS
                )
                matched_entry.__dict__.update(candidate.__dict__)
                is_indexed = False
                if metadata_changed and self.knowledge_retriever is not None and hasattr(self.knowledge_retriever, "update_entry"):
                    is_indexed = self.knowledge_retriever.update_entry(matched_entry, force=True)
                return KnowledgeUpdateResult(
                    action=KnowledgeUpdateAction.UPDATED if metadata_changed else KnowledgeUpdateAction.DUPLICATE_SKIPPED,
                    entry_id=matched_entry.id,
                    message=(f"Metadata updated for knowledge entry '{matched_entry.id}'." if metadata_changed
                             else f"Identical content already exists for entity '{fact.entity}' topic '{fact.topic}'. Duplicate skipped."),
                    entry=matched_entry,
                    is_indexed=is_indexed,
                )

            # Check for conflict vs safe update
            existing_rights_status = matched_entry.rights_status
            if isinstance(existing_rights_status, str) and existing_rights_status.strip().lower() == "approved":
                return KnowledgeUpdateResult(
                    action=KnowledgeUpdateAction.REJECTED,
                    entry_id=matched_entry.id,
                    message="Approved content requires a separate rights review before replacement.",
                    entry=matched_entry,
                    previous_entry=matched_entry,
                    is_indexed=False,
                )
            has_conflict, conflict_reason = self._detect_conflict(matched_entry, fact)
            if has_conflict:
                return KnowledgeUpdateResult(
                    action=KnowledgeUpdateAction.CONFLICT_REJECTED,
                    entry_id=matched_entry.id,
                    message=f"Conflict detected without sufficient validation precedence: {conflict_reason}",
                    entry=matched_entry,
                    previous_entry=matched_entry,
                    is_indexed=False,
                )

            # Validated Update: Apply changes to existing entry
            prev_snapshot = replace(matched_entry)
            candidate = replace(matched_entry)
            candidate.answer = fact.answer
            candidate.source_name = fact.source_name
            candidate.source_url = fact.source_url
            candidate.collected_at = fact.collected_at
            candidate.priority = fact.priority
            candidate.classification = fact.classification
            candidate.source = f"{fact.source_name} ({fact.source_url})"
            # A changed claim cannot inherit a review decision for the old version.
            for field in _REVIEW_BOUND_ENTRY_FIELDS:
                setattr(candidate, field, None)
            apply_metadata(candidate)
            rejected = persist_or_reject(candidate)
            if rejected:
                return rejected
            matched_entry.__dict__.update(candidate.__dict__)

            # Incremental re-index of affected chunk only
            is_indexed = True
            if self.knowledge_retriever is not None and hasattr(self.knowledge_retriever, "update_entry"):
                is_indexed = self.knowledge_retriever.update_entry(matched_entry, force=True)

            return KnowledgeUpdateResult(
                action=KnowledgeUpdateAction.UPDATED,
                entry_id=matched_entry.id,
                message=f"Updated existing knowledge entry '{matched_entry.id}' for entity '{fact.entity}'.",
                entry=matched_entry,
                previous_entry=prev_snapshot,
                is_indexed=is_indexed,
            )

        # Insert New Entry
        new_id = self._generate_entry_id(fact, existing_entries)
        new_entry = KnowledgeEntry(
            id=new_id,
            topic=fact.topic,
            role=fact.role,
            intent=fact.intent,
            sport=fact.sport,
            entity=fact.entity,
            question=fact.question,
            answer=fact.answer,
            source_name=fact.source_name,
            source_url=fact.source_url,
            collected_at=fact.collected_at,
            priority=fact.priority,
            classification=fact.classification,
            source=f"{fact.source_name} ({fact.source_url})",
        )

        apply_metadata(new_entry)
        rejected = persist_or_reject(new_entry)
        if rejected:
            return rejected

        if hasattr(self.repository, "_entries") and isinstance(self.repository._entries, list) and new_entry not in self.repository._entries:
            self.repository._entries.append(new_entry)
        elif hasattr(self.repository, "upsert_entry"):
            try:
                self.repository.upsert_entry(new_entry)
            except Exception:
                pass

        # Incremental index for new entry
        is_indexed = True
        if self.knowledge_retriever is not None and hasattr(self.knowledge_retriever, "index_entry"):
            is_indexed = self.knowledge_retriever.index_entry(new_entry)

        return KnowledgeUpdateResult(
            action=KnowledgeUpdateAction.INSERTED,
            entry_id=new_id,
            message=f"Inserted new knowledge entry '{new_id}' for entity '{fact.entity}'.",
            entry=new_entry,
            is_indexed=is_indexed,
        )

    # 4. Pipeline Execution
    def process_pipeline(
        self,
        web_items: List[Dict[str, Any]],
        persist_markdown: bool = False,
    ) -> List[KnowledgeUpdateResult]:
        """Execute end-to-end update pipeline on a batch of web items."""
        results = []
        for item in web_items:
            fact = self.extract_facts_from_raw_web_item(item)
            result = self.apply_fact_update(fact, persist_markdown=persist_markdown)
            results.append(result)
        return results

    # --- Helper methods ---
    def _find_matching_entry(
        self,
        fact: ExtractedSportsFact,
        entries: List[KnowledgeEntry],
    ) -> Optional[KnowledgeEntry]:
        """Find an existing entry matching entity and topic/question."""
        norm_ent = normalize_text(fact.entity)
        norm_top = normalize_text(fact.topic)
        norm_q = normalize_text(fact.question)

        # 1. Exact match on entity and topic
        for entry in entries:
            if entry.entity and normalize_text(entry.entity) == norm_ent:
                if entry.topic and normalize_text(entry.topic) == norm_top:
                    return entry
                if entry.question and normalize_text(entry.question) == norm_q:
                    return entry

        # 2. Match by exact question
        for entry in entries:
            if entry.question and normalize_text(entry.question) == norm_q:
                return entry

        return None

    def _is_identical_content(self, text_a: str, text_b: str) -> bool:
        """Compare two answers for semantic equivalence and normalization."""
        return normalize_text(text_a) == normalize_text(text_b)

    def _detect_conflict(
        self,
        existing: KnowledgeEntry,
        incoming: ExtractedSportsFact,
    ) -> Tuple[bool, str]:
        """
        Determine if incoming fact represents an unresolvable conflict:
        - If existing entry is official (priority 1) and incoming is secondary (priority 2) without newer verified timestamp -> Conflict.
        - If incoming fact has older timestamp than existing -> Conflict (stale update).
        """
        # Timestamp comparison
        if existing.collected_at and incoming.collected_at:
            try:
                exist_date = datetime.strptime(existing.collected_at[:10], "%Y-%m-%d")
                inc_date = datetime.strptime(incoming.collected_at[:10], "%Y-%m-%d")
                if inc_date < exist_date:
                    return True, f"Incoming fact date ({incoming.collected_at}) is older than existing entry date ({existing.collected_at})."
            except Exception:
                pass

        # Priority conflict: lower-priority source trying to overwrite priority 1 without newer date
        if existing.priority < incoming.priority and existing.collected_at == incoming.collected_at:
            return True, f"Cannot overwrite high-priority source ({existing.source_name}) with lower-priority source ({incoming.source_name}) of identical date."

        return False, ""

    def _generate_entry_id(
        self,
        fact: ExtractedSportsFact,
        entries: List[KnowledgeEntry],
    ) -> str:
        """Generate unique ID for new auto-updated knowledge entry."""
        sport_code = "FB"
        if "cau long" in normalize_text(fact.sport) or "badminton" in normalize_text(fact.sport):
            sport_code = "BDM"
        elif "pickleball" in normalize_text(fact.sport):
            sport_code = "PB"
        elif "tennis" in normalize_text(fact.sport):
            sport_code = "TEN"
        elif "bong ro" in normalize_text(fact.sport) or "basketball" in normalize_text(fact.sport):
            sport_code = "BB"
        elif "bong chuyen" in normalize_text(fact.sport) or "volleyball" in normalize_text(fact.sport):
            sport_code = "VB"

        clean_entity = re.sub(r'[^A-Z0-9]', '', fact.entity.upper())[:8] or "AUTO"
        clean_topic = re.sub(r'[^A-Z0-9]', '', fact.topic.upper())[:6] or "GEN"

        base_id = f"AUTO-{sport_code}-{clean_entity}-{clean_topic}"
        existing_ids = {e.id for e in entries}

        candidate_id = base_id
        counter = 1
        while candidate_id in existing_ids:
            candidate_id = f"{base_id}-{counter:03d}"
            counter += 1

        return candidate_id

    def _is_official_url(self, url: str) -> bool:
        """Check if URL belongs to official sports federations or government bodies."""
        if not url:
            return False
        for domain in OFFICIAL_SOURCE_DOMAINS:
            if domain in url.lower():
                return True
        return False

    def _persist_entry_to_markdown(self, entry: KnowledgeEntry) -> None:
        """Persist or append knowledge entry to sports knowledge markdown file."""
        metadata = self._validate_metadata(entry)
        values = (
            entry.id,
            entry.topic,
            entry.role,
            entry.intent,
            entry.sport,
            entry.entity,
            entry.question,
            entry.answer,
            entry.source_name,
            entry.source_url,
            metadata["collected_at"],
            entry.priority,
            entry.classification,
            metadata["source_title"],
            metadata["source_version"],
            metadata["verified_at"],
            metadata["effective_from"],
            metadata["effective_to"],
            metadata["rule_set"],
            metadata["jurisdiction"],
            metadata["rights_status"],
            metadata["license"],
            metadata["rights_evidence_url"],
            metadata["rights_checked_at"],
            metadata["approved_uses"],
            metadata["authoring_type"],
            metadata["record_status"],
        )
        cells = []
        for column, value in zip(_AUTO_UPDATED_KNOWLEDGE_COLUMNS, values):
            if value is None:
                cell = ""
            elif column == "Approved_Uses":
                if not isinstance(value, tuple) or any(not isinstance(item, str) for item in value):
                    raise TypeError("approved_uses must be a tuple of strings or None")
                normalized_uses = tuple(item.strip().lower() for item in value)
                if any(not item or "," in item for item in normalized_uses):
                    raise ValueError("approved_uses items must be non-empty identifiers without commas")
                if any(item == "[]" for item in normalized_uses):
                    raise ValueError("'[]' is reserved to encode an explicitly empty approved_uses tuple")
                cell = ", ".join(normalized_uses) if normalized_uses else "[]"
            else:
                cell = str(value)
            if any(delimiter in cell for delimiter in ("|", "\n", "\r")):
                raise ValueError(f"Cannot persist {column}: Markdown table delimiters are not supported")
            cells.append(cell)

        row = "| " + " | ".join(cells) + " |\n"
        expected_header = tuple(
            column.lower().replace(" ", "_").replace("-", "_")
            for column in _AUTO_UPDATED_KNOWLEDGE_COLUMNS
        )
        header = "| " + " | ".join(_AUTO_UPDATED_KNOWLEDGE_COLUMNS) + " |\n"
        separator = "|" + "|".join("---" for _ in _AUTO_UPDATED_KNOWLEDGE_COLUMNS) + "|\n"

        target_dir = os.path.join(self.repository.knowledge_root, "sports", "auto_updated")
        target_file = os.path.join(target_dir, "auto_updated_knowledge.md")

        lines = []
        if os.path.exists(target_file):
            with open(target_file, "r", encoding="utf-8", newline="") as f:
                lines = f.readlines()

        last_header = None
        old_header_line = None
        old_separator_line = None
        replacement_index = None
        replacement_header = None
        for index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped.startswith("|"):
                if stripped:
                    last_header = None
                continue
            parts = [part.strip() for part in stripped.split("|")[1:-1]]
            if parts and parts[0].lower() in ("id", "#", "stt", "entry_id", "mã"):
                last_header = tuple(part.lower().replace(" ", "_").replace("-", "_") for part in parts)
                old_header_line = line
                old_separator_line = None
            elif re.match(r"^\|[-:|\s]+\|$", stripped):
                old_separator_line = line
            elif parts and parts[0] == entry.id:
                if replacement_index is not None:
                    raise ValueError(f"Duplicate ID {entry.id!r} in auto-updated knowledge file")
                replacement_index = index
                replacement_header = (last_header, old_header_line, old_separator_line)

        # A duplicate elsewhere could win before this writer-owned row when
        # the repository reloads, so refuse ambiguous persistence.
        for root, _, files in os.walk(self.repository.knowledge_root):
            for name in files:
                path = os.path.join(root, name)
                if not name.lower().endswith(".md") or os.path.abspath(path) == os.path.abspath(target_file):
                    continue
                with open(path, "r", encoding="utf-8") as source_file:
                    if any(source_line.strip().split("|")[1].strip() == entry.id
                           for source_line in source_file if source_line.strip().startswith("|")):
                        raise ValueError(f"Entry {entry.id!r} belongs to another Markdown file")

        if replacement_index is not None:
            old_columns, old_header, old_separator = replacement_header
            if old_columns == expected_header:
                lines[replacement_index] = row
            elif old_columns and old_header and old_separator:
                # Upgrade only the target row, retaining the legacy rows.
                following_row = bool(replacement_index + 1 < len(lines) and
                                     lines[replacement_index + 1].strip().startswith("|"))
                replacement = ["\n", header, separator, row]
                if following_row:
                    replacement.extend(["\n", old_header, old_separator])
                lines[replacement_index:replacement_index + 1] = replacement
            else:
                raise ValueError(f"Cannot safely replace row {entry.id!r} without its table header")
            content = "".join(lines)
        elif os.path.exists(target_file):
            prefix = ""
            if lines and lines[-1].strip():
                if not lines[-1].endswith(("\n", "\r")):
                    prefix += "\n"
                prefix += "\n"
            content = "".join(lines) + prefix + ("" if last_header == expected_header else header + separator) + row
        else:
            content = "# Auto-Updated Sports Knowledge\n\n---\n\n" + header + separator + row

        os.makedirs(target_dir, exist_ok=True)
        temporary_path = None
        try:
            fd, temporary_path = tempfile.mkstemp(prefix=".knowledge-", suffix=".tmp", dir=target_dir)
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                f.write(content)
            os.replace(temporary_path, target_file)
        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.unlink(temporary_path)

    @staticmethod
    def _validate_fact_metadata(fact: ExtractedSportsFact) -> Dict[str, Any]:
        """Validate supplied metadata even when an update would otherwise be a duplicate."""
        probe = KnowledgeEntry(
            id="__metadata_validation__",
            topic=fact.topic,
            role=fact.role,
            intent=fact.intent,
            sport=fact.sport,
            entity=fact.entity,
            question=fact.question,
            answer=fact.answer,
            source=f"{fact.source_name} ({fact.source_url})",
            classification=fact.classification,
            source_name=fact.source_name,
            source_url=fact.source_url,
            collected_at=fact.collected_at,
            priority=fact.priority,
            **{
                field: getattr(fact, field)
                for field in _METADATA_STRING_FIELDS + ("approved_uses",)
            },
        )
        return SportsKnowledgeUpdater._validate_metadata(probe)

    @staticmethod
    def _validate_metadata(entry: KnowledgeEntry) -> Dict[str, Any]:
        """Validate optional metadata before touching the destination file."""
        metadata = {field: getattr(entry, field) for field in _METADATA_STRING_FIELDS}
        metadata["collected_at"] = entry.collected_at

        for field, value in metadata.items():
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{field} must be a string or None")

        for field in _METADATA_DATE_FIELDS:
            value = metadata[field]
            if value is None or not value.strip():
                continue
            try:
                parsed_date = date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(f"{field} must use YYYY-MM-DD") from exc
            if parsed_date.isoformat() != value:
                raise ValueError(f"{field} must use YYYY-MM-DD")

        for field, allowed_values in (
            ("rights_status", _RIGHTS_STATUSES),
            ("record_status", _RECORD_STATUSES),
        ):
            value = metadata[field]
            if value is None or not value.strip():
                metadata[field] = None
                continue
            normalized = value.strip().lower()
            if normalized not in allowed_values:
                allowed = ", ".join(sorted(allowed_values))
                raise ValueError(f"{field} must be one of: {allowed}")
            metadata[field] = normalized

        approved_uses = entry.approved_uses
        if approved_uses is not None:
            if not isinstance(approved_uses, tuple) or any(not isinstance(item, str) for item in approved_uses):
                raise TypeError("approved_uses must be a tuple of strings or None")
            normalized_uses = tuple(item.strip().lower() for item in approved_uses)
            if any(not item or "," in item for item in normalized_uses):
                raise ValueError("approved_uses items must be non-empty identifiers without commas")
            if any(item == "[]" for item in normalized_uses):
                raise ValueError("'[]' is reserved to encode an explicitly empty approved_uses tuple")
            metadata["approved_uses"] = normalized_uses
        else:
            metadata["approved_uses"] = None

        return metadata
