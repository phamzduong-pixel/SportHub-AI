# Báo Cáo Phân Tích Kiến Trúc & Cơ Chế Hoạt Động Của Trợ Lý AI (SportHub AI Assistant)

> **Ngày lập báo cáo:** 02/09/2026 (Cập nhật đồng bộ hoàn thiện: 10/09/2026)  
> **Phạm vi kiểm tra:** Toàn bộ hệ thống Trợ lý AI (`AIAssistantService`, `IntentRouter`, `RAGGuardrail`, `KnowledgeService`, `AIFeatureService`, `OpenAIProvider`, `AIRepository`, `Frontend/src/services/aiAssistantService.ts`).  
> **Mục tiêu:** Phân tích chính xác 100% theo source code hiện có, xác định rõ vai trò của LLM/GenAI, Intent Router, Guardrailed RAG, Context Memory và bản chất kiến trúc.

---

## 1. Sử Dụng GenAI / LLM Trong Hệ Thống

GenAI/LLM được đóng gói qua adapter [`OpenAIProvider`](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Backend/app/services/ai_provider.py#L35-L132) (alias: `StructuredAIProvider`), kết nối trực tiếp đến endpoint OpenAI Chat Completions (`settings.OPENAI_MODEL`) với chế độ **Strict JSON Schema** (`response_format={'type': 'json_schema', 'strict': True}`).

LLM **KHÔNG** tham gia vào việc nhận diện câu hỏi hay trò chuyện tự do trực tiếp với người dùng. LLM chỉ được kích hoạt tại **3 tác vụ chuyên biệt, đóng khung dữ liệu**:

1. **Xếp hạng slot trống & viết lý do (`task='rank_available_slots'`)**:
   - **Vị trí:** [`AIFeatureService.recommend_slots`](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Backend/app/services/ai_feature_service.py#L70-L92)
   - **Cơ chế:** Backend truy vấn database để lọc ra danh sách các cặp sân/slot **thực sự còn trống** (`available_slots`), sau đó gửi kèm nhu cầu khách hàng vào prompt để LLM chọn tối đa 3 slot phù hợp nhất và viết lý do (`reason`). Nếu LLM trả về slot không hợp lệ hoặc xảy ra lỗi/timeout, backend tự động chuyển sang giải thuật sắp xếp an toàn bằng code thuần (Fallback).
2. **Tóm tắt công suất & gợi ý khuyến mãi (`task='summarize_occupancy_and_suggest_promotions'`)**:
   - **Vị trí:** [`AIFeatureService.occupancy_summary`](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Backend/app/services/ai_feature_service.py#L254-L285)
   - **Cơ chế:** Nhận bảng thống kê số liệu công suất đã tính toán từ [`AnalyticsService`](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Backend/app/services/analytics_service.py), yêu cầu LLM viết nhận định định tính (không được tự sửa số liệu) và đề xuất ý tưởng ưu đãi cho các khung giờ thấp điểm (`low_demand_hours`).
3. **Sinh lời chào/kết tin nhắn booking (`task='write_booking_message_copy'`)**:
   - **Vị trí:** [`BookingMessageService.generate`](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Backend/app/services/booking_message_service.py#L40-L58)
   - **Cơ chế:** Các sự thật nghiệp vụ (mã đặt, số tiền, cọc, ngày giờ, trạng thái) do backend khóa cứng (`facts`), LLM chỉ được phép sinh câu mở đầu (`lead`) và lời kết (`closing`).

---

## 2. Intent Router & Phân Loại Ý Định (NLU Layer)

### Vị trí mã nguồn
- Bộ định tuyến: [`IntentRouter`](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Backend/app/services/ai_intent_router.py#L105-L247)
- Bộ chính sách miền: [`ai_domain_policy.py`](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Backend/app/services/ai_domain_policy.py)
- Bộ điều phối thực thi: [`AIAssistantService.ask`](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Backend/app/services/ai_assistant_service.py#L74-L234)

### Danh sách 19 Intents (`AssistantIntent`)
| Nhóm Intent | Tên Intent | Chức năng nghiệp vụ |
|---|---|---|
| **Tìm kiếm & Đặt sân** | `SEARCH_VENUE` | Tìm sân/cơ sở theo môn thể thao, vị trí |
| | `RECOMMEND_VENUE` | Đề xuất sân tốt nhất / phù hợp |
| | `CHECK_AVAILABILITY` | Kiểm tra lịch trống của sân |
| | `RECOMMEND_SLOT` | Gợi ý khung giờ còn trống tối ưu |
| | `CREATE_BOOKING` | Hướng dẫn tạo booking / xác nhận đặt |
| | `FOLLOW_UP` | Câu hỏi tiếp nối (chọn sân 1, xem sân khác, đổi ngày...) |
| **Thông tin & Tiện ích** | `GET_VENUE_DETAIL` | Tra cứu địa chỉ, tiện ích, chính sách của sân |
| | `GET_PRODUCTS` | Tra cứu sản phẩm/dịch vụ phụ trợ (thuê vợt, nước...) |
| | `SYSTEM_GUIDE` | Hướng dẫn sử dụng các chức năng hệ thống |
| **Quản lý & Nghiệp vụ** | `GET_BOOKING` | Tra cứu trạng thái booking theo mã |
| | `CANCEL_BOOKING` | Hướng dẫn & kiểm tra điều kiện hủy booking |
| | `RESCHEDULE_BOOKING`| Hướng dẫn & kiểm tra điều kiện dời lịch |
| | `PAYMENT_SUPPORT` | Tra cứu thanh toán, đặt cọc, hoàn tiền, doanh thu |
| | `ACCOUNT_SUPPORT` | Tra cứu hồ sơ cá nhân, số lượng tài khoản |
| | `PARTNER_APPLICATION_SUPPORT` | Hướng dẫn & tra cứu trạng thái hồ sơ đối tác chủ sân |
| | `OCCUPANCY_INSIGHT` | Phân tích công suất giờ cao/thấp điểm (chủ sân) |
| **Điều hướng & Kiểm soát**| `GREETING` | Chào hỏi |
| | `UNCLEAR` | Yêu cầu mơ hồ, thiếu thông tin |
| | `OUT_OF_SCOPE` | Câu hỏi ngoài phạm vi nghiệp vụ SportHub |

### Các Entities Trích Xuất (`IntentEntities`)
- `sport_type`: Môn thể thao (`bóng đá`, `cầu lông`, `pickleball`, `tennis`, `bóng rổ`, `bóng chuyền`).
- `court_type`: Loại sân / sức chứa (`5 người`, `7 người`, `sân đơn`, `sân đôi`, `trong nhà`, `ngoài trời`).
- `venue_name`: Tên cơ sở / sân cụ thể.
- `location`: Khu vực / quận huyện / địa chỉ.
- `date`: Ngày đặt (nhận diện `hôm nay`, `ngày mai`, `thứ bảy`, `2026-09-02`,...).
- `start_time`, `end_time`: Giờ bắt đầu / kết thúc.
- `preferred_time`: Buổi trong ngày (`morning`, `afternoon`, `evening`).
- `max_price`: Mức giá tối đa (xử lý đơn vị `k`, `nghìn`, `triệu`, `đ`).
- `number_of_players`: Số người chơi.
- `booking_code`: Mã đặt sân định dạng `SH-XXXXXX`.

### Cơ chế định tuyến
Sử dụng **Giải thuật Rule-based NLU / Heuristics thuần túy**:
1. Chuẩn hóa tiếng Việt không dấu (`normalize_text`).
2. Khớp từ khóa chặn phạm vi (`OUT_OF_SCOPE_TERMS`).
3. Khớp Regex & Từ điển nhận diện ngày/giờ (`_times`, `_date`), môn thể thao (`SPORT_ALIASES`), mức giá (`_price`), mã booking (`_booking_code`).
4. Chấm điểm độ tin cậy (`confidence`). **Hoàn toàn không dùng LLM để phân loại intent.**

---

## 3. Xử Lý Ngữ Cảnh & Bộ Nhớ Hội Thoại (Context / Memory)

1. **Backend Stateless**:
   - Backend không lưu phiên chat (session) trong RAM, Redis hay Database.
   - Endpoint [`POST /ai/assistant`](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Backend/app/api/routes/ai.py#L69-L88) nhận payload gồm `{ message, context_field_id, context }`.
2. **Client-driven Context State**:
   - Phía Frontend ([`AIAssistantPage.tsx`](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Frontend/src/pages/AIAssistantPage.tsx)) duy trì state `understood` và `context` qua từng lượt hội thoại.
   - Khi gửi tin nhắn mới, Frontend đính kèm context hiện tại (chứa `sport_type`, `location`, `booking_date`, `field_id`, `result_field_ids`, `reference_price`, `last_intent`...).
3. **Hợp nhất & Đặt lại ngữ cảnh (Context Merge & Reset)**:
   - [`_merge_context`](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Backend/app/services/ai_assistant_service.py#L705-L730): Bổ sung các thông tin còn thiếu trong câu hỏi mới từ context cũ.
   - [`_starts_new_request`](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Backend/app/services/ai_intent_router.py#L324-L333): Khi người dùng đổi sang tìm kiếm môn khác, vị trí khác hoặc bắt đầu yêu cầu mới, hệ thống kích hoạt `context_reset = True` để xóa bỏ context cũ.
   - Tham chiếu vị trí (`_resolve_result_reference`): Hiểu các câu hỏi tiếp nối như *"sân đầu tiên"*, *"lựa chọn 2"*, *"sân rẻ hơn"* bằng cách tra ngược danh sách `result_field_ids` trong context.

---

## 4. Xác Định Bản Chất: Có AI Agent Thực Sự Không?

> **KẾT LUẬN: KHÔNG CÓ AI AGENT TỰ TRỊ (NO AUTONOMOUS AGENT).**

- **Không có** ReAct loop hay vòng lặp suy luận (`Thought -> Action -> Observation`).
- **Không có** Framework Agentic (LangChain, LlamaIndex, AutoGen, CrewAI).
- **Không có** LLM Tool Calling tự động: LLM không tự quyết định khi nào gọi hàm hay chọn dữ liệu.
- Hệ thống hoạt động theo mô hình **Deterministic Rule-based Workflow**: Toàn bộ luồng điều khiển (routing, truy vấn database, phân quyền, kiểm tra tính khả dụng, định dạng phản hồi) được thực thi 100% bằng code Python truyền thống. LLM chỉ đóng vai trò là một dịch vụ phụ trợ (worker) để xếp hạng dữ liệu đã chuẩn bị sẵn và sinh văn bản có cấu trúc kiểm soát.

### 4.1. Cơ chế RAG Có Kiểm Soát (Guardrailed RAG vs Autonomous RAG)
Hệ thống triển khai tầng **Guardrailed RAG** (`RAGGuardrail` + `KnowledgeService` + `KnowledgeRetriever` + `ai_system_knowledge.py` + `docs/AI/knowledge/`):
- **Phạm vi kích hoạt chặt chẽ**: Chỉ kích hoạt đối với 4 static intents (`SYSTEM_GUIDE`, `ACCOUNT_SUPPORT`, `PARTNER_APPLICATION_SUPPORT`, `PAYMENT_SUPPORT`).
- **Không trao quyền cho LLM tự truy xuất**: Router xác định intent trước, sau đó bộ lọc rào chắn (`RAGGuardrail`) kiểm tra whitelist rồi mới lấy tri thức chuẩn hóa (27 static entries).
- **Rào chắn phân quyền vai trò (Role-gating)**: Ngăn chặn tuyệt đối việc người dùng CUSTOMER đọc được các hướng dẫn hoặc chính sách nội bộ của OWNER hay SYSTEM_ADMIN.
- **Tách biệt hoàn toàn với dữ liệu động**: Giá sân, lịch trống, mã đặt chỗ, doanh thu được truy vấn trực tiếp từ cơ sở dữ liệu quan hệ thông qua Repository tương ứng, triệt tiêu nguy cơ dữ liệu cũ hoặc hallucination.

### 4.2. Chi Tiết Kỹ Thuật Retrieval/RAG Trong Source Code
Module retrieval tri thức của hệ thống bao gồm 2 tầng thực thi:
1. **Tầng tri thức tĩnh siêu tốc (`ai_system_knowledge.py`)**:
   - 27 mục tri thức cốt lõi về quy định, chính sách, hướng dẫn tài khoản được cấu trúc sẵn dạng `KnowledgeEntry`.
   - Đối sánh trực tiếp qua chuỗi ký tự chuẩn hóa không dấu (`_plain(text)` kết hợp `pattern in clean`).
   - Cung cấp câu trả lời xác định 100%, không độ trễ, không tốn chi phí gọi LLM và loại bỏ hoàn toàn nguy cơ hallucination.
2. **Tầng trích xuất tri thức mở rộng (`KnowledgeRetriever` & `KnowledgeRepository`)**:
   - Tải dữ liệu từ các file Markdown bảng biểu (`docs/AI/knowledge/*.md`).
   - **Cơ chế đối sánh kép (Dual Matching)**:
     - **Fuzzy/String Matching**: Dùng `difflib.SequenceMatcher.ratio()` đo mức độ tương đồng chuỗi ký tự theo tỷ lệ `[0, 1]`.
     - **Dense Semantic Matching**: Dùng mô hình Bi-Encoder `SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")` mã hóa câu hỏi thành vector dầy và đo tương đồng ngữ nghĩa bằng `sklearn.metrics.pairwise.cosine_similarity`.
   - **Tính điểm kết hợp (Score Combination)**: `combined = (kw_score + sem_score) / 2.0`.
   - **Sắp xếp ứng viên (Candidate Sorting)**: Sắp xếp giảm dần theo điểm số `candidates.sort(key=lambda x: x[1], reverse=True)`.
   - **Top-K Retrieval**: Trích xuất K ứng viên có điểm cao nhất với tham số mặc định `DEFAULT_TOP_K = 5` (`top_candidates = candidates[:top_k]`).
     > *Ghi chú quan trọng:* **Top-K Retrieval ở đây là một bước trích xuất/lựa chọn ứng viên theo điểm số ban đầu, KHÔNG PHẢI là mô hình Reranker (Second-stage re-ranking).**
   - **Rào lọc ngưỡng (Relevance Gating)**: Áp dụng ngưỡng `relevance_threshold = 0.60`. Nếu ứng viên đứng đầu có điểm `< 0.60`, hệ thống trả về danh sách rỗng để tránh trả lời sai.
   - **Lưu trữ Vector trên RAM**: Các vector embedding được tính toán và lưu trực tiếp trên mảng NumPy trong RAM (`self._embeddings`), hoàn toàn **không sử dụng Vector Database chuyên dụng**.

### 4.3. Bảng Các Công Nghệ / Kỹ Thuật KHÔNG Sử Dụng Trong Hệ Thống

| Công nghệ / Kỹ thuật | Trạng thái | Bằng chứng thực tế trong Codebase |
|---|---|---|
| **LangChain** | **Không sử dụng** | Không có trong `requirements.txt`; toàn bộ logic điều phối và gọi OpenAI API viết bằng code thuần + `httpx`. |
| **LlamaIndex** | **Không sử dụng** | Không có trong dependencies; module đọc tài liệu và chunking được viết thủ công trong `KnowledgeRepository`. |
| **BM25** | **Không sử dụng** | Không có thư viện `rank_bm25`/`bm25s`; code không tính toán Term Frequency, IDF hay Document Length Normalization. |
| **Sparse Vector** | **Không sử dụng** | Không dùng SPLADE, Lexical Sparse Embeddings hay `TfidfVectorizer` cho tác vụ retrieval. |
| **Vector Database chuyên dụng** | **Không sử dụng** | Không dùng Chroma, Qdrant, Milvus, Pinecone, pgvector hay FAISS. Toàn bộ embeddings chỉ lưu trên RAM dạng NumPy array. |
| **Reranker** | **Không sử dụng** | Không có mô hình Reranker độc lập (Cohere Rerank, BGE-Reranker, Cross-Encoder). Code chỉ `sort()` danh sách mảng 1 lần duy nhất. |
| **Cross-Encoder** | **Không sử dụng** | Không dùng `CrossEncoder`. Mô hình nhúng là `all-MiniLM-L6-v2` hoạt động theo kiến trúc Bi-Encoder độc lập. |

### 4.4. Phân Biệt Rõ Ràng Các Khái Niệm Kỹ Thuật

* **Fuzzy Matching ≠ BM25**: `difflib.SequenceMatcher` đo sự trùng lặp ký tự theo thuật toán Gestalt pattern matching, không phải mô hình xác suất từ khóa BM25.
* **SequenceMatcher ≠ Sparse Vector**: So khớp xâu chuỗi không tạo ra hay thao tác trên bất kỳ vector thưa nhiều chiều nào.
* **SentenceTransformer (Bi-Encoder) ≠ Cross-Encoder**: `all-MiniLM-L6-v2` mã hóa riêng rẽ query và document thành 2 vector dầy rồi tính Cosine Similarity, không truyền đồng thời cặp `[Query, Document]` vào Transformer qua self-attention.
* **Dense Embedding trong RAM ≠ Vector Database**: Mảng NumPy lưu vector trong bộ nhớ tiến trình không hỗ trợ chỉ mục không gian xấp xỉ (HNSW, IVFFlat), không lưu trữ bền vững (persistence) và không phải Vector DB.
* **Top-K Retrieval ≠ Reranking**: Cắt lấy Top-K (`candidates[:top_k]`) là bước lọc đơn cấp cơ bản theo score, không có mô hình học máy thứ hai để tái đánh giá thứ hạng (2nd-stage re-ranking).
* **Đối sánh kép (Fuzzy + Semantic) ≠ Hybrid Search (BM25 + Dense Vector)**: Hệ thống sử dụng cơ chế đối sánh kép kết hợp fuzzy string ratio và dense cosine similarity, không phải kiến trúc Hybrid Search tiêu chuẩn vốn dung hợp Inverted Index BM25 và Vector Index qua Reciprocal Rank Fusion (RRF).
* **Làm rõ ngữ cảnh thuật ngữ "Hybrid"**: Trong tài liệu của dự án, khi nhắc đến "Hybrid Recommendation System", ngữ cảnh là hệ thống gợi ý khung giờ/sân bãi kết hợp giữa lọc cơ sở dữ liệu quan hệ + mô hình ML Random Forest dự đoán nhu cầu + chấm điểm quy tắc (Rule-based Heuristic Scoring). Thuật ngữ này **hoàn toàn không liên quan đến Hybrid Search trong Retrieval/RAG**.

---

## 5. Các Backend Business Services & Repositories Được Tích Hợp

| Service / Thành phần | File mã nguồn | Chức năng trong hệ thống AI |
|---|---|---|
| [`AvailabilityService`](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Backend/app/services/availability_service.py) | `availability_service.py` | Kiểm tra lịch trống thực tế, ghép chuỗi slot liên tiếp, loại trừ slot đã đặt/khóa |
| [`AIRepository`](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Backend/app/repositories/ai_repository.py) | `ai_repository.py` | Truy vấn cơ sở dữ liệu sân bãi, hồ sơ đối tác, doanh thu, đếm số lượng cơ sở |
| [`AIFeatureService`](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Backend/app/services/ai_feature_service.py) | `ai_feature_service.py` | Điều phối xếp hạng slot trống và tổng hợp báo cáo công suất |
| [`CustomerRecommendationService`](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Backend/app/services/customer_recommendation_service.py) | `customer_recommendation_service.py` | Đề xuất sân cá nhân hóa dựa trên lịch sử đặt sân của khách hàng |
| [`InventoryService`](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Backend/app/services/inventory_service.py) | `inventory_service.py` | Tra cứu sản phẩm/dịch vụ phụ trợ còn hàng (nước uống, thuê vợt,...) |
| [`BookingService`](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Backend/app/services/booking_service.py) & Repo | `booking_service.py` | Tra cứu thông tin booking, chính sách hủy, tiền cọc |
| [`AnalyticsService`](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Backend/app/services/analytics_service.py) | `analytics_service.py` | Tính toán tỷ lệ lấp đầy, số giờ khai thác, giờ cao điểm/thấp điểm |
| [`DemandPredictionService`](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Backend/app/ai/inference/prediction_service.py) | `prediction_service.py` | Mô hình Scikit-Learn (Random Forest) dự báo nhu cầu LOW / MEDIUM / HIGH |
| [`RAGGuardrail`](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Backend/app/services/rag_guardrail.py) & [`KnowledgeService`](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Backend/app/services/knowledge_service.py) | `rag_guardrail.py`, `knowledge_service.py`, `ai_system_knowledge.py` | Tra cứu tri thức tĩnh có bảo vệ (RAG) cho 4 intent tĩnh (`SYSTEM_GUIDE`, `ACCOUNT_SUPPORT`, `PARTNER_APPLICATION_SUPPORT`, `PAYMENT_SUPPORT`), lọc theo quyền vai trò (RBAC) |
| [`KnowledgeRetriever`](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Backend/app/services/knowledge_retriever.py) & Repo | `knowledge_retriever.py`, `knowledge_repository.py` | Tầng trích xuất tài liệu Markdown (`docs/AI/knowledge/`) kết hợp đối sánh kép (SequenceMatcher + Bi-Encoder all-MiniLM-L6-v2), tính điểm kết hợp và trích xuất Top-K Retrieval (top_k=5) kèm rào lọc relevance_threshold |
| [`OpenAIProvider`](file:///c:/Users/MY%20PC/Documents/AI/SportHub%20AI/Backend/app/services/ai_provider.py) | `ai_provider.py` | Adapter kết nối OpenAI API qua HTTP với Strict JSON Schema |

---

## 6. Sơ Đồ Kiến Trúc & Luồng Xử Lý AI

### Sơ đồ Mermaid (Phản ánh chính xác 100% source code)

```mermaid
flowchart TD
    subgraph Frontend["Frontend Layer (React / TypeScript)"]
        UI["User on AIAssistantPage"]
        SvcClient["aiAssistantService.ts\n(askSportHubAssistant)"]
    end

    subgraph API["API Endpoint Layer (FastAPI)"]
        Endpoint["POST /ai/assistant\n(api/routes/ai.py)"]
    end

    subgraph CoreRouter["NLU & Routing Layer (Deterministic)"]
        AssistantSvc["AIAssistantService\n(services/ai_assistant_service.py)"]
        Router["Rule-based NLU / IntentRouter\n(Regex & Heuristics - 19 Intents)"]
    end

    subgraph StaticRAG["Static Retrieval/RAG Pipeline (4 Static Intents)"]
        Guardrail["RAGGuardrail\n(Intent Whitelist & Role Gating)"]
        Retriever["KnowledgeRetriever & KnowledgeRepo\n(docs/AI/knowledge/*.md & ai_system_knowledge)"]
        DualMatch["Dual Matching:\nFuzzy SequenceMatcher + Semantic all-MiniLM-L6-v2"]
        Scoring["Score Combination & Candidate Sorting\n((kw_score + sem_score) / 2.0)"]
        TopK["Top-K Retrieval (DEFAULT_TOP_K = 5)\n& Relevance Gating (threshold = 0.60)"]
        RelKnowledge["Relevant Grounded Knowledge"]
    end

    subgraph DynamicData["Dynamic Data Pipeline (Database & Business Services)"]
        AvailSvc["AvailabilityService\n(Lọc slot trống thực tế)"]
        FeatureSvc["AIFeatureService\n(recommend_slots / occupancy_summary)"]
        InvSvc["InventoryService\n(Sản phẩm & Dịch vụ)"]
        AnalytSvc["AnalyticsService\n(Số liệu công suất)"]
        BookSvc["BookingService\n(Thông tin booking & chính sách hủy)"]
        AIRepo["AIRepository\n(Truy vấn DB sân bãi, đối tác, user)"]
        Database[("SportHub Relational Database\nPostgreSQL / SQLite\n(GROUND TRUTH)")]
    end

    subgraph ScopedLLM["Scoped GenAI & Validation Layer"]
        OpenAIAdapter["OpenAIProvider / StructuredAIProvider\n(services/ai_provider.py)"]
        OpenAIAPI["Scoped OpenAI API\n(Strict JSON Schema)"]
        Validator["Response Validator & Fallback Guard\n(rag_response_validator / Rule Fallback)"]
    end

    %% Client flow
    UI -->|Gửi message + conversation context| SvcClient
    SvcClient -->|HTTP POST| Endpoint
    Endpoint --> AssistantSvc
    AssistantSvc -->|Phân tích text| Router

    %% Branching: Static RAG vs Dynamic Data
    Router -->|Static Intents: SYSTEM_GUIDE, ACCOUNT, PARTNER, PAYMENT| Guardrail
    Guardrail --> Retriever
    Retriever --> DualMatch
    DualMatch --> Scoring
    Scoring --> TopK
    TopK --> RelKnowledge
    RelKnowledge --> Validator

    Router -->|Dynamic Intents: SEARCH, RECOMMEND, AVAILABILITY, OCCUPANCY, BOOKING| DynamicData
    AvailSvc --> AIRepo
    InvSvc --> AIRepo
    BookSvc --> AIRepo
    AnalytSvc --> AIRepo
    AIRepo --> Database
    DynamicData --> FeatureSvc

    %% Dynamic Data to Scoped LLM
    FeatureSvc -->|Chỉ gửi available_slots đã lọc từ DB| OpenAIAdapter
    OpenAIAdapter -->|Task-specific JSON Schema| OpenAIAPI
    OpenAIAPI -->|Structured JSON| OpenAIAdapter
    OpenAIAdapter --> Validator
    FeatureSvc -.->|Nếu API timeout/lỗi| Validator

    %% Final response flow
    Validator --> AssistantSvc
    AssistantSvc -->|Chuẩn hóa JSON + Understood Context| Endpoint
    Endpoint -->|HTTP 200 JSON| SvcClient
    SvcClient -->|Render tin nhắn + Card sân UI| UI
```

---

### Sơ đồ ASCII

```
+-----------------------------------------------------------------------------------------------+
|                                FRONTEND LAYER (React / TypeScript)                            |
|  [AIAssistantPage.tsx]  <====== (Duy trì conversation context qua mỗi lượt chat)             |
|          │                                                                                    |
|          ▼                                                                                    |
|  [askSportHubAssistant] (Gửi HTTP POST: message, context_field_id, context)                   |
+-----------------------------------------------------------------------------------------------+
                                               │
                                               ▼
+-----------------------------------------------------------------------------------------------+
|                            API LAYER: POST /ai/assistant (FastAPI)                            |
+-----------------------------------------------------------------------------------------------+
                                               │
                                               ▼
+-----------------------------------------------------------------------------------------------+
|                         CORE NLU & ROUTING LAYER (AIAssistantService)                         |
|                                              │                                                |
|             [Rule-based IntentRouter] (Regex & Heuristics phân loại 19 Intents)               |
|                                              │                                                |
|            ┌─────────────────────────────────┴────────────────────────────────┐               |
|            │ (Static Intents)                                                 │ (Dynamic)     |
|            ▼                                                                  ▼               |
|  +-----------------------------------+             +---------------------------------------+  |
|  |     STATIC RETRIEVAL/RAG PIPELINE |             |         DYNAMIC DATA PIPELINE         |  |
|  |                                   |             |                                       |  |
|  | [RAGGuardrail] (Role RBAC Whitelist)            | [Business Services & Repositories]   |  |
|  |          │                        |             | - AvailabilityService (lọc slot trống)|  |
|  |          ▼                        |             | - BookingService (tra cứu đơn đặt)    |  |
|  | [KnowledgeRetriever]              |             | - InventoryService (sản phẩm/dịch vụ) |  |
|  |          │                        |             | - AnalyticsService (tính công suất)   |  |
|  |          ▼                        |             | - AIRepository                        |  |
|  | [Dual Matching]                   |             |                  │                    |  |
|  | - Fuzzy: SequenceMatcher.ratio()  |             |                  ▼                    |  |
|  | - Dense: all-MiniLM-L6-v2 Cosine  |             |    +----------------------------+     |  |
|  |          │                        |             |    |      RELATIONAL DATABASE   |     |  |
|  |          ▼                        |             |    |     (PostgreSQL / SQLite)  |     |  |
|  | [Score Combine & Sort Candidates] |             |    |         GROUND TRUTH       |     |  |
|  |          │                        |             |    +----------------------------+     |  |
|  |          ▼                        |             |                  │                    |  |
|  | [Top-K Retrieval (top_k = 5)]     |             |                  ▼                    |  |
|  | (Trích xuất Top-K theo score,     |             | [AIFeatureService (recommend_slots)]  |  |
|  |  KHÔNG PHẢI Reranker)             |             +---------------------------------------+  |
|  |          │                        |                                │                       |
|  |          ▼                        |                                ▼                       |
|  | [Relevance Gate (threshold=0.60)] |             +---------------------------------------+  |
|  |          │                        |             |        SCOPED LLM & VALIDATION        |  |
|  |          ▼                        |             |                                       |  |
|  | [Relevant Static Knowledge]       |             | [OpenAIProvider (Structured JSON)]    |  |
|  +-----------------------------------+             |         - Task: rank_available_slots  |  |
|            │                                       |         - Task: summarize_occupancy   |  |
|            │                                       | [Fallback: Rule-based Heuristic Rank] |  |
|            │                                       | [Validation / RAG Response Validator] |  |
|            │                                       +---------------------------------------+  |
|            │                                                          │                       |
|            └─────────────────────────────────┬────────────────────────┘                       |
|                                              │                                                |
|                                              ▼                                                |
|            [_response]: Đóng gói Text phản hồi + Context understood + Action UI Link          |
+-----------------------------------------------------------------------------------------------+
                                               │ HTTP 200 JSON Response
                                               ▼
                              [Frontend Client UI Render: Text + Cards]
```

---

## 7. Tổng Kết

1. **SportHub AI có GenAI không?**
   - **Có.** Hệ thống tích hợp OpenAI API (`OpenAIProvider`) nhưng chỉ dùng có kiểm soát thông qua **Strict JSON Schema** cho 3 tác vụ chuyên biệt: xếp hạng slot trống (`rank_available_slots`), viết gợi ý ưu đãi công suất (`summarize_occupancy_and_suggest_promotions`), và sinh lời chào tin nhắn (`write_booking_message_copy`).
2. **Có AI Agent thực sự không?**
   - **Không.** Hệ thống không có Agent tự hành (ReAct / Autonomous Loop / Dynamic Tool Selection). Toàn bộ luồng nghiệp vụ được điều khiển 100% bằng code Python theo kịch bản xác định.
3. **Intent Router đang đóng vai trò gì?**
   - Đóng vai trò là **Bộ phân loại ý định và trích xuất thực thể bằng luật (Rule-based NLU)**. Nó phân tích câu tiếng Việt bằng Regex và từ điển từ khóa, trích xuất thông tin (môn, ngày, giờ, giá, mã booking), quản lý trạng thái context và chuyển hướng tới đúng Backend Service tương ứng.
4. **Hệ thống xử lý tri thức tĩnh (FAQ, hướng dẫn, chính sách) như thế nào?**
   - Sử dụng **Guardrailed RAG & Static Knowledge Base** (`RAGGuardrail`, `KnowledgeService`, `KnowledgeRetriever`, `ai_system_knowledge.py` và `docs/AI/knowledge/*.md`).
   - Kích hoạt độc quyền cho 4 intent tĩnh (`SYSTEM_GUIDE`, `ACCOUNT_SUPPORT`, `PARTNER_APPLICATION_SUPPORT`, `PAYMENT_SUPPORT`) kèm rào chắn phân quyền vai trò (Role-gated).
   - Tầng retrieval ứng dụng **cơ chế đối sánh kép (Dual Matching)** kết hợp Fuzzy String Matching (`difflib.SequenceMatcher`) và Dense Semantic Matching (`all-MiniLM-L6-v2`), tính điểm kết hợp, sắp xếp ứng viên và trích xuất **Top-K Retrieval (`DEFAULT_TOP_K = 5`)** kèm bộ lọc ngưỡng (`relevance_threshold = 0.60`).
   - Top-K là bước lựa chọn ứng viên theo điểm số ban đầu, **không phải Reranker**. Hệ thống **không sử dụng Vector Database** (embeddings lưu trên RAM), **không có BM25/Sparse Vector** và **không dùng Cross-Encoder**.
5. **Kiến trúc hiện tại nên được gọi chính xác là gì?**
   - **"Deterministic Rule-based Pipeline with Guardrailed RAG (Dual Matching & Top-K Retrieval), Scoped LLM Structured Output & Scikit-Learn Demand Prediction"** (Hệ thống đường ống theo luật xác định kết hợp RAG tri thức có bảo vệ ứng dụng đối sánh kép & Top-K retrieval, LLM sinh dữ liệu có cấu trúc kiểm soát nghiêm ngặt và Machine Learning dự báo nhu cầu).
