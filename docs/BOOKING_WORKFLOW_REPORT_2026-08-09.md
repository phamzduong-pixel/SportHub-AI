# Báo cáo hoàn thiện nghiệp vụ Booking — 2026-08-09

## Phạm vi đã hoàn thành

- State machine do backend kiểm soát: `PENDING_PAYMENT`, `EXPIRED`, `PENDING_CONFIRMATION`, `CONFIRMED`, `CANCELLED`, `IN_PROGRESS`, `COMPLETED`, `NO_SHOW`; giữ `REJECTED`/`FAILED` để tương thích dữ liệu cũ.
- CUSTOMER có “Đặt sân của tôi” với 6 nhóm, chi tiết tiền/cơ sở/sân/lịch/mã booking, countdown dùng `hold_expires_at` UTC do backend trả về.
- Chính sách hủy nhiều mốc theo Facility; backend báo giá hoàn trước khi hủy, lưu lý do/thời gian/khoản hoàn và tạo giao dịch `REFUND` duy nhất.
- Đổi lịch cùng Facility: kiểm tra availability và conflict trước khi cập nhật; lịch cũ không bị thay đổi nếu lịch mới lỗi; chênh lệch tăng tạo khoản phải thanh toán thêm, chênh lệch giảm ghi nhận credit/refund.
- Payment tách `DEPOSIT`, `REMAINING`, `REFUND`, lưu customer/owner/provider/lỗi/thời gian hoàn và ngăn giao dịch pending trùng.
- Invoice được lưu riêng sau khi booking hoàn tất và CUSTOMER xem lại từ lịch sử.
- OWNER có danh sách theo nhóm, tìm mã/khách/điện thoại/sân/ngày, action xác nhận/bắt đầu/no-show/hoàn tất theo permission.
- Lịch quản lý ngày/tuần hiển thị theo sân và màu trạng thái, dùng booking thật từ API.
- Chống concurrency: PostgreSQL khóa hàng Field; SQLite dùng `BEGIN IMMEDIATE` để tuần tự hóa bước kiểm tra availability + insert. Unique partial index là lớp bảo vệ bổ sung.

## API mới/mở rộng

- `GET/POST /facilities`
- `PUT /facilities/{id}/cancellation-policy`
- `GET /bookings/{id}/cancellation-quote`
- `PATCH /bookings/{id}/cancel`
- `POST /bookings/{id}/reschedule/quote`
- `PATCH /bookings/{id}/reschedule`
- `PATCH /bookings/{id}/start`
- `PATCH /bookings/{id}/no-show`
- `PATCH /bookings/{id}/complete`
- `GET /bookings/{id}/invoice`
- Payment API hiện nhận `deposit`, `remaining`, `refund`; `full` chỉ còn alias tương thích dữ liệu/client cũ.

## Database/migration

- Thêm bảng `facilities`, `invoices`.
- Bổ sung Facility snapshot, cancellation/refund/credit/reschedule fields cho Booking.
- Bổ sung tenant/provider/failure/refund timestamps cho Payment.
- Tự tạo Facility cho Field legacy và backfill Facility/Customer/Owner cho Booking/Payment hiện có.
- Mở rộng unique open-booking index để `IN_PROGRESS` tiếp tục khóa slot.
- Migration đã chạy thành công trên database hiện tại và có thể chạy lặp lại an toàn.

## Kiểm thử

- Backend: **52/52 unittest đạt**, gồm auth, CUSTOMER/OWNER, booking/payment, timeout, hủy/hoàn, đổi lịch, invoice, tenant isolation, AI và concurrency hai khách đặt hai slot chồng lấn.
- Frontend: `tsc -b && vite build` thành công.
- OpenAPI đã xác nhận đầy đủ các route booking/facility/payment mới.

## Phần cần tích hợp ngoài hệ thống

- Giao dịch ngân hàng production và hoàn tiền thật vẫn cần webhook/API của nhà cung cấp thanh toán. Hiện backend đã có trạng thái, idempotency, số tiền và quy trình xác nhận; chế độ demo/manual không giả lập rằng tiền production đã thực sự chuyển.
- UI lịch chưa hỗ trợ kéo-thả vì thao tác đó cần quy tắc vận hành riêng; click chi tiết và đổi lịch có kiểm tra backend đã hoạt động.

## Bổ sung: sửa luồng xem chi tiết sân

### Nguyên nhân

- Frontend trước đây gọi dữ liệu backend `Field/Court` bằng tên `Venue`, dễ gây nhầm `facility.id` với `court.id`.
- Trang chi tiết ghép hai request `/fields/{id}` và `/fields/{id}/time-slots` bằng `Promise.all`; lỗi ở request phụ cũng làm toàn trang bị xử lý như không tìm thấy sân.
- Route legacy `/san-the-thao/:venueId` redirect về `/venues` nhưng làm mất ID.
- UI chưa phân biệt rõ lỗi 404 với lỗi network/server.

### Thay đổi

- Route chi tiết chuẩn chuyển từ `/venues/:venueId` sang `/courts/:courtId`.
- `/venues/:venueId` và `/san-the-thao/:venueId` vẫn được hỗ trợ bằng redirect giữ nguyên ID sang `/courts/{id}`.
- Thêm endpoint nguyên tử `GET /public/courts/{court_id}` trả:
  - `court`;
  - `facility`;
  - `time_slots`;
  - `images`;
  - `min_price` và `max_price`.
- Endpoint public chỉ trả Court đang `available` và không áp dụng bộ lọc tenant OWNER.
- Đã đồng bộ link từ card Khám phá, recommendation, AI Assistant, sân yêu thích và lịch sử booking.
- Trang chi tiết tự tải bằng ID khi refresh/mở tab mới; không tìm trong state đã filter ở trang trước.
- 404 hiển thị “Sân này không tồn tại hoặc đã ngừng hoạt động”; network/500 hiển thị thông báo tải thất bại và nút thử lại.
- Chặn request ID `NaN`, `0` hoặc ID không hợp lệ ở chức năng favorite.
- Đã xóa `Frontend/src/data/mockData.ts` và `Frontend/src/services/mockService.ts`; luồng public Explore/Detail không còn dùng mock.

### File liên quan

- Backend mới: `app/api/routes/public_courts.py`, `app/schemas/public_court.py`.
- Backend sửa: `app/main.py`.
- Frontend sửa: `routes/AppRouter.tsx`, `pages/VenueDetailPage.tsx`, `services/venueService.ts`, `services/apiClient.ts`, `components/venue/VenueCard.tsx`, `components/venue/PersonalizedRecommendations.tsx`, `pages/AIAssistantPage.tsx`, `pages/CustomerPages.tsx`, `pages/CustomerBookingDetailPage.tsx`, `hooks/useFavoriteField.ts`, `types/index.ts`.

### Kiểm thử

- Court ID 1, 2 và 3 trên database thật đều trả HTTP 200, đúng `court.id`, `facility.id` và danh sách khung giờ.
- ID không tồn tại trả HTTP 404.
- Endpoint public không bị chặn bởi token không hợp lệ hoặc token ngoài tenant.
- 7 test field/tenant isolation đạt.
- Frontend TypeScript và production build thành công.

## Trạng thái hiện tại

**Tạm dừng theo yêu cầu người dùng ngày 09/08/2026.** Các thay đổi trên đã được lưu và kiểm thử; chưa tiếp tục phát triển chức năng mới sau mốc này.
