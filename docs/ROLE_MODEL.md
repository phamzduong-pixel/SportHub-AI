# Mô hình vai trò SportHub AI

Runtime chỉ chấp nhận ba giá trị `users.role`: `CUSTOMER`, `OWNER`, `SYSTEM_ADMIN`.

- CUSTOMER sử dụng chức năng tìm sân, booking, thanh toán, hóa đơn và AI trong phạm vi tài khoản của mình.
- OWNER trực tiếp quản lý cơ sở, sân, lịch, booking, thanh toán, hoàn tiền, báo cáo và AI theo ownership.
- SYSTEM_ADMIN quản trị tài khoản, xét duyệt hồ sơ OWNER, khóa/mở cơ sở và xem thống kê nền tảng; không vận hành booking hằng ngày.

Hồ sơ đăng ký chủ sân nằm trong `owner_applications`; CUSTOMER không đổi role khi đang chờ. Chỉ quyết định phê duyệt của SYSTEM_ADMIN mới chuyển tài khoản sang OWNER.

Migration giữ lại tài khoản legacy, chuyển role `MANAGER` về CUSTOMER, chuyển `OWNER_PENDING` thành CUSTOMER kèm hồ sơ chờ duyệt, và đổi `ADMIN` thành SYSTEM_ADMIN. Bảng/cột permission legacy không bị drop tự động để tránh mất dữ liệu, nhưng không còn được runtime đọc hoặc cấp quyền.
