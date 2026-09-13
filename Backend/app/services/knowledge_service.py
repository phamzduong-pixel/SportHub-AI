import os
from typing import List, Tuple, Optional

from ..models.knowledge_entry import KnowledgeEntry
from .knowledge_retriever import KnowledgeRetriever
from ..repositories.knowledge_repository import KnowledgeRepository


class KnowledgeService:
    """High‑level service used by the AI assistant.

    It delegates to :class:`KnowledgeRetriever` and applies the *Relevance Gate*.
    If the caller's intent is ``OUT_OF_SCOPE`` or no entry meets the
    ``relevance_threshold`` a sentinel ``NO_KNOWLEDGE`` is returned.
    """

    NO_KNOWLEDGE = "NO_KNOWLEDGE"

    def __init__(self, repository: KnowledgeRepository = None, retriever: KnowledgeRetriever = None):
        self.repo = repository or KnowledgeRepository()
        self.retriever = retriever or KnowledgeRetriever(self.repo)

    def retrieve(
        self,
        query: str,
        role: Optional[str] = None,
        intent: Optional[str] = None,
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
            top_k=top_k,
            relevance_threshold=relevance_threshold,
        )
        if not results:
            return []
        return results
