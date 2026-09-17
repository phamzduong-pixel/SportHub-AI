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


def test_internal_only_answer():
    """Stable sports question (e.g. tournament background) is answered purely from internal knowledge."""
    mock_repo = MagicMock()
    mock_provider = MagicMock()
    web_retriever = SportsWebRetriever(search_provider=mock_provider)
    guardrail = RAGGuardrail(web_retriever=web_retriever)
    service = AIAssistantService(repository=mock_repo, guardrail=guardrail)

    res = service.ask("ICTU CUP 2024 có bao nhiêu đội?")
    assert res["status"] == "OK"
    assert "8 đội" in res["reply"] or "4 đội nam" in res["reply"]
    # Provider should not even be called for sufficient internal facts
    mock_provider.assert_not_called()


def test_internal_plus_web_combined_answer():
    """Combines stable background from internal knowledge with fresh dynamic facts from web evidence."""
    # Internal knowledge has general background on player/team
    internal_entry = (
        KnowledgeEntry(
            id="FB-BG-01",
            topic="Thể thao",
            role="CUSTOMER",
            intent="SPORTS_KNOWLEDGE",
            question="Tiểu sử cầu thủ",
            answer="Cầu thủ sinh năm 2006 tại Brazil, sở hữu kỹ thuật điêu luyện.",
            source="manual",
            classification="static",
            sport="football",
            entity="Endrick",
            source_name="Hồ sơ cầu thủ",
            source_url="https://fifa.com/players/endrick",
            collected_at="2026-09-01",
            priority=1,
        ),
        0.90,
    )

    # Web evidence has the current team/performance
    web_ev = SportsWebEvidence(
        url="https://baothainguyen.vn/the-thao/endrick-real-madrid",
        title="Endrick tỏa sáng tại Real Madrid",
        source_name="Báo Thái Nguyên",
        domain="baothainguyen.vn",
        snippet="Endrick hiện đang thi đấu cho CLB Real Madrid và ghi bàn thắng quan trọng tại giải La Liga.",
        sport="football",
        published_date="2026-09-15",
        relevance_score=0.95,
        is_rumor=False,
        is_confirmed=True,
    )

    retriever = SportsWebRetriever()
    merged = retriever.merge_and_prefer_evidence(
        query="Endrick đang thi đấu ở đâu?",
        internal_entries=[internal_entry],
        web_evidences=[web_ev],
    )

    # Both entries are retained and ranked
    assert len(merged) == 2
    answers_text = " ".join(e.answer for e, _ in merged)
    assert "Real Madrid" in answers_text
    assert "sinh năm 2006" in answers_text


def test_newer_web_fact_overriding_stale_internal_fact():
    """When internal fact is stale (e.g. from 2023) and web evidence is verified (2026), stale fact is superseded."""
    stale_internal = (
        KnowledgeEntry(
            id="FB-STALE-01",
            topic="Thể thao",
            role="CUSTOMER",
            intent="SPORTS_KNOWLEDGE",
            question="CLB của Messi",
            answer="Lionel Messi hiện đang thi đấu cho CLB Paris Saint-Germain (PSG).",
            source="manual",
            classification="static",
            sport="football",
            entity="Messi",
            source_name="Báo Cũ",
            source_url="https://thethao247.vn/old-messi",
            collected_at="2023-01-10",
            priority=1,
        ),
        0.80,
    )

    fresh_web = SportsWebEvidence(
        url="https://baothainguyen.vn/the-thao/messi-inter-miami",
        title="Messi thăng hoa tại Inter Miami",
        source_name="Báo Thái Nguyên",
        domain="baothainguyen.vn",
        snippet="Lionel Messi hiện đang là thủ quân và thi đấu cho CLB Inter Miami tại MLS.",
        sport="football",
        published_date="2026-08-20",
        relevance_score=0.95,
        is_rumor=False,
        is_confirmed=True,
    )

    retriever = SportsWebRetriever()
    merged = retriever.merge_and_prefer_evidence(
        query="Messi đang thi đấu cho CLB nào?",
        internal_entries=[stale_internal],
        web_evidences=[fresh_web],
    )

    # Stale 2023 entry about PSG should be superseded/removed
    entry_ids = [e.id for e, _ in merged]
    assert "FB-STALE-01" not in entry_ids
    assert any("Inter Miami" in e.answer for e, _ in merged)


def test_conflicting_evidence_handling():
    """When two reliable sources from similar timeframe report conflicting claims, the conflict is explicitly flagged."""
    retriever = SportsWebRetriever()

    web_ev1 = SportsWebEvidence(
        url="https://thanhnien.vn/the-thao/chuyen-nhuong-a",
        title="Thương vụ chuyển nhượng A",
        source_name="Báo Thanh Niên",
        domain="thanhnien.vn",
        snippet="Cầu thủ X đã chính thức ký hợp đồng và gia nhập CLB Alpha.",
        sport="football",
        published_date="2026-09-10",
        relevance_score=0.90,
        is_rumor=False,
        is_confirmed=True,
    )

    web_ev2 = SportsWebEvidence(
        url="https://tuoitre.vn/the-thao/chuyen-nhuong-b",
        title="Thương vụ chuyển nhượng B",
        source_name="Báo Tuổi Trẻ",
        domain="tuoitre.vn",
        snippet="Cầu thủ X đã quyết định gia nhập CLB Beta theo hợp đồng 3 năm.",
        sport="football",
        published_date="2026-09-10",
        relevance_score=0.90,
        is_rumor=False,
        is_confirmed=True,
    )

    merged = retriever.merge_and_prefer_evidence(
        query="Cầu thủ X gia nhập CLB nào?",
        internal_entries=[],
        web_evidences=[web_ev1, web_ev2],
    )

    # Conflict note should be prepended
    first_entry, score = merged[0]
    assert first_entry.id == "CONFLICT-NOTE"
    assert "khác biệt giữa các nguồn tin" in first_entry.answer


def test_unrelated_web_evidence_exclusion():
    """Web search results from unrelated sports or non-sports topics are strictly filtered out."""
    provider = lambda q: [
        {
            "url": "https://baothainguyen.vn/the-thao/bong-da-vleague",
            "title": "Kết quả vòng 15 giải bóng đá V-League",
            "snippet": "CLB Hà Nội giành chiến thắng 2-1 trước đối thủ trong trận đấu bóng đá kịch tính.",
            "published_date": "2026-09-12",
            "relevance_score": 0.90,
        },
        {
            "url": "https://baothainguyen.vn/the-thao/giai-cau-long-thai-nguyen",
            "title": "Giải vô địch cầu lông tỉnh Thái Nguyên",
            "snippet": "Vận động viên Nguyễn Thùy Linh tham dự giải cầu lông với phong độ xuất sắc.",
            "published_date": "2026-09-14",
            "relevance_score": 0.95,
        },
    ]

    retriever = SportsWebRetriever(search_provider=provider)

    # When querying for badminton, football articles must be excluded
    evidences = retriever.retrieve_evidence(
        query="giải vô địch cầu lông",
        intent=AssistantIntent.SPORTS_KNOWLEDGE,
        sport="badminton",
    )

    assert len(evidences) == 1
    assert "cầu lông" in evidences[0].snippet.lower()
    assert "v-league" not in evidences[0].snippet.lower()
