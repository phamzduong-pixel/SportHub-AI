import os
import difflib
from typing import List, Tuple, Optional

import numpy as np
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None
from sklearn.metrics.pairwise import cosine_similarity

from ..models.knowledge_entry import KnowledgeEntry
from ..repositories.knowledge_repository import KnowledgeRepository


class KnowledgeRetriever:
    """Retrieve static knowledge entries based on a user query.

    The retriever supports:
    - keyword fuzzy matching (difflib.SequenceMatcher)
    - optional semantic similarity using a lightweight sentence‑transformer
    - role and intent filtering
    - top‑k selection and relevance gating
    """

    RELEVANCE_THRESHOLD = 0.60  # can be overridden by caller
    DEFAULT_TOP_K = 5
    # Use a small model that works on Windows without heavy GPU requirements
    EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self, repository: KnowledgeRepository = None, use_semantic: bool = True):
        self.repo = repository or KnowledgeRepository()
        self.use_semantic = use_semantic
        self._static_entries: List[KnowledgeEntry] = self.repo.get_static_entries()
        if self.use_semantic and SentenceTransformer is not None:
            self._model = SentenceTransformer(self.EMBEDDING_MODEL_NAME)
            # Pre‑compute embeddings for all static questions
            questions = [e.question for e in self._static_entries]
            self._embeddings = self._model.encode(questions, batch_size=32, show_progress_bar=False)
        else:
            self.use_semantic = False
            self._model = None
            self._embeddings = None

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.lower().split())

    def _keyword_score(self, query: str, question: str) -> float:
        # Simple fuzzy ratio in range [0, 1]
        return difflib.SequenceMatcher(None, self._normalize(query), self._normalize(question)).ratio()

    def _semantic_score(self, query: str, question_idx: int) -> float:
        if not self.use_semantic:
            return 0.0
        query_emb = self._model.encode([query], show_progress_bar=False)[0]
        return float(cosine_similarity([query_emb], [self._embeddings[question_idx]])[0, 0])

    def retrieve(
        self,
        query: str,
        role: Optional[str] = None,
        intent: Optional[str] = None,
        top_k: int = DEFAULT_TOP_K,
        relevance_threshold: float = RELEVANCE_THRESHOLD,
    ) -> List[Tuple[KnowledgeEntry, float]]:
        """Return a list of (entry, score) sorted by descending relevance.

        If no entry reaches ``relevance_threshold`` an empty list is returned.
        """
        if not query:
            return []
        # Filter by role / intent first – role may be a comma‑separated list in the entry
        candidates = []
        for idx, entry in enumerate(self._static_entries):
            # Role filtering – entry.role may contain multiple roles separated by commas
            entry_roles = [r.strip().lower() for r in entry.role.split(',')]
            if role and role.lower() not in entry_roles:
                continue
            if intent and intent.upper() != entry.intent.upper():
                continue
            # Compute keyword similarity
            kw_score = self._keyword_score(query, entry.question)
            # Compute semantic similarity if enabled
            sem_score = self._semantic_score(query, idx) if self.use_semantic else 0.0
            # Combine – simple average when both are available, otherwise use whichever exists
            if self.use_semantic:
                combined = (kw_score + sem_score) / 2.0
            else:
                combined = kw_score
            candidates.append((entry, combined))

        # Sort by combined score descending
        candidates.sort(key=lambda x: x[1], reverse=True)
        # Keep top‑k
        top_candidates = candidates[:top_k]
        # Apply relevance gate
        if not top_candidates or top_candidates[0][1] < relevance_threshold:
            return []
        return top_candidates
