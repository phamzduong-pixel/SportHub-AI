import os
import re
from dataclasses import dataclass
from datetime import datetime
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
    ):
        self.repository = repository or KnowledgeRepository()
        self.retriever = retriever or SportsWebRetriever()
        self.knowledge_retriever = knowledge_retriever

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

        existing_entries = self.repository.list_entries()
        matched_entry = self._find_matching_entry(fact, existing_entries)

        if matched_entry:
            # Check for exact duplicate content
            if self._is_identical_content(matched_entry.answer, fact.answer):
                # Duplicate: Update timestamp if newer, but do not create duplicate or re-index
                if fact.collected_at and (not matched_entry.collected_at or fact.collected_at > matched_entry.collected_at):
                    matched_entry.collected_at = fact.collected_at
                return KnowledgeUpdateResult(
                    action=KnowledgeUpdateAction.DUPLICATE_SKIPPED,
                    entry_id=matched_entry.id,
                    message=f"Identical content already exists for entity '{fact.entity}' topic '{fact.topic}'. Duplicate skipped.",
                    entry=matched_entry,
                    is_indexed=False,
                )

            # Check for conflict vs safe update
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
            prev_snapshot = KnowledgeEntry(
                id=matched_entry.id,
                topic=matched_entry.topic,
                role=matched_entry.role,
                intent=matched_entry.intent,
                sport=matched_entry.sport,
                entity=matched_entry.entity,
                question=matched_entry.question,
                answer=matched_entry.answer,
                source_name=matched_entry.source_name,
                source_url=matched_entry.source_url,
                collected_at=matched_entry.collected_at,
                priority=matched_entry.priority,
                classification=matched_entry.classification,
                source=matched_entry.source,
            )

            matched_entry.answer = fact.answer
            matched_entry.source_name = fact.source_name
            matched_entry.source_url = fact.source_url
            matched_entry.collected_at = fact.collected_at
            matched_entry.priority = fact.priority
            matched_entry.classification = fact.classification
            matched_entry.source = f"{fact.source_name} ({fact.source_url})"

            # Incremental re-index of affected chunk only
            is_indexed = True
            if self.knowledge_retriever is not None and hasattr(self.knowledge_retriever, "update_entry"):
                is_indexed = self.knowledge_retriever.update_entry(matched_entry, force=True)

            if persist_markdown:
                self._persist_entry_to_markdown(matched_entry)

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

        if persist_markdown:
            self._persist_entry_to_markdown(new_entry)

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
        target_dir = os.path.join(self.repository.knowledge_root, "sports", "auto_updated")
        os.makedirs(target_dir, exist_ok=True)
        target_file = os.path.join(target_dir, "auto_updated_knowledge.md")

        if not os.path.exists(target_file):
            with open(target_file, "w", encoding="utf-8") as f:
                f.write("# Auto-Updated Sports Knowledge\n\n---\n\n")
                f.write("| ID | Topic | Role | Intent | Sport | Entity | Question | Answer | Source_Name | Source_URL | Collected_At | Priority | Classification |\n")
                f.write("|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")

        row = (
            f"| {entry.id} | {entry.topic} | {entry.role} | {entry.intent} | {entry.sport or ''} | "
            f"{entry.entity or ''} | {entry.question} | {entry.answer} | {entry.source_name or ''} | "
            f"{entry.source_url or ''} | {entry.collected_at or ''} | {entry.priority} | {entry.classification} |\n"
        )
        with open(target_file, "a", encoding="utf-8") as f:
            f.write(row)
