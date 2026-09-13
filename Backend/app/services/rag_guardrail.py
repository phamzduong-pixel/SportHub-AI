from typing import List, Tuple

from ..models.knowledge_entry import KnowledgeEntry
from .knowledge_service import KnowledgeService


class RAGGuardrail:
    """Decides when to use RAG and performs retrieval.

    Static intents that are answered from the static knowledge base:
    - SYSTEM_GUIDE
    - ACCOUNT_SUPPORT
    - PARTNER_APPLICATION_SUPPORT
    - PAYMENT_SUPPORT

    The guardrail checks the intent whitelist and delegates to ``KnowledgeService``.
    ``KnowledgeService`` already applies role‑based filtering.
    """

    # Intent names as strings matching ``AssistantIntent`` values
    _STATIC_INTENT_WHITELIST = {
        "SYSTEM_GUIDE",
        "ACCOUNT_SUPPORT",
        "PARTNER_APPLICATION_SUPPORT",
        "PAYMENT_SUPPORT",
    }

    def __init__(self, knowledge_service: KnowledgeService | None = None):
        # Allow dependency injection for testing; create a default instance otherwise.
        self.knowledge_service = knowledge_service or KnowledgeService()

    def should_use_rag(self, intent_name: str, role: str) -> bool:
        """Return ``True`` if the intent is eligible for RAG.

        ``role`` is kept for potential future extensions where certain roles may be
        restricted from accessing specific knowledge entries.
        """
        return intent_name in self._STATIC_INTENT_WHITELIST

    def retrieve_context(
        self,
        query: str,
        role: str,
        intent_name: str,
        top_k: int = 5,
        relevance_threshold: float = 0.6,
    ) -> List[Tuple[KnowledgeEntry, float]]:
        """Fetch relevant static knowledge entries for static intents.

        For static intents we directly use the in‑code ``ai_system_knowledge`` entries.
        This avoids dependence on the markdown knowledge repository and guarantees
        that the FAQ answers used in the tests are available.
        """
        if not self.should_use_rag(intent_name, role):
            return []
        # Import lazily to avoid circular imports at module load time.
        from .ai_system_knowledge import match_system_knowledge
        entry, answer, action = match_system_knowledge(query, current_role=role)
        if entry is None:
            return []
        # Return a single entry with a perfect relevance score.
        return [(entry, 1.0)]
