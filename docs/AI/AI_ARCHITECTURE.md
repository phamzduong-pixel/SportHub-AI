# Kiến trúc Hệ thống AI — SportHub AI Assistant (CP-11B)

> **Hiện trạng đã đối chiếu source: 27/10/2026.** Phần dưới ghi lại các checkpoint cũ, có thể không còn phản ánh runtime. Khi mâu thuẫn, dùng mục **Hiện trạng vận hành hiện tại** bên dưới và source code; không dùng các tuyên bố cũ về “độ chính xác 100%”, web được duyệt mặc định hoặc auto-update như trạng thái hiện tại.

## Hiện trạng vận hành hiện tại

SportHub dùng pipeline điều phối có kiểm soát, không phải autonomous agent. `IntentRouter` nhận intent/entity/context; `AIAssistantService` chọn luồng nghiệp vụ, System Domain, Sports Knowledge hoặc phản hồi phạm vi. Dữ liệu giá, sân, slot, booking, tài khoản và thanh toán phải qua backend/database và scope theo tài khoản/tenant; LLM không tự xác nhận dữ liệu này hoặc tạo giao dịch.

| Chế độ | Hành vi hiện tại |
|---|---|
| **Natural** | Có thể dùng Sports Knowledge và nguồn web qua guardrail theo điều kiện; evidence cần qua policy/review trước khi hiển thị hoặc gửi provider. Nếu không có evidence được phép, có thể dùng Gemini general knowledge khi cấu hình sẵn; không có citation và không phải live search. |
| **Professional** | Tập trung nghiệp vụ SportHub/System Domain. Câu Sports Knowledge bị từ chối trước World Cup lookup, Sports RAG và sports web retrieval. Không tải ba lớp personal profile vào prompt. |

### Nhánh Sports Knowledge và kiểm soát evidence

- Retrieval tìm candidate local; candidate không đồng nghĩa với quyền sử dụng.
- Quyền `display_answer`, `prompt_llm_external` và `display_citation` được xét riêng. Review ledger phải hợp lệ, chữ ký đúng và quyết định khớp fingerprint nội dung cùng mục đích.
- Local deterministic answer chỉ nhận record qua quyền hiển thị; citation local cũng phải qua quyền citation. Record bị chặn không còn được đưa trở lại qua local fallback.
- Khi không có record được phép hiển thị, Natural chuyển sang general-knowledge fallback của Gemini nếu provider sẵn sàng. Câu trả lời đó không được trình bày là thông tin đã kiểm chứng/có nguồn từ SportHub. Dữ kiện biến động cần nêu độ không chắc chắn; câu hỏi live không được đoán.
- World Cup finals là lookup JSON local riêng, sau guard Professional và trước Sports RAG; chưa tích hợp Sports Knowledge review ledger.

### Context và cá nhân hóa

- Context tường minh được ưu tiên hơn snapshot. `context: {}` là reset: không khôi phục snapshot hoặc chèn các lượt cũ làm context. `context: null` cho phép dùng snapshot/lịch sử đã lưu.
- Lịch sử hội thoại chỉ hỗ trợ hiểu follow-up; không là bằng chứng factual.
- Natural có thể nhận ba profile riêng: explicit user memory, booking behavior (cửa sổ 180 ngày) và conversation topic (tín hiệu yếu, cửa sổ 180 ngày). Chúng không phải Sports Knowledge evidence/citation. Professional không nạp các profile này.

### Regression gần nhất

Ngày 27/10/2026, nhóm test policy, runtime và intent router được chọn chạy bằng backend virtualenv: **168 passed, 24 subtests passed**. Đây không phải full suite, không phải kiểm thử Gemini thật và không chứng minh toàn hệ thống không còn lỗi.

Kịch bản demo hiện hành: [`DEMO_SCENARIOS.md`](DEMO_SCENARIOS.md).

## I. Tuyên bố Kiến trúc Chính thức (Official Architecture Statement)

> **Lưu trữ checkpoint CP-11B:** Nội dung checkpoint cũ bắt đầu từ đây. Các bảng provider, danh sách intent, lời khẳng định về độ chính xác, web/auto-update và test count phía dưới không phải kết quả audit hiện tại; dùng mục “Hiện trạng vận hành hiện tại” ở đầu file.

> **Kiến trúc chính thức**:
> **Deterministic Rule-based Pipeline with Guardrailed RAG, Scoped LLM Structured Output & Scikit-Learn Demand Prediction**
>
> Hệ thống **không** sử dụng kiến trúc Autonomous Agent hay ReAct vòng lặp mở để đảm bảo:
> 1. Tính tiền định (Determinism) và kiểm soát hoàn toàn phạm vi truy cập dữ liệu.
> 2. Độ trễ thấp, không lặp prompt không kiểm soát.
> 3. Tuyệt đối không hallucination đối với dữ liệu tài chính, đặt sân và thông tin thực tế.

---

## II. Sơ đồ Khối Kiến trúc Tổng thể (System Block Diagram)

```mermaid
flowchart TD
    User["Người dùng / Giao diện Frontend\n(AIAssistantPage + Mode Selector)"] --> Request["AssistantRequest\n{message, assistant_mode, context}"]
    Request --> IntentRouter["Intent Router (19 Intents)\n(Domain Terms + Entity Parser)"]
    
    IntentRouter --> ModePolicy{"Mode Scope Policy\n(evaluate_mode_scope)"}
    
    ModePolicy -->|PROFESSIONAL Mode| ProEngine["Professional Handler\n- SportHub PostgreSQL DB\n- Internal Static RAG / FAQ\n- Strict Sports & Web Refusal"]
    
    ModePolicy -->|NATURAL Mode| NatEngine["Natural Handler\n- SportHub DB (Business flow)\n- Sports Knowledge RAG (6 Sports)\n- Approved Sports Web (Freshness)\n- Safe Fallback Guardrail"]
    
    ProEngine --> ResponseFormatter["Response Formatter\n- Structured JSON Contract\n- Citations & Scope Metadata"]
    NatEngine --> ResponseFormatter
    
    ResponseFormatter --> User
```

---

## III. Ma trận Phân quyền Nguồn dữ liệu theo Chế độ (Mode Scope Policy Matrix)

| Nguồn dữ liệu (Data Source) | NATURAL Mode | PROFESSIONAL Mode |
| :--- | :---: | :---: |
| **SportHub DB (PostgreSQL)** (Sân, Slot, Giá, Đơn đặt, Người dùng) | ✅ Được phép | ✅ Được phép |
| **Internal Static RAG** (Cẩm nang SportHub, Hướng dẫn chủ sân) | ✅ Được phép | ✅ Được phép |
| **Sports Knowledge RAG** (6 môn: Bóng đá, Cầu lông, Pickleball, Tennis, Bóng rổ, Bóng chuyền) | ✅ Được phép | ❌ **Bị chặn tuyệt đối** *(Controlled Refusal)* |
| **Approved Sports Web** (vff.org.vn, baothainguyen.vn, thethao247.vn...) | ✅ Khi cần cập nhật/freshness | ❌ **Bị chặn tuyệt đối** |
| **External General Web** (Google, Wikipedia...) | ❌ Bị chặn | ❌ Bị chặn |

---

## IV. Các Phân hệ Cốt lõi

### 1. Intent Router & Multi-level Priority Routing
Phân loại tiền định dựa trên thực thể, đại từ, hành động và ngữ cảnh đa lượt:
- **Priority Routing Order**:
  1. Safety / Abusive / Nonsense Detection (`ABUSIVE`, `NONSENSE`)
  2. Natural Conversational Chit-chat (`GREETING`, `AI_IDENTITY`, `AI_CAPABILITY`, `THANKS`, `GOODBYE`, `CASUAL`)
  3. SportHub Business & Operations (`SEARCH_VENUE`, `RECOMMEND_VENUE`, `CHECK_AVAILABILITY`, `RECOMMEND_SLOT`, `GET_VENUE_DETAIL`, `CREATE_BOOKING`, `GET_BOOKING`, `CANCEL_BOOKING`, `RESCHEDULE_BOOKING`, `PAYMENT_SUPPORT`, `ACCOUNT_SUPPORT`, `PARTNER_APPLICATION_SUPPORT`, `OCCUPANCY_INSIGHT`, `GET_PRODUCTS`, `SYSTEM_GUIDE`, `FOLLOW_UP`)
  4. Sports Knowledge & Real-world Information (`SPORTS_KNOWLEDGE`)
  5. Fallback & Clarification (`UNCLEAR`, `OUT_OF_SCOPE`)

### 2. Context & Natural Sports Entity Understanding (`SportsContextResolver`)
- **Chuẩn hóa số từ chữ sang số**: Hỗ trợ đọc hiểu số áo bằng chữ hoặc chữ số (`anh bảy` $\leftrightarrow$ `anh 7`, `anh mười` $\leftrightarrow$ `anh 10`, `anh chín` $\leftrightarrow$ `anh 9`...).
- **Multi-sport Slang & Nickname Registry**: Hỗ trợ nhận diện biệt danh thân mật trên 6 môn thể thao (Bóng đá, Tennis, Cầu lông, Bóng rổ, Bóng chuyền, Pickleball).
- **Phân giải đa lượt (Context-driven Follow-up)**: Tự động kế thừa môn thể thao và đối tượng từ lượt hội thoại trước để phân giải chính xác (ví dụ: turn 1 hỏi *"Anh 7 trong bóng đá là ai?"* $\rightarrow$ turn 2 hỏi *"Còn anh 10 là ai?"* $\rightarrow$ suy luận `Lionel Messi`).
- **Xử lý có điều kiện khi thiếu context**: Khi người dùng hỏi câu độc lập thiếu context (*"anh 7 là ai?"*), trả lời có điều kiện và giải thích ngữ cảnh thể thao phổ biến nhất.
- **Xử lý meme / trào lưu hài hước**: Hiểu hóm hỉnh các câu đùa (*"đấng maguire"*, *"anh 7 đi bộ vuốt tóc"*, *"lakaka"*) mà không biến meme thành sự thật.

### 3. Web Source Preview Panel (WP-01 → WP-06)
- **Tách biệt luồng UI**: Chatbot bên trái giữ nguyên, Web Preview Panel hiển thị cố định ở bên phải.
- **Iframe & Fallback UX**: Ưu tiên nhúng iframe khi website cho phép; tự động hiển thị fallback chuyên nghiệp có nút "Mở link" (new tab) và "Copy URL" (kèm toast feedback) khi website chặn iframe hoặc lỗi mạng.
- **Tương tác Nguồn (Citation Linkage)**: Click vào bất kỳ source nào trong câu trả lời AI sẽ ngay lập tức đồng bộ và chuyển đổi nội dung preview panel sang source đó.

### 4. Auto-Update Knowledge Pipeline
```
Approved Sports Web 
    ──> Fact Extraction 
    ──> Schema & Reliability Validation 
    ──> KnowledgeRepository (Idempotent Update) 
    ──> Incremental Re-index (KnowledgeRetriever) 
    ──> Sports RAG (Natural Mode)
```
- **Idempotency**: Kiểm tra hash nội dung tránh duplicate bản ghi.
- **Incremental Index**: Chỉ re-index các bản ghi/chunk thay đổi trong bộ nhớ, không rebuild toàn bộ cơ sở dữ liệu tri thức.
- **Trigger**: Hỗ trợ kích hoạt nền qua background worker và endpoint quản trị bảo vệ (`POST /ai/knowledge/update`).

### 5. RAG Guardrail & Safe Grounding
- **Sufficiency & Freshness Gate**: Đánh giá độ tin cậy và ngày cập nhật của tri thức nội bộ trước khi kích hoạt web search.
- **Evidence-grounded Citations**: Mọi câu trả lời factual thể thao đều kèm theo nguồn (`source_name`, `source_url`, `collected_at`).
- **Safe Fallback**: Khi không có bằng chứng xác thực, trả về thông báo kiểm soát chuẩn hóa, loại bỏ hoàn toàn hiện tượng sinh thông tin ảo (hallucination).

### 6. Mode Context Isolation
- Khi chuyển từ `NATURAL` sang `PROFESSIONAL`: Ngữ cảnh thực thể thể thao (`sports_entity`, `sports_entities`) và intent thể thao của lượt trước được lọc sạch (`_sanitize_context_for_mode`).
- Khi chuyển từ `PROFESSIONAL` sang `NATURAL`: Ngữ cảnh kinh doanh được giữ nguyên đồng thời kích hoạt lại khả năng tra cứu tri thức thể thao.

---

## V. Kết quả Đánh giá Thực nghiệm (Evaluation Results)

- **Bộ Kiểm thử Tự nhiên & Thực thể Thể thao (`test_ai_natural_context_entity.py` & `test_ai_natural_conversation.py`)**: **24/24 test methods PASSED (64+ subtests passed)**.
- **Scenario Harness (`mode_evaluation_dataset.json`)**: **31/31 scenarios PASSED (100.0%)**.
- **Bộ Kiểm thử Toàn diện**: **100% tests PASSED**, 0 failures, 0 regressions.
- **Độ tin cậy**: Đáp ứng 100% các tiêu chuẩn về an toàn thông tin, phân quyền chế độ, và tính toàn vẹn dữ liệu.

## VII. System Domain Context Continuity (CP-SYS-03)

System Domain là nhánh dữ liệu nghiệp vụ chỉ đọc cho products/services và amenities ở cấp sport hoặc venue. Nhánh này dùng `SystemDomainContextService` làm source-of-truth và không tạo IntentRouter thứ hai.

### Semantic context resolution

`IntentRouter.is_system_domain_followup()` nhận diện các follow-up ngắn như `còn cầu lông`, `thế cầu lông thì sao`, `còn môn này`, `môn đó thì sao` và `sân đó thì sao` khi context trước có `domain_context_type` hợp lệ:

1. Giữ operation trước đó: `sport_amenities`, `venue_amenities`, `sport_products` hoặc `venue_products`.
2. Thay sport/venue/entity chỉ khi câu hiện tại nêu rõ.
3. Giữ `context_reset=False` cho semantic follow-up.
4. Khi có yêu cầu business rõ ràng như `tìm sân cầu lông tối nay`, business routing được ưu tiên và context được reset.

Natural và Professional cùng gọi resolver này. Khác biệt giữa hai mode chỉ nằm ở policy nguồn dữ liệu và cách diễn đạt:

- **Natural**: được dùng Sports Knowledge RAG/approved Web cho câu hỏi tri thức thể thao; System Domain và business data vẫn lấy từ backend source-of-truth.
- **Professional**: chỉ xử lý SportHub DB, System Domain và internal guide/FAQ; Sports RAG và external Web bị chặn.

### System Domain data contract

Context trả về có thể chứa `domain_context_type`, `sport_type`, `field_id`, `result_field_ids` và `last_intent`. Metadata intent tiếp tục phản ánh operation (`GET_VENUE_DETAIL` hoặc `GET_PRODUCTS`) để downstream policy không hiểu nhầm follow-up là tìm sân. Không có schema database mới, RAG mới hoặc autonomous-agent loop.
