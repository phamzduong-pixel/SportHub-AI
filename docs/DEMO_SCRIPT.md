# Kịch bản demo SportHub AI

## Chuẩn bị

1. Chạy backend với `.env` có `SEED_DEMO_DATA=true`.
2. Chạy frontend và mở `http://localhost:5173`.
3. Kiểm tra Swagger `/docs` và model file `Backend/app/ai/saved_models/demand_pipeline.joblib`.

## Luồng đề xuất (10–15 phút)

1. **Đăng nhập OWNER**
   - Giới thiệu giao diện auth responsive, nút hiện/ẩn mật khẩu và trạng thái loading/error.
   - Giới thiệu JWT, ba role và menu ẩn theo permission.

2. **Quản lý sân/khung giờ**
   - Mở danh sách ba sân mẫu.
   - Trình bày bốn thẻ tổng hợp trạng thái sân, mô tả riêng và danh sách tiện ích.
   - Mở form sửa sân để giới thiệu bộ đếm mô tả; đổi trạng thái và quan sát summary cập nhật.
   - Tạo hoặc sửa một sân; thử khung giờ overlap để trình bày validation 409.
   - Giải thích field/time slot đã có booking được khóa thay vì mất lịch sử.

3. **Luồng CUSTOMER**
   - Đăng nhập CUSTOMER.
   - Chọn ngày tương lai, sân, khung giờ và tạo booking.
   - Thử đặt lại cùng khung giờ để cho thấy backend chặn duplicate.
   - Mở lịch sử và chi tiết booking.

4. **Duyệt booking**
   - Xác nhận booking vừa tạo.

5. **Thanh toán mô phỏng**
   - CUSTOMER tạo `mock_online` hoặc giao dịch đặt cọc.
   - Trình bày tổng tiền, đã trả, đang chờ, còn lại và hóa đơn.

6. **Dashboard**
   - Lọc 30 ngày, theo sân.
   - Giải thích doanh thu chỉ tính payment `paid`, biểu đồ booking và tỷ lệ sử dụng.

7. **AI Insights**
   - Chọn bóng đá, ngày cuối tuần, 18h và giá 650.000.
   - Chạy dự đoán; giải thích LOW/MEDIUM/HIGH, probability và feature context.
   - Trình bày Accuracy/Precision/Recall/F1, Confusion Matrix và so sánh ba model.
   - Mở danh sách đề xuất: chỉ lấy slot còn trống, sau đó xếp hạng rule-based kết hợp model.

8. **Kết luận**
   - Model không train trong request và không dùng `Math.random`.
   - Nêu rõ dataset mô phỏng và hướng nâng cấp bằng dữ liệu thật.

## Tài khoản demo mặc định của workspace đã seed

- OWNER: `owner@sporthub.local` / `Owner@123456`
- CUSTOMER: `customer@sporthub.local` / `Customer@123456`

Đây là credential demo công khai, chỉ dùng local. Khi tạo database mới, đặt đúng các giá trị này trong `.env` hoặc dùng mật khẩu khác và cập nhật kịch bản.
