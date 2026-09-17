import unittest
from unittest.mock import MagicMock

from app.services.ai_intent_router import (
    AssistantIntent,
    IntentRouter,
    is_business_intent,
    is_supported_sport,
)
from app.services.rag_guardrail import RAGGuardrail
from app.services.sports_web_retriever import (
    DEFAULT_SPORTS_SOURCE_WHITELIST,
    SportsWebEvidence,
    SportsWebRetriever,
)
from app.services.ai_assistant_service import AIAssistantService, ScopeClassification
from app.repositories.ai_repository import AIRepository


class SportsWebRetrieverTests(unittest.TestCase):
    """
    Focused test suite for AI-WEB-02:
    Controlled Web Retrieval for SPORTS_KNOWLEDGE only with Source Whitelist and Graceful Fallback.
    """

    def setUp(self):
        self.router = IntentRouter()
        self.retriever = SportsWebRetriever()

    # ----------------------------------------------------
    # 1. Business query -> No Web Retrieval
    # ----------------------------------------------------
    def test_business_query_never_triggers_web_retrieval(self):
        business_intents = [
            AssistantIntent.SEARCH_VENUE,
            AssistantIntent.CHECK_AVAILABILITY,
            AssistantIntent.RECOMMEND_SLOT,
            AssistantIntent.RECOMMEND_VENUE,
            AssistantIntent.GET_VENUE_DETAIL,
            AssistantIntent.CREATE_BOOKING,
            AssistantIntent.GET_BOOKING,
            AssistantIntent.CANCEL_BOOKING,
            AssistantIntent.RESCHEDULE_BOOKING,
            AssistantIntent.PAYMENT_SUPPORT,
            AssistantIntent.ACCOUNT_SUPPORT,
            AssistantIntent.PARTNER_APPLICATION_SUPPORT,
            AssistantIntent.OCCUPANCY_INSIGHT,
            AssistantIntent.GET_PRODUCTS,
            AssistantIntent.SYSTEM_GUIDE,
        ]

        for b_intent in business_intents:
            self.assertFalse(
                self.retriever.can_retrieve(intent=b_intent, sport="bóng đá"),
                f"Business intent {b_intent} must NEVER allow web retrieval",
            )
            # Even if search provider is given, retrieve_evidence must return []
            mock_provider = MagicMock(return_value=[{"url": "https://vff.org.vn/news/1", "title": "Bóng đá", "snippet": "Bóng đá"}])
            retriever_with_mock = SportsWebRetriever(search_provider=mock_provider)
            results = retriever_with_mock.retrieve_evidence("Đặt sân bóng đá", intent=b_intent, sport="bóng đá")
            self.assertEqual(results, [])
            mock_provider.assert_not_called()

    # ----------------------------------------------------
    # 2. Out-of-Scope / Non-Sports -> No Web Retrieval
    # ----------------------------------------------------
    def test_out_of_scope_never_triggers_web_retrieval(self):
        self.assertFalse(self.retriever.can_retrieve(intent=AssistantIntent.OUT_OF_SCOPE))
        self.assertFalse(self.retriever.can_retrieve(intent=AssistantIntent.GREETING))
        self.assertFalse(self.retriever.can_retrieve(intent=AssistantIntent.UNCLEAR))

        # Unsupported sport scope rejected
        self.assertFalse(self.retriever.can_retrieve(intent=AssistantIntent.SPORTS_KNOWLEDGE, sport="golf"))
        self.assertFalse(self.retriever.can_retrieve(intent=AssistantIntent.SPORTS_KNOWLEDGE, sport="bơi lội"))
        self.assertFalse(self.retriever.can_retrieve(intent=AssistantIntent.SPORTS_KNOWLEDGE, sport="esports"))

    # ----------------------------------------------------
    # 3. Supported Sports Query -> Allowed Web Retrieval
    # ----------------------------------------------------
    def test_supported_sports_query_allows_web_retrieval(self):
        for sp in ("bóng đá", "cầu lông", "pickleball", "tennis", "bóng rổ", "bóng chuyền"):
            self.assertTrue(
                self.retriever.can_retrieve(intent=AssistantIntent.SPORTS_KNOWLEDGE, sport=sp),
                f"Supported sport '{sp}' should be permitted for web retrieval under SPORTS_KNOWLEDGE",
            )

        # Mock web search returning whitelisted results
        mock_provider = MagicMock(return_value=[
            {
                "url": "https://vff.org.vn/doi-tuyen-viet-nam-thong-tin-moi",
                "title": "Thông tin Đội tuyển Bóng đá Việt Nam",
                "snippet": "Đội tuyển bóng đá nam quốc gia Việt Nam chuẩn bị cho giải đấu vô địch Đông Nam Á.",
                "date": "2026-09-15",
            }
        ])
        retriever = SportsWebRetriever(search_provider=mock_provider)
        evidence = retriever.retrieve_evidence("Đội tuyển Việt Nam", intent=AssistantIntent.SPORTS_KNOWLEDGE, sport="bóng đá")
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0].source_name, "Liên đoàn Bóng đá Việt Nam (VFF)")
        self.assertEqual(evidence[0].url, "https://vff.org.vn/doi-tuyen-viet-nam-thong-tin-moi")
        self.assertEqual(evidence[0].published_date, "2026-09-15")

    # ----------------------------------------------------
    # 4. Source Whitelist Verification & Non-Whitelisted Rejected
    # ----------------------------------------------------
    def test_whitelist_filtering_and_non_whitelisted_rejected(self):
        # Whitelisted examples
        self.assertTrue(self.retriever.is_whitelisted("https://vff.org.vn/article/1")[0])
        self.assertTrue(self.retriever.is_whitelisted("https://fit.ictu.edu.vn/giao-luu-bong-da")[0])
        self.assertTrue(self.retriever.is_whitelisted("https://baothainguyen.vn/the-thao/clb-bong-da")[0])
        self.assertTrue(self.retriever.is_whitelisted("https://sovanhoathethao.hanoi.gov.vn/tin-tuc")[0])
        self.assertTrue(self.retriever.is_whitelisted("https://svhtt.hochiminhcity.gov.vn/the-thao")[0])
        self.assertTrue(self.retriever.is_whitelisted("https://vba.vn/teams/saigon-heat")[0])

        # Non-whitelisted examples
        self.assertFalse(self.retriever.is_whitelisted("https://random-sports-blog.xyz/post1")[0])
        self.assertFalse(self.retriever.is_whitelisted("https://unverified-forum.com/thread/123")[0])
        self.assertFalse(self.retriever.is_whitelisted("https://fake-news-portal.net/article")[0])

        # Provider returns mixed whitelisted and non-whitelisted
        mock_provider = MagicMock(return_value=[
            {
                "url": "https://random-sports-blog.xyz/post1",
                "title": "Tin tức bóng đá không xác thực",
                "snippet": "Cầu thủ CLB bóng đá Thái Nguyên",
            },
            {
                "url": "https://baothainguyen.vn/the-thao/fc-thai-nguyen",
                "title": "FC Thái Nguyên chính thức ra mắt",
                "snippet": "Câu lạc bộ bóng đá Thái Nguyên ra mắt tham gia giải bóng đá quốc gia.",
                "date": "2026-08-15",
            },
        ])
        retriever = SportsWebRetriever(search_provider=mock_provider)
        evidence = retriever.retrieve_evidence("CLB bóng đá Thái Nguyên", intent=AssistantIntent.SPORTS_KNOWLEDGE, sport="bóng đá")
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0].domain, "baothainguyen.vn")

    # ----------------------------------------------------
    # 5. Non-sports content from whitelisted domain rejected
    # ----------------------------------------------------
    def test_unrelated_content_from_allowed_domain_rejected(self):
        mock_provider = MagicMock(return_value=[
            {
                "url": "https://thanhnien.vn/thoi-su/chinh-tri-xa-hoi.htm",
                "title": "Tình hình giao thông đô thị",
                "snippet": "Các tuyến đường trung tâm đang được nâng cấp sửa chữa hệ thống thoát nước.",
            }
        ])
        retriever = SportsWebRetriever(search_provider=mock_provider)
        evidence = retriever.retrieve_evidence("Tin tức mới", intent=AssistantIntent.SPORTS_KNOWLEDGE, sport="bóng đá")
        # Since snippet is not sports related, it must be rejected
        self.assertEqual(len(evidence), 0)

    # ----------------------------------------------------
    # 6. Web Failure Graceful Fallback
    # ----------------------------------------------------
    def test_web_failure_safe_fallback(self):
        def failing_search(query: str):
            raise ConnectionError("Network timeout connecting to search provider")

        retriever = SportsWebRetriever(search_provider=failing_search)
        evidence = retriever.retrieve_evidence("Messi là ai?", intent=AssistantIntent.SPORTS_KNOWLEDGE, sport="bóng đá")
        self.assertEqual(evidence, [])

        # End-to-end Assistant service with failing web provider still falls back safely
        mock_repo = MagicMock(spec=AIRepository)
        mock_repo.db = MagicMock()
        guardrail = RAGGuardrail(web_retriever=retriever)
        service = AIAssistantService(repository=mock_repo, guardrail=guardrail)

        # 1. When query matches internal knowledge (e.g. Messi), internal knowledge answers correctly
        res = service.ask("Messi là ai?")
        self.assertEqual(res["status"], "OK")
        self.assertIn("Lionel Messi", res["reply"])

        # 2. When query has no internal knowledge and web fails, returns safe fallback message
        res_unknown = service.ask("Cầu thủ bóng đá vô danh 12345 là ai?")
        self.assertEqual(res_unknown["status"], "OK")
        self.assertIn("chưa có thông tin kiểm chứng", res_unknown["reply"])

    # ----------------------------------------------------
    # 7. End-to-End Web Retrieval Integration in Assistant
    # ----------------------------------------------------
    def test_assistant_uses_web_evidence_when_internal_is_missing(self):
        mock_provider = MagicMock(return_value=[
            {
                "url": "https://ictu.edu.vn/su-kien-the-thao-moi-2026",
                "title": "Giải bóng chuyền giao lưu ICTU 2026",
                "snippet": "Trường Đại học Công nghệ Thông tin và Truyền thông tổ chức giải bóng chuyền giao lưu năm 2026 với sự tham gia của 6 đội tuyển khoa.",
                "date": "2026-09-10",
            }
        ])
        web_retriever = SportsWebRetriever(search_provider=mock_provider)
        guardrail = RAGGuardrail(web_retriever=web_retriever)
        mock_repo = MagicMock(spec=AIRepository)
        mock_repo.db = MagicMock()
        service = AIAssistantService(repository=mock_repo, guardrail=guardrail)

        res = service.ask("Giải bóng chuyền giao lưu ICTU 2026 tổ chức thế nào?")
        self.assertEqual(res["status"], "OK")
        self.assertIn("ictu.edu.vn", res["reply"])
        self.assertIn("Trường ĐH Công nghệ Thông tin & Truyền thông Thái Nguyên", res["reply"])


if __name__ == "__main__":
    unittest.main()
