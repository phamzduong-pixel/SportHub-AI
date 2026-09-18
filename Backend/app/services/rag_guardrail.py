from typing import List, Tuple

from ..models.knowledge_entry import KnowledgeEntry
from ..schemas.ai import AssistantMode
from .knowledge_service import KnowledgeService, get_knowledge_service
from .sports_web_retriever import SportsWebEvidence, SportsWebRetriever


class RAGGuardrail:
    """Decides when to use RAG and performs retrieval.

    Static intents that are answered from the static knowledge base:
    - SYSTEM_GUIDE
    - ACCOUNT_SUPPORT
    - PARTNER_APPLICATION_SUPPORT
    - PAYMENT_SUPPORT
    - SPORTS_KNOWLEDGE

    The guardrail checks the intent whitelist and delegates to ``KnowledgeService``.
    ``KnowledgeService`` already applies role‑based filtering.
    Controlled Web Retrieval is permitted ONLY for ``SPORTS_KNOWLEDGE``.
    """

    # Intent names as strings matching ``AssistantIntent`` values
    _STATIC_INTENT_WHITELIST = {
        "SYSTEM_GUIDE",
        "ACCOUNT_SUPPORT",
        "PARTNER_APPLICATION_SUPPORT",
        "PAYMENT_SUPPORT",
        "SPORTS_KNOWLEDGE",
    }

    def __init__(
        self,
        knowledge_service: KnowledgeService | None = None,
        web_retriever: SportsWebRetriever | None = None,
    ):
        # Allow dependency injection for testing; create a default instance otherwise.
        self.knowledge_service = knowledge_service or get_knowledge_service()
        self.web_retriever = web_retriever or SportsWebRetriever()

    def should_use_rag(
        self, intent_name: str, role: str, assistant_mode: AssistantMode | str = AssistantMode.NATURAL,
    ) -> bool:
        """Return ``True`` if the intent is eligible for RAG under the current mode.

        ``role`` is kept for potential future extensions where certain roles may be
        restricted from accessing specific knowledge entries.
        """
        if assistant_mode in (AssistantMode.PROFESSIONAL, 'PROFESSIONAL') and intent_name == "SPORTS_KNOWLEDGE":
            return False
        return intent_name in self._STATIC_INTENT_WHITELIST

    def can_retrieve_web(
        self, intent_name: str, sport: str | None = None, assistant_mode: AssistantMode | str = AssistantMode.NATURAL,
    ) -> bool:
        """Return ``True`` if the intent and sport are eligible for controlled Web Retrieval."""
        if assistant_mode in (AssistantMode.PROFESSIONAL, 'PROFESSIONAL'):
            return False
        return self.web_retriever.can_retrieve(intent=intent_name, sport=sport)

    def retrieve_context(
        self,
        query: str,
        role: str,
        intent_name: str,
        sport: str | None = None,
        entity: str | None = None,
        top_k: int = 5,
        relevance_threshold: float = 0.6,
        assistant_mode: AssistantMode | str = AssistantMode.NATURAL,
    ) -> List[Tuple[KnowledgeEntry, float]]:
        """Fetch relevant static knowledge entries for static or sports intents."""
        if not self.should_use_rag(intent_name, role, assistant_mode=assistant_mode):
            return []

        if intent_name == "SPORTS_KNOWLEDGE":
            return self.knowledge_service.retrieve(
                query=query,
                role=role,
                intent=intent_name,
                sport=sport,
                entity=entity,
                top_k=top_k,
                relevance_threshold=relevance_threshold,
            )

        # For system static intents we directly use the in‑code ``ai_system_knowledge`` entries.
        # This avoids dependence on the markdown knowledge repository and guarantees
        # that the FAQ answers used in the tests are available.
        from .ai_system_knowledge import match_system_knowledge
        entry, answer, action = match_system_knowledge(query, current_role=role)
        if entry is None:
            return []
        # Return a single entry with a perfect relevance score.
        return [(entry, 1.0)]

    def evaluate_freshness_and_sufficiency(
        self,
        query: str,
        internal_entries: List[Tuple[KnowledgeEntry, float]],
        current_date_str: str = "2026-09-17",
    ):
        """Evaluate whether internal knowledge is fresh & sufficient or web retrieval is needed."""
        return self.web_retriever.evaluate_freshness_and_sufficiency(
            query=query,
            internal_entries=internal_entries,
            current_date_str=current_date_str,
        )

    def merge_and_prefer_evidence(
        self,
        query: str,
        internal_entries: List[Tuple[KnowledgeEntry, float]],
        web_evidences: List[SportsWebEvidence],
    ) -> List[Tuple[KnowledgeEntry, float]]:
        """Merge internal entries and web evidences with freshness precedence."""
        return self.web_retriever.merge_and_prefer_evidence(
            query=query,
            internal_entries=internal_entries,
            web_evidences=web_evidences,
        )

    def retrieve_web_context(
        self,
        query: str,
        intent_name: str,
        sport: str | None = None,
        entity: str | None = None,
        assistant_mode: AssistantMode | str = AssistantMode.NATURAL,
    ) -> List[SportsWebEvidence]:
        """Fetch controlled web evidence for SPORTS_KNOWLEDGE only."""
        if not self.can_retrieve_web(intent_name, sport, assistant_mode=assistant_mode):
            return []
        return self.web_retriever.retrieve_evidence(
            query=query,
            intent=intent_name,
            sport=sport,
            entity=entity,
        )

