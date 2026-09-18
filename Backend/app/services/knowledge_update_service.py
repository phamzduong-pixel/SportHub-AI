import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..models.knowledge_entry import KnowledgeEntry
from ..repositories.knowledge_repository import KnowledgeRepository
from .ai_intent_router import is_supported_sport
from .knowledge_retriever import KnowledgeRetriever
from .sports_knowledge_updater import (
    ExtractedSportsFact,
    FactValidationResult,
    FactValidationStatus,
    KnowledgeUpdateAction,
    KnowledgeUpdateResult,
    SportsKnowledgeUpdater,
)
from .sports_web_retriever import (
    DEFAULT_SPORTS_SOURCE_WHITELIST,
    SportsWebEvidence,
    SportsWebRetriever,
)

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeUpdateSummary:
    """Summary of a Knowledge Update job execution."""
    total_sources_scanned: int = 0
    collected: int = 0
    accepted: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    rejected: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0
    status: str = "COMPLETED"  # "COMPLETED", "PARTIAL_SUCCESS", "FAILED"
    details: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_sources_scanned": self.total_sources_scanned,
            "collected": self.collected,
            "accepted": self.accepted,
            "inserted": self.inserted,
            "updated": self.updated,
            "skipped": self.skipped,
            "rejected": self.rejected,
            "errors": self.errors,
            "duration_seconds": round(self.duration_seconds, 3),
            "status": self.status,
            "timestamp": self.timestamp,
            "details_count": len(self.details),
        }


class KnowledgeUpdateService:
    """
    Dedicated Service for Sports Knowledge Base Updates.
    
    Orchestrates the complete lifecycle:
    Approved Web -> Collect -> Extract Fact -> Validate -> Update Knowledge -> Summary Report
    
    Guarantees:
    1. Only approved sports web sources are processed.
    2. Only 6 supported sports (football, badminton, pickleball, tennis, basketball, volleyball).
    3. Strict validation before writing.
    4. Handles insert, update, duplicate skip, and conflict rejection.
    5. Preserves full provenance (source_url, source_name, entity, sport, collected_at).
    6. Error resilience: Single source/item failures do not crash the entire update job.
    7. Provides comprehensive execution summaries.
    """

    def __init__(
        self,
        repository: Optional[KnowledgeRepository] = None,
        retriever: Optional[KnowledgeRetriever] = None,
        web_retriever: Optional[SportsWebRetriever] = None,
        updater: Optional[SportsKnowledgeUpdater] = None,
    ):
        self.repository = repository or KnowledgeRepository()
        self.retriever = retriever or KnowledgeRetriever(self.repository)
        self.web_retriever = web_retriever or SportsWebRetriever()
        self.updater = updater or SportsKnowledgeUpdater(
            repository=self.repository,
            retriever=self.web_retriever,
            knowledge_retriever=self.retriever,
        )
        self._last_summary: Optional[KnowledgeUpdateSummary] = None

    def get_last_summary(self) -> Optional[KnowledgeUpdateSummary]:
        """Return the summary of the most recent update job."""
        return self._last_summary

    def update_knowledge_pipeline(
        self,
        raw_items: List[Dict[str, Any]],
        persist_markdown: bool = False,
    ) -> KnowledgeUpdateSummary:
        """
        Execute full update pipeline on a collection of raw web scraper / API items:
        Extract -> Validate -> Upsert -> Index -> Summarize
        """
        start_time = time.time()
        summary = KnowledgeUpdateSummary(
            total_sources_scanned=len(raw_items),
            collected=len(raw_items),
        )

        for idx, item in enumerate(raw_items):
            try:
                # 1. Extraction step
                fact = self.updater.extract_facts_from_raw_web_item(item)
                
                # 2. Validation step
                validation: FactValidationResult = self.updater.validate_fact(fact)
                if not validation.is_valid:
                    summary.rejected += 1
                    summary.details.append({
                        "index": idx,
                        "entity": fact.entity,
                        "sport": fact.sport,
                        "source_url": fact.source_url,
                        "action": KnowledgeUpdateAction.REJECTED.value,
                        "reason": validation.reason,
                        "status": validation.status.value,
                    })
                    continue

                summary.accepted += 1

                # 3. Knowledge Persistence / Upsert step
                update_result: KnowledgeUpdateResult = self.updater.apply_fact_update(
                    fact,
                    persist_markdown=persist_markdown,
                )

                # 4. Record action
                if update_result.action == KnowledgeUpdateAction.INSERTED:
                    summary.inserted += 1
                elif update_result.action == KnowledgeUpdateAction.UPDATED:
                    summary.updated += 1
                elif update_result.action == KnowledgeUpdateAction.DUPLICATE_SKIPPED:
                    summary.skipped += 1
                elif update_result.action in (KnowledgeUpdateAction.CONFLICT_REJECTED, KnowledgeUpdateAction.REJECTED):
                    summary.rejected += 1

                summary.details.append({
                    "index": idx,
                    "entity": fact.entity,
                    "sport": fact.sport,
                    "source_url": fact.source_url,
                    "action": update_result.action.value,
                    "entry_id": update_result.entry_id,
                    "message": update_result.message,
                    "is_indexed": update_result.is_indexed,
                })

            except Exception as e:
                item_url = item.get("url") if isinstance(item, dict) else "unknown"
                item_title = item.get("title") if isinstance(item, dict) else "unknown"
                logger.error("Error processing item at index %d (%s): %s", idx, item_url, str(e))
                summary.errors.append({
                    "index": idx,
                    "url": item_url,
                    "title": item_title,
                    "error": str(e),
                })

        summary.duration_seconds = time.time() - start_time
        if summary.errors and summary.accepted == 0 and summary.total_sources_scanned > 0:
            summary.status = "FAILED"
        elif summary.errors:
            summary.status = "PARTIAL_SUCCESS"
        else:
            summary.status = "COMPLETED"

        self._last_summary = summary
        return summary

    def update_from_web_evidence(
        self,
        evidence_list: List[SportsWebEvidence],
        topic: str = "general",
        question: Optional[str] = None,
        persist_markdown: bool = False,
    ) -> KnowledgeUpdateSummary:
        """
        Execute update pipeline from a list of validated SportsWebEvidence objects.
        """
        start_time = time.time()
        summary = KnowledgeUpdateSummary(
            total_sources_scanned=len(evidence_list),
            collected=len(evidence_list),
        )

        for idx, evidence in enumerate(evidence_list):
            try:
                # 1. Extraction from evidence
                fact = self.updater.extract_fact_from_evidence(
                    evidence,
                    topic=topic,
                    question=question,
                )

                # 2. Validation
                validation = self.updater.validate_fact(fact)
                if not validation.is_valid:
                    summary.rejected += 1
                    summary.details.append({
                        "index": idx,
                        "entity": fact.entity,
                        "sport": fact.sport,
                        "source_url": fact.source_url,
                        "action": KnowledgeUpdateAction.REJECTED.value,
                        "reason": validation.reason,
                    })
                    continue

                summary.accepted += 1

                # 3. Update & Index
                update_result = self.updater.apply_fact_update(fact, persist_markdown=persist_markdown)

                if update_result.action == KnowledgeUpdateAction.INSERTED:
                    summary.inserted += 1
                elif update_result.action == KnowledgeUpdateAction.UPDATED:
                    summary.updated += 1
                elif update_result.action == KnowledgeUpdateAction.DUPLICATE_SKIPPED:
                    summary.skipped += 1
                elif update_result.action in (KnowledgeUpdateAction.CONFLICT_REJECTED, KnowledgeUpdateAction.REJECTED):
                    summary.rejected += 1

                summary.details.append({
                    "index": idx,
                    "entity": fact.entity,
                    "sport": fact.sport,
                    "source_url": fact.source_url,
                    "action": update_result.action.value,
                    "entry_id": update_result.entry_id,
                    "message": update_result.message,
                    "is_indexed": update_result.is_indexed,
                })

            except Exception as e:
                logger.error("Error processing evidence item at index %d: %s", idx, str(e))
                summary.errors.append({
                    "index": idx,
                    "url": evidence.url,
                    "title": evidence.title,
                    "error": str(e),
                })

        summary.duration_seconds = time.time() - start_time
        if summary.errors and summary.accepted == 0 and summary.total_sources_scanned > 0:
            summary.status = "FAILED"
        elif summary.errors:
            summary.status = "PARTIAL_SUCCESS"
        else:
            summary.status = "COMPLETED"

        self._last_summary = summary
        return summary

    def run_targeted_update(
        self,
        query: str,
        sport: Optional[str] = None,
        entity: Optional[str] = None,
        persist_markdown: bool = False,
    ) -> KnowledgeUpdateSummary:
        """
        Run targeted update by querying approved web sources for a specific query/entity,
        validating, and updating the Knowledge Base.
        """
        # Collect approved web evidence
        web_evidences = self.web_retriever.retrieve(
            query=query,
            sport=sport,
            entity=entity,
        )
        return self.update_from_web_evidence(
            evidence_list=web_evidences,
            question=query,
            persist_markdown=persist_markdown,
        )


class KnowledgeUpdateJobManager:
    """
    Singleton / Thread-safe manager to coordinate background Knowledge Update Jobs.
    
    Guarantees:
    - Mutex lock preventing concurrent / duplicate execution of update jobs.
    - Observability into currently running job ID and latest update summary.
    """

    import threading
    _lock = threading.Lock()
    _is_running: bool = False
    _current_job_id: Optional[str] = None
    _last_summary: Optional[KnowledgeUpdateSummary] = None

    @classmethod
    def is_running(cls) -> bool:
        with cls._lock:
            return cls._is_running

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        with cls._lock:
            return {
                "is_running": cls._is_running,
                "current_job_id": cls._current_job_id,
                "last_summary": cls._last_summary.to_dict() if cls._last_summary else None,
            }

    @classmethod
    def trigger_job(
        cls,
        service: Optional[KnowledgeUpdateService] = None,
        query: Optional[str] = None,
        sport: Optional[str] = None,
        entity: Optional[str] = None,
        raw_items: Optional[List[Dict[str, Any]]] = None,
        persist_markdown: bool = False,
    ) -> Tuple[bool, str, Optional[KnowledgeUpdateSummary], Optional[str]]:
        """
        Acquire lock and trigger Knowledge Update Job.
        
        Returns:
            Tuple of (success, message, summary, job_id)
        """
        import uuid

        with cls._lock:
            if cls._is_running:
                return (
                    False,
                    "Một tiến trình cập nhật tri thức thể thao đang được thực thi. Vui lòng chờ hoàn tất.",
                    None,
                    cls._current_job_id,
                )
            cls._is_running = True
            job_id = f"JOB-{uuid.uuid4().hex[:8].upper()}"
            cls._current_job_id = job_id

        update_service = service or KnowledgeUpdateService()
        try:
            if raw_items:
                summary = update_service.update_knowledge_pipeline(
                    raw_items=raw_items,
                    persist_markdown=persist_markdown,
                )
            elif query:
                summary = update_service.run_targeted_update(
                    query=query,
                    sport=sport,
                    entity=entity,
                    persist_markdown=persist_markdown,
                )
            else:
                # Default targeted sports update across supported sport federations
                summary = update_service.run_targeted_update(
                    query="thông tin thể thao cập nhật",
                    sport=sport,
                    entity=entity,
                    persist_markdown=persist_markdown,
                )

            with cls._lock:
                cls._last_summary = summary
            return True, "Cập nhật tri thức thể thao hoàn tất thành công.", summary, job_id

        except Exception as e:
            logger.error("Failed to execute knowledge update job %s: %s", job_id, str(e))
            with cls._lock:
                cls._last_summary = KnowledgeUpdateSummary(
                    total_sources_scanned=0,
                    status="FAILED",
                    errors=[{"error": str(e)}],
                )
            return False, f"Lỗi thực thi cập nhật tri thức: {str(e)}", cls._last_summary, job_id

        finally:
            with cls._lock:
                cls._is_running = False
                cls._current_job_id = None
