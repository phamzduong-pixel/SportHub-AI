# Gợi ý nội dung báo cáo

## 1. Đặt vấn đề

- Khó khăn khi quản lý nhiều sân, khung giờ, giá, booking và thanh toán thủ công.
- Mục tiêu số hóa vận hành và bổ sung dự báo nhu cầu.

## 2. Phân tích yêu cầu

- Ba tác nhân duy nhất: CUSTOMER, OWNER, SYSTEM_ADMIN.
- Use case theo module và permission matrix.
- Business rules: overlap, snapshot, soft delete, payment cap, model availability.

## 3. Thiết kế hệ thống

- Sơ đồ kiến trúc từ `ARCHITECTURE.md`.
- ERD gồm User, UserPermission, Field, TimeSlot, Booking, Payment.
- Sequence diagram: đăng nhập, đặt sân, thanh toán, AI prediction.
- Giải thích repository/service/router và frontend feature modules.

## 4. Module AI

- Bài toán classification ba lớp.
- Mô tả 2.400 dòng dữ liệu mô phỏng, seed và quy tắc gán nhãn.
- Cleaning, OneHotEncoder, StandardScaler, stratified train/test.
- So sánh Decision Tree, Random Forest, Logistic Regression.
- Bảng metrics và Confusion Matrix.
- Lý do chọn Random Forest theo F1 weighted.
- Inference cache và hybrid recommendation.

## 5. Kiểm thử

- Bảng test cho 401/403/404/409/422/503.
- Duplicate booking, overlap slot, snapshot, payment transaction.
- Authorization và ownership CUSTOMER/OWNER/SYSTEM_ADMIN.
- Empty dashboard và missing AI model.
- Kết quả unittest backend và build frontend.

## 6. Bảo mật và chất lượng

- Bcrypt password, JWT environment secret, token expiration.
- Backend authorization là nguồn quyết định cuối.
- Validation hai lớp frontend/backend.
- Foreign keys, row locking khi database hỗ trợ, soft delete dữ liệu đã dùng.

## 7. Hạn chế và hướng phát triển

- Dataset AI mô phỏng; cần dữ liệu thật và theo dõi drift.
- SQLite phù hợp demo, chưa phù hợp concurrency production.
- Chưa tích hợp payment gateway, refresh token, email/SMS.
- Chưa có Alembic revision chain, E2E browser test và deployment CI/CD.
- Có thể bổ sung thời tiết, ngày lễ, sự kiện và explainability SHAP sau này.

Nên chụp màn hình: login/register desktop và mobile, permission checkbox, summary quản lý sân, card sân có mô tả/tiện ích, chọn slot, booking duplicate error, payment summary, dashboard, AI probability, model metrics và recommendations.
