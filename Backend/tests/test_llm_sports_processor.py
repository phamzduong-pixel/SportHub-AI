import pytest
from app.services.llm_sports_processor import (
    LLMSportsQueryProcessor,
    QueryUnderstanding,
    GroundedResponse,
    get_llm_sports_processor,
)
from app.models.knowledge_entry import KnowledgeEntry


def test_llm_sports_processor_singleton():
    proc1 = get_llm_sports_processor()
    proc2 = get_llm_sports_processor()
    assert proc1 is proc2


def test_understand_query_fallback_when_no_api_key(monkeypatch):
    """When OPENAI_API_KEY is not configured or mock unavailable, understand_query returns None."""
    processor = LLMSportsQueryProcessor()
    processor._available = False
    result = processor.understand_query("Messi là ai?")
    assert result is None


def test_generate_grounded_response_fallback_when_no_api_key():
    """When OPENAI_API_KEY is not configured, generate_grounded_response returns None."""
    processor = LLMSportsQueryProcessor()
    processor._available = False
    entry = KnowledgeEntry(
        id="K-001",
        topic="identity",
        role="CUSTOMER",
        intent="SPORTS_KNOWLEDGE",
        question="Messi là ai?",
        answer="Lionel Messi là cầu thủ bóng đá huyền thoại.",
        source="system",
        classification="static",
        sport="bóng đá",
        entity="Lionel Messi",
    )
    result = processor.generate_grounded_response("Messi là ai?", [(entry, 0.95)])
    assert result is None


def test_format_history():
    processor = LLMSportsQueryProcessor()
    msgs = [
        {"role": "user", "content": "Messi là ai?"},
        {"role": "assistant", "content": "Lionel Messi là siêu sao bóng đá người Argentina."},
    ]
    formatted = processor._format_history(msgs)
    assert "User: Messi là ai?" in formatted
    assert "Assistant: Lionel Messi là siêu sao bóng đá" in formatted


def test_format_evidence_and_citations():
    processor = LLMSportsQueryProcessor()
    entry = KnowledgeEntry(
        id="K-002",
        topic="birth_date",
        role="CUSTOMER",
        intent="SPORTS_KNOWLEDGE",
        question="Messi sinh ngày nào?",
        answer="Lionel Messi sinh ngày 24/06/1987.",
        source="system",
        classification="static",
        source_name="VnExpress Thể Thao",
        source_url="https://vnexpress.net",
        collected_at="2026-09-15",
        sport="bóng đá",
        entity="Lionel Messi",
    )
    evidence_text = processor._format_evidence([(entry, 0.98)])
    assert "Entity: Lionel Messi" in evidence_text
    assert "Content: Lionel Messi sinh ngày 24/06/1987." in evidence_text
    assert "Source: VnExpress Thể Thao" in evidence_text

    citations = processor._extract_citations([(entry, 0.98)])
    assert len(citations) == 1
    assert citations[0]["source_name"] == "VnExpress Thể Thao"
    assert citations[0]["source_url"] == "https://vnexpress.net"


def test_select_and_validate_evidence_filters_rules_for_athlete_query():
    processor = LLMSportsQueryProcessor()
    entry_player = KnowledgeEntry(
        id="TN-SPT-013",
        topic="Vận động viên Bóng đá",
        role="CUSTOMER",
        intent="SPORTS_KNOWLEDGE",
        question="Vận động viên bóng đá Thái Nguyên",
        answer="Bóng đá Thái Nguyên gồm Kim Thanh, Bích Thùy, Trần Thị Thu.",
        source="system",
        classification="static",
        sport="bóng đá",
        entity="Bóng đá Thái Nguyên",
    )
    entry_rule = KnowledgeEntry(
        id="SOC-RUL-001",
        topic="rules",
        role="CUSTOMER",
        intent="SPORTS_KNOWLEDGE",
        question="Việt vị là gì?",
        answer="Luật việt vị trong bóng đá.",
        source="system",
        classification="static",
        sport="bóng đá",
        entity="Bóng đá",
    )
    selected = processor.select_and_validate_evidence(
        [(entry_player, 0.95), (entry_rule, 0.85)],
        target_entity="Bóng đá Thái Nguyên",
        target_topic="vận động viên",
    )
    assert len(selected) == 1
    assert selected[0][0].id == "TN-SPT-013"


def test_generate_grounded_response_with_mock_provider(monkeypatch):
    processor = LLMSportsQueryProcessor()
    processor._available = True
    
    class MockProvider:
        def generate(self, task, system_data):
            return "Ở Thái Nguyên, các cầu thủ bóng đá nữ tiêu biểu của CLB Thái Nguyên T&T gồm:\n- Trần Thị Kim Thanh\n- Nguyễn Thị Bích Thùy"
    
    processor._provider = MockProvider()
    
    entry = KnowledgeEntry(
        id="TN-SPT-013",
        topic="Vận động viên Bóng đá",
        role="CUSTOMER",
        intent="SPORTS_KNOWLEDGE",
        question="Vận động viên bóng đá Thái Nguyên",
        answer="Bóng đá Thái Nguyên gồm Kim Thanh, Bích Thùy.",
        source="system",
        classification="static",
        sport="bóng đá",
        entity="Bóng đá Thái Nguyên",
    )
    
    res = processor.generate_grounded_response(
        "môn thể thao bóng đá ở thái nguyên có ai là vận động viên giỏi",
        [(entry, 0.95)],
    )
    assert res is not None
    assert res.used_llm is True
    assert "Kim Thanh" in res.answer
    assert "Bích Thùy" in res.answer


def test_general_knowledge_only_mode_requires_explicit_flag_and_no_evidence():
    processor = LLMSportsQueryProcessor()
    processor._background_available = True

    class MockProvider:
        def __init__(self):
            self.system_data = None

        def generate(self, task, system_data):
            self.system_data = system_data
            return "Cách tính điểm có thể khác nhau theo môn và thể thức thi đấu."

    provider = MockProvider()
    processor._background_provider = provider
    response = processor.generate_grounded_response(
        "Khác nhau về cách tính điểm giữa các môn là gì?",
        [],
        allow_general_knowledge=True,
    )

    assert response is not None
    assert response.citations == []
    assert "General knowledge-only mode: yes" in provider.system_data["user_message"]
    assert processor._provider is None
    assert "well-established historical athlete facts" in provider.system_data["system_prompt"]
    assert "Hiện tại SportHub AI chưa có thông tin kiểm chứng về nội dung này trong hệ thống." not in provider.system_data["system_prompt"]
    assert processor.last_generation_status == "success"


def test_general_knowledge_only_flag_cannot_override_provided_evidence():
    processor = LLMSportsQueryProcessor()
    processor._available = True

    class MockProvider:
        def __init__(self):
            self.system_data = None

        def generate(self, task, system_data):
            self.system_data = system_data
            return "Trả lời dựa trên evidence."

    provider = MockProvider()
    processor._provider = provider
    entry = KnowledgeEntry(
        id="K-POLICY-001",
        topic="rules",
        role="CUSTOMER",
        intent="SPORTS_KNOWLEDGE",
        question="Một luật mẫu là gì?",
        answer="Evidence đã cho.",
        source="test",
        classification="static",
    )
    response = processor.generate_grounded_response(
        "Một luật mẫu là gì?",
        [(entry, 0.9)],
        allow_general_knowledge=True,
    )

    assert response is not None
    assert "General knowledge-only mode: no" in provider.system_data["user_message"]


def test_volatile_general_knowledge_prompt_requires_uncertainty_and_no_citation():
    processor = LLMSportsQueryProcessor()
    processor._background_available = True

    class MockProvider:
        def __init__(self):
            self.system_data = None

        def generate(self, task, system_data):
            self.system_data = system_data
            return "Có thể có thay đổi gần đây."

    provider = MockProvider()
    processor._background_provider = provider
    response = processor.generate_grounded_response(
        "Messi hiện thi đấu cho CLB nào?",
        [],
        allow_general_knowledge=True,
        background_level="volatile",
    )

    assert response is not None
    assert response.citations == []
    assert "Background level: volatile" in provider.system_data["user_message"]
    assert "If Background level is volatile" in provider.system_data["system_prompt"]
    assert "Avoid exact figures, dates, and scores without a source" in provider.system_data["system_prompt"]
    assert "Never invent people, competitions, citations, source names, or URLs" in provider.system_data["system_prompt"]


def test_realtime_background_prompt_does_not_claim_live_data():
    processor = LLMSportsQueryProcessor()
    processor._background_available = True

    class MockProvider:
        def generate(self, task, system_data):
            self.system_data = system_data
            return "Mình không có dữ liệu trực tiếp để xác nhận tỷ số hiện tại."

    provider = MockProvider()
    processor._background_provider = provider
    response = processor.generate_grounded_response(
        "Tỷ số trận đang diễn ra?",
        [],
        allow_general_knowledge=True,
        background_level="realtime",
    )

    assert response is not None
    assert response.citations == []
    assert "Background level: realtime" in provider.system_data["user_message"]
    assert "Do not guess a current score, result, or upcoming fixture" in provider.system_data["system_prompt"]

