# SportHub AI

SportHub AI là nền tảng tìm kiếm, đặt sân và quản lý vận hành cơ sở thể thao với đúng 3 vai trò: `CUSTOMER`, `OWNER`, `SYSTEM_ADMIN`. OWNER vừa là chủ sân vừa trực tiếp vận hành cơ sở; hệ thống không sử dụng MANAGER hay permission theo nhân viên phụ.

> Frontend hiện dùng mock data và mô phỏng authentication/thanh toán/AI. Không sử dụng dữ liệu này cho môi trường production.

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
│       ├── services/      # Local storage và mock service
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
- `/management/customers`
- `/management/payments`
- `/management/reports`
- `/management/ai-insights`
- `/management/team`
- `/management/roles`
- `/management/settings`

Các route tiếng Việt cũ như `/dang-nhap`, `/dang-ky`, `/tai-khoan/*` và `/quan-ly/*` được giữ dưới dạng redirect tương thích.

## Tài khoản demo

Tất cả tài khoản dùng mật khẩu `123456`.

| Vai trò | Email | Điều hướng sau đăng nhập |
|---|---|---|
| CUSTOMER | `customer@sporthub.vn` | `/customer/dashboard` |
| OWNER | `owner@sporthub.vn` | `/management/dashboard` |
| SYSTEM_ADMIN | cấu hình qua `SYSTEM_ADMIN_EMAIL` | `/system-admin` |

Trong Management topbar có bộ chuyển tài khoản demo để kiểm tra việc sidebar và action tự ẩn theo quyền.

## Các phần đang dùng mock data

- Đăng nhập, đăng ký, quên mật khẩu và phiên người dùng.
- Hồ sơ đăng ký đối tác, trạng thái `PENDING`/`APPROVED`/`REJECTED`/`SUSPENDED` và chuyển quyền OWNER sau xác minh.
- Danh sách sân, lịch trống, booking và QR xác nhận.
- Thanh toán, hoàn tiền và đối soát.
- Dashboard, báo cáo và export PDF/Excel/CSV.
- Quản lý cơ sở, sân, khung giờ, bảng giá, khách hàng và đội ngũ.
- OWNER được kiểm tra ownership theo cơ sở/sân tại backend.
- Hội thoại AI, gợi ý sân, dự báo nhu cầu và insight vận hành.
- Toast/email/thông báo và mọi thao tác “áp dụng” AI.

Authentication, profile, booking, payment và dữ liệu quản trị được lấy từ backend theo JWT hiện tại. Frontend chỉ giữ cache giao diện có phạm vi user và xóa cache này khi logout hoặc trước khi đăng nhập tài khoản khác.

## API backend cần phát triển hoặc tích hợp tiếp

- Authentication: đăng nhập, đăng ký, refresh token, đăng xuất, quên/đặt lại mật khẩu, xác minh email.
- User và ownership: hồ sơ, ba vai trò, phạm vi cơ sở/sân và audit log.
- Venue: CRUD cơ sở, upload/xóa ảnh, tiện ích, chính sách và trạng thái.
- Court và schedule: CRUD sân, lịch hoạt động, slot, ngày nghỉ, khóa lịch và bảo trì.
- Pricing: giá cơ bản, rule cao/thấp điểm, ngày lễ, promotion và lịch sử giá.
- Booking: kiểm tra xung đột, giữ chỗ, xác nhận, hủy, đặt lại và đánh giá.
- Payment: tạo giao dịch, webhook nhà cung cấp, hoàn tiền, hóa đơn và đối soát.
- Customer CRM: thống kê khách hàng, trạng thái tài khoản và lịch sử hoạt động.
- Dashboard/report: KPI theo thời gian thực, bộ lọc, tổng hợp và export server-side.
- AI Customer: ranking sân, tìm kiếm ngôn ngữ tự nhiên và cá nhân hóa.
- AI Owner: inference dự báo, phát hiện bất thường, giải thích mô hình và lưu quyết định áp dụng.
- Notification: email, SMS, push notification và quản lý template.

## Cập nhật gần nhất

Phần đăng ký tài khoản, xác minh đối tác và tổ chức frontend đã hoàn thành các nội dung sau:

- Đăng ký public luôn tạo `CUSTOMER`; hồ sơ đăng ký OWNER nằm ở bảng xét duyệt riêng và chỉ SYSTEM_ADMIN có thể phê duyệt.
- Thêm quy trình hồ sơ đối tác ba bước và trang trạng thái xác minh tại `/owner-application` và `/owner-application/status`.
- `AuthGuard`, `RoleGuard` và backend dependency bảo đảm CUSTOMER không vào `/management`, OWNER không vào `/system-admin` và SYSTEM_ADMIN không vận hành API OWNER.
- Bổ sung tài khoản demo OWNER đang chờ xác minh `pending.owner@sporthub.vn` / `123456`.
- Hoàn thiện chống đặt trùng theo cùng sân và khoảng thời gian; các booking giữ lịch gồm `PENDING_PAYMENT`, `PENDING_CONFIRMATION`, `CONFIRMED`; giữ chỗ thanh toán trong 10 phút và trả HTTP 409 khi xung đột.
- Frontend vô hiệu hóa slot đã đặt/đang giữ, làm mới khung giờ và hiển thị toast khi có xung đột; booking do OWNER tạo cũng tuân theo cùng quy tắc.
- Chuẩn hóa stack thành React 19 + Vite + TypeScript + Tailwind CSS; không trộn Vue, Angular, Next.js, Bootstrap, Material UI hay Ant Design.
- Dọn phần authentication bị trùng, chỉ giữ một luồng Login/Register; tách `AuthShell`, `PasswordField`, trang quên mật khẩu, guard, mock auth service và TypeScript model theo đúng trách nhiệm.
- Xác nhận `components/common/index.ts` là barrel export hợp lệ; file dùng `.ts` vì không chứa JSX, còn các component giao diện dùng `.tsx`.
- Chuyển `@vitejs/plugin-react` sang `devDependencies` và đồng bộ `package-lock.json`.

Kết quả kiểm tra gần nhất:

```text
Frontend dependency tree: hợp lệ
TypeScript: npm run typecheck — thành công
Production build: npm run build — thành công, 2213 modules transformed
Backend compile check: python -m compileall -q app — thành công
Backend regression tests: 32/32 test thành công
Booking conflict tests: 10/10 test thành công
```

Lưu ý: dự án hiện chưa cấu hình ESLint nên chưa có script `npm run lint`. Authentication, hồ sơ đối tác, upload giấy tờ/hình ảnh và quá trình duyệt hồ sơ vẫn đang dùng mock data/localStorage; file upload chỉ lưu tên file mô phỏng, không lưu nội dung giấy tờ.

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

Kết quả kiểm tra:

```text
AI Assistant backend tests: 10/10 thành công
Toàn bộ backend regression tests gần nhất: 41/41 thành công
Frontend TypeScript + Vite production build: thành công, 2223 modules transformed
```

Lưu ý dữ liệu: schema hiện tại dùng `Field` làm thực thể sân/cơ sở hiển thị và chưa có bảng `Facility` riêng. AI không tự tạo tên cơ sở để bù cho dữ liệu chưa tồn tại.

## Tài liệu

- [Báo cáo tiến độ phiên 10/08/2026](docs/SESSION_PROGRESS_2026-08-10.md)
- [Frontend](Frontend/README.md)
- [Backend](Backend/README.md)
- [Tiến độ chức năng đặt sân có đặt cọc](docs/DEPOSIT_BOOKING_PROGRESS.md)
- [Kiến trúc](docs/ARCHITECTURE.md)
- [Danh sách API](docs/API.md)
- [Kịch bản demo](docs/DEMO_SCRIPT.md)
