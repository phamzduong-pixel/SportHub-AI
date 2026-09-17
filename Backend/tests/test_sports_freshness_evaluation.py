import pytest
from unittest.mock import MagicMock
from app.models.knowledge_entry import KnowledgeEntry
from app.services.ai_intent_router import AssistantIntent
from app.services.sports_web_retriever import (
    SportsWebEvidence,
    SportsWebRetriever,
)
from app.services.ai_assistant_service import AIAssistantService
from app.services.rag_guardrail import RAGGuardrail


def test_stable_fact_uses_internal_knowledge_without_web():
    """Stable query (e.g. birth date, background) with sufficient internal knowledge does not require web."""
    retriever = SportsWebRetriever()

    internal_entries = [
        (
            KnowledgeEntry(
                id="FB-ICTU-01",
                topic="Thể thao",
                role="CUSTOMER",
                intent="SPORTS_KNOWLEDGE",
                question="Giải bóng đá ICTU Cup",
                answer="Giải bóng đá sinh viên ICTU Cup do Trường ĐH CNTT&TT tổ chức hàng năm.",
                source="ictu.edu.vn",
                classification="static",
                sport="football",
                entity="ICTU",
                source_name="ICTU",
                source_url="https://ictu.edu.vn/khoi-tranh-giai-bong-da-sinh-vien-ictu-cup-2024/",
                collected_at="2026-09-17",
                priority=1,
            ),
            0.92,
        )
    ]

    eval_result = retriever.evaluate_freshness_and_sufficiency(
        query="Giải bóng đá ICTU Cup là gì?",
        internal_entries=internal_entries,
    )

    assert eval_result.is_high_volatility is False
    assert eval_result.needs_fresh_web is False
    assert eval_result.internal_is_sufficient is True


def test_high_volatility_transfer_current_club_requires_fresh_web():
    """Transfer or current club queries are classified as high volatility and require fresh web evidence if internal is stale/incomplete."""
    retriever = SportsWebRetriever()

    # Query asking for current club / transfer
    query = "Messi đang thi đấu cho CLB nào hiện tại?"
    assert retriever.is_high_volatility_query(query) is True

    # Stale internal entry (e.g. older than 60 days)
    stale_internal = [
        (
            KnowledgeEntry(
                id="FB-MESSI-01",
                topic="Thể thao",
                role="CUSTOMER",
                intent="SPORTS_KNOWLEDGE",
                question="Messi thi đấu ở đâu?",
                answer="Lionel Messi thi đấu cho PSG.",
                source="manual",
                classification="static",
                sport="football",
                entity="Messi",
                source_name="Báo Thể thao",
                source_url="https://thethao247.vn/messi",
                collected_at="2023-01-01",
                priority=1,
            ),
            0.95,
        )
    ]

    eval_result = retriever.evaluate_freshness_and_sufficiency(
        query=query,
        internal_entries=stale_internal,
        current_date_str="2026-09-17",
    )

    assert eval_result.is_high_volatility is True
    assert eval_result.needs_fresh_web is True
    assert eval_result.internal_is_sufficient is False


def test_stale_internal_fact_prefers_newer_verified_web_evidence():
    """When web evidence is retrieved from a verified whitelisted source, it takes precedence over stale internal facts."""
    retriever = SportsWebRetriever()
    query = "Messi đang khoác áo đội bóng nào?"

    stale_internal = [
        (
            KnowledgeEntry(
                id="FB-MESSI-OLD",
                topic="Thể thao",
                role="CUSTOMER",
                intent="SPORTS_KNOWLEDGE",
                question="Messi CLB",
                answer="Messi đang khoác áo PSG.",
                source="manual",
                classification="static",
                sport="football",
                entity="Messi",
                collected_at="2023-01-01",
                priority=1,
            ),
            0.85,
        )
    ]

    web_evidences = [
        SportsWebEvidence(
            url="https://baothainguyen.vn/the-thao/messi-inter-miami",
            title="Messi thi đấu thăng hoa tại Inter Miami",
            source_name="Báo Thái Nguyên",
            domain="baothainguyen.vn",
            snippet="Lionel Messi hiện đang là đội trưởng và thi đấu cho CLB Inter Miami tại giải MLS.",
            sport="football",
            published_date="2026-08-15",
            relevance_score=0.95,
            is_rumor=False,
            is_confirmed=True,
        )
    ]

    merged = retriever.merge_and_prefer_evidence(
        query=query,
        internal_entries=stale_internal,
        web_evidences=web_evidences,
    )

    assert len(merged) >= 1
    # The first (preferred) entry should be the verified web evidence
    preferred_entry, score = merged[0]
    assert preferred_entry.source == "web"
    assert "Inter Miami" in preferred_entry.answer
    assert preferred_entry.source_name == "Báo Thái Nguyên"


def test_rumor_and_unverified_reports_are_rejected_or_unconfirmed():
    """Rumors or unconfirmed transfer reports are flagged and not accepted as confirmed facts."""
    retriever = SportsWebRetriever()

    rumor_text = "Tin đồn rò rỉ: Cầu thủ X có thể sẽ gia nhập CLB Y với mức phí kỷ lục."
    assert retriever.is_rumor_or_unconfirmed(rumor_text) is True

    # Search provider returning a rumor
    provider = lambda q: [
        {
            "url": "https://thethao247.vn/tin-don-chuyen-nhuong",
            "title": "Tin đồn: Cầu thủ đang đàm phán hợp đồng mới",
            "snippet": "Nghi vấn cầu thủ sắp rời CLB, nguồn tin nội bộ cho biết đang thương thảo chưa chính thức.",
            "published_date": "2026-09-10",
            "relevance_score": 0.9,
        }
    ]

    retriever_with_provider = SportsWebRetriever(search_provider=provider)
    evidences = retriever_with_provider.retrieve_evidence(
        query="tin chuyển nhượng mới nhất",
        intent=AssistantIntent.SPORTS_KNOWLEDGE,
        sport="football",
    )

    assert len(evidences) == 1
    assert evidences[0].is_rumor is True
    assert evidences[0].is_confirmed is False

    # When merging, rumor evidence is not promoted as confirmed facts
    internal_entries = [
        (
            KnowledgeEntry(
                id="FB-CONFIRMED",
                topic="Thể thao",
                role="CUSTOMER",
                intent="SPORTS_KNOWLEDGE",
                question="Cầu thủ",
                answer="Cầu thủ đang thuộc biên chế đội A chính thức.",
                source="official",
                classification="static",
                sport="football",
                collected_at="2026-09-01",
                priority=1,
            ),
            0.9,
        )
    ]

    merged = retriever_with_provider.merge_and_prefer_evidence(
        query="tin chuyển nhượng",
        internal_entries=internal_entries,
        web_evidences=evidences,
    )

    # Confirmed internal entry remains primary
    assert len(merged) == 1
    assert merged[0][0].id == "FB-CONFIRMED"


def test_ai_assistant_e2e_freshness_evaluation_with_web():
    """AIAssistantService answers with updated current-club when fresh web evidence is retrieved for entity without internal facts."""
    mock_repo = MagicMock()
    mock_provider = lambda q: [
        {
            "url": "https://baothainguyen.vn/the-thao/endrick-real-madrid",
            "title": "Endrick thi đấu tại Real Madrid",
            "snippet": "Cầu thủ bóng đá Endrick hiện đang thi đấu cho CLB Real Madrid tại giải La Liga.",
            "published_date": "2026-08-20",
            "relevance_score": 0.95,
        }
    ]
    web_retriever = SportsWebRetriever(search_provider=mock_provider)
    guardrail = RAGGuardrail(web_retriever=web_retriever)
    service = AIAssistantService(repository=mock_repo, guardrail=guardrail)

    res = service.ask("Cầu thủ bóng đá Endrick đang thi đấu cho CLB nào?")
    assert res["status"] == "OK"
    assert "Real Madrid" in res["reply"]
    # Verify source citation is present in the reply text
    assert "baothainguyen.vn" in res["reply"]
    assert "Báo Thái Nguyên" in res["reply"]
