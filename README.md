# CS117 - Smart Parking System

## Hệ thống đỗ xe thông minh giúp phát hiện chỗ trống và đề xuất chỗ đỗ gần nhất

Đồ án cuối kỳ môn **Tư duy Tính toán (CS117)**.
Hệ thống nhận video bãi đỗ xe, xác định trạng thái các ô đỗ và đề xuất ô đỗ trống gần nhất cho xe đi vào bãi.

---

## Thông tin môn học

* **Môn học:** Tư duy Tính toán - CS117
* **Mã lớp:** CS117.Q21
* **Giảng viên:** Ngô Đức Thành
* **Trường:** Trường Đại học Công nghệ Thông tin - ĐHQG TP.HCM
* **Khoa:** Khoa Khoa học Máy tính

---

## Thành viên nhóm

| STT | Họ và tên           | MSSV     |
| --- | ------------------- | -------- |
| 1   | Nguyễn Thị Ngọc Như | 24521278 |
| 2   | Nguyễn Thị Vân Anh  | 24520119 |
| 3   | Nguyễn Khang        | 24520749 |
| 4   | Nguyễn Thị Ái Trâm  | 24521805 |
| 5   | Lê Đan Thảo Tiên    | 24521766 |
| 6   | Lê Ngọc Tường Vy    | 24522054 |

---

## Mô tả bài toán

Trong bãi đỗ xe, người lái thường mất thời gian để tìm ô trống. Dự án xây dựng hệ thống hỗ trợ tự động:

* Phân tích video bãi đỗ.
* Xác định ô đỗ đang trống hoặc đã có xe.
* Kiểm tra bãi còn chỗ hay không.
* Đề xuất ô đỗ trống gần nhất từ cổng vào.

Bài toán được mô tả:

```text
RecommendParking(V, M) -> (A, P)
```

Trong đó:

* `V`: video/luồng hình ảnh bãi đỗ.
* `M`: cấu hình bãi đỗ.
* `A`: bãi còn chỗ hay không.
* `P`: ô đỗ được đề xuất.

---

## Chức năng chính

* Đọc video theo từng frame.
* Annotate vùng ô đỗ qua giao diện web.
* Phân loại trạng thái ô đỗ: `vacant` / `occupied`.
* Tìm ô đỗ trống gần nhất bằng đồ thị đường đi.
* Hiển thị kết quả trực quan trên giao diện.
* Xuất trạng thái ra file JSON.

---

## Demo

Do nhóm không có video stream thực tế từ camera bãi đỗ, demo sử dụng một video bãi đỗ xe lấy từ Internet.

Video trên mạng không có tín hiệu **"xe đi vào bãi"**, nên hệ thống không kích hoạt đề xuất theo sự kiện xe vào thực tế. Thay vào đó, hệ thống xử lý video liên tục và ghi nhận ô đỗ gần nhất mỗi khi trạng thái đầu ra thay đổi.

Output hiện tại được lưu tại:

```text
output/parking_status.json
```

Lịch sử các lần thay đổi được lưu tại:

```text
output/parking_status_log.jsonl
```

Ví dụ output:

```json
{
  "has_available_slot": true,
  "recommended_slot": "S47"
}
```

---

## Cấu trúc thư mục

```text
.
├── auto_setup.py
├── evaluate.py
├── prepare_data.py
├── requirements.txt
├── run_inference.py
├── train_cnn.py
├── config/
│   └── parking_lot.json
├── output/
│   ├── parking_status.json
│   └── parking_status_log.jsonl
├── src/
│   ├── detector.py
│   ├── pathfinder.py
│   ├── pipeline.py
│   ├── slot_analyzer.py
│   ├── slot_classifier.py
│   └── stabilizer.py
└── web/
    ├── app.py
    ├── static/
    └── templates/
```

---

## Công nghệ sử dụng

* Python
* OpenCV
* Flask
* NumPy
* Shapely
* YOLO-based detection
* Dijkstra / graph-based path finding
* JSON / JSONL

---

## Cài đặt

Clone repository:

```bash
git clone <your-repository-url>
cd <your-repository-folder>
```

Tạo môi trường ảo:

```bash
python -m venv venv
```

Kích hoạt môi trường ảo:

```bash
venv\Scripts\activate
```

Cài thư viện:

```bash
pip install -r requirements.txt
```

Nếu cần chạy YOLO:

```bash
pip install ultralytics torch torchvision
```

---

## Chạy demo web

```bash
python web/app.py
```

Mở trình duyệt tại:

```text
http://localhost:5005
```

Trang annotate ô đỗ:

```text
http://localhost:5005/annotate
```

---

## Lưu ý

* Video demo không phải video stream thực tế.
* Video không có tín hiệu xe đi vào bãi.
* Kết quả phụ thuộc vào góc quay, chất lượng video và cấu hình vùng ô đỗ.
* Nếu chạy demo nhiều lần, nên xóa file log cũ để tránh nối kết quả:

```bash
rm output/parking_status_log.jsonl
```

---

## Hướng phát triển

* Kết nối camera stream thực tế.
* Thêm module phát hiện xe đi vào bãi.
* Cải thiện độ ổn định qua nhiều frame.
* Tối ưu tốc độ xử lý real-time.
* Hiển thị chỉ đường trực quan đến ô đỗ được đề xuất.

---

## License

Dự án được thực hiện cho mục đích học tập trong môn **Tư duy Tính toán (CS117)** tại Trường Đại học Công nghệ Thông tin - ĐHQG TP.HCM.
