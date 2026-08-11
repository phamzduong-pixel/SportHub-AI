# Booking demand dataset

`booking_demand.csv` là **dữ liệu mô phỏng**, được tạo riêng cho mục đích học tập và trình diễn quy trình machine learning của SportHub AI. Đây không phải dữ liệu khảo sát thị trường hoặc dữ liệu kinh doanh thực tế.

Dataset có 2.400 dòng và được sinh bằng seed cố định `42` qua:

```powershell
Backend\.venv\Scripts\python.exe -m app.ai.training.generate_dataset
```

Quy tắc mô phỏng kết hợp môn thể thao, lịch sử đặt, cuối tuần, giờ cao điểm, mùa và mức giá tương đối. Một lượng nhiễu có seed được thêm vào điểm tiềm ẩn để dữ liệu không trở thành một bảng luật hoàn toàn tách biệt. Nhiễu này chỉ dùng khi tạo dataset; API inference không sinh số ngẫu nhiên.

Các nhãn:

- `LOW`: điểm nhu cầu mô phỏng dưới 4,6.
- `MEDIUM`: từ 4,6 đến dưới 7,2.
- `HIGH`: từ 7,2 trở lên.
