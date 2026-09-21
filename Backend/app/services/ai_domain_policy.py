from dataclasses import dataclass
from enum import Enum

from ..schemas.ai import AssistantMode
from .ai_intent_router import AssistantIntent


class ScopeDomain(str, Enum):
    SPORTHUB_BUSINESS = 'SPORTHUB_BUSINESS'
    SPORTS_KNOWLEDGE = 'SPORTS_KNOWLEDGE'
    CONVERSATIONAL_FOLLOWUP = 'CONVERSATIONAL_FOLLOWUP'
    OUT_OF_SCOPE = 'OUT_OF_SCOPE'


class ScopeClassification(str, Enum):
    IN_SCOPE = 'IN_SCOPE'
    OUT_OF_SCOPE = 'OUT_OF_SCOPE'
    UNCLEAR = 'UNCLEAR'


class ScopeDecision(str, Enum):
    SPORT_HUB_BUSINESS = 'SPORT_HUB_BUSINESS'
    SPORTS_KNOWLEDGE = 'SPORTS_KNOWLEDGE'
    OUT_OF_SCOPE = 'OUT_OF_SCOPE'
    UNCLEAR = 'UNCLEAR'


class AllowedSource(str, Enum):
    SPORTHUB_DB = 'SPORTHUB_DB'
    INTERNAL_RAG = 'INTERNAL_RAG'
    SPORTS_KNOWLEDGE_RAG = 'SPORTS_KNOWLEDGE_RAG'
    APPROVED_SPORTS_WEB = 'APPROVED_SPORTS_WEB'


class ScopeRouter:
    """Domain classification layer for SportHub AI.
    
    Determines the high-level capability branch before handing off to specialized services:
    - SPORTHUB_BUSINESS: Venue search, booking, availability, facilities, owner application, system guide.
    - SPORTS_KNOWLEDGE: Multi-sport knowledge (World Cup, rules, athletes, tournaments, stats).
    - CONVERSATIONAL_FOLLOWUP: Multi-turn context references, pronouns, entity/sport shifts, or returning to prior tasks.
    - OUT_OF_SCOPE: Non-sports / non-SportHub queries rejected gracefully via guardrail.
    """

    @classmethod
    def classify_domain(
        cls,
        query: str,
        context: dict | None = None,
        assistant_mode: AssistantMode | str = AssistantMode.NATURAL,
    ) -> ScopeDomain:
        from .ai_intent_router import normalize_text, DOMAIN_TERMS, UNSUPPORTED_SPORTS_TERMS, IntentRouter, AssistantIntent
        import re

        context = context or {}
        norm_q = normalize_text(query.strip())
        mode_val = AssistantMode(assistant_mode) if isinstance(assistant_mode, str) else (assistant_mode or AssistantMode.NATURAL)

        # 1. Abusive / Nonsense
        if IntentRouter._is_abusive(norm_q) or IntentRouter._is_nonsense(norm_q):
            return ScopeDomain.OUT_OF_SCOPE

        # 2. Out-of-scope non-sports detection
        if any(term in norm_q for term in UNSUPPORTED_SPORTS_TERMS):
            return ScopeDomain.OUT_OF_SCOPE

        out_of_scope_patterns = (
            'thoi tiet', 'du bao thoi tiet', 'nau an', 'cong thuc nau', 'lam banh', 'mon an', 'thit cho', 'cach nau',
            'che buoi', 'nau che', 'cong thuc', 'an gi', 'uong gi',
            'viet code', 'lap trinh', 'giai toan', 'bai toan', 'viet cv', 'dich tieng anh',
            'tin tuc', 'bitcoin', 'crypto', 'gia vang', 'chung khoan', 'xem phim', 'rap chieu phim',
            'tinh cam', 'tam su', 'sua may tinh', 'dien thoai', 'hoc bai', 'sua xe', 'xe may', 'sua xe may', 'cach sua xe',
        )
        if any(p in norm_q for p in out_of_scope_patterns):
            # Check if domain terms are present
            has_domain = any(term in norm_q for term in DOMAIN_TERMS)
            if not has_domain:
                return ScopeDomain.OUT_OF_SCOPE

        # In professional mode, sports knowledge is out of scope
        is_sports_inquiry = any(k in norm_q for k in (
            'world cup', 'wc', 'c1', 'champions league', 'ballon d\'or', 'qua bong vang', 'grand slam',
            'cau thu', 'van dong vien', 'vdv', 'tay vot', 'sieu sao', 'hlv', 'huan luyen vien',
            'vo dich', 'ghi ban', 'ban thang', 'cup', 'danh hieu', 'giai nghe', 'sinh nam', 'que o',
            'messi', 'ronaldo', 'cr7', 'm10', 'mbappe', 'haaland', 'neymar', 'federer', 'nadal', 'djokovic',
            'thuy linh', 'tien minh', 'axelsen', 'lin dan', 'lebron', 'curry', 'bich tuyen', 'ben johns',
        ))
        if mode_val == AssistantMode.PROFESSIONAL and is_sports_inquiry and not any(k in norm_q for k in ('tim san', 'dat san', 'gia san', 'san nao')):
            return ScopeDomain.OUT_OF_SCOPE

        # 3. Conversational Follow-up detection
        return_to_business_patterns = (
            'thoi tim san', 'quay lai tim san', 'quay lai dat san', 'tim san luc nay', 'san luc nay',
            'dat san luc nay', 'thoi xem san', 'quay lai xem san', 'thoi kiem san', 'tim san bong luc nay',
        )
        if any(p in norm_q for p in return_to_business_patterns):
            return ScopeDomain.CONVERSATIONAL_FOLLOWUP

        follow_up_starters = (
            'con ', 'the con ', 'vay con ', 'vay ', 'the thi ', 'o do ', 'o day ', 'ong nay ', 'anh ay ',
            'co ay ', 'nguoi nay ', 'doi nay ', 'giai nay ', 'mon nay ', 'bao nhieu ', 'may qua ', 'co chua ',
            'da co chua ', 'o dau ', 'thi sao ',
        )
        is_followup = (
            any(norm_q.startswith(p) for p in follow_up_starters)
            or any(re.search(r'\b' + re.escape(p) + r'\b', norm_q) for p in (
                'anh ay', 'ong ay', 'ong nay', 'co ay', 'nguoi nay', 'mon nay', 'doi nay', 'giai nay',
                'o do', 'o day', 'thi sao', 'con c1', 'con wc', 'con messi', 'con ronaldo', 'con cr7',
            ))
        )
        has_prior_context = bool(
            context.get('last_intent') or context.get('active_entity') or context.get('sports_entity')
            or context.get('sport_type') or context.get('sport') or context.get('field_id') or context.get('business_context')
        )
        if is_followup and has_prior_context:
            return ScopeDomain.CONVERSATIONAL_FOLLOWUP

        # 4. Sports Knowledge vs SportHub Business
        business_indicators = (
            'tim san', 'dat san', 'kiem san', 'thue san', 'gia san', 'san nao', 'co san', 'con san',
            'lich dat', 'ma dat', 'huy san', 'doi san', 'doi lich', 'thanh toan', 'hoan tien', 'dat coc',
            'chu san', 'dang ky doi tac', 'dang ky owner', 'ho so doi tac', 'san pham', 'thue vot', 'mua nuoc',
            'cong suat', 'ti le lap day', 'huong dan', 'tai khoan', 'dang nhap', 'dang ky',
        )
        if any(term in norm_q for term in business_indicators):
            return ScopeDomain.SPORTHUB_BUSINESS

        if is_sports_inquiry or any(k in norm_q for k in ('luat choi', 'luat thi dau', 'kich thuoc san', 'chieu cao luoi', 'doi tuyen', 'clb')):
            return ScopeDomain.SPORTS_KNOWLEDGE

        # Greetings and general conversation are handled inside SportHub Business / Natural assistant
        return ScopeDomain.SPORTHUB_BUSINESS


PROFESSIONAL_SPORTS_KNOWLEDGE_REFUSAL = (
    "Ở chế độ Chuyên nghiệp (Professional), tôi chỉ hỗ trợ các nghiệp vụ trực tiếp trên hệ thống SportHub AI "
    "(tìm sân, kiểm tra lịch trống, đặt sân, thanh toán, quản lý cơ sở). "
    "Vui lòng chuyển sang chế độ Tự nhiên (Natural) nếu bạn muốn tra cứu kiến thức thể thao chung."
)


@dataclass
class ModeScopeEvaluation:
    mode: AssistantMode
    scope_decision: ScopeDecision
    classification: ScopeClassification
    allowed_sources: set[AllowedSource]
    is_allowed: bool
    refusal_reply: str | None = None


def evaluate_mode_scope(
    mode: AssistantMode | str = AssistantMode.NATURAL,
    intent: AssistantIntent | str = AssistantIntent.SEARCH_VENUE,
    query: str | None = None,
) -> ModeScopeEvaluation:
    # Normalize mode
    if isinstance(mode, str):
        mode_str = mode.upper()
        mode_val = AssistantMode[mode_str] if mode_str in AssistantMode.__members__ else AssistantMode.NATURAL
    else:
        mode_val = mode or AssistantMode.NATURAL

    # Normalize intent
    if isinstance(intent, str):
        intent_val = AssistantIntent[intent] if intent in AssistantIntent.__members__ else AssistantIntent(intent)
    else:
        intent_val = intent

    # 1. Determine Scope Decision & base classification
    if intent_val in (AssistantIntent.ABUSIVE, AssistantIntent.NONSENSE):
        scope_decision = ScopeDecision.OUT_OF_SCOPE
        base_classification = ScopeClassification.OUT_OF_SCOPE
    elif intent_val == AssistantIntent.OUT_OF_SCOPE:
        scope_decision = ScopeDecision.OUT_OF_SCOPE
        base_classification = ScopeClassification.OUT_OF_SCOPE
    elif intent_val == AssistantIntent.UNCLEAR:
        scope_decision = ScopeDecision.UNCLEAR
        base_classification = ScopeClassification.UNCLEAR
    elif intent_val == AssistantIntent.SPORTS_KNOWLEDGE:
        scope_decision = ScopeDecision.SPORTS_KNOWLEDGE
        base_classification = ScopeClassification.IN_SCOPE
    else:
        scope_decision = ScopeDecision.SPORT_HUB_BUSINESS
        base_classification = ScopeClassification.IN_SCOPE

    # 2. Determine Allowed Sources & Permissions by Mode
    if mode_val == AssistantMode.PROFESSIONAL:
        allowed_sources = {AllowedSource.SPORTHUB_DB, AllowedSource.INTERNAL_RAG}
        if scope_decision == ScopeDecision.SPORTS_KNOWLEDGE:
            return ModeScopeEvaluation(
                mode=mode_val,
                scope_decision=scope_decision,
                classification=ScopeClassification.OUT_OF_SCOPE,
                allowed_sources=set(),
                is_allowed=False,
                refusal_reply=PROFESSIONAL_SPORTS_KNOWLEDGE_REFUSAL,
            )
        elif intent_val == AssistantIntent.OUT_OF_SCOPE:
            return ModeScopeEvaluation(
                mode=mode_val,
                scope_decision=scope_decision,
                classification=ScopeClassification.OUT_OF_SCOPE,
                allowed_sources=set(),
                is_allowed=False,
                refusal_reply=OUT_OF_SCOPE_REPLY,
            )
        else:
            return ModeScopeEvaluation(
                mode=mode_val,
                scope_decision=scope_decision,
                classification=base_classification,
                allowed_sources=allowed_sources,
                is_allowed=True,
                refusal_reply=None,
            )
    else:  # NATURAL
        allowed_sources = {
            AllowedSource.SPORTHUB_DB,
            AllowedSource.INTERNAL_RAG,
            AllowedSource.SPORTS_KNOWLEDGE_RAG,
            AllowedSource.APPROVED_SPORTS_WEB,
        }
        if intent_val == AssistantIntent.OUT_OF_SCOPE:
            return ModeScopeEvaluation(
                mode=mode_val,
                scope_decision=scope_decision,
                classification=ScopeClassification.OUT_OF_SCOPE,
                allowed_sources=set(),
                is_allowed=False,
                refusal_reply=OUT_OF_SCOPE_REPLY,
            )
        else:
            return ModeScopeEvaluation(
                mode=mode_val,
                scope_decision=scope_decision,
                classification=base_classification,
                allowed_sources=allowed_sources,
                is_allowed=True,
                refusal_reply=None,
            )


# Canonical prompt for any present or future LLM integration. Runtime access control
# must still be enforced by the API/repository; a prompt is never a security boundary.
SPORTHUB_ASSISTANT_SYSTEM_PROMPT = """
Bạn là AI Trợ lý chuyên biệt của SportHub AI, một nhân viên hỗ trợ nghiệp vụ sân thể thao.

Trước mỗi yêu cầu, bắt buộc chạy Intent Router và chỉ gọi service tương ứng sau khi có
intent. Các intent hợp lệ: SEARCH_VENUE, RECOMMEND_VENUE, CHECK_AVAILABILITY, RECOMMEND_SLOT,
OCCUPANCY_INSIGHT,
GET_VENUE_DETAIL, GET_PRODUCTS, CREATE_BOOKING, GET_BOOKING, CANCEL_BOOKING, RESCHEDULE_BOOKING,
PAYMENT_SUPPORT, ACCOUNT_SUPPORT, SYSTEM_GUIDE, GREETING, FOLLOW_UP, UNCLEAR và
OUT_OF_SCOPE. Router phải trả confidence, entities và needs_clarification.

Phân loại phạm vi vẫn bắt buộc là IN_SCOPE, OUT_OF_SCOPE hoặc UNCLEAR.
- IN_SCOPE: tìm/gợi ý sân; môn, cơ sở, địa điểm, tiện ích; giá và lịch trống; đặt sân,
  sản phẩm/dịch vụ đang bán hoặc cho thuê, giá snapshot và số lượng khả dụng từ backend;
  chống trùng lịch; cọc, thanh toán, hoàn tiền, hóa đơn; trạng thái/chính sách booking;
  hướng dẫn SportHub AI; hồ sơ/lịch sử của chính người dùng; nghiệp vụ OWNER
  trong quyền được cấp; giải thích dữ liệu SportHub AI truy xuất được.
- OUT_OF_SCOPE: mọi kiến thức hay tác vụ không trực tiếp phục vụ SportHub AI. Từ chối
  thân thiện và không trả lời nội dung chung.
- UNCLEAR: thiếu ý định hoặc đối tượng; hỏi lại một câu ngắn theo ngữ cảnh SportHub AI.

Chỉ dùng dữ liệu do backend SportHub AI cung cấp. Không tự tạo tên sân, sản phẩm, giá, số lượng, địa chỉ,
lịch trống, booking, thanh toán hay chính sách. Nếu không có dữ liệu, nói rõ không tìm
thấy trong SportHub AI. Không thực hiện đặt sân/thanh toán thay người dùng; hướng dẫn
bước xác nhận tiếp theo. Không tiết lộ dữ liệu người khác. CUSTOMER chỉ thấy dữ liệu
của mình; OWNER chỉ thấy cơ sở thuộc mình; SYSTEM_ADMIN chỉ xem dữ liệu quản trị tổng hợp
được cấp quyền. Dùng danh sách kết quả trong context để hiểu các tham chiếu tiếp nối.
""".strip()


OUT_OF_SCOPE_REPLY = (
    "Xin lỗi bạn, tôi là trợ lý chuyên biệt của SportHub AI nên chỉ hỗ trợ các thông tin liên quan đến:\n"
    "- Tìm kiếm sân và kiểm tra lịch trống\n"
    "- Giá sân và tiện ích đi kèm\n"
    "- Hướng dẫn đặt sân, đổi lịch, hủy lịch\n"
    "- Quy trình thanh toán và tài khoản SportHub\n"
    "- Hướng dẫn dành cho chủ sân (Owner)\n\n"
    "Bạn có thể thử các câu hỏi như:\n"
    "- 'Tìm sân cầu lông tối nay ở Cầu Giấy'\n"
    "- 'Sân bóng đá nào còn trống sau 18h?'\n"
    "- 'Làm thế nào để đổi lịch đặt sân?'\n\n"
    "Tôi có thể giúp gì cho bạn về các dịch vụ trên?"
)

COMBINED_OUT_OF_SCOPE_REPLY = (
    "Xin lỗi bạn, tôi là trợ lý chuyên biệt của SportHub AI nên chỉ có thể hỗ trợ bạn tìm sân và dịch vụ thể thao trong hệ thống. "
    "Tôi không thể hỗ trợ các nội dung ngoài phạm vi này. "
    "Bạn có muốn tôi kiểm tra lại lịch sân hoặc gợi ý sân gần bạn không?"
)

NO_DATA_REPLY = 'Hiện tôi chưa tìm thấy dữ liệu phù hợp với yêu cầu này trong SportHub AI.'


def generate_out_of_scope_redirect(
    query: str,
    context: dict | None = None,
    mode: AssistantMode | str = AssistantMode.NATURAL,
) -> str:
    """Generate a polite, natural out-of-scope redirect according to SportHub AI Response Policy.
    
    Response Policy:
    - Brief and polite acknowledgement without judging the user.
    - No pretend knowledge for un-scoped topics.
    - Contextual bridge back to SportHub capabilities (venue search, booking, sports knowledge).
    - Suggest relevant sports/court functionality if prior context exists.
    - Strict professional format in Professional Mode.
    """
    from .ai_intent_router import normalize_text
    norm_q = normalize_text(query.strip()) if query else ''
    context = context or {}
    
    if isinstance(mode, str):
        mode_val = AssistantMode[mode.upper()] if mode.upper() in AssistantMode.__members__ else AssistantMode.NATURAL
    else:
        mode_val = mode or AssistantMode.NATURAL

    # 1. Professional Mode: Strict, direct business refusal
    if mode_val == AssistantMode.PROFESSIONAL:
        return OUT_OF_SCOPE_REPLY

    # 2. Natural Mode: Contextual bridge
    prev_sport = context.get('sport_type') or context.get('sport')
    prev_venue = context.get('venue_name')
    prev_entity = context.get('sports_entity') or context.get('active_entity')

    context_tail = ""
    if prev_sport:
        context_tail = f" Bạn có muốn tiếp tục tìm sân hoặc xem khung giờ trống cho môn {prev_sport} không? 🏸⚽"
    elif prev_venue:
        context_tail = f" Bạn có muốn kiểm tra tiếp lịch trống của {prev_venue} không?"
    elif prev_entity:
        context_tail = f" Hoặc bạn có muốn tìm hiểu thêm thông tin gì về {prev_entity} không? 🏆"

    import re

    def has_term(terms: tuple[str, ...]) -> bool:
        for t in terms:
            if ' ' in t:
                if t in norm_q:
                    return True
            else:
                if re.search(r'\b' + re.escape(t) + r'\b', norm_q):
                    return True
        return False

    # Category 1: Food / Culinary / Dining
    food_terms = ('thit cho', 'mon an', 'nau an', 'cong thuc', 'lam banh', 'an gi', 'uong gi', 'nha hang', 'quan an', 'mon ngon', 'bun cha', 'pho bo', 'nau', 'cach nau', 'che', 'che buoi', 'pizza')
    if has_term(food_terms):
        base = (
            "Xin lỗi bạn, tôi là trợ lý chuyên biệt của SportHub AI nên chỉ hỗ trợ các thông tin liên quan đến thể thao và hệ thống:\n"
            "- Tìm kiếm sân và kiểm tra lịch trống (bóng đá, cầu lông, pickleball, tennis, bóng rổ...)\n"
            "- Giá sân và tiện ích đi kèm\n"
            "- Hướng dẫn đặt sân, đổi lịch, hủy lịch\n"
            "- Tra cứu kiến thức, luật thi đấu và thông tin thể thao\n\n"
            "Hiện tại mình chưa có thông tin chuyên sâu về ẩm thực hay nấu ăn."
        )
        return base + (context_tail or " Bạn đang muốn tìm sân thể thao nào để vận động cùng bạn bè không? 🏸⚽")

    # Category 2: Finance / Stocks / Crypto / Real Estate / Money
    finance_terms = ('chung khoan', 'bitcoin', 'crypto', 'tai chinh', 'tien ao', 'gia vang', 'dau tu', 'bat dong san', 'forex', 'co phieu')
    if has_term(finance_terms):
        base = (
            "Xin lỗi bạn, tôi là trợ lý chuyên biệt của SportHub AI nên chỉ hỗ trợ các thông tin liên quan đến thể thao và hệ thống:\n"
            "- Tìm kiếm sân và kiểm tra lịch trống\n"
            "- Giá sân và tiện ích đi kèm\n"
            "- Hướng dẫn đặt sân, đổi lịch, hủy lịch\n"
            "- Tra cứu kiến thức thể thao\n\n"
            "Mình không có chuyên môn trong lĩnh vực tài chính, chứng khoán hay đầu tư tiền tệ."
        )
        return base + (context_tail or " Bạn đang quan tâm đến môn thể thao nào hôm nay? 🏸🎾")

    # Category 3: Technical / Vehicle Repair / Hardware / Software / Programming
    tech_terms = ('sua xe', 'xe may', 'sua xe may', 'sua o to', 'sua may tinh', 'cai win', 'lap trinh', 'python', 'viet code', 'sua code', 'fix bug', 'javascript', 'viet app', 'phan mem')
    if has_term(tech_terms):
        base = (
            "Xin lỗi bạn, tôi là trợ lý chuyên biệt của SportHub AI nên chỉ hỗ trợ các thông tin liên quan đến thể thao và hệ thống:\n"
            "- Tìm kiếm sân và kiểm tra lịch trống\n"
            "- Giá sân và tiện ích đi kèm\n"
            "- Hướng dẫn đặt sân, đổi lịch, hủy lịch\n"
            "- Tra cứu kiến thức thể thao\n\n"
            "Hiện tại mình không hỗ trợ kỹ thuật sửa chữa máy móc hay lập trình phần mềm."
        )
        return base + (context_tail or " Bạn có muốn mình hỗ trợ tìm sân để rèn luyện và thư giãn không? 🏃‍♂️✨")

    # Category 4: Academic / Homework / Essay / Translation / Admissions
    academic_terms = ('toan hoc', 'giai toan', 'giai bai', 'bai toan', 'viet cv', 'viet bai', 'viet van', 'bai tho', 'dich thuat', 'dich sang', 'dich tieng anh', 'tuyen sinh', 'hoc phi', 'diem chuan')
    if has_term(academic_terms):
        base = (
            "Xin lỗi bạn, tôi là trợ lý chuyên biệt của SportHub AI nên chỉ hỗ trợ các thông tin liên quan đến thể thao và hệ thống:\n"
            "- Tìm kiếm sân và kiểm tra lịch trống\n"
            "- Giá sân và tiện ích đi kèm\n"
            "- Hướng dẫn đặt sân, đổi lịch, hủy lịch\n"
            "- Tra cứu kiến thức thể thao\n\n"
            "Mình không hỗ trợ giải bài tập hay viết văn bản ngoài lĩnh vực thể thao."
        )
        return base + (context_tail or " Bạn có muốn mình gợi ý một số sân thể thao thuận tiện không? 🏸⚽")

    # Category 5: Weather / News / General Non-sports
    news_terms = ('thoi tiet', 'du bao thoi tiet', 'tin tuc', 'phim', 'am nhac', 'du lich', 'tinh cam', 'tinh yeu')
    if has_term(news_terms):
        base = (
            "Xin lỗi bạn, tôi là trợ lý chuyên biệt của SportHub AI nên chỉ hỗ trợ các thông tin liên quan đến thể thao và hệ thống:\n"
            "- Tìm kiếm sân và kiểm tra lịch trống\n"
            "- Giá sân và tiện ích đi kèm\n"
            "- Hướng dẫn đặt sân, đổi lịch, hủy lịch\n"
            "- Tra cứu kiến thức thể thao\n\n"
            "Hiện tại mình chưa hỗ trợ tra cứu thông tin ngoài phạm vi thể thao."
        )
        return base + (context_tail or " Bạn có muốn tìm sân chơi hoặc hỏi về môn thể thao nào không? ⚽🏆")

    # Category 6: Default Natural Redirect
    base = (
        "Xin lỗi bạn, tôi là trợ lý chuyên biệt của SportHub AI nên chỉ hỗ trợ các thông tin liên quan đến thể thao và hệ thống:\n"
        "- Tìm kiếm sân và kiểm tra lịch trống (bóng đá, cầu lông, tennis, pickleball...)\n"
        "- Giá sân và tiện ích đi kèm\n"
        "- Hướng dẫn đặt sân, đổi lịch, hủy lịch\n"
        "- Tra cứu kiến thức thể thao\n\n"
        "Câu hỏi này nằm ngoài phạm vi chuyên môn của mình."
    )
    return base + (context_tail or " Bạn cần mình hỗ trợ thông tin gì về thể thao hôm nay? 😊🏸")


