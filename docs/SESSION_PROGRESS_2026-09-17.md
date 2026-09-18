# Báo cáo Tiến độ SportHub AI — 17/09/2026

Tài liệu tổng hợp các công việc đã hoàn thành trong phiên làm việc ngày **17/09/2026** liên quan đến việc Audit, Triển khai tính năng **Multi-Attribute Sports Knowledge RAG**, Phân tích cơ chế nạp tri thức Markdown và Kiểm tra Phân loại Scope thể thao cho hệ thống **SportHub AI**.

---

## 1. Audit Khả năng Nhận diện Entity / Alias cho 8 Vận động viên

### 1.1. Kết quả Audit 6 Tiêu chí Kỹ thuật
1. **Mapping Alias ➔ Canonical Entity**: 100% alias của 8 vận động viên (`Lionel Messi`, `Cristiano Ronaldo`, `Nguyễn Quang Hải`, `Nguyễn Tiến Linh`, `Nguyễn Hoàng Đức`, `Nguyễn Thùy Linh`, `Nguyễn Tiến Minh`, `Viktor Axelsen`) được ánh xá chính xác về tên chuẩn.
2. **Tiếng Việt không dấu (Unaccented Names)**: Quá trình chuẩn hóa NFD trong `ai_intent_router.py` và `knowledge_retriever.py` xử lý hoàn hảo các câu hỏi không dấu.
3. **Thuộc tính & Topic Retrieval**: Trích xuất chính xác các nhu cầu thông tin về ngày sinh (`birth_date`), nơi sinh (`birth_place`), CLB hiện tại (`current_club`), thành tích (`achievements`), trạng thái (`status`), tiểu sử (`identity`).
4. **Lưu vết Context Đa lượt**: `AIAssistantService` luôn ghi nhận `understood['sports_entity']` bằng Canonical Name, đảm bảo các lượt hỏi tiếp theo (follow-up) dùng đúng tên chuẩn.
5. **Kiểm soát False Positive cho Alias ngắn**: Các từ dễ nhầm lẫn như `"Leo"`, `"CR7"` trong câu hỏi đặt sân (*"Tìm sân ở quận Liên Chiểu"*, *"Sân ở Nguyễn Văn Linh"*, *"Đặt sân cho 7 người"*) được bảo vệ qua bộ lọc `is_venue_operation`, ưu tiên đúng Intent đặt sân.
6. **Đồng bộ Router & Retriever**: Đã kiểm tra sự đồng nhất giữa `KNOWN_SPORTS_ENTITIES` (Router) và `ENTITY_ALIASES` (Retriever).

---

## 2. Phân tích Cơ chế Nạp Markdown Knowledge (`docs/AI/knowledge/`)

### 2.1. Thành phần Cốt lõi & Luồng Dữ liệu
- **File đảm nhận**: [app/repositories/knowledge_repository.py](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Backend/app/repositories/knowledge_repository.py)
- **Class & Function**: `KnowledgeRepository._load_entries()` (khởi tạo tự động trong `__init__`).
- **Thư mục gốc**: Khai báo tại `os.path.abspath(..., "docs", "AI", "knowledge")`.
- **Cơ chế duyệt (Directory Walker)**: Sử dụng `os.walk()` duyệt đệ quy (recursive), nạp toàn bộ các file `.md` trong thư mục gốc và tất cả các thư mục con (`sports/`, `players/`, `thai_nguyen/`, `tournaments/`, `national_teams/`...).
- **Cơ chế Parse Markdown Table**:
  - Tách cột qua `stripped.split('|')[1:-1]`.
  - Tự động nhận diện dòng tiêu đề (Header: `id`, `entry_id`, `mã`, `stt`) để tạo map thuộc tính động.
  - Hỗ trợ cả 3 cấu trúc: Bảng 13 cột chuẩn Sports Knowledge, Bảng 8 cột legacy General Knowledge, và Bảng linh hoạt theo Header.
- **Truyền dữ liệu sang Retriever**: `KnowledgeRetriever` nhận `KnowledgeRepository` và gọi `self.repo.get_static_entries()` nạp toàn bộ `KnowledgeEntry` (loại `static`) vào bộ nhớ RAM.

---

## 3. Triển khai Nâng cấp Multi-Attribute Sports Knowledge RAG

### 3.1. Đột phá Xử lý Đa thuộc tính trong 1 Câu hỏi
- **Vấn đề trước đây**: Với câu hỏi gộp nhiều thuộc tính (ví dụ: *"Quang Hải là ai, sinh vào ngày nào, quê ở đâu, đang đá cho câu lạc bộ nào?"*), hệ thống chỉ lấy `retrieved[0]` (quê quán) và đánh rơi 3 ý còn lại.
- **Giải pháp đã nâng cấp**:
  1. **Tối ưu Topic Pattern & Scoring (`knowledge_retriever.py`)**:
     - Bổ sung `TOPIC_ALIASES` map `'cầu thủ'`, `'vận động viên'`, `'profile'`, `'tiểu sử'` ➔ `'identity'`.
     - Mở rộng `TOPIC_PATTERNS` hỗ trợ cụm tự nhiên: `'la ai'`, `'gioi thieu'`, `'tieu su'`, `'sinh vao ngay'`, `'que o'`, `'thi dau o dau'`.
     - Tính toán mảng `query_matched_topics` để không đánh điểm phạt `topic_mismatch` đối với các thuộc tính được yêu cầu trong câu đa thuộc tính.
  2. **Gom & Phối hợp Multi-Evidence (`ai_assistant_service.py`)**:
     - Bỏ giới hạn cắt cứng `retrieved[0]`. Thu thập tất cả các evidence đạt ngưỡng `relevance_threshold = 0.60`, thuộc target entity và thuộc các topic được hỏi.
     - Loại bỏ duplicate answers (`seen_answers`).
     - Trả lời trọn vẹn văn bản cho từng thuộc tính có evidence.
  3. **Thông báo Thuộc tính Thiếu & Chống Ảo Giác (Anti-Hallucination for Missing Attributes)**:
     - Khi hỏi thuộc tính chưa có dữ liệu RAG (ví dụ: chiều cao, cân nặng), hệ thống trả lời các ý có dữ liệu và ghi chú rõ ràng:  
       *(Lưu ý: Hiện tại SportHub AI chưa có thông tin kiểm chứng về chiều cao của Nguyễn Quang Hải trong cơ sở dữ liệu).*
  4. **Gộp Nguồn Trích Dẫn (Unified Citations)**: Gộp `source_name`, `source_url`, `collected_at` từ tất cả các evidence thực sự được sử dụng.

---

## 4. Phân tích & Định hướng Phân loại Scope Thể thao (Sports Scope Audit)

### 4.1. Phân biệt 2 Loại Truy vấn Phạm vi (Scope Rules)
1. **Môn ngoài 6 môn hỗ trợ** (Golf, Bida, Bơi lội, Võ thuật, Esports...): Luôn nằm trong `UNSUPPORTED_SPORTS_TERMS` ➔ Gán **`OUT_OF_SCOPE`**.
2. **Thực thể thuộc 6 môn hỗ trợ** (Bóng đá, Cầu lông, Pickleball, Tennis, Bóng rổ, Bóng chuyền) nhưng chưa có RAG Evidence (như *Modric*, *Lamine Yamal*): Phân loại **`SPORTS_KNOWLEDGE`** (`IN_SCOPE`) và trả về phản hồi safe fallback kiểm chứng chứ **không** bị gán nhầm thành `OUT_OF_SCOPE`.

## 5. Mở Rộng Cơ Sở Tri Thức Thể Thao Đa Địa Phương & Học Đường (ICTU / Thái Nguyên / Hà Nội / TP.HCM)

### 5.1. Nguồn Dữ Liệu & Tri Thức Đã Chuẩn Hóa
1. **Bóng đá Thái Nguyên & ICTU**:
   - Bổ sung tri thức chính thức từ Báo Thái Nguyên, Cổng thông tin Tỉnh Thái Nguyên và website chính thức ICTU (`ictu.edu.vn`).
   - Chuẩn hóa thông tin: CLB Bóng đá Thái Nguyên / FC Thái Nguyên (đội nam phong trào/hạng Nhì), CLB Bóng đá nữ Thái Nguyên T&T (đội nữ chuyên nghiệp Vô địch Quốc gia, tài trợ bởi Tập đoàn T&T).
   - Phong trào thể thao sinh viên ICTU: Giải đấu ICTU CUP (8 đội nam/nữ từ 4 khoa: CNTT, KT&CN, KT&QT, NT&TT), Đại hội Thể thao Sinh viên, giải bóng chuyền hơi, cầu lông, pickleball học đường.
   - Chuẩn hóa thực thể/alias: `ICTU`, `Trường Đại học CNTT và TT`, `Trường ĐH CNTT&TT Thái Nguyên`, `đội bóng ICTU`, `CLB ICTU`.
2. **Tri thức thể thao theo Tỉnh / Thành phố**:
   - **Thái Nguyên**: Bóng đá nữ (Thái Nguyên T&T), Sân vận động Thái Nguyên (sức chứa 22.000 chỗ), phong trào thể thao học đường ICTU, bóng bàn, cầu lông địa phương.
   - **Hà Nội**: Bóng đá (Hà Nội FC, CLB Công An Hà Nội, Thể Công - Viettel tại SVĐ Hàng Đẫy / Mỹ Đình), Bóng rổ (Hanoi Buffaloes, Thang Long Warriors tại VBA), Cầu lông, Bóng chuyền (Bộ Tư lệnh Thông tin).
   - **TP. Hồ Chí Minh**: Bóng đá (CLB TP. Hồ Chí Minh tại SVĐ Thống Nhất), Bóng rổ (Saigon Heat, Hochiminh City Wings), Cầu lông (đội tuyển TP.HCM - Nguyễn Tiến Minh), Bóng chuyền (CLB TP.HCM, VTV Bình Điền Long An lân cận).
   - Danh mục 6 môn thể thao hỗ trợ chuẩn: Football, Badminton, Pickleball, Tennis, Basketball, Volleyball.

---

## 6. Triển Khai Controlled Web Retrieval & Grounded Context (AI-WEB-01 ➔ AI-WEB-04)

### 6.1. Chi Tiết Các Hạng Mục Kỹ Thuật Hoàn Thành
1. **AI-WEB-01 — Tách biệt Luồng Nghiệp vụ (Business Flow) & Tri thức Thể thao (Sports Knowledge)**:
   - Cơ chế rẽ nhánh xác định: Các Business Intent (`SEARCH_VENUE`, `RECOMMEND_SLOT`, `CHECK_AVAILABILITY`, `CREATE_BOOKING`, `PAYMENT_SUPPORT`, `ACCOUNT_SUPPORT`...) luôn truy vấn Database (Ground Truth) và **tuyệt đối KHÔNG kích hoạt Web Retrieval**.
   - Bộ lọc `Sports Scope Filter` xác định: Chỉ câu hỏi thuộc 6 môn thể thao hỗ trợ mới đi vào nhánh `SPORTS_KNOWLEDGE`. Câu hỏi phi thể thao hoặc môn ngoài danh mục chuyển sang `OUT_OF_SCOPE` và không gọi Web.
2. **AI-WEB-02 — Controlled Web Retrieval & Source Whitelist**:
   - Module `Backend/app/services/sports_web_retriever.py` chỉ kích hoạt cho `SPORTS_KNOWLEDGE`.
   - Danh sách Whitelist nghiêm ngặt (`DEFAULT_SPORTS_SOURCE_WHITELIST`): Chỉ chấp nhận các nguồn chính thống, liên đoàn, cơ quan thể thao, trường học và báo chí thể thao uy tín (`vff.org.vn`, `ictu.edu.vn`, `baothainguyen.vn`, `thethao247.vn`, `fifa.com`, `bwfbadminton.com`, `nba.com`...).
   - Lọc từ khóa nội dung theo môn thể thao (`SPORT_SPECIFIC_KEYWORDS`), ngăn chặn tuyệt đối các bài báo không liên quan lọt vào context.
   - Lưu trữ và bảo toàn metadata nguồn: `url`, `title`, `domain`, `published_date`, `extracted_snippets`.
3. **AI-WEB-03 — Đánh Giá Freshness & Quyết Định Nhu Cầu Web Evidence**:
   - Đánh giá thông minh không dựa thuần túy vào LLM: Sử dụng bộ luật phân loại tính biến động thông tin (`volatility`):
     - *High volatility* (thời sự, chuyển nhượng, CLB hiện tại, HLV đương nhiệm, kết quả/bảng xếp hạng mới nhất).
     - *Low volatility / Stable* (tiểu sử, lịch sử hình thành, thành tích quá khứ, thông tin nền tảng trường/CLB).
   - Cơ chế quyết định: Nếu Internal Knowledge đã đủ và còn mới $\rightarrow$ dùng Internal Knowledge. Nếu thông tin mang tính thời sự hoặc Internal Knowledge bị khuyết/cũ $\rightarrow$ kích hoạt Web Retrieval.
   - Cơ chế Bằng chứng thay thế (Freshness Superseding): Bằng chứng Web mới hơn và đáng tin cậy từ Whitelist sẽ ưu tiên bổ sung hoặc thay thế các sự thật nội bộ đã lỗi thời khi có xung đột dữ liệu.
4. **AI-WEB-04 — Hợp Nhất Bằng Chứng (Combined Evidence) & Grounded LLM Response**:
   - Hợp nhất Internal Knowledge RAG + Validated Web Evidence thành một context chung có chấm điểm xếp hạng tổng hợp (`composite_score` từ relevance, reliability, freshness).
   - Rào chắn chống ảo giác (Output Guardrail): LLM chỉ được phép trả lời dựa trên Grounded Context được cung cấp, không suy diễn ngoài dữ liệu.
   - Tự động đính kèm trích dẫn nguồn xác thực (Title, Domain, URL, Publication Date) trong câu trả lời cuối cùng.

---

## 7. Báo Cáo Kiểm Thử Nghiệm Thu Toàn Bộ 8 Kịch Bản (Final Validation)

| # | Kịch Bản Kiểm Thử | Query Thử Nghiệm | Luồng Xử Lý Thực Tế | Trạng Thái |
|---|---|---|---|:---:|
| **1** | **Business Flow** | *"Tìm sân cầu lông ở Hà Nội tối nay"* | Định tuyến `SEARCH_VENUE` $\rightarrow$ DB PostgreSQL $\rightarrow$ **Không gọi Web** | **PASS** |
| **2** | **Sports Knowledge** | *"Thái Nguyên có những đội bóng nào?"* | Định tuyến `SPORTS_KNOWLEDGE` $\rightarrow$ Internal Knowledge RAG $\rightarrow$ **Không gọi Web** | **PASS** |
| **3** | **Supported Sport Scope** | *"ICTU có những môn thể thao nào?"* | Định tuyến `SPORTS_KNOWLEDGE` $\rightarrow$ Tri thức thể thao chính thức ICTU $\rightarrow$ Chuẩn scope | **PASS** |
| **4** | **Current / Time-sensitive** | *"Cầu thủ bóng đá Endrick hiện đang thi đấu cho CLB nào?"* | Phân loại `volatility = high` $\rightarrow$ Web Retrieval qua Whitelist $\rightarrow$ Kèm trích dẫn nguồn | **PASS** |
| **5** | **Non-sports Topic** | *"Chính sách tuyển sinh của ICTU là gì?"* | Chủ đề học thuật / phi thể thao $\rightarrow$ `OUT_OF_SCOPE` $\rightarrow$ **Không gọi Web** | **PASS** |
| **6** | **Unsupported Sport** | *"Luật chơi môn bi-a carom như thế nào?"* | Môn ngoài danh mục $\rightarrow$ `OUT_OF_SCOPE` $\rightarrow$ **Không gọi Web** | **PASS** |
| **7** | **Multi-entity** | *"Messi và Ronaldo hiện đang thi đấu cho đội nào?"* | Nhận diện & bảo toàn `['Lionel Messi', 'Cristiano Ronaldo']` $\rightarrow$ Trả lời đầy đủ cả hai | **PASS** |
| **8** | **Regression Coverage** | Tìm sân, đặt sân, thanh toán, nạp hồ sơ, Voice input, Multi-turn context | Tất cả các luồng nghiệp vụ kinh doanh và nền tảng hoạt động trơn tru 100% | **PASS** |

### Tổng Hợp Test Suites Hệ Thống AI
- **Backend Test Suites**: `76/76 unit & integration tests PASSED (100%)`
  - `test_final_sports_web_validation.py`: 8/8 passed
  - `test_sports_combined_evidence.py`: 5/5 passed
  - `test_sports_freshness_evaluation.py`: 5/5 passed
  - `test_sports_web_retriever.py`: 7/7 passed
  - `test_ai_web_flow_separation.py`: 6/6 passed
  - `test_sports_intent_router.py`: 11/11 passed
  - `test_sports_knowledge_validation.py`: 14/14 passed
  - `test_ai_location_search.py`: 20/20 passed
- **Frontend Verification**: `tsc -b && vite build` hoàn thành với **0 lỗi**.
- **Bảo tồn nguyên tắc**: Không thay đổi Business Flow, không can thiệp Database Ground Truth, tuân thủ nghiêm ngặt bảo mật và phân quyền vai trò.

