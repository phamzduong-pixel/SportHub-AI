import os
from typing import List, Tuple, Optional, Any

from ..models.knowledge_entry import KnowledgeEntry
from .knowledge_retriever import KnowledgeRetriever
from ..repositories.knowledge_repository import KnowledgeRepository, get_knowledge_repository


class KnowledgeService:
    """High‑level service used by the AI assistant.

    It delegates to :class:`KnowledgeRetriever` and applies the *Relevance Gate*.
    If the caller's intent is ``OUT_OF_SCOPE`` or no entry meets the
    ``relevance_threshold`` a sentinel ``NO_KNOWLEDGE`` is returned.
    """

    NO_KNOWLEDGE = "NO_KNOWLEDGE"

    def __init__(self, repository: KnowledgeRepository = None, retriever: KnowledgeRetriever = None):
        self.repo = repository or get_knowledge_repository()
        self.retriever = retriever or KnowledgeRetriever(self.repo)

    def retrieve(
        self,
        query: str,
        role: Optional[str] = None,
        intent: Optional[str] = None,
        sport: Optional[str] = None,
        entity: Optional[str] = None,
        top_k: int = KnowledgeRetriever.DEFAULT_TOP_K,
        relevance_threshold: float = KnowledgeRetriever.RELEVANCE_THRESHOLD,
    ) -> List[Tuple[KnowledgeEntry, float]]:
        """Return a list of (entry, score) or ``NO_KNOWLEDGE``.

        Parameters
        ----------
        query: str
            User query string.
        role: str | None
            Caller role (e.g., ``CUSTOMER``, ``OWNER``, ``ADMIN``).
        intent: str | None
            Intent enum name. If ``OUT_OF_SCOPE`` the method short‑circuits.
        sport: str | None
            Sport name to filter entries by.
        entity: str | None
            Entity name to prioritize.
        top_k: int
            Number of candidates to consider.
        relevance_threshold: float
            Minimum score required for a result to be considered relevant.
        """
        if intent and intent.upper() == "OUT_OF_SCOPE":
            return []
        results = self.retriever.retrieve(
            query=query,
            role=role,
            intent=intent,
            sport=sport,
            entity=entity,
            top_k=top_k,
            relevance_threshold=relevance_threshold,
        )
        if not results:
            return []
        return results

    def index_entry(self, entry: KnowledgeEntry) -> bool:
        """Incrementally index a knowledge entry in retriever and repository."""
        self.repo.upsert_entry(entry)
        return self.retriever.index_entry(entry)

    def update_entry(self, entry: KnowledgeEntry) -> bool:
        """Incrementally update an existing entry in retriever and repository."""
        self.repo.upsert_entry(entry)
        return self.retriever.update_entry(entry)

    def remove_entry(self, entry_id: str) -> bool:
        """Remove an entry from retriever and repository."""
        self.repo.remove_entry(entry_id)
        return self.retriever.remove_entry(entry_id)

    def apply_fact_update(
        self,
        fact: Any,
        persist_markdown: bool = False,
    ) -> Any:
        """Apply sports fact update through SportsKnowledgeUpdater and incrementally sync index."""
        from .sports_knowledge_updater import SportsKnowledgeUpdater, KnowledgeUpdateAction

        updater = SportsKnowledgeUpdater(repository=self.repo, knowledge_retriever=self.retriever)
        result = updater.apply_fact_update(fact, persist_markdown=persist_markdown)
        return result


_shared_knowledge_service_instance: Optional[KnowledgeService] = None


def get_knowledge_service(
    repository: Optional[KnowledgeRepository] = None,
    retriever: Optional[KnowledgeRetriever] = None,
) -> KnowledgeService:
    global _shared_knowledge_service_instance
    if _shared_knowledge_service_instance is None or repository is not None or retriever is not None:
        service = KnowledgeService(repository=repository, retriever=retriever)
        if repository is None and retriever is None:
            _shared_knowledge_service_instance = service
        return service
    return _shared_knowledge_service_instance


def reset_shared_knowledge_service() -> None:
    global _shared_knowledge_service_instance
    _shared_knowledge_service_instance = None
