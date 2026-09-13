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
