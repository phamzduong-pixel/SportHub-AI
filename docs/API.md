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

AI Assistant chuyên biệt cho nghiệp vụ SportHub AI (public/CUSTOMER/OWNER/SYSTEM_ADMIN):

- `POST /ai/assistant` — nhận `message`, `context_field_id` và `context`; chỉ đọc dữ liệu SportHub, không tạo booking hay giao dịch.
- Mọi request đi qua Intent Router trước khi gọi service. Các intent: `SEARCH_VENUE`, `RECOMMEND_VENUE`, `CHECK_AVAILABILITY`, `GET_VENUE_DETAIL`, `CREATE_BOOKING`, `GET_BOOKING`, `CANCEL_BOOKING`, `RESCHEDULE_BOOKING`, `PAYMENT_SUPPORT`, `ACCOUNT_SUPPORT`, `SYSTEM_GUIDE`, `GREETING`, `FOLLOW_UP`, `UNCLEAR`, `OUT_OF_SCOPE`.
- Response gồm `intent`, `confidence`, `entities`, `needs_clarification`, `classification`, `reply`, `understood`, `suggestions` và `source=live_backend`. `entities` chuẩn hóa `sport_type`, `venue_name`, `location`, `date`, `start_time`, `end_time`, `price_max`, `number_of_players`, `booking_code`.
- `OUT_OF_SCOPE`, `GREETING` và `UNCLEAR` không query inventory/recommendation. Các intent hủy/đổi lịch chỉ đọc booking đúng quyền và hướng dẫn người dùng xác nhận trên màn hình; trợ lý không tự thực hiện mutation.
- Tìm sân công khai dùng inventory/lịch trống thật. Truy vấn riêng tư cần JWT: CUSTOMER chỉ thấy dữ liệu của mình; OWNER chỉ thấy tenant của mình; SYSTEM_ADMIN chỉ nhận các tổng hợp toàn nền tảng được API quản trị cho phép.
- Context kết quả chứa `result_field_ids` và `result_time_slot_ids` theo thứ tự để xử lý chính xác câu nối tiếp như “sân thứ 2”. Context chỉ là tham chiếu hội thoại; repository vẫn áp dụng lại tenant scope và quyền.
- Frontend xóa VenueCard của lượt cũ khi nhận intent mới; chỉ suggestions của response hiện tại được hiển thị.
- Frontend gọi qua `/api/ai/assistant`; Vite development proxy bỏ prefix `/api` trước khi chuyển tới FastAPI.

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
