# SportHub AI – Demand Prediction

Module phân loại nhu cầu thuê sân thành `LOW`, `MEDIUM`, `HIGH`. Pipeline được huấn luyện ngoại tuyến và được nạp theo nhu cầu bằng cache; model không được huấn luyện lại trong request.

## Cấu trúc

- `datasets/loader.py`: đọc, làm sạch và kiểm tra dataset.
- `preprocessing/feature_engineering.py`: tạo đặc trưng lịch và ngữ cảnh.
- `preprocessing/pipeline.py`: imputation, OneHotEncoder và StandardScaler.
- `training/generate_dataset.py`: tạo dữ liệu mô phỏng có seed.
- `training/train_model.py`: chia train/test, huấn luyện và chọn model.
- `evaluation/metrics.py`: Accuracy, Precision, Recall, F1, Confusion Matrix.
- `evaluation/evaluate_model.py`: đánh giá lại pipeline đã lưu trên test split cố định.
- `inference/`: nạp model và phục vụ dự đoán.
- `saved_models/`: pipeline `joblib`, metrics JSON và bảng so sánh CSV.

Dataset chính nằm tại `Backend/database/datasets/booking_demand.csv` và được ghi rõ là dữ liệu mô phỏng trong README cùng thư mục.

## Đặc trưng

| Cột | Ý nghĩa |
|---|---|
| `sport_type` | Môn thể thao, được One-Hot Encoding |
| `day_of_week` | Thứ trong tuần, 0 là thứ Hai |
| `start_hour` | Giờ bắt đầu |
| `price` | Giá khung giờ |
| `month` | Tháng trong năm |
| `is_weekend` | 1 nếu thứ Bảy/Chủ Nhật |
| `previous_booking_count` | Số booking hợp lệ trong 90 ngày trước, quanh cùng giờ |
| `field_capacity` | Sức chứa sân |

Khi API không nhận `previous_booking_count` hoặc `field_capacity`, service suy ra từ database. Các trường lịch được tạo từ `booking_date` ở backend.

## Huấn luyện lại

Chạy từ thư mục `Backend`:

```powershell
.\.venv\Scripts\python.exe -m app.ai.training.generate_dataset
.\.venv\Scripts\python.exe -m app.ai.training.train_model
.\.venv\Scripts\python.exe -m app.ai.evaluation.evaluate_model
```

Ba mô hình được đánh giá trên cùng test split stratified 20%, `random_state=42`:

- Decision Tree.
- Random Forest.
- Logistic Regression.

Model được chọn theo F1 weighted, sau đó Accuracy. Lần huấn luyện hiện tại chọn Random Forest:

| Metric | Kết quả |
|---|---:|
| Accuracy | 0,8250 |
| Precision weighted | 0,8260 |
| Recall weighted | 0,8250 |
| F1 weighted | 0,8252 |

Confusion Matrix theo thứ tự `[LOW, MEDIUM, HIGH]`:

```text
136  21   0
 23 162  16
  0  24  98
```

## API

- `POST /ai/predict-demand`
- `GET /ai/model-metrics`
- `GET /ai/demand-overview`
- `GET /ai/recommendations`

Các API cần quyền `ai.view`. Nếu model hoặc metrics chưa tồn tại, backend vẫn khởi động và API trả HTTP `503` kèm lệnh huấn luyện rõ ràng.

## Cơ chế đề xuất

Đây là hybrid đơn giản:

1. Lọc đúng môn, sân hoạt động, khung giờ mở và chưa có booking chồng lấn.
2. Model dự đoán nhu cầu cho từng ứng viên.
3. Rule-based score kết hợp giá, tính phù hợp và demand class.
4. `LOW/MEDIUM` được ưu tiên cho khả năng đặt và giá trị; `HIGH` vẫn được hiển thị cùng cảnh báo nên đặt sớm.

Không có `Math.random`, random response hay nhãn hardcode trong inference.

## Giới hạn

- Dataset hiện tại là mô phỏng, chưa phản ánh đầy đủ hành vi khách hàng thực tế.
- Model chưa sử dụng thời tiết, ngày lễ, sự kiện địa phương hoặc lead time đặt sân.
- `previous_booking_count` phụ thuộc lượng lịch sử có trong database; hệ thống mới sẽ có tín hiệu này thấp.
- Xác suất là mức tự tin của mô hình trên phân phối dữ liệu huấn luyện, không phải xác suất doanh thu được đảm bảo.
- Cần huấn luyện lại bằng dữ liệu thực tế và theo dõi drift trước khi dùng cho quyết định kinh doanh.
