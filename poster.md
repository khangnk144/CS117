# Introduction

In shopping malls, drivers often waste time searching for vacant parking spaces. In addition, finding a suitable parking spot usually requires vehicles to move around the parking lot multiple times, increasing internal traffic congestion and causing inconvenience for drivers. To address this problem, our team develops a smart parking system that detects parking slot occupancy using surveillance cameras and guides drivers to the nearest vacant space through the shortest path.

---

# Input

- Video-stream giám sát có độ phân giải cao từ camera giám sát
- Tín hiệu kích hoạt
- Bản đồ bãi đỗ xe
- Vị trí hiện tại của xe

# Output

- Video đã chú thích
- Bounding box của phương tiện và độ tin cậy
- Mỗi chỗ đỗ được đánh dấu bằng polygon phủ màu:
  - Xanh lá = trống
  - Đỏ = đã có xe
- Chỗ đỗ được đề xuất: được tô nổi màu vàng
- Vị trí đỗ xe (vd: E12.3)
- Sơ đồ bãi đỗ xe 2D được cập nhật liên tục theo vị trí hiện tại của xe
- Thông tin đường đi ngắn nhất (lộ trình trong bãi xe)

---

# Requirements (Khách hàng yêu cầu)

## Yêu cầu chức năng

### FR1 – Parking Slot Occupancy Classification

Xác định trạng thái của từng chỗ đỗ xe (trống / có xe) từ video camera giám sát theo thời gian thực.

### FR2 – Optimal Parking Slot Recommendation

Xác định đường đi ngắn nhất từ lối vào tới chỗ đỗ trống.

### FR3 – Real-time Parking Status Update

Hệ thống phải tự động cập nhật trạng thái chỗ đỗ khi xe đi vào hoặc rời khỏi vị trí đỗ.

### FR4 – Visualization and Navigation Interface

Hệ thống phải cung cấp giao diện trực quan bao gồm:

- Video giám sát có chú thích
- Sơ đồ bãi đỗ xe 2D
- Hiển thị trạng thái các chỗ đỗ, tuyến đường được đề xuất cho người dùng

## Yêu cầu phi chức năng

### NFR1 – Classification Accuracy

Độ chính xác phân loại trạng thái chỗ đỗ phải đạt F1-score ≥ 0.95.

### NFR2 – Path Recommendation Accuracy

Kết quả đề xuất chỗ đỗ và tuyến đường phải đạt độ chính xác 100%.

### NFR3 – Response Time

Trạng thái chỗ đỗ phải được cập nhật với độ trễ trung bình không vượt quá 3 giây kể từ thời điểm xe chiếm ít nhất một nửa diện tích ô đỗ.

### NFR4 – Real-time Processing Performance

Hệ thống phải xử lý video theo thời gian thực với tốc độ tối thiểu 15 FPS.

### NFR5 – Synchronization Consistency

Video giám sát và sơ đồ bãi đỗ 2D phải được cập nhật đồng bộ với sai lệch hiển thị không vượt quá 2 giây.

---

# Constraints

- Hệ thống sử dụng 1 camera cố định, gắn ở độ cao ≥ 3m và hướng xuống khu vực đỗ xe, có độ phân giải tối thiểu 720p (khuyến nghị 1080p), có góc nhìn đủ bao quát, không bị lóa bởi ánh sáng.
- Các phương tiện không bị che khuất khỏi tầm nhìn camera bởi cột hay các thứ khác.
- Đảm bảo hệ thống camera và máy chủ xử lý được kết nối mạng ổn định để dữ liệu hình ảnh có thể được truyền và xử lý gần thời gian thực.
- Ánh sáng trong bãi đỗ xe ổn định với độ rọi tối thiểu 30 lux.

---

# Assumptions

- Tài xế luôn luôn tuân thủ 100% và đỗ đúng vào vị trí hệ thống đã chỉ định.
- Mỗi ô đỗ chỉ có sức chứa đúng 1 xe ô tô.
- Các xe tiến vào tuần tự từng chiếc một, không có hiện tượng 2 xe vào cùng một phần nghìn giây dẫn đến tranh chấp một ô đỗ.
- Sơ đồ vật lý của bãi đỗ là tĩnh, không bị thay đổi trong quá trình hệ thống đang vận hành.
- Chỉ có 1 lối vào duy nhất.

---

# Scope

## 1. Phạm vi hệ thống (In-Scope)

### Nhận diện trạng thái

Dùng camera cố định, tự học baseline từ video bằng YOLO26 + ByteTrack, để cập nhật liên tục trạng thái ô đỗ trên mặt bằng 2D.

### Tìm đường & Giữ chỗ

Dùng thuật toán Dijkstra tìm đường đi ngắn nhất. Tự động khóa ô đỗ thành "Đang giữ chỗ" ngay khi xe quét thẻ vào cổng thành công.

### Giao diện chỉ đường

Hiển thị bản đồ 2D kèm tuyến đường và mũi tên điều hướng trực quan.

### Lưu trữ dữ liệu

Ghi nhận lịch sử đỗ xe và trạng thái hệ thống vào database để xuất báo cáo cơ bản.

## 2. Ngoài phạm vi (Out-of-Scope)

### Thanh toán & Thu phí

Không quản lý việc tính thời gian lưu bãi hay xử lý giao dịch.

### Đọc biển số (ALPR/ANPR)

Nhận diện phương tiện theo hình khối (Bounding Box) để quản lý không gian, không đọc/lưu thông tin biển số.

### An ninh & An toàn

Không cảnh báo va chạm, cháy nổ, hay giám sát các hành vi bất thường.

### Bãi xe nhiều tầng

Chỉ xử lý thuật toán và chỉ đường trên một mặt phẳng (1 tầng hầm duy nhất), không hỗ trợ định tuyến qua các đoạn dốc liên tầng.

---

# Decomposition Hierarchy / Breakdown Tree

Bài toán chính: **Smart Parking Slot Occupancy Detection & Shortest-Path Navigation**

- **Input**: Video-stream từ camera giám sát, bản đồ bãi đỗ xe (cấu hình JSON), vị trí hiện tại của xe
- **Output**: Trạng thái trống/có xe của từng ô đỗ, chỗ đỗ đề xuất, đường đi ngắn nhất, video/bản đồ 2D có chú thích trực quan

```
                        ┌─────────────────────────────────────────────┐
                        │     P0: Smart Parking Detection & Navigation │
                        │  In: Video stream, Parking map, User pos     │
                        │  Out: Annotated video, 2D map, Route         │
                        └──────────┬──────────────────────┬────────────┘
                                   │                      │
               ┌───────────────────┤                      ├───────────────────┐
               ▼                   ▼                      ▼                   ▼
 ┌──────────────────┐  ┌───────────────────┐  ┌───────────────────┐  ┌────────────────────┐
 │ SP1: Auto Learn  │  │ SP2: Hybrid       │  │ SP3: Shortest-    │  │ SP4: Visualization │
 │ + YOLO26 Tracking│  │ Occupancy         │  │ Path Navigation   │  │ & User Interface   │
 │                  │  │ Classification    │  │                   │  │                    │
 │ In: Video frame  │  │ In: Bounding      │  │ In: Slot statuses,│  │ In: Slot statuses, │
 │ Out: Bounding    │  │  boxes + Slot     │  │  Parking graph,   │  │  Route, Annotated  │
 │  boxes + conf    │  │  polygons         │  │  User position    │  │  frame             │
 │                  │  │ Out: Status mỗi   │  │ Out: Target slot, │  │ Out: Video stream  │
 │ → Baseline + det│  │  ô (+ unknown)     │  │  Route, Distance  │  │  + Bản đồ 2D + UI │
 └───────┬──────────┘  └────────┬──────────┘  └────────┬──────────┘  └──────┬─────────────┘
         │                      │                      │                    │
    ┌────┴────┐           ┌─────┴─────┐           ┌────┴────┐         ┌────┴─────┐
    ▼         ▼           ▼           ▼           ▼         ▼         ▼          ▼
┌────────┐┌────────┐ ┌────────┐ ┌─────────┐ ┌────────┐┌────────┐┌────────┐ ┌─────────┐
│SP1.1   ││SP1.2   │ │SP2.1   │ │SP2.2    │ │SP3.1   ││SP3.2   ││SP4.1   │ │SP4.2    │
│Auto    ││YOLO26 +│ │Hybrid  │ │Temporal │ │Graph   ││Dijkstra││Video   │ │2D Map   │
│Baseline││ByteTrack││Fusion  │ │Hysteresis││Modeling││Search  ││Annotate│ │Rendering│
│        ││(NMS,   │ │        │ │         │ │        ││        ││        │ │         │
│In: BGR ││filter) │ │In: BBs │ │In: Raw  │ │In: JSON││In:Graph││In:Frame││In: Slot │
│ frame  ││In: Raw │ │ + slot │ │ status  │ │ config ││+vacant ││+status ││ statuses│
│Out: Raw││ dets   │ │ polygons│ │ sequence│ │Out:    ││ slots  ││+route  ││ + route │
│ dets   ││Out:    │ │Out: Raw│ │Out:     │ │ Graph  ││Out:    ││Out:    ││Out: Map │
│        ││ clean  │ │ status │ │ stable  │ │ object ││ target,││ annot. ││ overlay │
│        ││ BBs    │ │ per ô  │ │ status  │ │        ││ path   ││ frame  ││         │
└────────┘└────────┘ └────────┘ └─────────┘ └────────┘└────────┘└────────┘ └─────────┘
```

### Giải pháp cho từng sub-problem (node lá)

| Sub-problem | Mô tả | Giải pháp |
|---|---|---|
| **SP1.1** – Video Auto-calibration | Gắn appearance rỗng cho từng ô | Quét video, loại frame overlap xe và lấy baseline theo polygon |
| **SP1.2** – Detection + Tracking | Thêm evidence phương tiện | YOLO26 + ByteTrack; có thể fine-tune từ bãi triển khai |
| **SP2.1** – Hybrid Occupancy | Xác định trạng thái an toàn | Background change theo polygon hợp nhất với bbox overlap; có trạng thái `unknown` |
| **SP2.2** – Temporal Hysteresis | Giảm nhấp nháy và false-vacant | Xác nhận `occupied` sau 2 frame, `vacant` sau 4 frame; `unknown` không được định tuyến |
| **SP3.1** – Graph Modeling | Mô hình hóa bãi đỗ xe dạng đồ thị | Đồ thị vô hướng có trọng số (JSON); node = ô đỗ / waypoint / entrance; edge = khoảng cách thực (mét) |
| **SP3.2** – Dijkstra Search | Tìm ô trống gần nhất theo đường đi | Thuật toán Dijkstra từ vị trí người dùng; tie-breaking theo thứ tự ID nhỏ nhất |
| **SP4.1** – Video Annotation | Chú thích trực quan lên video | OpenCV: polygon overlay (xanh/đỏ/vàng), bounding box phương tiện, text thông tin |
| **SP4.2** – 2D Map Rendering | Hiển thị sơ đồ bãi đỗ 2D | Flask-SocketIO real-time; bản đồ SVG/Canvas với trạng thái ô đỗ và tuyến đường |

---

# Evaluation (Metrics)

## 3.1. Tiêu chí đánh giá và dữ liệu đánh giá

| Yêu cầu (Requirement) | NFR liên quan | Tiêu chí đánh giá (Metric) | Kì vọng (Target) | Phương pháp kiểm thử |
|---|---|---|---|---|
| FR1: Phân loại trạng thái ô đỗ | NFR1 | F1-Score, Precision, Recall | $\ge 0.95$ | Kiểm thử trên tập Test Dataset (Confusion Matrix) |
| FR2: Đề xuất chỗ đỗ & Tìm đường | NFR2 | Routing Accuracy (% đường đi đúng) | 100% | So sánh kết quả của thuật toán với Ground truth (đường đi thủ công) |
| FR3: Cập nhật trạng thái realtime | NFR3 | System Latency (Độ trễ phản hồi) | $\le 3$ giây | Đo thời gian từ lúc xe vào ô đến lúc UI đổi màu |
| FR4: Xử lý video | NFR4 | FPS (Frames Per Second) | $\ge 15$ FPS | Chạy real-time inference và đo tốc độ khung hình |
| FR4: Giao diện đồng bộ | NFR5 | Sync Delay (Độ lệch đồng bộ) | $\le 2$ giây | So sánh mốc thời gian (timestamp) giữa Video và Bản đồ 2D |

### Dữ liệu đánh giá

> **Lưu ý**: Hệ thống tự học baseline từ video camera mới bằng YOLO26 + ByteTrack và giữ `unknown` cho ô không đủ evidence. Hiện tại **chưa có sẵn** bộ dữ liệu đánh giá riêng, nên chưa thể tuyên bố đạt target độ chính xác trước khi đo trên video thực tế.

| Dữ liệu cần thu thập | Dùng cho Metric | Phương án thu thập & chuẩn bị |
|---|---|---|
| **Video giám sát bãi đỗ xe** | M1, M3, M4 (F1-score, Latency, FPS) | Quay video thực tế từ camera overhead cố định tại bãi đỗ xe (độ phân giải ≥ 720p, thời lượng ≥ 10 phút). Thu thập ở nhiều thời điểm khác nhau (đông xe / vắng xe) để đảm bảo đa dạng trạng thái. |
| **Ground Truth – Nhãn trạng thái ô đỗ** | M1 (F1-score) | Trích xuất frame từ video theo mỗi 5–10 giây. Nhóm gán nhãn thủ công (manual annotation) trạng thái từng ô đỗ (occupied / vacant) cho mỗi frame. Lưu vào file JSON với format: `{image_path, labels: {slot_id: status}}`. Mục tiêu: ≥ 200 frame có nhãn. |
| **Kịch bản kiểm thử tìm đường (Navigation Scenarios)** | M2 (Routing Accuracy) | Xây dựng thủ công ≥ 30 kịch bản, mỗi kịch bản gồm: (1) vị trí xuất phát, (2) danh sách ô đang trống, (3) ô đỗ kỳ vọng (tính bằng tay trên đồ thị). Đảm bảo có các trường hợp: 1 ô trống, nhiều ô trống, ô trống cùng khoảng cách (tie-breaking). |
| **Dữ liệu đo thời gian phản hồi** | M3, M4 (Latency, FPS) | Sử dụng video đã thu thập ở trên. Chạy pipeline trên phần cứng chuẩn (GPU server), đo tự động bằng script `evaluate.py`: thời gian xử lý mỗi frame (M3) và tốc độ khung hình trung bình (M4). |
| **Dữ liệu đo độ đồng bộ** | M5 (Sync Delay) | Ghi timestamp khi pipeline xuất kết quả (video annotated) và khi giao diện 2D map cập nhật. So sánh chênh lệch timestamp giữa hai kênh hiển thị trên ≥ 50 lần cập nhật liên tiếp. |

## 3.2. Ánh xạ Tiêu chí đánh giá ↔ Yêu cầu bài toán

| Tiêu chí đánh giá (Metric) | Yêu cầu chức năng (FR) | Yêu cầu phi chức năng (NFR) | Ý nghĩa |
|---|---|---|---|
| **F1-Score** (Precision, Recall) | FR1 – Slot Occupancy Classification | NFR1 – Classification Accuracy ≥ 0.95 | Đảm bảo hệ thống nhận diện chính xác trạng thái ô đỗ, giảm thiểu false positive (báo có xe khi trống) và false negative (báo trống khi có xe). |
| **Routing Accuracy** | FR2 – Optimal Slot Recommendation | NFR2 – Path Accuracy = 100% | Đảm bảo đường đi được đề xuất luôn là đường ngắn nhất; thuật toán Dijkstra đảm bảo tính tối ưu tuyệt đối trên đồ thị có trọng số dương. |
| **System Latency** | FR3 – Real-time Status Update | NFR3 – Response Time ≤ 3s | Đo thời gian phản hồi từ khi xe chiếm ô đến khi giao diện cập nhật, đảm bảo trải nghiệm người dùng mượt mà. |
| **FPS** (Frames Per Second) | FR4 – Visualization | NFR4 – Real-time ≥ 15 FPS | Đảm bảo video giám sát được xử lý và hiển thị liên tục, không bị giật lag. |
| **Sync Delay** | FR4 – Visualization | NFR5 – Sync ≤ 2s | Đảm bảo bản đồ 2D và video giám sát được cập nhật đồng bộ, tránh gây nhầm lẫn cho người dùng. |

---

# Solution

## Thuật toán tổng thể (End-to-End Pipeline)

Thuật toán xử lý theo pipeline tuần tự cho mỗi frame video, tương ứng với các sub-problem đã phân rã:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        INPUT: Video Frame (BGR)                        │
│                      + Parking Config (JSON)                           │
│                      + User Position (click / entrance)                │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │  Bước 1: AUTO LEARN + TRACK  │  ← SP1.1 + SP1.2
                    │  scan video + YOLO26 tracks  │
                    │  → Reference crop + vehicle  │
                    │    bounding boxes            │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │  Bước 2: SLOT OCCUPANCY      │  ← SP2.1
                    │  CLASSIFICATION              │
                    │  Với mỗi ô đỗ (polygon):     │
                    │   background change score   │
                    │   + detector overlap        │
                    │  → OCCUPIED / VACANT /      │
                    │    UNKNOWN (fail-safe)      │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │  Bước 3: TEMPORAL HYSTERESIS │  ← SP2.2
                    │  Occupied: 2 / vacant: 4     │
                    │  frame xác nhận liên tiếp    │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │  Bước 4: SHORTEST-PATH       │  ← SP3.1 + SP3.2
                    │  NAVIGATION                  │
                    │  Graph = load(parking_lot.json│)
                    │  vacant_list = filter(VACANT) │
                    │  Dijkstra(user_pos → all nodes│)
                    │  target = argmin(dist[vacant])│
                    │  path = reconstruct(prev)     │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │  Bước 5: VISUALIZATION       │  ← SP4.1 + SP4.2
                    │  • Polygon overlay trên video │
                    │    (Xanh=trống, Đỏ=có xe,    │
                    │     Vàng=đề xuất)             │
                    │  • Bounding box phương tiện   │
                    │  • Bản đồ 2D real-time (WS)  │
                    │  • Thông tin route + distance  │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │  OUTPUT:                      │
                    │  • Annotated video frame      │
                    │  • Slot statuses (JSON)       │
                    │  • Target slot + route        │
                    │  • 2D parking map (WebSocket) │
                    │  • Processing time (ms)       │
                    └──────────────────────────────┘
```

### Mô tả chi tiết

1. **Video Auto-calibration & Tracking (SP1)**: Hệ thống quét video, dùng YOLO26 + ByteTrack để loại frame có xe khỏi mẫu nền của từng polygon. Weights có thể được fine-tune theo bãi triển khai.

2. **Slot Occupancy Classification (SP2)**: Hệ thống đo background change trong polygon và hợp nhất với bbox overlap nếu có. Evidence mơ hồ hoặc ô chưa hiệu chỉnh được gắn `unknown`; hysteresis xác nhận ô trống thận trọng hơn ô đã có xe.

3. **Shortest-Path Navigation (SP3)**: Bãi đỗ xe được mô hình hóa thành đồ thị vô hướng có trọng số, trong đó node là các ô đỗ, waypoint, và entrance; edge là khoảng cách đi bộ/lái xe (mét). Thuật toán Dijkstra chạy từ vị trí người dùng, tìm ô trống gần nhất. Khi nhiều ô có cùng khoảng cách → tie-break bằng ID nhỏ nhất (đảm bảo deterministic).

4. **Visualization & UI (SP4)**: Video chú thích bằng OpenCV (polygon overlay, bounding box, text). Giao diện web Flask với SocketIO để cập nhật real-time bản đồ 2D. Người dùng có thể click trực tiếp trên video để đặt vị trí → hệ thống tự động tạo temporary node trên đồ thị, tính đường đi, rồi xóa node tạm.

---

# Ethical & Social Issues

## 1. Quyền riêng tư (Privacy)

- **Giám sát hình ảnh**: Hệ thống sử dụng camera giám sát liên tục, có khả năng ghi lại hình ảnh phương tiện và gián tiếp nhận diện người dùng. Dù hệ thống **không** thực hiện nhận diện biển số (ALPR) hay nhận diện khuôn mặt, video giám sát vẫn có thể chứa thông tin nhạy cảm.
- **Biện pháp giảm thiểu**: Chỉ xử lý video trên server nội bộ (on-premise), không truyền ra ngoài. Không lưu trữ video gốc dài hạn, chỉ lưu trạng thái ô đỗ (metadata). Áp dụng chính sách xóa dữ liệu định kỳ.

## 2. Thiên lệch và công bằng (Bias & Fairness)

- **Thiên lệch mô hình**: Model YOLO26 pretrained trên COCO có thể có bias đối với một số loại phương tiện đặc thù (xe ba gác, xe tải nhỏ địa phương) không phổ biến trong tập huấn luyện, dẫn đến phát hiện sai hoặc bỏ sót.
- **Công bằng truy cập**: Hệ thống đề xuất ô đỗ gần nhất từ lối vào, có thể vô tình ưu tiên xe đến trước. Cần cân nhắc cơ chế phân bổ công bằng cho người khuyết tật hoặc các nhóm ưu tiên.

## 3. An toàn (Safety)

- **Rủi ro từ sai sót hệ thống**: Nếu hệ thống phân loại sai (false negative — báo ô trống khi thực tế đã có xe), có thể dẫn đến va chạm. Calibration, hysteresis và việc loại `unknown` khỏi đề xuất được thiết kế để giảm rủi ro này.
- **Phụ thuộc vào hạ tầng**: Khi camera hỏng hoặc mất kết nối mạng, hệ thống không thể cung cấp thông tin → cần có cơ chế fallback (hiển thị cảnh báo, chuyển sang chế độ thủ công).

## 4. Tác động xã hội (Social Impact)

- **Tích cực**: Giảm thời gian tìm chỗ đỗ, giảm ùn tắc nội bộ bãi xe, giảm khí thải CO₂ do xe không phải chạy vòng vòng, nâng cao trải nghiệm người dùng tại trung tâm thương mại.
- **Tiêu cực tiềm ẩn**: Tự động hóa quản lý bãi xe có thể thay thế nhân viên giữ xe truyền thống, ảnh hưởng đến việc làm. Sự phụ thuộc vào công nghệ có thể gây khó khăn cho người dùng lớn tuổi hoặc không quen với thiết bị điện tử.

## 5. Trách nhiệm và minh bạch (Accountability & Transparency)

- Cần minh bạch về cách hệ thống hoạt động: người dùng phải được thông báo rằng bãi xe có sử dụng camera AI.
- Khi xảy ra sự cố (ví dụ: đề xuất sai ô đỗ dẫn đến tranh chấp), cần có log hệ thống và cơ chế khiếu nại rõ ràng để quy trách nhiệm.
