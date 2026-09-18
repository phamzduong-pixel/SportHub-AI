import os
import re
from typing import List, Optional, Tuple, Dict, Any

from ..models.knowledge_entry import KnowledgeEntry


class KnowledgeRepository:
    """Loads static knowledge entries from markdown files.

    The markdown files under ``docs/AI/knowledge`` contain tables with structured
    knowledge and metadata across general topics and sports subfolders:
    - ``docs/AI/knowledge/customer.md``
    - ``docs/AI/knowledge/general.md``
    - ``docs/AI/knowledge/sports/`` (including subfolders: players/, national_teams/, thai_nguyen/)

    Supports both legacy 8-column format:
        ID | Topic | Role | Intent | Question | Answer | Source | Classification

    and extended 13-column metadata format:
        ID | Topic | Role | Intent | Sport | Entity | Question | Answer | Source_Name | Source_URL | Collected_At | Priority | Classification
    """

    def __init__(self, knowledge_root: str = None):
        if knowledge_root is None:
            knowledge_root = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "AI", "knowledge")
            )
        self.knowledge_root = knowledge_root
        self._entries: List[KnowledgeEntry] = []
        self._load_entries()

    def _load_entries(self) -> None:
        """Read all ``*.md`` files recursively and extract table rows into KnowledgeEntry instances.

        Deduplicates entries by ``id`` and parses all metadata fields.
        """
        if not os.path.exists(self.knowledge_root):
            return

        seen_ids = set()

        for root, _, files in os.walk(self.knowledge_root):
            for fname in sorted(files):
                if not fname.lower().endswith('.md'):
                    continue
                path = os.path.join(root, fname)
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                header_map = None
                for line in lines:
                    stripped = line.strip()
                    if not stripped.startswith('|'):
                        continue
                    # Skip table separator lines e.g. |---|---|
                    if re.match(r"^\|[-:|\s]+\|$", stripped):
                        continue

                    parts = [p.strip() for p in stripped.split('|')[1:-1]]
                    if not parts:
                        continue

                    # Check if this is a header row
                    first_col = parts[0].lower()
                    if first_col in ('id', '#', 'stt', 'entry_id', 'mã'):
                        header_map = {
                            p.lower().replace(' ', '_').replace('-', '_'): i
                            for i, p in enumerate(parts)
                        }
                        continue

                    entry_id = parts[0]
                    if not entry_id or entry_id in seen_ids:
                        continue

                    entry = None
                    if header_map and 'question' in header_map and 'answer' in header_map:
                        priority_val = 0
                        if 'priority' in header_map and header_map['priority'] < len(parts):
                            try:
                                priority_val = int(parts[header_map['priority']])
                            except (ValueError, TypeError):
                                priority_val = 0

                        source_name = parts[header_map['source_name']] if 'source_name' in header_map and header_map['source_name'] < len(parts) else None
                        source_url = parts[header_map['source_url']] if 'source_url' in header_map and header_map['source_url'] < len(parts) else None
                        collected_at = parts[header_map['collected_at']] if 'collected_at' in header_map and header_map['collected_at'] < len(parts) else None
                        sport = parts[header_map['sport']] if 'sport' in header_map and header_map['sport'] < len(parts) else None
                        entity = parts[header_map['entity']] if 'entity' in header_map and header_map['entity'] < len(parts) else None
                        source = parts[header_map['source']] if 'source' in header_map and header_map['source'] < len(parts) else (
                            f"{source_name} ({source_url})" if source_name and source_url else (source_name or source_url or "")
                        )
                        classification = parts[header_map['classification']].lower() if 'classification' in header_map and header_map['classification'] < len(parts) else "static"

                        entry = KnowledgeEntry(
                            id=entry_id,
                            topic=parts[header_map.get('topic', 1)] if header_map.get('topic', 1) < len(parts) else "",
                            role=parts[header_map.get('role', 2)] if header_map.get('role', 2) < len(parts) else "CUSTOMER",
                            intent=parts[header_map.get('intent', 3)] if header_map.get('intent', 3) < len(parts) else "SPORTS_KNOWLEDGE",
                            question=parts[header_map['question']],
                            answer=parts[header_map['answer']],
                            source=source,
                            classification=classification,
                            sport=sport,
                            entity=entity,
                            source_name=source_name,
                            source_url=source_url,
                            collected_at=collected_at,
                            priority=priority_val,
                        )
                    elif len(parts) >= 13:
                        # Standard 13-column sports knowledge table
                        try:
                            priority_val = int(parts[11])
                        except (ValueError, TypeError):
                            priority_val = 0
                        source_label = parts[8]
                        if parts[9]:
                            source_label = f"{source_label} ({parts[9]})" if source_label else parts[9]
                        entry = KnowledgeEntry(
                            id=parts[0],
                            topic=parts[1],
                            role=parts[2],
                            intent=parts[3],
                            sport=parts[4],
                            entity=parts[5],
                            question=parts[6],
                            answer=parts[7],
                            source_name=parts[8],
                            source_url=parts[9],
                            collected_at=parts[10],
                            priority=priority_val,
                            classification=parts[12].lower(),
                            source=source_label,
                        )
                    elif len(parts) >= 8:
                        # Legacy 8-column general knowledge table
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

                    if entry:
                        seen_ids.add(entry.id)
                        self._entries.append(entry)

    def list_entries(self) -> List[KnowledgeEntry]:
        """Return all loaded entries."""
        return list(self._entries)

    def get_static_entries(self) -> List[KnowledgeEntry]:
        """Return only entries whose ``classification`` is ``static``."""
        return [e for e in self._entries if e.classification == "static"]

    def get_entry_by_id(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """Find an entry by its unique ID."""
        for entry in self._entries:
            if entry.id == entry_id:
                return entry
        return None

    def upsert_entry(self, entry: KnowledgeEntry) -> Tuple[bool, bool]:
        """Insert a new entry or update an existing one in-memory.

        Returns:
            Tuple[bool, bool]: (is_new, is_updated)
        """
        for i, existing in enumerate(self._entries):
            if existing.id == entry.id:
                is_changed = (
                    existing.answer != entry.answer
                    or existing.question != entry.question
                    or existing.topic != entry.topic
                    or existing.entity != entry.entity
                    or existing.sport != entry.sport
                )
                if not is_changed:
                    # Update metadata only if newer/present without marking content updated
                    if entry.collected_at and (not existing.collected_at or entry.collected_at > existing.collected_at):
                        existing.collected_at = entry.collected_at
                    if entry.source_url:
                        existing.source_url = entry.source_url
                    if entry.source_name:
                        existing.source_name = entry.source_name
                    return False, False

                self._entries[i] = entry
                return False, True

        self._entries.append(entry)
        return True, False

    def remove_entry(self, entry_id: str) -> bool:
        """Remove an entry by ID from the repository."""
        initial_len = len(self._entries)
        self._entries = [e for e in self._entries if e.id != entry_id]
        return len(self._entries) < initial_len


_shared_repository_instance: Optional[KnowledgeRepository] = None


def get_knowledge_repository(knowledge_root: Optional[str] = None) -> KnowledgeRepository:
    global _shared_repository_instance
    if _shared_repository_instance is None or knowledge_root is not None:
        repo = KnowledgeRepository(knowledge_root=knowledge_root)
        if knowledge_root is None:
            _shared_repository_instance = repo
        return repo
    return _shared_repository_instance


def reset_shared_knowledge_repository() -> None:
    global _shared_repository_instance
    _shared_repository_instance = None
