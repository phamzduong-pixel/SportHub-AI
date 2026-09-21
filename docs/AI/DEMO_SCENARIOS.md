# Kịch bản Demo Chuẩn hóa — SportHub AI Assistant (CP-11B)

Tài liệu này cung cấp kịch bản demo trực tiếp các tính năng của Trợ lý AI SportHub trên 2 chế độ: **Tự nhiên (Natural)** và **Chuyên nghiệp (Professional)**.

---

## I. Kịch bản Demo 1: Chế độ Tự nhiên (NATURAL MODE)
*Mục tiêu: Thể hiện khả năng trò chuyện linh hoạt, tra cứu nghiệp vụ SportHub kết hợp tri thức thể thao có nguồn kiểm chứng, xử lý đa lượt, fallback an toàn và chặn câu hỏi ngoài phạm vi.*

```
Frontend: Chọn chế độ "🌿 Tự nhiên"
```

| Bước | Người dùng nhập (Prompt) | Hành vi mong đợi của AI | Luồng kỹ thuật & Nguồn dữ liệu |
| :---: | :--- | :--- | :--- |
| **1** | `"Messi là ai?"` | Trả lời đầy đủ thông tin tiểu sử, quốc tịch Argentina, câu lạc bộ hiện tại của Lionel Messi kèm nguồn trích dẫn. | `SPORTS_KNOWLEDGE` $\rightarrow$ Sports RAG $\rightarrow$ `docs/AI/knowledge/sports/players/players.md` |
| **2** | `"Anh ấy sinh ở đâu?"` *(Follow-up)* | Nhận diện đại từ *"Anh ấy"* là Lionel Messi và trả lời nơi sinh (Rosario, Argentina). | Multi-turn Context $\rightarrow$ Sports RAG $\rightarrow$ Entity Continuity |
| **3** | `"Tìm sân bóng đá gần tôi lúc 19h tối nay"` | Chuyển mượt sang nghiệp vụ SportHub, hỏi khu vực hoặc gợi ý danh sách sân bóng đá phù hợp giờ trống. | `SEARCH_VENUE` / `CHECK_AVAILABILITY` $\rightarrow$ SportHub PostgreSQL DB |
| **4** | `"Giá thuê sân cầu lông khoảng bao nhiêu tiền?"` | Trả lời thông tin bảng giá trung bình của các sân cầu lông trên hệ thống SportHub. | `SPORT_HUB_BUSINESS` $\rightarrow$ SportHub DB / Internal RAG |
| **5** | `"Thái Nguyên có những đội bóng nào?"` | Cung cấp thông tin có bằng chứng về CLB Nữ Thái Nguyên T&T và FC Thái Nguyên kèm link nguồn kiểm chứng (*Báo Thái Nguyên*). | `SPORTS_KNOWLEDGE` $\rightarrow$ Sports RAG (`thai_nguyen.md`) + Citation |
| **6** | `"Cầu thủ bóng đá Zyxw Vuivui là ai?"` | Trả về thông báo fallback có kiểm soát: *"Hiện tại SportHub AI chưa có thông tin kiểm chứng..."*, không tự bịa đặt profile. | Safe Fallback Guardrail (Không có bằng chứng $\rightarrow$ Không hallucinate) |
| **7** | `"Hãy viết cho tôi một đoạn code Python"` | Từ chối lịch sự, nêu rõ SportHub AI chỉ hỗ trợ nghiệp vụ đặt sân và kiến thức 6 môn thể thao. | `OUT_OF_SCOPE` $\rightarrow$ Out-of-Scope Refusal Message |

---

## II. Kịch bản Demo 2: Chế độ Chuyên nghiệp (PROFESSIONAL MODE)
*Mục tiêu: Thể hiện phong cách giao tiếp trang trọng, tập trung tuyệt đối vào nghiệp vụ cốt lõi của SportHub, từ chối dứt khoát tri thức ngoài và cô lập hoàn toàn khỏi Web/Sports RAG.*

```
Frontend: Chọn chế độ "💼 Chuyên nghiệp"
```

| Bước | Người dùng nhập (Prompt) | Hành vi mong đợi của AI | Luồng kỹ thuật & Nguồn dữ liệu |
| :---: | :--- | :--- | :--- |
| **1** | `"Tìm sân cầu lông tại Hà Nội"` | Tìm kiếm và hiển thị danh sách sân cầu lông có sẵn trên SportHub DB. | `SEARCH_VENUE` $\rightarrow$ SportHub DB Query |
| **2** | `"Sân còn trống lúc 19h hôm nay không?"` | Kiểm tra lịch đặt thực tế (booking slots) và phản hồi tình trạng còn trống chính xác. | `CHECK_AVAILABILITY` $\rightarrow$ SportHub DB Availability Engine |
| **3** | `"Làm thế nào để đăng ký làm chủ sân đối tác trên SportHub?"` | Hướng dẫn quy trình nộp hồ sơ, giấy tờ phê duyệt dành cho chủ sân (Owner). | `PARTNER_APPLICATION_SUPPORT` $\rightarrow$ Internal FAQ / Static Knowledge |
| **4** | `"Tôi muốn đặt sân pickleball 7 người vào tối mai"` | Nhận diện đúng từ khóa thể thao (*pickleball*) nằm trong mục đích đặt sân, chuyển tiếp sang flow booking bình thường. | `SPORT_HUB_BUSINESS` $\rightarrow$ Booking Criteria Parser |
| **5** | `"Messi là ai?"` | Từ chối lịch sự theo mẫu chuẩn: *"Ở chế độ Chuyên nghiệp (Professional), tôi chỉ hỗ trợ các nghiệp vụ trực tiếp trên hệ thống SportHub AI... Vui lòng chuyển sang Tự nhiên (Natural)..."* | `SPORTS_KNOWLEDGE` Blocked $\rightarrow$ Controlled Formal Refusal |
| **6** | `"Ronaldo hay Messi giỏi hơn?"` | Từ chối trả lời câu hỏi so sánh kiến thức thể thao, giữ vững tính trang trọng và tập trung nghiệp vụ. | `SPORTS_KNOWLEDGE` Blocked $\rightarrow$ Controlled Formal Refusal |

---

## III. Kịch bản Demo 3: Chuyển đổi Mode trong cùng phiên (MODE SWITCHING)

```
1. (Đang ở Natural)   User: "Messi là ai?" -> AI: Trả lời thông tin Messi.
2. (Chuyển sang Pro)  User: "Anh ấy sinh năm bao nhiêu?" -> AI: Từ chối do Pro mode không cho phép tra cứu cầu thủ (Lọc sạch context thể thao).
3. (Vẫn ở Pro)        User: "Tìm sân bóng đá tại Cầu Giấy" -> AI: Xử lý tìm sân bình thường.
4. (Chuyển về Natural) User: "Nguyễn Quang Hải sinh năm bao nhiêu?" -> AI: Trả lời năm sinh 1997 của Quang Hải.
```

## IV. CP-SYS-03 — System Domain Context Continuity

Mục tiêu của CP-SYS-03 là giữ đúng ngữ cảnh semantic khi người dùng hỏi follow-up ngắn, đồng thời không làm thay đổi business search/booking flow.

| Bước | Prompt | Kỳ vọng Natural & Professional | Semantic context / source |
| :---: | :--- | :--- | :--- |
| 1 | `Bóng đá có những tiện ích gì?` | Trả lời tiện ích cấp System Domain cho bóng đá. | `SYSTEM_DOMAIN` + `AMENITIES` + sport `FOOTBALL` → `SystemDomainContextService` |
| 2 | `Còn cầu lông?` | Kế thừa `AMENITIES`, chỉ đổi sport thành `BADMINTON`; không hỏi ngày chơi. | Giữ operation/domain trước đó, không route thành `SEARCH_VENUE` |
| 3 | `Bóng đá có những sản phẩm gì?` | Trả lời sản phẩm/dịch vụ cấp System Domain cho bóng đá. | `SYSTEM_DOMAIN` + `PRODUCTS` |
| 4 | `Còn tennis?` | Kế thừa `PRODUCTS`, chỉ đổi sport thành `TENNIS`. | Giữ operation/domain trước đó |
| 5 | `Tìm sân cầu lông tối nay.` | Quay về tìm sân/availability bình thường. | Explicit business request thắng context; `context_reset=True` |
| 6 | `Sân đó có những tiện ích gì?` | Giữ operation `AMENITIES`, đổi sang venue đang được tham chiếu. | `VENUE_AMENITIES` + `result_field_ids`/venue context |

Quy tắc áp dụng giống nhau cho Natural và Professional:

- Follow-up ngắn ưu tiên `domain_context_type` của lượt trước.
- Chỉ thay entity mà người dùng nêu rõ: sport, venue hoặc entity.
- Từ khóa tìm sân, lịch trống, thời gian hoặc booking vẫn chuyển về business flow.
- Dữ liệu sản phẩm/tiện ích được lấy từ `SystemDomainContextService`; LLM không tự mutation database.

### CP-SYS-03 Final Check

- Route smoke test: PASS.
- Natural và Professional dùng cùng context resolver: PASS.
- Intent metadata giữ `GET_VENUE_DETAIL` cho amenities và `GET_PRODUCTS` cho products: PASS.
- Compile Python: PASS.
- Router regression: 25 tests passed; Natural follow-up/multiturn: 10 tests passed.