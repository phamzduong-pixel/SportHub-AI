# Báo cáo tiến độ phiên 20/09/2026 — Hoàn thiện Natural Sports Assistant & Multi-Turn Context Resolution

## 1. Tổng quan phiên làm việc
Phiên làm việc tập trung hoàn thiện toàn diện chế độ **Natural Mode** cho Trợ lý Thể thao SportHub AI (**Natural Sports Assistant**), đảm bảo:
- Xử lý mượt mà ngôn ngữ tự nhiên, tiếng lóng, meme thể thao, câu hỏi follow-up và chuyển đổi thực thể (Entity Switching / Sport Switching) mà không làm ô nhiễm hoặc mất ngữ cảnh.
- Duy trì tính toàn vẹn của kiến trúc:
  $$\text{Deterministic Rule-based Pipeline with Guardrailed RAG, Scoped LLM Structured Output \& Scikit-Learn Demand Prediction}$$
- Phân tách tuyệt đối giữa **Natural Mode** (hỗ trợ kiến thức thể thao tự nhiên, hội thoại thân thiện) và **Professional Mode** (kỷ luật nghiệp vụ chặt chẽ, từ chối câu hỏi ngoài luồng đặt sân).
- Bảo toàn trọn vẹn nghiệp vụ cốt lõi SportHub (tìm sân, kiểm tra slot trống, báo giá, đặt sân, đối tác, tài khoản, thanh toán) mà không tạo router thứ hai hoặc bypass business logic.

---

## 2. Các hạng mục đã triển khai & tối ưu

### 2.1. Nâng cấp Bộ giải quyết Ngữ cảnh Thể thao (`SportsContextResolver` & `LocationUtils`)
- **Khử nhiễu câu hỏi vị trí**: Bổ sung các từ nghi vấn (`'dau'`, `'o dau'`, `'nao'`, `'khac'`) vào `ignore_tokens` của `extract_location` nhằm ngăn chặn nhận diện sai từ để hỏi thành tên địa danh (ví dụ: *"Anh ấy sinh ở đâu?"* không bị hiểu nhầm là địa điểm *"Dau"*).
- **Phục hồi & Ưu tiên ngữ cảnh Thực thể khi Follow-up**:
  - Tinh chỉnh logic query rewriting để ưu tiên thực thể (`ent_name`) so với địa phương khi follow-up ngắn gọn (ví dụ: *"còn Tiến Minh?"* trong ngữ cảnh cầu lông Việt Nam).
  - Bổ sung thực thể còn thiếu vào `GLOBAL_ENTITY_CATALOG` (ví dụ: *Romelu Lukaku* cùng biệt danh/meme *'lakaka'*).
- **Quay lại nghiệp vụ cốt lõi (`is_return_to_business`)**:
  - Khi người dùng đang hỏi kiến thức thể thao và chuyển về tìm sân (*"Thôi tìm sân lúc nãy"*), hệ thống khôi phục toàn bộ tiêu chí tìm kiếm ban đầu (`sport_type`, `location`, `court_type`, `max_price`) từ `business_context` mà không bị đè bởi môn thể thao của câu hỏi kiến thức trước đó.

### 2.2. Kiểm soát Luồng Nghiệp vụ & Out-of-Scope Redirect
- Chuẩn hóa thông điệp từ chối / chuyển hướng ngoài phạm vi (`generate_out_of_scope_redirect`) với format nhất quán: khẳng định vai trò trợ lý chuyên biệt của SportHub AI, kèm gợi ý các môn thể thao hỗ trợ hoặc điều hướng về tìm sân.
- Giữ vững cơ chế an toàn: không suy đoán khi thiếu dữ liệu (no hallucination), trích dẫn nguồn (`citations`) xác thực và chỉ lấy evidence liên quan trực tiếp.

---

## 3. Kết quả Kiểm thử & Đánh giá (Test Matrix)

Tất cả các bộ kiểm thử tự động chuyên sâu đều đạt **100% PASS**:

1. **Natural Sports Assistant E2E Verification (`test_natural_sports_assistant_e2e_verification.py`)**: 12/12 test scenarios PASSED (Athlete, Competition, Rules/Scoring, Team/Club, Vietnam Local, Follow-up continuity, Entity Switching no contamination, Sport Switching isolation, Business switching flow, Out-of-scope natural redirect, Evidence failure handling).
2. **AI Mode Evaluation Harness (`test_ai_mode_evaluation_harness.py`)**: 5/5 suites PASSED (31/31 subtests), pass rate đạt 100% trên cả 4 nhóm:
   - Group 1: Natural Mode Scenarios.
   - Group 2: Professional Mode Scenarios.
   - Group 3: Mode Switching Scenarios.
   - Group 4: Grounding & Safety Scenarios.
3. **Natural Mode Context & Entity (`test_ai_natural_context_entity.py`)**: 12/12 PASSED.
4. **Natural Follow-up Context Chains (`test_ai_natural_followup_context.py`)**: 6/6 PASSED.
5. **Scope Router & Natural Assistant (`test_ai_scope_router_natural_assistant.py`)**: 4/4 PASSED.
6. **Domain Boundary & Intent Router (`test_ai_domain_boundary.py`, `test_ai_intent_router.py`)**: 31/31 & 25/25 PASSED.
7. **Availability & Business Flow E2E (`test_ai_availability_e2e.py`)**: 9/9 PASSED.

---

## 4. Trạng thái Hệ thống Hiện tại

```text
User Input
  │
  ├──► Scope Router (Domain Classification: SPORTHUB_BUSINESS | SPORTS_KNOWLEDGE | SYSTEM_STATIC | OUT_OF_SCOPE)
  │      │
  │      ├──► SPORTHUB_BUSINESS ──► Intent Router ──► Deterministic Business Services (Database Ground Truth)
  │      │
  │      ├──► SPORTS_KNOWLEDGE (Natural Mode only)
  │      │      │
  │      │      └──► SportsContextResolver (Entity / Sport / Topic / Follow-up / Deictic Resolution)
  │      │             │
  │      │             └──► Guardrailed Knowledge Retrieval + Scoped LLM (Strict Evidence Only + Citations)
  │      │
  │      ├──► SYSTEM_STATIC ──► Static FAQ / Help / System Guides
  │      │
  │      └──► OUT_OF_SCOPE ──► Canonical Friendly Redirect (No Hallucination, No Agent Loop)
  │
  └──► Mode Discipline: Natural Mode (Sports Enthusiast) vs Professional Mode (Strict Venue Operations)
```

Hệ thống hoạt động ổn định, phân tách rõ ràng, sẵn sàng phục vụ người dùng.

---

## 5. CP-SYS-01 - Audit System Awareness Layer

Checkpoint nay chi audit va thiet ke, chua thay doi code hoac database.

### Domain source-of-truth hien co

- Sport: `Field.sport_type`, `Facility.sports`, `ProductCatalogItem.sport_name` va `ProductSport.sport_name`.
- Venue/court: `Facility` va `Field` trong live database.
- Amenity: JSON `Facility.amenities` va `Field.amenities`; chua co bang Amenity rieng.
- Product/service: `FacilityProduct`; catalog: `ProductCatalogItem`.
- Sport <-> product/service: `ProductSport` (`facility_product_sports`).
- Price/availability: `Field.base_price`, `TimeSlot.price`, `TimeSlot.is_active` va booking state.
- Booking/payment/account: `Booking`, `BookingSlot`, `BookingProductItem`, `Payment`, `User`.
- Owner/partner/admin: `User.role`, `OwnerApplication`, `Facility.owner_id` va cac trang thai review.

Du lieu nghiep vu tren la live DB. Sports Knowledge/RAG la lop tri thuc the thao rieng, khong phai source-of-truth cho inventory, amenity, gia hoac availability.

### Product / Service / Amenity audit

`ProductService` va `InventoryService` da ho tro truy van product theo facility va sport, gom status, gia, inventory va mapping `ProductSport`. Tuy nhien AI hien chi goi chung khi da co `field_id`/venue context.

`_answer_venue_detail()` doc duoc amenity cua mot field cu the. Chua co truy van system-domain o cap sport de tong hop product/service hoac amenity.

Vi vay cac cau hoi nhu "san bong da co nhung tien ich nao?", "bong da co nhung tien ich gi?" va follow-up "tien ich cua mon the thao do" co the roi ve fallback: router chua bao phu day du tu khoa tien ich, Natural co nhanh tra loi dung cu generic, con Product handler yeu cau venue/field context.

### Kien truc de xuat cho checkpoint tiep theo

Them mot read-only `SystemDomainContext` dung truc tiep DB/repository hien co, khong duplicate database vao prompt va khong tao RAG moi. Context chi lay domain data can thiet:

- sport-level products/services;
- venue/field amenities;
- venue products va availability;
- price, booking, payment hoac account theo quyen hien tai.

Natural se resolve semantic/entity/context roi truy van System Domain Context va dien dat tu nhien. Professional van giu IntentRouter va business services hien tai, uu tien deterministic live DB. Mutation van bat buoc di qua business service va authorization.

### Trang thai he thong sau cac checkpoint AI

- Natural Mode da co direct answer, small talk, Sports Knowledge/Web/RAG co citation, context/entity follow-up, alias resolution va SportHub bridge.
- Professional Mode van giu business flow cho venue, availability, booking, payment, account, owner/partner va admin.
- Sports Web/RAG da co whitelist/domain guardrail, evidence grounding va fallback khi thieu nguon.
- Nguon the thao Thai Nguyen va Cong TTDT tinh da duoc ingest/index theo pipeline hien tai.
- System Awareness cho Product/Service/Amenity theo sport hoac venue van la phan chua trien khai; day la hang muc tiep theo.

### Rui ro can kiem soat

- Khong dung du lieu catalog de khang dinh availability thuc te.
- Khong tra product/amenity cua facility khac hoac vuot quyen owner/customer.
- Khong nham dung cu the thao generic voi product/service dang co trong SportHub.
- Khong de Natural early fallback chan live system lookup.
- Khong bien system context thanh autonomous agent hoac business router thu hai.
