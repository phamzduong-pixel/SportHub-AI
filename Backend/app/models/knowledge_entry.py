from dataclasses import dataclass


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

    @property
    def content(self) -> str:
        """Combined question and answer content representation."""
        return f"{self.question} {self.answer}".strip()
