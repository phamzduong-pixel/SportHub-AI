# SportHub AI Frontend

Frontend React + TypeScript cho nền tảng đặt sân và quản lý vận hành SportHub AI.

## Chạy ứng dụng

```powershell
npm install
npm run dev
```

## Kiểm tra

```powershell
npm run typecheck
npm run build
npm run preview
```

## Công nghệ

- React 19, TypeScript, Vite.
- Tailwind CSS và Lucide React.
- React Router DOM.
- Recharts.

## Cấu trúc `src`

```text
components/   Design system và component theo nghiệp vụ
contexts/     PermissionProvider và PermissionGuard
data/         Mock data
hooks/        React hooks dùng chung
layouts/      Public, Customer và Management layout
pages/        Các route page
routes/       Cấu hình router
services/     Local storage và mock services
styles/       Tailwind/global styles
types/        TypeScript models
utils/        Hàm tiện ích
```

Danh sách route, tài khoản demo, phạm vi mock data và API cần tích hợp được mô tả trong [README dự án](../README.md).

## Trạng thái hiện tại

- Authentication đã được chuẩn hóa với một bộ Login/Register, `AuthShell`, `PasswordField`, mock auth service và các route guard dùng chung.
- Chỉ hỗ trợ CUSTOMER, OWNER và SYSTEM_ADMIN; hồ sơ chờ duyệt OWNER không phải một user role.
- Đã có `/owner-application` và `/owner-application/status` cho quy trình xác minh đối tác.
- `components/common/index.ts` là barrel export chủ đích; các component có JSX tiếp tục sử dụng `.tsx`.
- Không có framework frontend thứ hai được trộn vào dự án.
- `npm run typecheck` và `npm run build` đều thành công ở lần kiểm tra gần nhất.

## Cập nhật giao diện và nghiệp vụ 10/08/2026

- Hoàn thiện giao diện CUSTOMER cho hủy booking, hoàn cọc, khiếu nại, thanh toán phần còn lại và đánh giá sau khi hoàn thành.
- Bổ sung hotline cơ sở trong chi tiết sân và booking, hỗ trợ `tel:` và fallback dữ liệu demo.
- Thay các link `Xem giao dịch PAY-...` bằng lịch sử giao dịch responsive và modal chi tiết tải từ API.
- Chuẩn hóa responsive cho Public, CUSTOMER và Management tại các breakpoint 320–1024 px và desktop.
- Đồng bộ theme xanh ngọc/xanh lá, badge trạng thái, button, card, AI Assistant và Footer.

Chi tiết đầy đủ và kết quả kiểm tra được ghi tại [báo cáo tiến độ 10/08/2026](../docs/SESSION_PROGRESS_2026-08-10.md).
