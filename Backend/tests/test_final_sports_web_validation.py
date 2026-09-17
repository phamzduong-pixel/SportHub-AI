import pytest
from unittest.mock import MagicMock
from app.models.knowledge_entry import KnowledgeEntry
from app.services.ai_intent_router import IntentRouter, AssistantIntent
from app.services.sports_web_retriever import (
    SportsWebEvidence,
    SportsWebRetriever,
)
from app.services.ai_assistant_service import AIAssistantService
from app.services.rag_guardrail import RAGGuardrail


class TestSportsWebValidationFlow:
    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        self.mock_repo = MagicMock()
        # Mock database venues for business search
        self.mock_repo.search_available_slots.return_value = []
        self.mock_repo.search_venues.return_value = []
        self.mock_provider = MagicMock()
        self.web_retriever = SportsWebRetriever(search_provider=self.mock_provider)
        self.guardrail = RAGGuardrail(web_retriever=self.web_retriever)
        self.service = AIAssistantService(repository=self.mock_repo, guardrail=self.guardrail)
        self.router = IntentRouter()

    def test_scenario_1_business_flow(self):
        """1. Business: 'Tìm sân cầu lông tối nay' -> Business Flow -> Database -> NO Web Search"""
        res = self.service.ask("Tìm sân cầu lông ở Hà Nội tối nay")
        # Should be a business intent (SEARCH_VENUE or CHECK_AVAILABILITY)
        assert res["intent"] in ["SEARCH_VENUE", "CHECK_AVAILABILITY"]
        # Database repository was queried
        assert self.mock_repo.search_available_slots.called or self.mock_repo.search_venues.called
        # Web search provider was NEVER called
        self.mock_provider.assert_not_called()

    def test_scenario_2_sports_knowledge_internal_preferred(self):
        """2. Sports Knowledge: 'Thái Nguyên có những đội bóng nào?' -> SPORTS_KNOWLEDGE -> Internal Knowledge"""
        res = self.service.ask("Thái Nguyên có những đội bóng nào?")
        assert res["status"] == "OK"
        assert res["intent"] == "SPORTS_KNOWLEDGE"
        # Uses internal knowledge about Thai Nguyen football
        assert "Thái Nguyên T&T" in res["reply"] or "FC Thái Nguyên" in res["reply"]
        # Sufficient internal knowledge -> mock provider was not called
        self.mock_provider.assert_not_called()

    def test_scenario_3_supported_sport_ictu(self):
        """3. Supported sport: 'ICTU có những môn thể thao nào?' -> Sports Scope -> Internal Knowledge / official sources"""
        res = self.service.ask("ICTU có những môn thể thao nào?")
        assert res["status"] == "OK"
        assert res["intent"] == "SPORTS_KNOWLEDGE"
        assert "Bóng đá" in res["reply"] or "Cầu lông" in res["reply"] or "Pickleball" in res["reply"]

    def test_scenario_4_current_information_time_sensitive(self):
        """4. Current information: 'Cầu thủ bóng đá Endrick hiện đang thi đấu cho CLB nào?' -> time-sensitive -> official/reliable Web Evidence"""
        self.mock_provider.side_effect = lambda q: [
            {
                "url": "https://baothainguyen.vn/the-thao/endrick-real-madrid",
                "title": "Endrick thi đấu tại Real Madrid",
                "snippet": "Cầu thủ bóng đá Endrick hiện đang thi đấu cho CLB Real Madrid tại giải La Liga.",
                "published_date": "2026-08-20",
                "relevance_score": 0.95,
            }
        ]
        res = self.service.ask("Cầu thủ bóng đá Endrick hiện đang thi đấu cho CLB nào?")
        assert res["status"] == "OK"
        assert res["intent"] == "SPORTS_KNOWLEDGE"
        assert "Real Madrid" in res["reply"]
        assert "baothainguyen.vn" in res["reply"]

    def test_scenario_5_non_sports_out_of_scope(self):
        """5. Non-sports: 'Chính sách tuyển sinh của ICTU là gì?' -> OUT_OF_SCOPE -> NO Web Search"""
        res = self.service.ask("Chính sách tuyển sinh của ICTU là gì?")
        assert res["intent"] == "OUT_OF_SCOPE"
        assert res["status"] == "OUT_OF_SCOPE"
        self.mock_provider.assert_not_called()

    def test_scenario_6_unsupported_sport_out_of_scope(self):
        """6. Unsupported sport: 'Luật chơi môn bi-a carom' -> OUT_OF_SCOPE -> NO Web Search"""
        res = self.service.ask("Luật chơi môn bi-a carom như thế nào?")
        assert res["intent"] == "OUT_OF_SCOPE"
        assert res["status"] == "OUT_OF_SCOPE"
        self.mock_provider.assert_not_called()

    def test_scenario_7_multi_entity_preservation(self):
        """7. Multi-entity: 'Messi và Ronaldo hiện đang thi đấu cho đội nào?' -> all entities preserved -> evidence retrieved for both"""
        res = self.service.ask("Messi và Ronaldo hiện đang thi đấu cho đội nào?")
        assert res["status"] == "OK"
        assert res["intent"] == "SPORTS_KNOWLEDGE"
        assert set(res["understood"]["sports_entities"]) == {"Lionel Messi", "Cristiano Ronaldo"}
        # Mentions both Messi and Ronaldo
        assert "Messi" in res["reply"]
        assert "Ronaldo" in res["reply"]

    def test_scenario_8_regression_coverage(self):
        """8. Regression: venue search, booking, payment, partner/account intents, multi-turn context, voice input"""
        # A. Venue search
        res_search = self.service.ask("Tìm sân cầu lông ở Hà Nội")
        assert res_search["intent"] == "SEARCH_VENUE"

        # B. Booking / Slot check
        res_slot = self.service.ask("Còn sân vào lúc 18h ngày mai không?")
        assert res_slot["intent"] in ["CHECK_AVAILABILITY", "RECOMMEND_SLOT", "SEARCH_VENUE"]

        # C. Payment support
        res_pay = self.service.ask("Làm sao để thanh toán tiền đặt sân?")
        assert res_pay["intent"] == "PAYMENT_SUPPORT"

        # D. Partner application
        res_partner = self.service.ask("Quy trình đăng ký chủ sân như thế nào?")
        assert res_partner["intent"] == "PARTNER_APPLICATION_SUPPORT"

        # E. Multi-turn context
        first = self.service.ask("Messi là ai?")
        assert first["intent"] == "SPORTS_KNOWLEDGE"
        second = self.service.ask("Anh ấy đang thi đấu ở đâu?", context=first["understood"])
        assert second["intent"] == "SPORTS_KNOWLEDGE"
        assert "Inter Miami" in second["reply"]

        # F. Voice input normalized
        res_voice = self.service.ask("   tìm sân bóng đá hà nội   ")
        assert res_voice["intent"] == "SEARCH_VENUE"
