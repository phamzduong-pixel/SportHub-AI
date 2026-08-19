# SportHub AI

SportHub AI là nền tảng tìm kiếm, đặt sân và quản lý vận hành cơ sở thể thao với đúng 3 vai trò: `CUSTOMER`, `OWNER`, `SYSTEM_ADMIN`. OWNER vừa là chủ sân vừa trực tiếp vận hành cơ sở; hệ thống không có vai trò nhân viên phụ.

Authentication, hồ sơ đối tác, booking, availability, payment, maintenance, avatar và khu vực quản trị hệ thống đã kết nối FastAPI/database thật. Một số màn hình phụ hoặc dữ liệu trình diễn cũ vẫn có thể còn mock và cần được thay thế có kiểm soát trước production.

## Công nghệ

- Frontend: React 19, TypeScript, Vite, React Router DOM.
- Giao diện: Tailwind CSS, Lucide React.
- Biểu đồ: Recharts.
- Backend hiện có: FastAPI, SQLAlchemy, SQLite, JWT.
- AI backend hiện có: pandas, scikit-learn, joblib.

## Cài đặt và chạy dự án

Yêu cầu Node.js 20+ và Python 3.12+.

### Frontend

```powershell
cd Frontend
npm install
npm run dev
```

Vite sẽ hiển thị địa chỉ truy cập, mặc định là `http://localhost:5173`.

Kiểm tra và build production:

```powershell
npm run typecheck
npm run build
npm run preview
```

### Backend

```powershell
cd Backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --env-file .env
```

Backend mặc định tại `http://localhost:8000`, Swagger tại `http://localhost:8000/docs`.

## Cấu trúc thư mục

```text
SportHub AI/
├── Frontend/
│   └── src/
│       ├── components/    # Design system, layout, booking, venue, AI
│       ├── contexts/      # Permission context và guard
│       ├── data/          # Mock data dùng chung
│       ├── hooks/         # React hooks
│       ├── layouts/       # Public, Customer, Management
│       ├── pages/         # Các màn hình ứng dụng
│       ├── routes/        # React Router
│       ├── services/      # API client và service nghiệp vụ
│       ├── styles/        # Tailwind và global CSS
│       ├── types/         # TypeScript models
│       └── utils/         # Hàm tiện ích
├── Backend/
│   ├── app/               # FastAPI, services, repositories, AI
│   ├── database/          # Dataset và SQLite
│   └── tests/             # Backend tests
└── docs/                  # Kiến trúc, API và kịch bản demo
```

## Route chính

### Public và authentication

- `/` — Trang chủ.
- `/venues`, `/venues/:venueId` — Tìm kiếm và chi tiết sân.
- `/booking/:venueId`, `/booking/success` — Quy trình đặt sân.
- `/login`, `/register`, `/forgot-password` — Authentication.
- `/owner-application` — Hoàn thiện hồ sơ đăng ký đối tác chủ sân.
- `/owner-application/status` — Theo dõi trạng thái xác minh đối tác.
- `/ai-assistant` — Trợ lý AI cho người chơi.

### Customer

- `/customer/dashboard`
- `/customer/bookings`, `/customer/bookings/:bookingId`
- `/customer/favorites`
- `/customer/transactions`
- `/customer/profile`
- `/customer/settings`

### OWNER

- `/management/dashboard`
- `/management/calendar`
- `/management/bookings`, `/management/bookings/:bookingId`
- `/management/venues`
- `/management/courts`
- `/management/schedules`
- `/management/pricing`
- `/management/products`
- `/management/customers`
- `/management/payments`
- `/management/reports`
- `/management/ai-insights`
- `/management/maintenance`
- `/management/complaints`
- `/management/reviews`
- `/management/settings`

Các route tiếng Việt cũ như `/dang-nhap`, `/dang-ky`, `/tai-khoan/*` và `/quan-ly/*` được giữ dưới dạng redirect tương thích.

## Tài khoản demo

Mật khẩu demo không được ghi cố định trong repository. Tài khoản `SYSTEM_ADMIN` phải được tạo bằng script an toàn hoặc biến môi trường và hệ thống không cung cấp API đăng ký/nâng quyền admin công khai.

| Vai trò | Email | Điều hướng sau đăng nhập |
|---|---|---|
| CUSTOMER | `customer@sporthub.vn` | `/customer/dashboard` |
| OWNER | `owner@sporthub.vn` | `/management/dashboard` |
| SYSTEM_ADMIN | cấu hình qua `SYSTEM_ADMIN_EMAIL` hoặc script khởi tạo | `/system-admin` |

## Trạng thái dữ liệu hiện tại

Các luồng xác thực, hồ sơ đối tác, hồ sơ cơ sở, upload giấy tờ, sân/slot, booking nhiều khung giờ, sản phẩm/tồn kho, payment, refund, invoice, notification và dashboard đều dùng FastAPI/database thật theo JWT.

Các giới hạn còn lại:

- Quên/đặt lại mật khẩu qua email chưa hoàn chỉnh.
- Bản đồ đang dùng `MapMock`, chưa tích hợp nhà cung cấp bản đồ thật.
- Email/SMS/push/realtime notification chưa hoàn chỉnh; thông báo trong ứng dụng đã có model/API/UI.
- UI riêng cho field-block và audit log còn giới hạn.
- Payment gateway ngân hàng thật và LLM ngoài phụ thuộc cấu hình môi trường; hệ thống có demo/fallback được kiểm soát.

## Cập nhật gần nhất

Hiện trạng chức năng ngày 16/08/2026 được tổng hợp tại [docs/Chucnang.md](docs/Chucnang.md) và [docs/FUNCTIONAL_HIERARCHY.md](docs/FUNCTIONAL_HIERARCHY.md).

Đợt cập nhật mới nhất hoàn thiện đăng ký/xét duyệt cơ sở, draft, booking nhiều khung giờ, dịch vụ–sản phẩm–tồn kho, catalog 47 mục, cấu hình dịch vụ tại sân, payment/invoice snapshot và notification trong ứng dụng.

Bàn giao Platform/Deploy ngày 11/08/2026 được giữ tại [docs/SECTION_HANDOFF_2026-08-11_PLATFORM_DEPLOY.md](docs/SECTION_HANDOFF_2026-08-11_PLATFORM_DEPLOY.md) như tài liệu lịch sử.

Các điểm đã xác minh trong đợt hiện tại:

- Ba vai trò `CUSTOMER`, `OWNER`, `SYSTEM_ADMIN` được bảo vệ ở frontend và backend.
- Facility là thực thể riêng, liên kết OWNER, sân, giấy tờ, sản phẩm và booking.
- Booking hỗ trợ nhiều slot và dịch vụ snapshot; inventory được reserve/release theo trạng thái.
- Catalog sản phẩm được seed idempotent trong database, không tự gán cho mọi cơ sở.
- File giấy tờ được lưu private và chỉ xem qua endpoint có quyền.

Kết quả kiểm tra module dịch vụ gần nhất:

```text
Product/Inventory/Booking/Payment/Invoice tests: 21/21 thành công
Frontend TypeScript + Vite production build: thành công
```

## Cập nhật AI Trợ lý SportHub — 07/08/2026

### Giới hạn domain và phân quyền — 10/08/2026

- Backend phân loại mọi câu hỏi thành `IN_SCOPE`, `OUT_OF_SCOPE` hoặc `UNCLEAR`; câu ngoài nghiệp vụ SportHub bị từ chối thay vì trả lời bằng kiến thức chung.
- Chính sách chuẩn cho tích hợp mô hình được đặt tại `Backend/app/services/ai_domain_policy.py`; enforcement thực tế nằm tại API/service/repository, không phụ thuộc riêng vào prompt.
- Endpoint nhận JWT tùy chọn. Hồ sơ, booking, payment, hoàn tiền/hóa đơn chỉ được đọc theo tài khoản; OWNER bị giới hạn đúng tenant bằng ownership backend.
- Tìm sân, giá, lịch trống và chính sách chỉ dùng dữ liệu database. Trợ lý không tự tạo sân, booking, thanh toán hoặc dữ liệu thay thế.
- Context lưu thứ tự field/time slot để hiểu chính xác “sân thứ 2”; frontend gửi token, hiển thị trạng thái ngoài phạm vi/cần làm rõ và không log nội dung hội thoại ra console.
- Intent Router tách riêng bước hiểu ý định khỏi nghiệp vụ, trả `intent`, `confidence`, `entities`, `needs_clarification` và dispatch đúng service. Frontend chỉ giữ VenueCard của response hiện tại để không hiển thị kết quả sân cũ cho intent booking/account/payment hoặc ngoài phạm vi.

Các hạng mục đã hoàn thành trong đợt này:

- Sửa vòng đời `useEffect` của `AIAssistantPage`: callback không còn trả về Promise/giá trị không hợp lệ và không còn lỗi `destroy is not a function`.
- Sửa lỗi loading vô hạn trong React `StrictMode`. Cờ mounted được khởi tạo lại ở lần effect setup thứ hai; response hợp lệ không còn bị bỏ qua và `loading` luôn được đóng trong `finally`.
- Request AI dùng `AbortController`, tự hủy khi chuyển route và timeout sau 12 giây. Giao diện phân biệt lỗi timeout, lỗi HTTP từ backend và lỗi không kết nối được backend.
- Vùng hội thoại chỉ tự cuộn bên trong khung chat, không kéo toàn bộ trang xuống footer; điều hướng sang trang chi tiết sân/đặt sân mở ở đầu trang.
- Sửa focus/bo góc của chat input và đồng bộ màu hover của button “Khám phá giải pháp”.
- Nâng cấp trích xuất yêu cầu: môn thể thao, ngày, giờ bắt đầu/kết thúc, thời lượng, khu vực, ngân sách, số người, tiện ích đặc biệt và yêu cầu tìm phương án thay thế.
- Hỗ trợ cách nói tự nhiên như “tối nay”, “8 giờ sáng mai”, “cuối tuần này”, “7–9 giờ”, “sân giá rẻ”, “gần đây” và hội thoại hỏi đáp nối tiếp.
- Nếu thiếu môn/ngày/khu vực cho yêu cầu “gần đây”, trợ lý hỏi lại ngắn gọn và giữ tiêu chí đã hiểu cho câu trả lời tiếp theo.
- Sửa alias “đá bóng” → “bóng đá” và lỗi từ đại từ “tôi” bị nhận nhầm thành buổi “tối”.
- Search chỉ đọc inventory hiện tại từ database, kiểm tra `Field/SportType → TimeSlot/Pricing → Booking`, loại booking chồng giờ và không tạo booking/thanh toán.
- Nếu không có kết quả khớp hoàn toàn, service xếp hạng phương án gần nhất theo sân, thời gian, khu vực, ngân sách, khoảng cách, rating và tiện ích; response giới hạn tối đa 5 card.
- Bổ sung log theo luồng request ở frontend/backend để chẩn đoán vị trí lỗi. Endpoint hiện dùng database search, không gọi Gemini và không dùng streaming.

Luồng hiện tại:

```text
AIAssistantPage
  → POST /api/ai/assistant
  → Vite proxy /ai/assistant
  → intent extraction + context merge
  → database availability search
  → exact filter / fallback ranking
  → JSON response
  → chat message + suggestion cards
```

AI chỉ đọc dữ liệu hiện có qua repository/service theo quyền. Schema hiện có thực thể `Facility` riêng; `Field` là từng sân/court thuộc cơ sở. AI không tự tạo dữ liệu thay thế khi database không có kết quả.

## Tài liệu

- [Bàn giao OWNER Facility, Mobile UX và Booking Service — 16/08/2026](docs/SECTION_HANDOFF_2026-08-16_OWNER_FACILITY_MOBILE_BOOKING_SERVICE.md)
- [Bàn giao AI hỗ trợ CUSTOMER đăng ký OWNER — 14/08/2026](docs/SECTION_HANDOFF_2026-08-14_AI_PARTNER_SUPPORT.md)
- [Báo cáo tiến độ phiên 10/08/2026](docs/SESSION_PROGRESS_2026-08-10.md)
- [Frontend](Frontend/README.md)
- [Backend](Backend/README.md)
- [Tiến độ chức năng đặt sân có đặt cọc](docs/DEPOSIT_BOOKING_PROGRESS.md)
- [Kiến trúc](docs/ARCHITECTURE.md)
- [Danh sách API](docs/API.md)
- [Kịch bản demo](docs/DEMO_SCRIPT.md)
