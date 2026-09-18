import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.ai import AssistantMode
from app.services.ai_intent_router import AssistantIntent
from app.services.ai_domain_policy import (
    AllowedSource,
    ScopeClassification,
    ScopeDecision,
    evaluate_mode_scope,
)
from app.services.rag_guardrail import RAGGuardrail


class AssistantMockProvider:
    def generate_json(self, **kwargs):
        available = kwargs.get('system_data', {}).get('available_slots', [])
        return {
            'status': 'OK',
            'recommendations': [
                {'court_id': item['court_id'], 'slot_id': item['slot_id'], 'reason': 'Phù hợp nhu cầu.'}
                for item in available[:3]
            ],
        }


class AIModePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provider_patch = patch('app.services.ai_feature_service.StructuredAIProvider', return_value=AssistantMockProvider())
        cls.provider_patch.start()
        cls.client = TestClient(app)
        cls.context = cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.client.__exit__(None, None, None)
        finally:
            cls.client.close()
            cls.provider_patch.stop()

    # 1. NATURAL + SportHub business -> ALLOW
    def test_natural_mode_sporthub_business_allowed(self):
        # Venue Search
        response = self.client.post('/ai/assistant', json={
            'message': 'Tìm sân cầu lông tối nay ở Cầu Giấy',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('classification'), 'IN_SCOPE')
        self.assertNotEqual(data.get('status'), 'OUT_OF_SCOPE')
        self.assertEqual(data.get('understood', {}).get('scope_decision'), 'SPORT_HUB_BUSINESS')

        # System Guide / Account
        response_guide = self.client.post('/ai/assistant', json={
            'message': 'Quy trình đặt cọc và thanh toán thế nào?',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(response_guide.status_code, 200)
        self.assertEqual(response_guide.json().get('understood', {}).get('scope_decision'), 'SPORT_HUB_BUSINESS')

    # 2. NATURAL + supported Sports Knowledge -> ALLOW
    def test_natural_mode_supported_sports_knowledge_allowed(self):
        response = self.client.post('/ai/assistant', json={
            'message': 'Kích thước sân bóng đá 7 người',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('classification'), 'IN_SCOPE')
        self.assertNotEqual(data.get('status'), 'OUT_OF_SCOPE')
        self.assertEqual(data.get('understood', {}).get('scope_decision'), 'SPORTS_KNOWLEDGE')

    # 3. NATURAL + outside scope -> BLOCK
    def test_natural_mode_outside_scope_blocked(self):
        # Non-sports unrelated question
        response = self.client.post('/ai/assistant', json={
            'message': 'Thời tiết ngày mai ở Hà Nội thế nào?',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'OUT_OF_SCOPE')
        self.assertEqual(data.get('classification'), 'OUT_OF_SCOPE')
        self.assertEqual(data.get('understood', {}).get('scope_decision'), 'OUT_OF_SCOPE')

        # Coding question
        response_code = self.client.post('/ai/assistant', json={
            'message': 'Hãy viết cho tôi một đoạn mã Python',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(response_code.status_code, 200)
        self.assertEqual(response_code.json().get('status'), 'OUT_OF_SCOPE')

    # 4. PROFESSIONAL + SportHub business -> ALLOW
    def test_professional_mode_sporthub_business_allowed(self):
        # Search venue with sport keyword
        response = self.client.post('/ai/assistant', json={
            'message': 'Tìm sân bóng đá',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('classification'), 'IN_SCOPE')
        self.assertNotEqual(data.get('status'), 'OUT_OF_SCOPE')
        self.assertEqual(data.get('understood', {}).get('scope_decision'), 'SPORT_HUB_BUSINESS')

        # Partner application support in professional mode
        response_partner = self.client.post('/ai/assistant', json={
            'message': 'Làm sao để trở thành chủ sân?',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(response_partner.status_code, 200)
        self.assertEqual(response_partner.json().get('understood', {}).get('scope_decision'), 'SPORT_HUB_BUSINESS')

    # 5. PROFESSIONAL + Sports Knowledge -> BLOCK
    def test_professional_mode_sports_knowledge_blocked(self):
        # Athlete knowledge
        response_messi = self.client.post('/ai/assistant', json={
            'message': 'Messi là ai?',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(response_messi.status_code, 200)
        data_messi = response_messi.json()
        self.assertEqual(data_messi.get('status'), 'OUT_OF_SCOPE')
        self.assertEqual(data_messi.get('classification'), 'OUT_OF_SCOPE')
        self.assertIn('Chuyên nghiệp (Professional)', data_messi.get('reply', ''))

        # Sports comparison
        response_compare = self.client.post('/ai/assistant', json={
            'message': 'Ronaldo hay Messi giỏi hơn?',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(response_compare.status_code, 200)
        self.assertEqual(response_compare.json().get('status'), 'OUT_OF_SCOPE')

        # Rules / general sports knowledge
        response_rules = self.client.post('/ai/assistant', json={
            'message': 'Luật thi đấu bóng đá 7 người',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(response_rules.status_code, 200)
        self.assertEqual(response_rules.json().get('status'), 'OUT_OF_SCOPE')

    # 6. PROFESSIONAL + Sports Knowledge does NOT call Sports RAG
    @patch('app.services.rag_guardrail.KnowledgeService.retrieve')
    def test_professional_mode_does_not_call_sports_rag(self, mock_retrieve: MagicMock):
        response = self.client.post('/ai/assistant', json={
            'message': 'Messi là ai?',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('status'), 'OUT_OF_SCOPE')
        mock_retrieve.assert_not_called()

    # 7. PROFESSIONAL + Sports Knowledge does NOT call External Sports Web
    @patch('app.services.rag_guardrail.RAGGuardrail.retrieve_web_context')
    def test_professional_mode_does_not_call_external_web(self, mock_web: MagicMock):
        response = self.client.post('/ai/assistant', json={
            'message': 'Messi là ai?',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('status'), 'OUT_OF_SCOPE')
        mock_web.assert_not_called()

    # 8. Allowed sources verified per mode across all decisions
    def test_allowed_sources_matrix_by_mode(self):
        # NATURAL Mode: Full sources for Business and Sports Knowledge
        eval_nat_bus = evaluate_mode_scope(AssistantMode.NATURAL, AssistantIntent.SEARCH_VENUE)
        self.assertEqual(eval_nat_bus.allowed_sources, {
            AllowedSource.SPORTHUB_DB,
            AllowedSource.INTERNAL_RAG,
            AllowedSource.SPORTS_KNOWLEDGE_RAG,
            AllowedSource.APPROVED_SPORTS_WEB,
        })
        self.assertTrue(eval_nat_bus.is_allowed)

        eval_nat_know = evaluate_mode_scope(AssistantMode.NATURAL, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(eval_nat_know.allowed_sources, {
            AllowedSource.SPORTHUB_DB,
            AllowedSource.INTERNAL_RAG,
            AllowedSource.SPORTS_KNOWLEDGE_RAG,
            AllowedSource.APPROVED_SPORTS_WEB,
        })
        self.assertTrue(eval_nat_know.is_allowed)

        eval_nat_oos = evaluate_mode_scope(AssistantMode.NATURAL, AssistantIntent.OUT_OF_SCOPE)
        self.assertEqual(eval_nat_oos.allowed_sources, set())
        self.assertFalse(eval_nat_oos.is_allowed)

        # PROFESSIONAL Mode: Only DB + Internal RAG for Business, 0 for Sports Knowledge & Out of Scope
        eval_pro_bus = evaluate_mode_scope(AssistantMode.PROFESSIONAL, AssistantIntent.SEARCH_VENUE)
        self.assertEqual(eval_pro_bus.allowed_sources, {
            AllowedSource.SPORTHUB_DB,
            AllowedSource.INTERNAL_RAG,
        })
        self.assertTrue(eval_pro_bus.is_allowed)

        eval_pro_know = evaluate_mode_scope(AssistantMode.PROFESSIONAL, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(eval_pro_know.allowed_sources, set())
        self.assertFalse(eval_pro_know.is_allowed)
        self.assertEqual(eval_pro_know.classification, ScopeClassification.OUT_OF_SCOPE)

        eval_pro_oos = evaluate_mode_scope(AssistantMode.PROFESSIONAL, AssistantIntent.OUT_OF_SCOPE)
        self.assertEqual(eval_pro_oos.allowed_sources, set())
        self.assertFalse(eval_pro_oos.is_allowed)

    # Guardrail level checks
    def test_guardrail_method_mode_restrictions(self):
        guardrail = RAGGuardrail()
        # Natural Mode
        self.assertTrue(guardrail.should_use_rag("SPORTS_KNOWLEDGE", role="CUSTOMER", assistant_mode=AssistantMode.NATURAL))
        self.assertTrue(guardrail.can_retrieve_web("SPORTS_KNOWLEDGE", sport="bóng đá", assistant_mode=AssistantMode.NATURAL))

        # Professional Mode
        self.assertFalse(guardrail.should_use_rag("SPORTS_KNOWLEDGE", role="CUSTOMER", assistant_mode=AssistantMode.PROFESSIONAL))
        self.assertFalse(guardrail.can_retrieve_web("SPORTS_KNOWLEDGE", sport="bóng đá", assistant_mode=AssistantMode.PROFESSIONAL))

    def test_professional_mode_formal_greeting(self):
        response = self.client.post('/ai/assistant', json={
            'message': 'Xin chào',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('classification'), 'IN_SCOPE')
        self.assertIn('Trợ lý Nghiệp vụ SportHub AI', data.get('reply', ''))

    def test_professional_mode_booking_and_pricing_intents(self):
        # Pricing query in professional mode
        response_price = self.client.post('/ai/assistant', json={
            'message': 'Tìm sân cầu lông giá dưới 300k',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(response_price.status_code, 200)
        self.assertEqual(response_price.json().get('classification'), 'IN_SCOPE')

        # Booking inquiry in professional mode
        response_booking = self.client.post('/ai/assistant', json={
            'message': 'Trạng thái booking của tôi thế nào?',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(response_booking.status_code, 200)
        self.assertEqual(response_booking.json().get('classification'), 'IN_SCOPE')

    def test_professional_mode_comprehensive_business_scope(self):
        # 1. Tìm sân -> ALLOW
        res_search = self.client.post('/ai/assistant', json={
            'message': 'Tìm sân bóng đá gần Cầu Giấy',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(res_search.status_code, 200)
        self.assertEqual(res_search.json().get('classification'), 'IN_SCOPE')
        self.assertEqual(res_search.json().get('understood', {}).get('scope_decision'), 'SPORT_HUB_BUSINESS')

        # 2. Availability -> ALLOW
        res_avail = self.client.post('/ai/assistant', json={
            'message': 'Sân cầu lông còn trống lúc 19h tối nay không?',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(res_avail.status_code, 200)
        self.assertEqual(res_avail.json().get('classification'), 'IN_SCOPE')
        self.assertEqual(res_avail.json().get('understood', {}).get('scope_decision'), 'SPORT_HUB_BUSINESS')

        # 3. Giá sân -> ALLOW
        res_price = self.client.post('/ai/assistant', json={
            'message': 'Giá thuê sân tennis ban ngày và ban đêm thế nào?',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(res_price.status_code, 200)
        self.assertEqual(res_price.json().get('classification'), 'IN_SCOPE')
        self.assertEqual(res_price.json().get('understood', {}).get('scope_decision'), 'SPORT_HUB_BUSINESS')

        # 4. Booking -> ALLOW
        res_book = self.client.post('/ai/assistant', json={
            'message': 'Xem lịch sử đặt sân của tôi',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(res_book.status_code, 200)
        self.assertEqual(res_book.json().get('classification'), 'IN_SCOPE')

        # 5. Payment / Account -> ALLOW
        res_pay = self.client.post('/ai/assistant', json={
            'message': 'Quy trình hoàn tiền và chính sách thanh toán cọc thế nào?',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(res_pay.status_code, 200)
        self.assertEqual(res_pay.json().get('classification'), 'IN_SCOPE')
        self.assertEqual(res_pay.json().get('understood', {}).get('scope_decision'), 'SPORT_HUB_BUSINESS')

        # 6. Owner / Admin support -> ALLOW
        res_owner = self.client.post('/ai/assistant', json={
            'message': 'Tôi muốn đăng ký làm chủ sân đối tác trên SportHub',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(res_owner.status_code, 200)
        self.assertEqual(res_owner.json().get('classification'), 'IN_SCOPE')
        self.assertEqual(res_owner.json().get('understood', {}).get('scope_decision'), 'SPORT_HUB_BUSINESS')

        # 7. Internal SportHub RAG -> ALLOW
        res_rag = self.client.post('/ai/assistant', json={
            'message': 'Hướng dẫn sử dụng tính năng tìm bạn chơi thể thao',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(res_rag.status_code, 200)
        self.assertEqual(res_rag.json().get('classification'), 'IN_SCOPE')

    def test_transition_natural_to_professional_mode_context_isolation(self):
        conv_id = 'test-session-transition-mode-101'

        # Turn 1: NATURAL Mode with sports knowledge query -> ALLOW
        turn1 = self.client.post('/ai/assistant', json={
            'conversation_id': conv_id,
            'message': 'Kích thước sân bóng đá 7 người tiêu chuẩn',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(turn1.status_code, 200)
        data_turn1 = turn1.json()
        self.assertEqual(data_turn1.get('classification'), 'IN_SCOPE')
        self.assertEqual(data_turn1.get('understood', {}).get('scope_decision'), 'SPORTS_KNOWLEDGE')

        # Turn 2: Switch to PROFESSIONAL Mode with sports knowledge follow-up -> Controlled Refusal (BLOCK)
        turn2 = self.client.post('/ai/assistant', json={
            'conversation_id': conv_id,
            'message': 'Đội bóng Thái Nguyên là gì?',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(turn2.status_code, 200)
        data_turn2 = turn2.json()
        self.assertEqual(data_turn2.get('status'), 'OUT_OF_SCOPE')
        self.assertEqual(data_turn2.get('classification'), 'OUT_OF_SCOPE')
        self.assertEqual(data_turn2.get('understood', {}).get('scope_decision'), 'SPORTS_KNOWLEDGE')
        self.assertIn('Chuyên nghiệp (Professional)', data_turn2.get('reply', ''))

        # Turn 3: Switch to PROFESSIONAL Mode with SportHub business -> ALLOW
        turn3 = self.client.post('/ai/assistant', json={
            'conversation_id': conv_id,
            'message': 'Tìm sân bóng đá tại Hà Nội',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(turn3.status_code, 200)
        data_turn3 = turn3.json()
        self.assertEqual(data_turn3.get('classification'), 'IN_SCOPE')
        self.assertEqual(data_turn3.get('understood', {}).get('scope_decision'), 'SPORT_HUB_BUSINESS')

    def test_natural_mode_friendly_greeting(self):
        response = self.client.post('/ai/assistant', json={
            'message': 'Xin chào',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('classification'), 'IN_SCOPE')
        reply = data.get('reply', '')
        self.assertIn('SportHub AI', reply)
        self.assertTrue('🏸' in reply or '⚽' in reply or '😊' in reply)

    def test_natural_mode_sports_conversational_followup(self):
        conv_id = 'test-natural-mode-multiturn-followup-1'

        # Turn 1: Sports Knowledge query
        turn1 = self.client.post('/ai/assistant', json={
            'conversation_id': conv_id,
            'message': 'Messi là ai?',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(turn1.status_code, 200)
        data_turn1 = turn1.json()
        self.assertEqual(data_turn1.get('understood', {}).get('scope_decision'), 'SPORTS_KNOWLEDGE')
        self.assertEqual(data_turn1.get('understood', {}).get('sports_entity'), 'Lionel Messi')

        # Turn 2: Sports conversational follow-up with pronoun (inherits sports_entity)
        turn2 = self.client.post('/ai/assistant', json={
            'conversation_id': conv_id,
            'message': 'Anh ấy sinh năm bao nhiêu?',
            'assistant_mode': 'NATURAL',
            'context': data_turn1.get('understood', {}),
        })
        self.assertEqual(turn2.status_code, 200)
        data_turn2 = turn2.json()
        self.assertEqual(data_turn2.get('classification'), 'IN_SCOPE')
        self.assertEqual(data_turn2.get('understood', {}).get('scope_decision'), 'SPORTS_KNOWLEDGE')
        self.assertEqual(data_turn2.get('understood', {}).get('sports_entity'), 'Lionel Messi')

        # Turn 3: Follow-up switching to SportHub business search
        turn3 = self.client.post('/ai/assistant', json={
            'conversation_id': conv_id,
            'message': 'Tìm sân bóng đá gần Cầu Giấy',
            'assistant_mode': 'NATURAL',
            'context': data_turn2.get('understood', {}),
        })
        self.assertEqual(turn3.status_code, 200)
        data_turn3 = turn3.json()
        self.assertEqual(data_turn3.get('classification'), 'IN_SCOPE')
        self.assertEqual(data_turn3.get('understood', {}).get('scope_decision'), 'SPORT_HUB_BUSINESS')

    def test_natural_mode_safe_fallback_no_hallucination(self):
        # Query for an unknown/unsupported sports fact within supported sport without evidence
        response = self.client.post('/ai/assistant', json={
            'message': 'Cầu thủ bóng đá Zyxw Vuivui là ai?',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('classification'), 'IN_SCOPE')
        # Returns safe controlled fallback notice instead of hallucinating factual profile
        self.assertIn('chưa có thông tin kiểm chứng', data.get('reply', ''))

    def test_natural_mode_grounded_answer_with_evidence(self):
        # Query with verified internal evidence from knowledge repository
        response = self.client.post('/ai/assistant', json={
            'message': 'Thái Nguyên có những đội bóng nào?',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('classification'), 'IN_SCOPE')
        self.assertEqual(data.get('status'), 'OK')
        reply = data.get('reply', '')
        # Grounded factual information from internal knowledge
        self.assertTrue('Thái Nguyên T&T' in reply or 'FC Thái Nguyên' in reply or 'ICTU' in reply)

    @patch('app.services.sports_web_retriever.SportsWebRetriever.retrieve_evidence')
    def test_natural_mode_does_not_unconditionally_call_web_for_static_queries(self, mock_web: MagicMock):
        # Query that is already fresh & sufficient in internal KB does not trigger external web search
        response = self.client.post('/ai/assistant', json={
            'message': 'Thái Nguyên có những đội bóng nào?',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('classification'), 'IN_SCOPE')
        mock_web.assert_not_called()

    def test_cp05_routing_time_sensitive_query_with_web_evidence(self):
        # Time-sensitive query with mocked search provider returning approved web evidence
        from app.services.sports_web_retriever import SportsWebEvidence

        mock_evidence = [
            SportsWebEvidence(
                url='https://baothainguyen.vn/the-thao/endrick-real-madrid-2026',
                title='Endrick thi đấu tại Real Madrid',
                source_name='Báo Thái Nguyên',
                domain='baothainguyen.vn',
                snippet='Cầu thủ bóng đá Endrick hiện đang thi đấu cho CLB Real Madrid.',
                sport='bóng đá',
                published_date='2026-08-20',
                relevance_score=0.95,
                is_confirmed=True,
            )
        ]
        with patch('app.services.rag_guardrail.RAGGuardrail.retrieve_web_context', return_value=mock_evidence) as mock_web:
            response = self.client.post('/ai/assistant', json={
                'message': 'Cầu thủ bóng đá Endrick hiện đang thi đấu cho CLB nào?',
                'assistant_mode': 'NATURAL',
            })
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data.get('classification'), 'IN_SCOPE')
            self.assertEqual(data.get('status'), 'OK')
            self.assertTrue(mock_web.called)
            reply = data.get('reply', '')
            self.assertIn('Real Madrid', reply)
            self.assertTrue('Báo Thái Nguyên' in reply or 'baothainguyen.vn' in reply)

    @patch('app.services.rag_guardrail.RAGGuardrail.retrieve_web_context')
    @patch('app.services.rag_guardrail.KnowledgeService.retrieve')
    def test_cp05_outside_scope_never_calls_sports_rag_or_web(self, mock_retrieve: MagicMock, mock_web: MagicMock):
        # Out-of-scope non-sports question
        response = self.client.post('/ai/assistant', json={
            'message': 'Thời tiết ngày mai ở Hà Nội thế nào?',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('classification'), 'OUT_OF_SCOPE')
        mock_retrieve.assert_not_called()
        mock_web.assert_not_called()

    @patch('app.services.rag_guardrail.RAGGuardrail.retrieve_web_context')
    @patch('app.services.rag_guardrail.KnowledgeService.retrieve')
    def test_cp05_professional_mode_strictly_blocks_time_sensitive_sports_queries(self, mock_retrieve: MagicMock, mock_web: MagicMock):
        # Even time-sensitive query is blocked early in Professional mode
        response = self.client.post('/ai/assistant', json={
            'message': 'Kết quả trận đấu mới nhất của Hà Nội FC thế nào?',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'OUT_OF_SCOPE')
        self.assertEqual(data.get('classification'), 'OUT_OF_SCOPE')
        self.assertIn('Chuyên nghiệp (Professional)', data.get('reply', ''))
        mock_retrieve.assert_not_called()
        mock_web.assert_not_called()

    def test_cp05_routing_insufficient_kb_fallback_to_approved_web(self):
        from app.services.sports_web_retriever import SportsWebEvidence

        mock_evidence = [
            SportsWebEvidence(
                url='https://vff.org.vn/doi-tuyen-bong-da-nu-2026',
                title='Đội tuyển bóng đá nữ Việt Nam',
                source_name='Liên đoàn Bóng đá Việt Nam (VFF)',
                domain='vff.org.vn',
                snippet='Đội tuyển bóng đá nữ Việt Nam đang tập huấn chuẩn bị giải đấu mới.',
                sport='bóng đá',
                published_date='2026-09-01',
                relevance_score=0.92,
                is_confirmed=True,
            )
        ]
        # When internal KB has no match (empty list), fallback to approved web evidence
        with patch('app.services.rag_guardrail.KnowledgeService.retrieve', return_value=[]):
            with patch('app.services.rag_guardrail.RAGGuardrail.retrieve_web_context', return_value=mock_evidence) as mock_web:
                response = self.client.post('/ai/assistant', json={
                    'message': 'Tình hình tập huấn của đội tuyển bóng đá nữ thế nào?',
                    'assistant_mode': 'NATURAL',
                })
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data.get('classification'), 'IN_SCOPE')
                self.assertEqual(data.get('status'), 'OK')
                self.assertTrue(mock_web.called)
                reply = data.get('reply', '')
                self.assertIn('tập huấn', reply)
                self.assertTrue('VFF' in reply or 'vff.org.vn' in reply)

    def test_cp05_non_whitelisted_web_sources_filtered_out_with_safe_fallback(self):
        # If web retriever returns empty list because all results were from unapproved domains or rumors
        with patch('app.services.rag_guardrail.KnowledgeService.retrieve', return_value=[]):
            with patch('app.services.rag_guardrail.RAGGuardrail.retrieve_web_context', return_value=[]):
                response = self.client.post('/ai/assistant', json={
                    'message': 'Cầu thủ bóng đá UnapprovedRumor có đá cho đội nào không?',
                    'assistant_mode': 'NATURAL',
                })
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data.get('classification'), 'IN_SCOPE')
                # Safe fallback message without hallucination
                self.assertIn('chưa có thông tin kiểm chứng', data.get('reply', ''))

    # CP-08: Mode Switching & Conversation Context Preservation / Sanitization
    def test_mode_switch_natural_to_professional_strips_sports_context(self):
        # Turn 1: Natural mode query on sports knowledge
        res1 = self.client.post('/ai/assistant', json={
            'message': 'Nguyễn Quang Hải là ai?',
            'assistant_mode': 'NATURAL',
        })
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1.get('classification'), 'IN_SCOPE')
        understood1 = data1.get('understood', {})
        self.assertEqual(understood1.get('sports_entity'), 'Nguyễn Quang Hải')

        # Turn 2: Switch to Professional mode and send follow-up using previous context
        res2 = self.client.post('/ai/assistant', json={
            'message': 'Anh ấy sinh năm bao nhiêu?',
            'assistant_mode': 'PROFESSIONAL',
            'context': understood1,
        })
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        # In Professional mode, sports knowledge context must NOT be answered as Natural would
        self.assertNotIn('Quang Hải sinh ngày', data2.get('reply', ''))
        # Should either be refused as sports knowledge or ask for clarification / out of scope
        self.assertEqual(data2.get('assistant_mode'), 'PROFESSIONAL')
        self.assertIsNone(data2.get('understood', {}).get('sports_entity'))

    def test_mode_switch_professional_to_natural_preserves_business_context(self):
        # Turn 1: Professional mode business query
        res1 = self.client.post('/ai/assistant', json={
            'message': 'Tìm sân bóng đá ở Cầu Giấy',
            'assistant_mode': 'PROFESSIONAL',
        })
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1.get('classification'), 'IN_SCOPE')
        understood1 = data1.get('understood', {})
        self.assertEqual(understood1.get('sport_type'), 'bóng đá')
        self.assertEqual(understood1.get('location'), 'Cầu Giấy')

        # Turn 2: Switch to Natural mode and send follow-up query
        res2 = self.client.post('/ai/assistant', json={
            'message': 'Tối mai có sân không?',
            'assistant_mode': 'NATURAL',
            'context': understood1,
        })
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2.get('classification'), 'IN_SCOPE')
        self.assertEqual(data2.get('assistant_mode'), 'NATURAL')
        # Business context is preserved
        self.assertEqual(data2.get('understood', {}).get('sport_type'), 'bóng đá')
        self.assertEqual(data2.get('understood', {}).get('location'), 'Cầu Giấy')


if __name__ == '__main__':
    unittest.main()






