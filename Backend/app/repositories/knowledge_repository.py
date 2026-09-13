import os
import re
from typing import List

from ..models.knowledge_entry import KnowledgeEntry


class KnowledgeRepository:
    """Loads static knowledge entries from markdown files.

    The markdown files under ``docs/AI/knowledge`` contain a table with the
    following columns (in order)::

        ID | Topic | Role | Intent | Question | Answer | Source | Classification

    ``KnowledgeRepository`` parses each table row into a :class:`KnowledgeEntry`
    instance. Only entries with ``classification`` equal to ``static`` are kept –
    dynamic entries are ignored by the retrieval layer.
    """

    def __init__(self, knowledge_root: str = None):
        # Default to repository root relative to this file
        if knowledge_root is None:
            # ``Backend/app/repositories`` -> go up two levels then to docs/AI/knowledge
            knowledge_root = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "AI", "knowledge")
            )
        self.knowledge_root = knowledge_root
        self._entries: List[KnowledgeEntry] = []
        self._load_entries()

    def _load_entries(self) -> None:
        """Read all ``*.md`` files and extract table rows.

        Files that do not contain a markdown table are ignored.
        """
        for fname in os.listdir(self.knowledge_root):
            if not fname.lower().endswith('.md'):
                continue
            path = os.path.join(self.knowledge_root, fname)
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            # Find lines that start a table row ("|" as first char after optional spaces)
            for line in lines:
                stripped = line.strip()
                if not stripped.startswith('|'):
                    continue
                # Skip header separator rows (e.g., "|---|---|")
                if re.match(r"^\|[-:|\s]+\|$", stripped):
                    continue
                # Split on '|' and discard the first (empty) and last empty entries
                parts = [p.strip() for p in stripped.split('|')[1:-1]]
                if len(parts) != 8:
                    # Not a valid knowledge row – ignore
                    continue
                entry = KnowledgeEntry(
                    id=parts[0],
                    topic=parts[1],
                    role=parts[2],
                    intent=parts[3],
                    question=parts[4],
                    answer=parts[5],
                    source=parts[6],
                    classification=parts[7].lower(),
                )
                # Only keep static entries – dynamic ones are filtered later but
                # we store them anyway for completeness.
                self._entries.append(entry)

    def list_entries(self) -> List[KnowledgeEntry]:
        """Return all loaded entries.
        """
        return list(self._entries)

    def get_static_entries(self) -> List[KnowledgeEntry]:
        """Convenience: return only entries whose ``classification`` is ``static``.
        """
        return [e for e in self._entries if e.classification == "static"]
