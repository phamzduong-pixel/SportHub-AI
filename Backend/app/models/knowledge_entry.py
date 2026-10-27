from dataclasses import dataclass


OPTIONAL_KNOWLEDGE_METADATA_FIELDS = (
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
    "approved_uses",
    "authoring_type",
    "record_status",
)


@dataclass
class KnowledgeEntry:
    id: str
    topic: str
    role: str
    intent: str
    question: str
    answer: str
    source: str
    classification: str
    sport: str | None = None
    entity: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    collected_at: str | None = None
    priority: int = 0
    source_title: str | None = None
    source_version: str | None = None
    verified_at: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    rule_set: str | None = None
    jurisdiction: str | None = None
    rights_status: str | None = None
    license: str | None = None
    rights_evidence_url: str | None = None
    rights_checked_at: str | None = None
    approved_uses: tuple[str, ...] | None = None
    authoring_type: str | None = None
    record_status: str | None = None

    @property
    def content(self) -> str:
        """Combined question and answer content representation."""
        return f"{self.question} {self.answer}".strip()
