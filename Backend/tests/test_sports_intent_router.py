from datetime import date
import unittest

from app.services.ai_intent_router import AssistantIntent, IntentRouter


class SportsIntentRouterTests(unittest.TestCase):
    def setUp(self):
        self.router = IntentRouter()
        self.today = date(2026, 9, 16)

    def route(self, message: str, context: dict | None = None):
        return self.router.route(message, context=context, today=self.today)

    # ----------------------------------------------------
    # 1. 6 SUPPORTED SPORTS TESTS
    # ----------------------------------------------------
    def test_football_knowledge(self):
        # International
        r1 = self.route('Messi là ai?')
        self.assertEqual(r1.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(r1.entities.sport_type, 'bóng đá')
        self.assertEqual(r1.entities.sports_entity, 'Lionel Messi')

        r2 = self.route('Cristiano Ronaldo có bao nhiêu bàn thắng?')
        self.assertEqual(r2.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(r2.entities.sport_type, 'bóng đá')

        # Vietnam
        r3 = self.route('Nguyễn Quang Hải đang chơi cho đội nào?')
        self.assertEqual(r3.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(r3.entities.sport_type, 'bóng đá')

        # Thai Nguyen
        r4 = self.route('Thái Nguyên T&T là câu lạc bộ bóng đá nào?')
        self.assertEqual(r4.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(r4.entities.sport_type, 'bóng đá')

    def test_badminton_knowledge(self):
        # Vietnam
        r1 = self.route('Nguyễn Thùy Linh là ai?')
        self.assertEqual(r1.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(r1.entities.sport_type, 'cầu lông')
        self.assertEqual(r1.entities.sports_entity, 'Nguyễn Thùy Linh')

        # Thai Nguyen
        r2 = self.route('Badminton ở Thái Nguyên có những gì?')
        self.assertEqual(r2.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(r2.entities.sport_type, 'cầu lông')

        # International & Rules
        r3 = self.route('Viktor Axelsen đã vô địch những giải đấu nào?')
        self.assertEqual(r3.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(r3.entities.sport_type, 'cầu lông')

        r4 = self.route('Kích thước sân cầu lông tiêu chuẩn quốc tế là bao nhiêu?')
        self.assertEqual(r4.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(r4.entities.sport_type, 'cầu lông')

    def test_pickleball_knowledge(self):
        r1 = self.route('Ben Johns là ai trong môn pickleball?')
        self.assertEqual(r1.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(r1.entities.sport_type, 'pickleball')

        r2 = self.route('Luật tính điểm môn pickleball như thế nào?')
        self.assertEqual(r2.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(r2.entities.sport_type, 'pickleball')

        r3 = self.route('Phong trào pickleball Thái Nguyên hiện nay ra sao?')
        self.assertEqual(r3.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(r3.entities.sport_type, 'pickleball')

    def test_tennis_knowledge(self):
        r1 = self.route('Novak Djokovic giành bao nhiêu danh hiệu Grand Slam?')
        self.assertEqual(r1.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(r1.entities.sport_type, 'tennis')

        r2 = self.route('Lý Hoàng Nam là ai?')
        self.assertEqual(r2.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(r2.entities.sport_type, 'tennis')

        r3 = self.route('Luật thi đấu tennis đánh đôi quy định thế nào?')
        self.assertEqual(r3.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(r3.entities.sport_type, 'tennis')

    def test_basketball_knowledge(self):
        r1 = self.route('LeBron James đang chơi cho câu lạc bộ nào?')
        self.assertEqual(r1.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(r1.entities.sport_type, 'bóng rổ')

        r2 = self.route('Saigon Heat thi đấu ở giải bóng rổ nào?')
        self.assertEqual(r2.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(r2.entities.sport_type, 'bóng rổ')

        r3 = self.route('Quy tắc ném 3 điểm trong bóng rổ là gì?')
        self.assertEqual(r3.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(r3.entities.sport_type, 'bóng rổ')

    def test_volleyball_knowledge(self):
        r1 = self.route('Đội tuyển bóng chuyền nữ Việt Nam?')
        self.assertEqual(r1.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(r1.entities.sport_type, 'bóng chuyền')

        r2 = self.route('Trần Thị Thanh Thúy là ai?')
        self.assertEqual(r2.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(r2.entities.sport_type, 'bóng chuyền')

        r3 = self.route('Giải bóng chuyền VTV Cup có lịch sử như thế nào?')
        self.assertEqual(r3.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(r3.entities.sport_type, 'bóng chuyền')

    # ----------------------------------------------------
    # 2. GEOGRAPHIC SCOPE PRIORITY (Thai Nguyen -> VN -> Global)
    # ----------------------------------------------------
    def test_geographic_scope_routing(self):
        # Thai Nguyen
        r_tn = self.route('Sân vận động Thái Nguyên có sức chứa bao nhiêu?')
        self.assertEqual(r_tn.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(r_tn.entities.sports_entity, 'Sân vận động Thái Nguyên')

        # Vietnam
        r_vn = self.route('Đội tuyển bóng đá nam Việt Nam vô địch AFF Cup những năm nào?')
        self.assertEqual(r_vn.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(r_vn.entities.sport_type, 'bóng đá')

        # Global
        r_global = self.route('Giải bóng đá FIFA World Cup tổ chức bao nhiêu năm một lần?')
        self.assertEqual(r_global.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(r_global.entities.sport_type, 'bóng đá')

    # ----------------------------------------------------
    # 3. BUSINESS INTENTS MUST NOT BE INTERCEPTED
    # ----------------------------------------------------
    def test_business_intents_are_preserved(self):
        # Check availability
        r1 = self.route('Sân bóng đá ở Thái Nguyên còn trống tối nay?')
        self.assertEqual(r1.intent, AssistantIntent.CHECK_AVAILABILITY)

        # Booking
        r2 = self.route('Đặt sân pickleball ngày mai')
        self.assertIn(r2.intent, (AssistantIntent.CREATE_BOOKING, AssistantIntent.CHECK_AVAILABILITY, AssistantIntent.SEARCH_VENUE))
        self.assertNotEqual(r2.intent, AssistantIntent.SPORTS_KNOWLEDGE)

        # Search venue
        r3 = self.route('Tìm sân cầu lông ở Quận 1')
        self.assertEqual(r3.intent, AssistantIntent.SEARCH_VENUE)

        # Venue price & detail
        r4 = self.route('Giá sân bóng đá ở Thái Nguyên bao nhiêu?')
        self.assertIn(r4.intent, (AssistantIntent.GET_VENUE_DETAIL, AssistantIntent.SEARCH_VENUE))

        # Cancel booking
        r5 = self.route('Hủy lịch đặt sân mã SH-12345')
        self.assertEqual(r5.intent, AssistantIntent.CANCEL_BOOKING)

        # Reschedule booking
        r6 = self.route('Tôi muốn đổi lịch sân sang ngày mai mã SH-999')
        self.assertEqual(r6.intent, AssistantIntent.RESCHEDULE_BOOKING)

        # Payment support
        r7 = self.route('Tôi muốn được hoàn tiền đặt cọc')
        self.assertEqual(r7.intent, AssistantIntent.PAYMENT_SUPPORT)

        # Products & rental
        r8 = self.route('Ở sân có bán nước hoặc thuê vợt cầu lông không?')
        self.assertEqual(r8.intent, AssistantIntent.GET_PRODUCTS)

    # ----------------------------------------------------
    # 4. ESPORTS & UNSUPPORTED SPORTS REJECTED AS OUT_OF_SCOPE
    # ----------------------------------------------------
    def test_unsupported_sports_out_of_scope(self):
        # Esports
        r1 = self.route('Faker là ai?')
        self.assertEqual(r1.intent, AssistantIntent.OUT_OF_SCOPE)

        r2 = self.route('Valorant có bao nhiêu nhân vật?')
        self.assertEqual(r2.intent, AssistantIntent.OUT_OF_SCOPE)

        r3 = self.route('Đội tuyển T1 vô địch Liên Minh Huyền Thoại mấy lần?')
        self.assertEqual(r3.intent, AssistantIntent.OUT_OF_SCOPE)

        # Other sports not in the 6 supported sports
        r4 = self.route('Luật chơi môn golf là gì?')
        self.assertEqual(r4.intent, AssistantIntent.OUT_OF_SCOPE)

        r5 = self.route('Cách chơi bi-a 8 bóng thế nào?')
        self.assertEqual(r5.intent, AssistantIntent.OUT_OF_SCOPE)

        r6 = self.route('Kỷ lục thế giới môn bơi lội 100m là bao nhiêu?')
        self.assertEqual(r6.intent, AssistantIntent.OUT_OF_SCOPE)

        r7 = self.route('Võ thuật Boxing có những hạng cân nào?')
        self.assertEqual(r7.intent, AssistantIntent.OUT_OF_SCOPE)

    # ----------------------------------------------------
    # 5. GENERAL NON-SPORTS QUERIES OUT_OF_SCOPE
    # ----------------------------------------------------
    def test_non_sports_out_of_scope(self):
        r1 = self.route('Python là gì?')
        self.assertEqual(r1.intent, AssistantIntent.OUT_OF_SCOPE)

        r2 = self.route('Hướng dẫn cách nấu món phở bò Nam Định')
        self.assertEqual(r2.intent, AssistantIntent.OUT_OF_SCOPE)

        r3 = self.route('Thời tiết hôm nay ở Hà Nội như thế nào?')
        self.assertEqual(r3.intent, AssistantIntent.OUT_OF_SCOPE)

        r4 = self.route('Viết cho tôi một bài thơ tình lãng mạn')
        self.assertEqual(r4.intent, AssistantIntent.OUT_OF_SCOPE)

        r5 = self.route('Giá tiền ảo Bitcoin hôm nay là bao nhiêu?')
        self.assertEqual(r5.intent, AssistantIntent.OUT_OF_SCOPE)

    # ----------------------------------------------------
    # 6. MULTI-TURN SPORTS KNOWLEDGE FOLLOW-UP
    # ----------------------------------------------------
    def test_sports_knowledge_follow_up(self):
        # Turn 1
        r1 = self.route('Messi là ai?')
        self.assertEqual(r1.intent, AssistantIntent.SPORTS_KNOWLEDGE)

        # Turn 2: Follow-up pronoun
        context1 = {'last_intent': 'SPORTS_KNOWLEDGE', 'sports_entity': 'Lionel Messi', 'sport_type': 'bóng đá'}
        r2 = self.route('Anh ấy sinh năm bao nhiêu?', context=context1)
        self.assertEqual(r2.intent, AssistantIntent.SPORTS_KNOWLEDGE)
        self.assertEqual(r2.entities.sports_entity, 'Lionel Messi')

        # Turn 3: Follow-up club
        r3 = self.route('Đang thi đấu cho câu lạc bộ nào?', context=context1)
        self.assertEqual(r3.intent, AssistantIntent.SPORTS_KNOWLEDGE)


if __name__ == '__main__':
    unittest.main()
