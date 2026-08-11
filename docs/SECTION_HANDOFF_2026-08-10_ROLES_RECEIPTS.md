# Bàn giao section vai trò và biên lai đặt cọc — 10/08/2026

Tài liệu này ghi lại trạng thái tại thời điểm tạm dừng sau hai hạng mục: chuẩn hóa mô hình vai trò toàn hệ thống và sửa chức năng xem/in biên lai đặt cọc.

## 1. Mô hình vai trò đã hoàn thành

Runtime SportHub AI chỉ còn ba vai trò:

- `CUSTOMER`: tìm sân, đặt sân, thanh toán, quản lý booking và dữ liệu cá nhân.
- `OWNER`: trực tiếp quản lý cơ sở, sân, lịch, giá, booking, thanh toán, hoàn tiền và báo cáo thuộc quyền sở hữu của mình.
- `SYSTEM_ADMIN`: quản trị tài khoản, xét duyệt OWNER, kiểm duyệt cơ sở và xem dữ liệu tổng hợp nền tảng.

Các phần đã đồng bộ:

- User model, role enum, JWT, authentication và authorization.
- API permissions và kiểm tra ownership ở backend.
- Protected routes, redirect, sidebar, menu và dashboard frontend.
- Seed/config, AI Assistant và tài liệu role.
- Form đăng ký công khai chỉ tạo `CUSTOMER`.
- CUSTOMER muốn trở thành OWNER phải gửi `owner_application`; chỉ SYSTEM_ADMIN được phê duyệt và đổi role.
- Đã loại bỏ Manager API, Manager routes, dashboard, menu, permission và quan hệ OWNER–MANAGER khỏi runtime.

Migration tương thích dữ liệu cũ:

- `ADMIN` được đổi thành `SYSTEM_ADMIN`.
- `MANAGER` được đổi về `CUSTOMER`.
- `OWNER_PENDING` được đổi về `CUSTOMER` và tạo hồ sơ OWNER chờ duyệt.
- Không tự động drop bảng/cột permission legacy hoặc xóa lịch sử.

Kiểm thử tại mốc hoàn thành role refactor: `76/76` backend tests thành công và frontend production build thành công.

## 2. Biên lai đặt cọc đã hoàn thành

Đã tách `DepositReceipt` thành component riêng tại:

`Frontend/src/components/payments/DepositReceipt.tsx`

Component được dùng cho CUSTOMER tại trang booking thành công và cho OWNER tại trang quản lý thanh toán.

Biên lai hiển thị dữ liệu do backend cung cấp:

- SportHub AI và tiêu đề `BIÊN LAI ĐẶT CỌC`.
- Mã biên lai, mã booking và mã giao dịch.
- Khách hàng, cơ sở, địa chỉ, sân và môn thể thao.
- Ngày đặt và khung giờ.
- Tổng tiền booking, tiền cọc đã thanh toán và số tiền còn lại.
- Phương thức, ngân hàng và thời gian thanh toán.
- Trạng thái booking, đặt cọc và hoàn tiền.

Các trạng thái nghiệp vụ được hỗ trợ:

- `Đã thanh toán cọc – Đang chờ chủ sân xác nhận.`
- `Chủ sân đã từ chối – Tiền cọc đang chờ hoàn.`
- `Tiền cọc đã được hoàn cho khách hàng.`

Trang CUSTOMER tiếp tục polling khi đang chờ OWNER hoặc đang chờ hoàn tiền để cập nhật lại biên lai từ backend.

## 3. API biên lai và bảo mật

Endpoint mới:

```http
GET /payments/{payment_id}/deposit-receipt
```

Quy tắc truy cập:

- CUSTOMER chỉ xem biên lai của booking do chính mình đặt.
- OWNER chỉ xem biên lai của booking thuộc sân/cơ sở do mình sở hữu.
- SYSTEM_ADMIN được xem khi thực hiện nghiệp vụ quản trị/hỗ trợ.
- Người không có quyền nhận HTTP `404` để không làm lộ việc payment ID có tồn tại hay không.
- Chỉ giao dịch đặt cọc đã thanh toán hợp lệ mới tạo được biên lai.

Không có tên sân, số tiền, mã booking, mã giao dịch, ngân hàng hoặc thời gian nào được hard-code trong component production.

## 4. Bố cục in

CSS tại `Frontend/src/styles/globals.css` đã bổ sung print stylesheet:

- Khổ `A4 portrait` với vùng đệm theo đơn vị `mm`.
- Chỉ vùng `.deposit-receipt-print` được hiển thị khi in.
- Ẩn Header, Navbar, sidebar, footer, toast, button và nội dung web không liên quan.
- Khóa layout biên lai thành hai cột ổn định, không phụ thuộc breakpoint responsive.
- Dùng `break-inside: avoid` và `page-break-inside: avoid` cho các section.
- Không để border, shadow hoặc nền website ảnh hưởng bản in.

Fixture dùng để kiểm tra browser nằm tại:

`Frontend/tests/fixtures/deposit-receipt-print.html`

Kết quả xuất PDF headless thực tế:

- Google Chrome: `1` trang A4.
- Microsoft Edge: `1` trang A4.
- Nội dung PDF không có Header, Navbar, button, footer website, URL `localhost/file` hoặc nội dung booking thừa.

## 5. Kiểm thử cuối section

- Test chuyên biệt kiểm tra dữ liệu biên lai, CUSTOMER ownership, OWNER ownership và SYSTEM_ADMIN access: thành công.
- Test chuyển trạng thái OWNER từ chối → chờ hoàn → đã hoàn và cập nhật lại biên lai: thành công.
- `13/13` test payment, refund và professional booking liên quan: thành công.
- Frontend TypeScript và Vite production build: thành công (`1654` modules).
- Chrome và Edge print-to-PDF: mỗi browser tạo đúng một trang.

## 6. Trạng thái tạm dừng

Hai hạng mục trong section này đã hoàn thành và không còn công việc bắt buộc đang mở. Khi tiếp tục, có thể bắt đầu bằng smoke test thủ công với tài khoản CUSTOMER/OWNER/SYSTEM_ADMIN trên dữ liệu triển khai thực tế.

Các lưu ý ngoài phạm vi section:

- Thanh toán và chuyển tiền hoàn thực tế vẫn cần tích hợp payment gateway/ngân hàng production.
- Môi trường hiện có cảnh báo model AI được lưu bởi scikit-learn `1.9.0` nhưng runtime dùng `1.8.0`; nên đồng bộ phiên bản trước khi triển khai production.
