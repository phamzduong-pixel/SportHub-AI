import pytest
from app.services.ai_assistant_service import AIAssistantService, AIRepository
from app.services.ai_domain_policy import ScopeClassification
from app.schemas.ai import AssistantMode


@pytest.fixture
def assistant():
    return AIAssistantService(AIRepository(None))


def test_natural_mode_admin_contact_queries(assistant):
    queries = [
        "Số điện thoại của admin là gì?",
        "Cho tôi số admin",
        "Liên hệ admin bằng số nào?",
        "Số điện thoại quản trị viên là gì?",
        "Số điện thoại admin là gì?",
        "Cho tôi số điện thoại admin.",
        "Cho mình xin số admin SportHub.",
        "Số admin SportHub là bao nhiêu?",
        "Tôi muốn liên hệ với admin.",
        "Tôi muốn gọi cho admin.",
        "Làm sao để liên hệ quản trị viên?",
        "Admin SportHub có số điện thoại không?",
        "Cho tôi xin thông tin liên hệ admin.",
    ]
    expected_reply = "Số điện thoại của admin SportHub là 0866606729."

    for q in queries:
        res = assistant.ask(q, assistant_mode=AssistantMode.NATURAL)
        assert res["reply"] == expected_reply, f"Failed for query: {q}"
        assert res["status"] == "OK"
        assert res["classification"] == ScopeClassification.IN_SCOPE
        assert "tìm sân" not in res["reply"]
        assert "đặt sân" not in res["reply"]
