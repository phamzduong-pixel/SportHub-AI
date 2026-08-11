> T?i li?u l?ch s? tr??c ??t refactor ba vai tr?. C?c tham chi?u MANAGER d??i ??y ch? m? t? tr?ng th?i c? v? kh?ng c?n ?p d?ng cho runtime hi?n t?i.

# Báo cáo audit SportHub AI — 09/08/2026

## Phạm vi

Đã kiểm tra source frontend, backend, schema SQLite hiện tại, quan hệ dữ liệu, route/API, phân quyền và các luồng auth → tìm sân → booking → đặt cọc → xác nhận → thanh toán còn lại → hoàn tất. Không phát triển module nghiệp vụ mới.

## Critical

### C1 — Không có ranh giới dữ liệu OWNER

- File: `Backend/app/models/user.py`, `Backend/app/models/field.py`, toàn bộ repository/service quản trị.
- Nguyên nhân: `Field` và `MANAGER` không có `owner_id`; OWNER/MANAGER có quyền có thể xem/sửa sân, booking, payment, dashboard, AI và manager toàn hệ thống.
- Sửa: thêm quan hệ OWNER → MANAGER và OWNER → Field; migration gán dữ liệu cũ cho OWNER; lọc ownership tại field, time slot, booking, payment, dashboard, AI, review và manager API; truy cập chéo trả 404/403.
- Kiểm chứng: `tests/test_owner_isolation.py` kiểm tra hai OWNER và hai MANAGER độc lập.

### C2 — Danh sách/chi tiết sân dùng mock nhưng booking dùng database

- File: `Frontend/src/pages/VenuesPage.tsx`, `Frontend/src/pages/VenueDetailPage.tsx`, `Frontend/src/components/venue/HomeSections.tsx`.
- Nguyên nhân: người dùng xem tên/giá/lịch mẫu rồi bước đặt sân lại gọi API thật, gây sai sân và sai giá.
- Sửa: tạo `Frontend/src/services/venueService.ts`; danh sách, chi tiết, sân nổi bật và sân gần đều dùng `/fields`, `/fields/{id}/time-slots`, `/availability`.

### C3 — `.env` không được tự nạp, JWT có thể đổi secret sau restart

- File: `Backend/app/core/config.py`, `Backend/requirements.txt`, `README.md`.
- Nguyên nhân: README gốc chạy Uvicorn không có `--env-file`; `Settings` chỉ đọc process environment nên có thể tạo secret ngẫu nhiên dù `Backend/.env` tồn tại.
- Sửa: nạp `Backend/.env` tường minh, khai báo `python-dotenv`, sửa lệnh chạy; vẫn kiểm tra secret tối thiểu 32 ký tự.

## High

### H1 — OWNER quản lý manager toàn hệ thống

- File: `Backend/app/api/routes/managers.py`.
- Nguyên nhân: list/update/delete chỉ lọc role MANAGER, không lọc OWNER tạo tài khoản.
- Sửa: create gán `owner_id`; list/update/status/delete bắt buộc cùng `owner_id`. MANAGER vẫn không thể cấp `managers.manage` hoặc tự nâng quyền.

### H2 — Các màn hình quản lý báo thành công nhưng chỉ sửa mock/local state

- File cũ: `ManagementDashboardPage.tsx`, `ManagementCalendarPage.tsx`, `OperationsVenueCourtPages.tsx`, `OperationsSchedulePricingPages.tsx`, `OperationsCustomerPaymentPages.tsx`, `ManagementAIReportsPages.tsx`, `OperationsTeamSettingsPages.tsx`.
- Nguyên nhân: route chính trỏ tới dữ liệu `managementData`/`operationsData`.
- Sửa: route chính chuyển sang `LiveManagementDataPages.tsx` và `ManagementTeamSettingsLivePages.tsx`; dashboard, calendar, sân, khung giờ, khách hàng, report, AI, manager, phân quyền và hồ sơ quản lý dùng API thật. File demo cũ được giữ lại nhưng không còn nằm trên luồng chạy.

### H3 — CUSTOMER không có đường thanh toán phần còn lại

- File: `Frontend/src/pages/CustomerPages.tsx`, `Frontend/src/pages/BankDepositPaymentPage.tsx`.
- Nguyên nhân: sau khi OWNER xác nhận, trang chi tiết không tạo payment `full`; trang QR chỉ hiển thị ngôn ngữ đặt cọc.
- Sửa: booking `confirmed` và còn dư có nút thanh toán phần còn lại; tái sử dụng pending intent để tránh trùng; QR/nhãn/số dư hiển thị đúng loại deposit/full.

### H4 — Khu vực giao dịch CUSTOMER luôn empty dù API đã có dữ liệu

- File: `Frontend/src/pages/CustomerPages.tsx`, `Frontend/src/services/customerApi.ts`.
- Sửa: gọi `/payments/my`, hiển thị giao dịch đúng tài khoản, loại tiền, số tiền, trạng thái và thời gian thật.

### H5 — Payment intent đặt cọc kéo dài lại thời gian giữ sân

- File: `Backend/app/services/payment_service.py`.
- Nguyên nhân: tạo QR đặt cọc ghi lại `hold_expires_at = now + 15 phút`, cho phép kéo dài slot ngoài thời hạn booking ban đầu.
- Sửa: booking là nơi duy nhất tạo hạn giữ; payment dùng nguyên giá trị backend đã lưu. UTC được serialize qua `as_utc`; frontend không tự tạo expiry.

### H6 — Trang hồ sơ OWNER/MANAGER dùng số điện thoại mẫu và không lưu database

- File cũ: `OperationsTeamSettingsPages.tsx`; file thay thế: `ManagementTeamSettingsLivePages.tsx`.
- Sửa: lấy user từ `/auth/me`, cập nhật `/auth/profile`, đổi mật khẩu qua `/auth/change-password`.

## Medium

### M1 — Dashboard không đếm trạng thái pending mới

- File: `Backend/app/services/dashboard_service.py`.
- Nguyên nhân: chỉ đếm status legacy `pending`, bỏ `pending_payment` và `pending_confirmation`.
- Sửa: chuẩn hóa hai trạng thái mới về nhóm pending cho summary và chuỗi báo cáo.

### M2 — Lỗi HTTP/validation/network/timeout hiển thị không nhất quán

- File: `Frontend/src/services/apiClient.ts`.
- Sửa: timeout 15 giây, thông báo mạng rõ ràng, map fallback cho 401/403/404/409/422/500, đọc được mảng lỗi validation 422, chỉ phát sự kiện hết phiên một lần.

### M3 — Booking page nuốt lỗi tải sân/lịch

- File: `Frontend/src/pages/BookingPage.tsx`.
- Sửa: hiển thị toast/error state, bỏ loading vô hạn khi sân 404, dùng ngày local làm ngày mặc định.

### M4 — MANAGER không có `reports.view` vẫn vào dashboard mẫu

- File: `Frontend/src/routes/AppRouter.tsx`, `Frontend/src/components/auth/Guards.tsx`.
- Sửa: dashboard yêu cầu `reports.view`; route bị từ chối chuyển về settings thay vì lặp redirect dashboard.

## Low / còn lại

- Domain hiện dùng `Field` cho cả thông tin cơ sở và sân; chưa có entity `Facility` riêng. Tách Facility → Court là thay đổi kiến trúc/module dữ liệu lớn, nằm ngoài phạm vi sửa lỗi lần này.
- Các file demo cũ và `customerStorage/useCustomerBookings/mockService` vẫn còn trong source để không xóa chức năng cũ, nhưng không còn được route chính sử dụng. Có thể xóa trong đợt cleanup riêng sau khi xác nhận không cần demo.
- `MapMock` vẫn là bản đồ minh họa vì database chưa có tọa độ địa lý.
- Notification, owner-application/forgot-password và một số placeholder là module chưa có backend hoàn chỉnh; đây là phần phát triển tiếp theo, không phải lỗi của luồng booking hiện tại.
- Test cảnh báo deprecation của FastAPI TestClient/httpx và joblib/NumPy; chưa ảnh hưởng kết quả nhưng nên nâng dependency trong đợt bảo trì riêng.

## Kiểm tra database hiện tại

- 0 booking mồ côi user/field/time-slot.
- 0 payment mồ côi booking.
- 0 booking mở trùng `field/date/time_slot`.
- 0 số tiền âm, 0 booking trả vượt tổng, 0 sai lệch `remaining = total - paid`.
- 8/8 field đã gán OWNER; MANAGER hiện tại đã gán đúng OWNER.

## Kết quả test

- Backend: 47/47 test qua (`unittest discover`), gồm auth/permissions, fields/time slots, duplicate booking, deposit/QR/webhook, payment idempotency, dashboard, AI Assistant và owner isolation.
- Frontend: `npm run typecheck` qua.
- Frontend production: `npm run build` qua.
- Test hồi quy cuối sau khi đổi ownership/dashboard/payment: 8/8 qua.
