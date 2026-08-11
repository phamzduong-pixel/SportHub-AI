# Kiến trúc SportHub AI

```text
Browser
  │  JWT Bearer / JSON
  ▼
Vite JavaScript/JSX SPA
  ├── Router + Guards
  ├── AuthContext
  ├── Feature pages/components
  │   ├── auth shell + password UX
  │   ├── field management summary/descriptions
  │   └── booking/payment/dashboard/AI views
  └── API clients
        │
        ▼
FastAPI routers
  ▼
Services (business rules + permission-aware workflows)
  ▼
Repositories (queries + transactions)
  ▼
SQLAlchemy models ── SQLite / PostgreSQL-compatible schema

AI routes
  ▼
DemandPredictionService
  ├── cached joblib pipeline
  ├── database context/history
  └── rule-based recommendation ranking
```

## Phân quyền

- Ba tác nhân nghiệp vụ chính: `CUSTOMER`, `OWNER`, `SYSTEM_ADMIN`.
- CUSTOMER: xem sân hoạt động, tự đặt/hủy hợp lệ, xem và tạo thanh toán của mình.
- OWNER: toàn quyền trên cơ sở, sân và dữ liệu thuộc tenant của chính mình.
- SYSTEM_ADMIN: quản trị tài khoản/cơ sở và thống kê toàn nền tảng; không thuộc OWNER và không vận hành booking hằng ngày.
Hệ thống không có MANAGER. OWNER trực tiếp thực hiện toàn bộ nghiệp vụ vận hành và mọi API đều kiểm tra `current_user.role == OWNER` cùng ownership của cơ sở/sân/booking.

## Tính toàn vẹn dữ liệu

- Mật khẩu chỉ lưu bcrypt hash.
- JWT dùng secret môi trường; user và trạng thái tài khoản được đọc lại ở mỗi request.
- Booking lưu snapshot giờ và giá.
- Backend kiểm tra overlap trước khi tạo; partial unique index bảo vệ cùng slot/ngày ở trạng thái mở.
- Payment giữ tổng `paid + pending` không vượt booking total; confirm/cancel khóa row khi database hỗ trợ.
- Field/time slot đã được dùng sẽ ngừng hoạt động thay vì xóa lịch sử.
- Model AI được load cache, không train trong request.

## Quy ước frontend hiện tại

- Tất cả source logic trong `Frontend/src` dùng `.jsx`; dự án không phụ thuộc React và tiếp tục render DOM/template theo kiến trúc ban đầu.
- CSS auth nằm riêng trong `features/auth/auth.css` và dùng namespace `auth-*`; CSS dashboard, payment và AI cũng nằm theo feature để hạn chế xung đột.
- Trang auth tính chiều cao từ `100dvh` sau khi trừ topbar. Màn hình thấp dùng compact mode, mobile ẩn topbar marketing để form không tạo scroll thừa.
- API URL chỉ lấy từ `VITE_API_URL` hoặc same-origin. API client từ chối phản hồi không phải JSON và bootstrap luôn có fallback UI.
- Backend vẫn là nguồn quyết định quyền cuối cùng; guard/menu frontend chỉ cải thiện trải nghiệm.
