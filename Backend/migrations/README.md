# Database migrations

SportHub AI hiện dùng SQLAlchemy `Base.metadata.create_all()` để tạo schema mới và một migration an toàn trong `app/database/migrations.py` để loại bỏ schema booking prototype cũ **chỉ khi các bảng cũ hoàn toàn rỗng**.

Khi schema cũ có dữ liệu, backend chủ động dừng bằng `RuntimeError` thay vì tự động xóa hoặc chuyển đổi dữ liệu. Đây là lựa chọn an toàn cho phiên bản môn học.

Trước khi demo:

```powershell
cd Backend
.\.venv\Scripts\python.exe -c "from app.database.session import engine; from sqlalchemy import inspect; print(inspect(engine).get_table_names())"
```

Giới hạn: dự án chưa có chuỗi revision Alembic hoàn chỉnh. Nếu tiếp tục phát triển production, cần khởi tạo Alembic, tạo baseline từ schema hiện tại và thay `create_all()` bằng quy trình `alembic upgrade head`.
