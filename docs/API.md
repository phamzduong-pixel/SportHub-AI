# Danh sách API SportHub AI

Swagger đầy đủ: `http://localhost:8000/docs`. Trừ đăng ký, đăng nhập, danh sách sân công khai, chi tiết sân công khai và availability, các API cần JWT Bearer.

## Auth và tài khoản

| Method | Path | Quyền |
|---|---|---|
| POST | `/auth/register` | Công khai |
| POST | `/auth/login` | Công khai |
| GET | `/auth/me` | Đăng nhập |
| PUT | `/auth/profile` | Đăng nhập |
| PUT | `/auth/change-password` | Đăng nhập |
| POST | `/auth/request-owner` | CUSTOMER gửi hồ sơ, vẫn giữ role CUSTOMER |
| GET | `/auth/owner-application` | CUSTOMER xem trạng thái hồ sơ OWNER |
| POST | `/auth/profile/avatar` | Người dùng đăng nhập tải ảnh đại diện mới |
| GET | `/auth/avatars/{file_name}` | Hiển thị ảnh đại diện đã lưu |
| POST | `/auth/owner-application/{id}/withdraw` | CUSTOMER rút hồ sơ đang chờ/cần bổ sung |
| POST | `/auth/owner-application/reapply` | CUSTOMER tạo hồ sơ mới sau khi đã rút |
| GET, PATCH | `/admin/owner-applications`, `/admin/owner-applications/{id}` | SYSTEM_ADMIN xét duyệt |
| GET | `/admin/owners` | SYSTEM_ADMIN xem danh sách OWNER và quy mô cơ sở/sân |
| GET | `/admin/summary` | SYSTEM_ADMIN |
| GET | `/admin/users` | SYSTEM_ADMIN |
| PATCH | `/admin/users/{id}/status` | SYSTEM_ADMIN |
| POST | `/admin/users/{id}/approve-owner` | SYSTEM_ADMIN |
| GET | `/admin/facilities` | SYSTEM_ADMIN |
| PATCH | `/admin/facilities/{id}/status` | SYSTEM_ADMIN |

## Cơ sở và xét duyệt cơ sở

| Method | Path | Quyền |
|---|---|---|
| GET, POST | `/facilities` | OWNER, tự giới hạn theo JWT |
| GET, PUT | `/facilities/{id}` | OWNER sở hữu cơ sở |
| DELETE | `/facilities/{id}/draft` | OWNER sở hữu; chỉ trạng thái `DRAFT` |
| POST | `/facilities/{id}/submit` | OWNER sở hữu; gửi sang `PENDING_APPROVAL` |
| POST | `/facilities/{id}/cancel-review` | OWNER sở hữu; theo điều kiện workflow |
| POST, DELETE | `/facilities/{id}/images`, `/facilities/{id}/images/{image_id}` | OWNER sở hữu |
| POST, DELETE | `/facilities/{id}/documents`, `/facilities/{id}/documents/{document_id}` | OWNER sở hữu |
| GET | `/facilities/{id}/documents/{document_id}/content` | OWNER sở hữu hoặc SYSTEM_ADMIN |
| GET | `/admin/facility-applications` | SYSTEM_ADMIN xem hồ sơ chờ duyệt |
| GET | `/admin/facility-applications/{id}` | SYSTEM_ADMIN xem hồ sơ và giấy tờ |
| PATCH | `/admin/facility-applications/{id}/review` | SYSTEM_ADMIN approve/reject; reject bắt buộc lý do |

Facility dùng trạng thái `DRAFT`, `PENDING_APPROVAL`, `APPROVED`, `REJECTED`, `SUSPENDED`. File xác minh là private; backend kiểm tra MIME, dung lượng, hash và quyền truy cập.

## Sân và khung giờ

| Method | Path | Quyền |
|---|---|---|
| GET | `/fields` | Công khai; CUSTOMER chỉ thấy available |
| GET | `/fields/{id}` | Công khai theo trạng thái |
| POST | `/fields` | `fields.create` |
| PUT | `/fields/{id}` | `fields.update` |
| PATCH | `/fields/{id}/status` | `fields.update` |
| DELETE | `/fields/{id}` | `fields.delete` |
| GET | `/time-slots` | `time_slots.manage` |
| GET | `/fields/{id}/time-slots` | Công khai theo trạng thái |
| POST, PUT | `/time-slots`, `/time-slots/{id}` | `time_slots.manage` |
| PATCH | `/time-slots/{id}/status` | `time_slots.manage` |
| DELETE | `/time-slots/{id}` | `time_slots.manage` |

## Booking

| Method | Path | Quyền |
|---|---|---|
| GET | `/availability` | Công khai |
| POST | `/bookings` | CUSTOMER hoặc `bookings.manage` |
| GET | `/bookings/my` | Đăng nhập |
| GET | `/bookings` | `bookings.manage` |
| GET | `/bookings/{id}` | Chủ booking hoặc `bookings.manage` |
| PUT | `/bookings/{id}` | `bookings.manage` |
| PATCH | `/bookings/{id}/confirm` | `bookings.manage` |
| PATCH | `/bookings/{id}/reject` | `bookings.manage` |
| PATCH | `/bookings/{id}/cancel` | Chủ booking hoặc `bookings.manage` |
| PATCH | `/bookings/{id}/complete` | `bookings.manage` |

Booking hỗ trợ nhiều `time_slot_ids`; response lưu snapshot trong `booking_slots`. Các endpoint dịch vụ phát sinh:

| Method | Path | Quyền |
|---|---|---|
| GET | `/bookings/{id}/product-options` | OWNER của booking |
| POST | `/bookings/{id}/products` | OWNER của booking; thêm dịch vụ phát sinh |
| PATCH | `/bookings/{id}/products/{item_id}` | OWNER của booking; sửa số lượng |
| DELETE | `/bookings/{id}/products/{item_id}` | OWNER của booking; xóa khoản phát sinh khi trạng thái cho phép |

## Dịch vụ, sản phẩm và tồn kho

| Method | Path | Quyền |
|---|---|---|
| GET | `/facility-products/catalog?sport=...` | OWNER; catalog database theo môn và dùng chung |
| POST | `/facility-products/from-catalog` | OWNER; import nhiều mục vào facility thuộc mình |
| GET | `/facility-products/available` | Dữ liệu khả dụng theo facility/sport |
| GET, POST | `/facility-products` | OWNER; danh sách/tạo trong tenant |
| PUT | `/facility-products/{id}` | OWNER sở hữu |
| PATCH | `/facility-products/{id}/status` | OWNER sở hữu; bật/tắt |
| PATCH | `/facility-products/{id}/price` | OWNER sở hữu |
| PATCH | `/facility-products/{id}/inventory` | OWNER sở hữu; điều chỉnh tồn kho |
| GET | `/facility-products/{id}/inventory-history` | OWNER sở hữu |
| DELETE | `/facility-products/{id}/sports?sport=...` | OWNER sở hữu; bỏ môn, archive nếu là môn cuối |
| DELETE | `/facility-products/{id}` | OWNER sở hữu; soft delete/archive |

Backend tự tính `available_quantity`, reserve/release inventory và snapshot BookingItem; không tin giá hoặc tổng tiền frontend gửi.

## Thanh toán

| Method | Path | Quyền |
|---|---|---|
| POST | `/payments` | Chủ booking hoặc `payments.manage` |
| GET | `/payments/my` | Đăng nhập |
| GET | `/payments` | `payments.manage` |
| GET | `/payments/{id}` | Chủ booking hoặc `payments.manage` |
| PATCH | `/payments/{id}/confirm` | Mock online của chủ; cash/bank cần `payments.manage` |
| PATCH | `/payments/{id}/cancel` | Chủ booking hoặc `payments.manage` |
| GET | `/bookings/{id}/payment-summary` | Chủ booking hoặc `payments.manage` |

Mỗi Payment có thêm `escrow_status` cho mô hình thanh toán trung gian mô phỏng: `pending` → `held` → `released`; nhánh lỗi/hoàn là `failed` hoặc `refunded`. Không có ví điện tử hoặc giải ngân ngân hàng thật.

## Hoàn tiền và khiếu nại

Khi OWNER từ chối hoặc hủy booking đã thu tiền, booking chuyển sang `cancelled_by_owner` và hệ thống tạo duy nhất một yêu cầu `refund_pending`. Hạn xử lý mặc định là 3 ngày.

| Method | Path | Quyền |
|---|---|---|
| GET | `/refunds/my` | CUSTOMER xem yêu cầu của mình |
| GET | `/refunds` | `payments.manage`, giới hạn theo OWNER |
| GET | `/refunds/{id}` | Chủ booking hoặc `payments.manage` |
| PATCH | `/refunds/{id}/mark-refunded` | `payments.manage`; bắt buộc `transaction_reference`, hỗ trợ `evidence_url` |
| PATCH | `/refunds/{id}/confirm-received` | CUSTOMER của booking |
| PATCH | `/refunds/{id}/dispute` | CUSTOMER của booking; bắt buộc lý do |
| GET | `/refunds/reputation` | `payments.manage`; tỷ lệ chủ sân hủy và hoàn đúng hạn |

Trạng thái hoàn tiền: `refund_pending`, `refund_overdue`, `refunded`, `disputed`. Các response hoàn tiền có `requested_at`, `due_at`, `refunded_at`, số tiền, lý do, người xử lý, bằng chứng và lịch sử thao tác.

## Vận hành, khiếu nại và audit

| Method | Path | Quyền |
|---|---|---|
| GET, POST | `/field-blocks` | `time_slots.manage`; xem/tạo ngày nghỉ hoặc khoảng bảo trì |
| DELETE | `/field-blocks/{id}` | `time_slots.manage` và đúng OWNER |
| POST | `/complaints` | CUSTOMER của booking |
| GET | `/complaints/my` | CUSTOMER xem khiếu nại của mình |
| GET, PATCH | `/complaints`, `/complaints/{id}` | `bookings.manage` và đúng OWNER |
| GET | `/audit-logs` | `reports.view` và đúng OWNER |

Availability hỗ trợ thêm `location`, `start_time`, `max_price` và `sort_by=relevance|price|rating`; lịch khóa/bảo trì được loại trực tiếp ở backend.

## Thông báo

| Method | Path | Quyền |
|---|---|---|
| GET | `/notifications` | Người dùng đăng nhập; chỉ thông báo của mình |
| GET | `/notifications/unread-count` | Người dùng đăng nhập |
| PATCH | `/notifications/read-all` | Người dùng đăng nhập |
| PATCH | `/notifications/{id}/read` | Chủ thông báo |

## Phiên đăng nhập

- `POST /auth/login` trả access token ngắn hạn và refresh token 7 ngày.
- `POST /auth/refresh` kiểm tra đúng loại token, trạng thái tài khoản và xoay cặp token mới.
- `POST /auth/logout` kết thúc phiên phía client; frontend xóa cả access/refresh token.

## Dashboard

Tất cả cần `reports.view`; hỗ trợ `date_from`, `date_to`, `field_id` khi phù hợp.

- `GET /dashboard/summary`
- `GET /dashboard/revenue`
- `GET /dashboard/bookings`
- `GET /dashboard/field-performance`
- `GET /dashboard/time-slot-performance`

## AI

### AI Assistant

`POST /ai/assistant` nhận `message`, `assistant_mode`, `context_field_id`, `context` và `conversation_id`. Assistant có thể nhận request public hoặc user đã đăng nhập; dữ liệu riêng tư luôn cần xác thực và scope theo user/tenant.

- Request đi qua IntentRouter và mode/scope policy. Các nhánh nghiệp vụ tìm sân, giá, availability, booking và payment lấy ground truth từ service/database; assistant không tự ghi booking hoặc thanh toán.
- Natural có thể xử lý Sports Knowledge, local World Cup lookup riêng, context đa lượt và profile cá nhân. Evidence, prompt LLM bên ngoài và citation có quyền kiểm soát riêng.
- Professional chỉ xử lý nghiệp vụ SportHub/System Domain; Sports Knowledge bị chặn trước World Cup lookup, Sports RAG và sports web retrieval.
- Khi `context` bị bỏ qua hoặc là `null`, server có thể khôi phục snapshot và lịch sử gần đây. Gửi `context: {}` nghĩa là reset: không dùng snapshot cũ và không chèn các lượt cũ làm context.
- Response có intent/scope, `reply`, `understood`, suggestions và venue results phù hợp với intent; các trường cụ thể được khai báo trong `Backend/app/schemas/ai.py`.

### Explicit User Memory

Các endpoint này yêu cầu người dùng đăng nhập và chỉ thao tác memory thuộc tài khoản hiện tại:

| Method | Path | Mô tả |
|---|---|---|
| GET | `/ai/memories` | Liệt kê memory đang hoạt động của user hiện tại |
| DELETE | `/ai/memories/{memory_id}` | Xóa một memory thuộc user hiện tại; trả 404 nếu không tìm thấy/không thuộc user |
| DELETE | `/ai/memories` | Xóa toàn bộ memory của user hiện tại |

Memory được ghi từ các phát biểu tường minh được extractor hỗ trợ trong Natural Mode; đây không phải bộ nhớ tự động tóm tắt toàn bộ hội thoại. Xóa memory không đồng nghĩa xóa lịch sử chat. Các quy tắc loại dữ liệu và category được định nghĩa tại `Backend/app/services/user_ai_memory_service.py`.

### AI Insights

Các API dự báo dành cho Management cần `ai.view`:

- `POST /ai/predict-demand`
- `GET /ai/model-metrics`
- `GET /ai/demand-overview`
- `GET /ai/recommendations`

## Mã lỗi chuẩn

- `401`: thiếu, sai hoặc hết hạn JWT.
- `403`: tài khoản bị khóa hoặc thiếu role/permission.
- `404`: tài nguyên không tồn tại hoặc không được phép công khai.
- `409`: xung đột trạng thái, overlap booking/time slot hoặc vượt tiền thanh toán.
- `422`: request/query không hợp lệ.
- `503`: model/metrics AI chưa sẵn sàng.
