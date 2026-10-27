from types import SimpleNamespace
from unittest.mock import Mock

from app.services.knowledge_retriever import KnowledgeRetriever
from app.services.knowledge_service import KnowledgeService
from app.services.rag_guardrail import RAGGuardrail


def _entry(entry_id: str, priority: int):
    return SimpleNamespace(
        id=entry_id,
        topic="rules",
        role="CUSTOMER",
        intent="SPORTS_KNOWLEDGE",
        sport="tennis",
        entity="tennis",
        question="What is a tennis serve fault?",
        answer="Synthetic retrieval test record.",
        priority=priority,
    )


def test_candidate_filter_runs_before_top_k_without_changing_default_behavior():
    blocked_high_rank = _entry("SYNTHETIC-BLOCKED", priority=10)
    eligible_lower_rank = _entry("SYNTHETIC-ELIGIBLE", priority=0)
    repository = SimpleNamespace(get_static_entries=lambda: [blocked_high_rank, eligible_lower_rank])
    retriever = KnowledgeRetriever(repository=repository)

    default_results = retriever.retrieve(
        "What is a tennis serve fault?", role="CUSTOMER", intent="SPORTS_KNOWLEDGE", top_k=1,
    )
    filtered_results = retriever.retrieve(
        "What is a tennis serve fault?", role="CUSTOMER", intent="SPORTS_KNOWLEDGE", top_k=1,
        candidate_filter=lambda entry: entry.id == "SYNTHETIC-ELIGIBLE",
    )

    assert default_results[0][0].id == "SYNTHETIC-BLOCKED"
    assert [entry.id for entry, _score in filtered_results] == ["SYNTHETIC-ELIGIBLE"]


def test_sports_guardrail_forwards_optional_filter_to_knowledge_service():
    repository = SimpleNamespace()
    retriever = SimpleNamespace(retrieve=Mock(return_value=[]))
    knowledge_service = KnowledgeService(repository=repository, retriever=retriever)
    guardrail = RAGGuardrail(knowledge_service=knowledge_service)
    policy_filter = lambda entry: entry.id == "SYNTHETIC-ELIGIBLE"

    guardrail.retrieve_context(
        "a synthetic sports query", "CUSTOMER", "SPORTS_KNOWLEDGE", sport="tennis",
        assistant_mode="NATURAL", candidate_filter=policy_filter,
    )

    assert retriever.retrieve.call_args.kwargs["candidate_filter"] is policy_filter

    # Omitting the new argument must preserve callers' old retriever call shape.
    knowledge_service.retrieve("a synthetic query", role="CUSTOMER", intent="SPORTS_KNOWLEDGE")
    assert "candidate_filter" not in retriever.retrieve.call_args.kwargs
