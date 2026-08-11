# Báo cáo tiến độ SportHub AI — 10/08/2026

Tài liệu này là mốc bàn giao tại thời điểm tạm dừng. Nội dung tổng hợp các nghiệp vụ và phần giao diện đã hoàn thiện trong phiên phát triển hiện tại, trên kiến trúc FastAPI + React sẵn có.

## 1. Booking, đặt cọc và thanh toán

- Luồng hiện tại: chọn sân → tạo booking → thanh toán cọc → chờ OWNER xác nhận → `CONFIRMED` → sử dụng sân → thanh toán phần còn lại → `COMPLETED`.
- Tổng tiền, tiền cọc, số đã thanh toán và số còn lại do backend tính; frontend không được tự gửi giá trị tiền để quyết định số phải thu.
- Chống thu trùng, xác nhận một payment nhiều lần và tạo payment mới khi booking đã thanh toán đủ.
- Booking bị chủ sân hủy/từ chối không thể tiếp tục thanh toán phần còn lại.
- CUSTOMER chỉ thấy nhãn thân thiện như “Đã đặt cọc”, “Đã thanh toán”, “Đã hoàn tiền”; không hiển thị trực tiếp trạng thái nội bộ `HELD`/`RELEASED`.
- Payment summary và hóa đơn giữ nguyên tổng giá trị booking; cọc và thanh toán còn lại là các thành phần của tổng tiền, không bị cộng trùng.

## 2. Chính sách hủy và hoàn tiền

- Cơ sở có thể cấu hình thời hạn hủy miễn phí; backend không hard-code một mốc chung cho mọi sân.
- CUSTOMER hủy trước hạn được hoàn 100% cọc theo luồng mô phỏng; hủy muộn chuyển `CANCELLED_BY_CUSTOMER` và không hoàn cọc.
- Trước khi hủy muộn, giao diện hiển thị cảnh báo mất cọc và yêu cầu CUSTOMER xác nhận.
- OWNER từ chối hoặc chủ động hủy booking đã nhận cọc phải nhập lý do; booking chuyển `CANCELLED_BY_OWNER` và CUSTOMER được hoàn đủ số tiền hợp lệ.
- Quy trình hoàn tiền hỗ trợ `REFUND_PENDING`, `REFUNDED`, `REFUND_OVERDUE`, `DISPUTED`.
- OWNER có thể xác nhận đã hoàn, nhập mã giao dịch và đường dẫn bằng chứng; CUSTOMER có thể xác nhận đã nhận tiền hoặc gửi khiếu nại.
- Lưu số tiền, lý do, người thao tác, thời gian yêu cầu, hạn hoàn, thời gian hoàn và lịch sử hoạt động.
- Có chỉ số tỷ lệ chủ sân hủy booking và tỷ lệ hoàn tiền đúng hạn cho dashboard/uy tín sau này.
- Các thao tác chuyển trạng thái và hoàn tiền có kiểm tra quyền, trạng thái hiện tại và idempotency để tránh xử lý lặp.

## 3. Lịch sử giao dịch CUSTOMER

- Đã sửa lỗi các dòng `Xem giao dịch PAY-...` bấm nhưng không phản hồi. Nguyên nhân là UI cũ chỉ render khi payment có `invoice`.
- Thay các link rời bằng khối **Lịch sử giao dịch** trong card Thanh toán.
- Mỗi dòng hiển thị loại giao dịch, mã giao dịch, số tiền và trạng thái thân thiện; hỗ trợ nhiều payment trong cùng booking.
- Bấm một giao dịch mở modal và tải lại đúng dữ liệu bằng `GET /payments/{id}`.
- Modal hiển thị mã giao dịch, loại thanh toán, số tiền, phương thức/ngân hàng, trạng thái, thời gian và mã booking.
- Frontend đối chiếu `booking_id`; backend tiếp tục kiểm tra CUSTOMER là chủ booking. Tài khoản khác truy cập payment nhận HTTP 403.
- Giao diện lịch sử và modal đã tối ưu cho mobile nhỏ.

Component chính: `Frontend/src/components/payments/TransactionHistory.tsx`.

## 4. Hoàn thành booking và đánh giá

- Sau khi booking `COMPLETED`, CUSTOMER thấy nút **Đánh giá sân**.
- Chỉ CUSTOMER đã hoàn thành booking được đánh giá 1–5 sao và nhận xét.
- Mỗi booking chỉ được đánh giá một lần.
- Điểm trung bình và số lượt đánh giá của sân được cập nhật từ dữ liệu review.
- OWNER có thể xem review và trạng thái booking/payment tương ứng.

## 5. Hotline cơ sở

- Trang chi tiết sân chỉ giữ một khối **Hotline chủ sân / cơ sở** trong tab Tổng quan → Giới thiệu.
- Ưu tiên hotline thật từ database; dữ liệu demo chưa có hotline dùng `0901 234 567`.
- Số điện thoại và nút **Gọi ngay** sử dụng liên kết `tel:`; nút đã được thu gọn trên mobile.
- Có ghi chú liên hệ trong giờ hoạt động.
- Hotline cũng xuất hiện trong chi tiết booking CUSTOMER.
- OWNER có thể cập nhật hotline theo cơ sở; dữ liệu rỗng được validate và không giả làm hotline thật trong database.

## 6. Danh sách và hình ảnh sân

- Toàn bộ card sân có thể bấm để mở trang chi tiết.
- CTA đổi thành **Đặt sân** và đi thẳng tới luồng chọn ngày/khung giờ.
- CTA chặn event nổi bọt để không điều hướng hai lần.
- Sân bảo trì/ngừng hoạt động không thể đặt và hiển thị trạng thái phù hợp.
- Ảnh sân được ánh xạ phù hợp với môn thể thao; gallery dùng `object-cover`, kích thước linh hoạt và thumbnail cuộn nội bộ trên mobile.
- Trang chi tiết đã loại hotline trùng và tối ưu khoảng cách/kích thước gallery ở màn hình nhỏ.

## 7. Responsive toàn frontend

- Đã rà soát CUSTOMER và OWNER tại các mốc 320, 375, 430, 768, 1024 px và desktop.
- Chuẩn hóa `min-width: 0`, `max-width`, `overflow-x`, grid/flex và khoảng đệm để tránh horizontal scroll.
- Bottom navigation CUSTOMER chia đều theo viewport và hỗ trợ safe-area.
- Sidebar Management chuyển thành drawer trên tablet/mobile; header quản lý thu gọn theo kích thước màn hình.
- Modal/drawer giới hạn theo `100dvh`, cuộn nội bộ và giảm padding trên mobile.
- Bảng và lịch rộng cuộn trong container thay vì làm tràn toàn trang.
- Form, bộ lọc, nhóm select và PageHeader tự xuống dòng ở màn hình hẹp.
- Footer xếp cột dọc trên mobile; gallery, bản đồ, ảnh hero và AI Assistant có chiều cao responsive.

## 8. Theme và màu sắc

- Theme chung chuyển sang xanh ngọc/xanh lá kết hợp nền trắng và xám xanh rất nhạt.
- Màu được gom tại `Frontend/src/styles/globals.css` và `Frontend/tailwind.config.js` qua các biến `--primary`, `--background`, `--surface`, `--success`, `--warning`, `--danger`, `--info`, `--ai` và nhóm màu Footer.
- Button chính dùng xanh thương hiệu; button phụ dùng outline/nền sáng.
- Badge tự ánh xạ trạng thái: xanh cho thành công, vàng cho chờ xử lý, đỏ nhạt cho hủy/lỗi, cyan cho thông tin/đang sử dụng/khiếu nại.
- AI giảm màu tím, chuyển sang teal nhẹ; dashboard CUSTOMER không còn gradient tím đậm.
- Hai phần Footer chuyển từ gần đen sang xanh xám vừa và xanh xám đậm hơn nhẹ ở thanh cuối.
- Hover, focus, border và shadow được đồng bộ theo màu thương hiệu, giữ tương phản chữ rõ ràng.

## 9. Các kiểm tra đã chạy ở mốc bàn giao

```text
Frontend npm run build: thành công
Frontend npm run typecheck: thành công
Backend PaymentWorkflowTests (summary + ownership): 2/2 thành công
Backend test_deposit_workflow: 1/1 thành công
```

`test_deposit_workflow` hiện xác nhận:

- Một booking có đúng hai giao dịch riêng cho cọc và phần tiền còn lại.
- Hai mã giao dịch khác nhau và mỗi `GET /payments/{id}` trả đúng payment/booking.
- CUSTOMER khác không thể xem payment, nhận HTTP 403.
- Không thể tạo thêm payment khi booking đã thanh toán đủ.

## 10. Phạm vi chưa triển khai

- Chưa tích hợp cổng thanh toán, ngân hàng hoặc chuyển khoản hoàn tiền thật; toàn bộ thanh toán/hoàn tiền vẫn là mô phỏng phục vụ đồ án.
- Chưa có chat hoặc tổng đài gọi điện; hotline chỉ dùng `tel:`.
- Chưa có kiểm thử trình duyệt tự động bằng Playwright/Cypress; responsive hiện được kiểm tra qua cấu trúc CSS, breakpoint và production build.
- Email, SMS, push notification và WebSocket vẫn là hạng mục mở rộng.

## 11. Điểm tiếp tục đề xuất

Khi tiếp tục phát triển, nên bắt đầu bằng một lượt smoke test thủ công trên trình duyệt với dữ liệu demo ở các viewport mục tiêu, sau đó mới mở rộng payment gateway hoặc notification. Không cần xây lại Booking/Payment; tiếp tục dùng service, schema và API hiện tại.
