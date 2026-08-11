# Tiến độ chức năng đặt sân có đặt cọc

Tài liệu này ghi nhận trạng thái triển khai tại thời điểm tạm dừng. Luồng đã được đồng bộ từ database, backend API đến giao diện CUSTOMER và OWNER.

## Luồng nghiệp vụ đã hoàn thành

`CUSTOMER chọn sân và lịch → backend kiểm tra lịch trống, tự tính tiền → tạo booking PENDING_PAYMENT và giữ slot 15 phút → hiển thị QR ngân hàng → xác nhận đã nhận đủ tiền cọc → chuyển PENDING_CONFIRMATION → OWNER xác nhận hoặc từ chối`

- OWNER xác nhận: booking chuyển `CONFIRMED`.
- OWNER từ chối: booking chuyển `REJECTED`, tiền cọc được đánh dấu `REFUND_PENDING`.
- Sau khi booking được xác nhận, lần thanh toán tiếp theo chỉ thu số tiền còn lại.
- Khi thanh toán đủ và hoàn tất sử dụng sân, booking có thể chuyển `COMPLETED`.

## Database và trạng thái

- Sân/cơ sở hỗ trợ cấu hình tiền cọc theo phần trăm hoặc số tiền cố định, đồng thời có dữ liệu nền cho chính sách hủy và hoàn cọc.
- Booking lưu snapshot `total_amount`, `deposit_amount`, `paid_amount` và `remaining_amount`; backend tự tính tiền, không tin giá trị tiền từ frontend.
- Các trạng thái booking đã được đồng bộ: `PENDING_PAYMENT`, `PENDING_CONFIRMATION`, `CONFIRMED`, `COMPLETED`, `CANCELLED`, `EXPIRED`, `REJECTED`. Trạng thái `FAILED` được giữ cho các trường hợp kỹ thuật/legacy phù hợp.
- Ràng buộc chống đặt trùng khóa slot cho cả `PENDING_PAYMENT`, `PENDING_CONFIRMATION` và `CONFIRMED`.
- Payment lưu tổng tiền, tiền cọc, số đã thanh toán, số còn lại, trạng thái, phương thức, mã giao dịch, thời gian thanh toán, thông tin ngân hàng, nội dung chuyển khoản, QR, hạn thanh toán, nhà cung cấp và nguồn xác nhận.
- Khi chủ sân từ chối, Booking và Payment đều ghi nhận `refund_status = refund_pending`; giao dịch cọc gốc vẫn là giao dịch đã thanh toán để bảo toàn lịch sử tài chính.
- Thời gian hết hạn được chuẩn hóa theo UTC ở backend/database và được frontend diễn giải từ `expires_at` do server trả về.

## Thanh toán đặt cọc bằng QR

- Mỗi booking có nội dung chuyển khoản riêng, tránh dùng một QR cho nhiều booking.
- QR do backend tạo từ đúng số tài khoản, số tiền cọc và nội dung chuyển khoản.
- Booking tạm và payment intent có hạn thanh toán 15 phút.
- Countdown dùng mốc `expires_at` cố định từ server; refresh trang không reset thời gian.
- Chỉ khi countdown về `00:00` và chưa thanh toán thành công, payment chuyển thất bại, booking chuyển `EXPIRED` và slot được giải phóng.
- Luồng xác nhận giao dịch có kiểm tra idempotency, số tiền và nội dung chuyển khoản để hạn chế thanh toán hai lần hoặc xác nhận sai giao dịch.
- Thanh toán cọc thành công chỉ chuyển booking sang `PENDING_CONFIRMATION`, không xác nhận giữ sân thành công thay cho chủ sân.

### Chế độ DEMO

```env
PAYMENT_MODE=demo
BANK_ID=MB
BANK_NAME=MB Bank
BANK_ACCOUNT_NO=0000000000
BANK_ACCOUNT_NAME=SPORTHUB AI DEMO
```

Nút `Tôi đã thanh toán` gọi API mô phỏng ở backend. Đây là mô phỏng có kiểm soát dành cho demo, không phải thao tác frontend tự xác nhận booking.

### Chế độ PRODUCTION

```env
PAYMENT_MODE=production
PAYMENT_WEBHOOK_SECRET=<strong-secret>
```

- Nhận kết quả qua `POST /payments/webhook/bank` với webhook secret.
- API mô phỏng bị vô hiệu hóa.
- Không cho phép khách hoặc thao tác thủ công thông thường tự xác nhận đã nhận tiền ngân hàng.
- Chưa kết nối một nhà cung cấp payment gateway/ngân hàng cụ thể; adapter webhook hiện là điểm tích hợp dành cho bước triển khai tiếp theo.

## API chính đã đồng bộ

- `GET /bookings/quote`: backend tính tổng tiền, tiền cọc và tiền còn lại.
- `POST /bookings`: tạo booking tạm `PENDING_PAYMENT` với hạn 15 phút.
- `POST /payments/bank-intents`: tạo giao dịch và QR riêng cho booking.
- `GET /payments/{id}`: lấy trạng thái thanh toán hiện tại.
- `POST /payments/{id}/demo-confirm`: mô phỏng giao dịch thành công trong chế độ DEMO.
- `POST /payments/webhook/bank`: nhận kết quả giao dịch trong chế độ PRODUCTION.
- `PATCH /bookings/{id}/confirm`: OWNER xác nhận booking đang chờ.
- `PATCH /bookings/{id}/reject`: OWNER từ chối và đánh dấu hoàn cọc đang chờ.
- `GET /bookings/{id}/payment-summary`: lấy số liệu thanh toán đồng bộ cho chi tiết và biên lai.

## Giao diện đã hoàn thành

- CUSTOMER thấy tổng tiền, tỷ lệ/tiền cọc và số tiền còn lại trước khi tạo booking.
- Màn hình thanh toán hiển thị thông tin ngân hàng, nội dung chuyển khoản, mã booking tạm, QR và countdown.
- Sau khi cọc thành công, giao diện hiển thị `Đã thanh toán cọc – Đang chờ chủ sân xác nhận` và kiểm tra trạng thái định kỳ.
- Khi OWNER xác nhận, CUSTOMER nhận trạng thái đặt sân thành công; khi bị từ chối, giao diện thể hiện trạng thái từ chối và hoàn cọc đang chờ.
- Trang quản lý OWNER có thao tác xác nhận/từ chối bằng API thật và hiển thị `Tổng tiền | Đã cọc | Còn lại | Trạng thái thanh toán`.
- Trang chi tiết CUSTOMER và quản lý đã hiển thị đầy đủ breakdown thanh toán.
- Biên lai/hóa đơn dùng tổng giá trị booking làm `TỔNG CỘNG`; tiền cọc và khoản thanh toán sau là các thành phần thanh toán, không bị ghi nhầm thành tổng hóa đơn.

## Kiểm thử tại thời điểm tạm dừng

- 7 bài kiểm thử tập trung cho đặt cọc, QR, webhook và Payment đã chạy thành công.
- Kiểm thử chuyển trạng thái xác nhận/từ chối và chống trùng slot đã chạy thành công.
- Kiểm thử booking hết hạn giải phóng slot đã chạy thành công.
- Migration và unique index khóa slot đã được kiểm tra trên database.
- Backend đã qua kiểm tra compile/startup.
- Frontend đã build production thành công.

## Việc còn lại cho giai đoạn sau

- Tích hợp payment gateway hoặc API ngân hàng cụ thể cho môi trường production.
- Thực hiện hoàn tiền tự động; hiện hệ thống mới theo dõi trạng thái `REFUND_PENDING`, không tự chuyển tiền hoàn.
- Có thể bổ sung thông báo email, push notification hoặc WebSocket; hiện CUSTOMER nhận thay đổi trạng thái bằng polling.

## Cập nhật bổ sung — 10/08/2026

Sau mốc tài liệu ban đầu, hệ thống đã hoàn thiện thêm:

- Chính sách hủy miễn phí theo cấu hình cơ sở và nhánh CUSTOMER hủy muộn bị mất cọc.
- OWNER hủy hoặc từ chối booking đã nhận cọc tạo yêu cầu hoàn đủ tiền với lý do bắt buộc.
- Quy trình `REFUND_PENDING` → `REFUNDED`/`REFUND_OVERDUE`/`DISPUTED`, mã giao dịch hoàn, bằng chứng và xác nhận của CUSTOMER.
- Lịch sử thao tác booking/refund và chỉ số uy tín hoàn tiền.
- Thanh toán phần còn lại, hoàn thành booking và review một lần cho mỗi booking.
- Lịch sử giao dịch CUSTOMER và modal chi tiết cho từng mã `PAY-...`.

Lưu ý “hoàn tiền tự động” ở mục việc còn lại nghĩa là chuyển tiền thật qua ngân hàng/payment gateway. Quy trình ghi nhận và xác nhận hoàn tiền mô phỏng trong hệ thống đã hoàn thành.

Xem báo cáo bàn giao đầy đủ tại [SESSION_PROGRESS_2026-08-10.md](SESSION_PROGRESS_2026-08-10.md).
