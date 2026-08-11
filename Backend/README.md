# SportHub AI Backend

## Cấu trúc

```text
app/
├── ai/             # dataset loader, preprocessing, training, evaluation, inference
├── api/routes/     # FastAPI routers
├── core/           # config, JWT, permission definitions
├── database/       # session, safe migration, seed
├── models/         # SQLAlchemy models
├── repositories/   # truy vấn dữ liệu
├── schemas/        # Pydantic request/response
└── services/       # nghiệp vụ
tests/              # unittest integration tests
database/datasets/  # dữ liệu AI mô phỏng
migrations/         # ghi chú chiến lược migration hiện tại
```

Route chỉ nhận request và gọi service; nghiệp vụ không đặt trực tiếp trong route. Repository chịu trách nhiệm truy vấn và transaction.

## Cài đặt và chạy

```powershell
cd Backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Chỉnh `.env`, đặc biệt `SECRET_KEY` tối thiểu 32 ký tự và mật khẩu demo. Tạo secret:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Khởi động:

```powershell
uvicorn app.main:app --reload --env-file .env
```

Nếu không cấu hình `SECRET_KEY`, backend tạo khóa tạm trong RAM và cảnh báo; token sẽ mất hiệu lực sau restart. Không có secret cố định trong source code.

## Seed demo

Khi `SEED_DEMO_DATA=true`, startup tạo idempotent:

- OWNER, CUSTOMER và SYSTEM_ADMIN theo email/password trong `.env`.

Tạo SYSTEM_ADMIN ban đầu (không có API công khai để tự nâng quyền):

```powershell
.\.venv\Scripts\python.exe scripts\create_system_admin.py --email admin@example.com --name "SportHub System Admin"
```
- Ba sân và chín khung giờ mẫu; mỗi sân có mô tả riêng và 5 tiện ích.
- Lịch completed, confirmed, pending.
- Một thanh toán paid để dashboard có doanh thu.

Seed không ghi đè mật khẩu tài khoản đã tồn tại. Với database demo cũ, seed nâng cấp mô tả chung thành nội dung riêng cho từng sân và có thể chạy lặp an toàn.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m compileall -q app
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Test bao phủ auth, role/permission, validation, field, overlap time slot, duplicate booking, snapshot, payment transaction, dashboard và AI model loading.

## Database và migration

Mặc định SQLite tại `data/sporthub.db`. SQLite được bật `PRAGMA foreign_keys=ON`. Schema mới được tạo bằng `Base.metadata.create_all()`; migration booking prototype chỉ tự chạy khi bảng cũ rỗng. Xem [migrations/README.md](migrations/README.md).

Production cần PostgreSQL, Alembic revisions đầy đủ, secret manager và HTTPS.
# Bank QR deposit payments

Configure the receiver account through environment variables:

```env
PAYMENT_MODE=demo
BANK_ID=MB
BANK_NAME=MB Bank
BANK_ACCOUNT_NO=0000000000
BANK_ACCOUNT_NAME=SPORTHUB AI DEMO
```

For production, set `PAYMENT_MODE=production` and a strong
`PAYMENT_WEBHOOK_SECRET`. The bank/payment gateway must call
`POST /payments/webhook/bank` with header `X-Payment-Webhook-Secret` and the
provider reference, exact transfer content, exact amount, and `success` status.
The customer-only demo confirmation endpoint is disabled in production.

QR images use VietQR Quick Link data generated entirely by the backend. Each
intent binds one booking, receiver account, exact amount, unique transfer
content, and expiration time.
