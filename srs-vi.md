# HỆ THỐNG BÃI ĐỖ XE THÔNG MINH SỬ DỤNG CAMERA GIÁM SÁT VÀ ĐỊNH TUYẾN ĐƯỜNG ĐI NGẮN NHẤT

---

## 1. Giới thiệu bài toán

Tại các trung tâm thương mại hoặc bãi đỗ xe trong nhà, tài xế thường mất nhiều thời gian để tìm kiếm chỗ đỗ còn trống. Việc phải di chuyển vòng quanh bãi xe nhiều lần không chỉ gây bất tiện cho người dùng mà còn làm tăng ùn tắc nội bộ, tiêu tốn nhiên liệu và ảnh hưởng đến trải nghiệm tổng thể khi sử dụng bãi đỗ.

Để giải quyết vấn đề này, nhóm xây dựng một hệ thống bãi đỗ xe thông minh có khả năng nhận diện trạng thái của từng ô đỗ thông qua camera giám sát, sau đó đề xuất ô đỗ còn trống gần nhất và hiển thị tuyến đường ngắn nhất từ vị trí hiện tại của xe đến ô đỗ được đề xuất.

Hệ thống tập trung vào hai nhiệm vụ chính:
Thứ nhất, hiệu chỉnh theo camera thực tế và phân loại trạng thái từng ô đỗ là trống, đã có xe hoặc chưa đủ tin cậy.
Thứ hai, mô hình hóa bãi đỗ xe thành đồ thị để tìm đường đi ngắn nhất đến ô đỗ phù hợp.

---

## 2. Định nghĩa chi tiết bài toán

### 2.1. Mục tiêu bài toán

Mục tiêu của bài toán là xây dựng một hệ thống có thể:

* Nhận dữ liệu video từ camera giám sát cố định.
* Phát hiện phương tiện xuất hiện trong khu vực bãi đỗ.
* Xác định trạng thái của từng ô đỗ xe theo thời gian thực.
* Tìm ô đỗ còn trống phù hợp nhất dựa trên khoảng cách đường đi.
* Hiển thị trực quan video đã chú thích, bản đồ bãi xe 2D, ô đỗ được đề xuất và tuyến đường ngắn nhất.

---

## 2.2. Input

Hệ thống nhận các đầu vào sau:

| Nhóm input                      | Mô tả                                                                                                                                             |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Video stream từ camera giám sát | Luồng video thời gian thực ghi lại khu vực bãi đỗ xe. Camera được đặt cố định, có góc nhìn bao quát các ô đỗ cần giám sát.                        |
| Bản đồ bãi đỗ xe                | Dữ liệu mô tả mặt bằng bãi đỗ, bao gồm danh sách ô đỗ, tọa độ polygon của từng ô, các waypoint, lối vào và các cạnh đường đi.                     |
| Vị trí hiện tại của xe          | Vị trí bắt đầu để tính đường đi. Trong phạm vi bài toán, vị trí này có thể là lối vào hoặc vị trí xe đang được xác định trên bản đồ 2D.           |
| Tín hiệu kích hoạt hệ thống     | Sự kiện cho biết có xe cần được hướng dẫn, ví dụ xe đi vào cổng, quét thẻ thành công hoặc người dùng yêu cầu tìm chỗ đỗ.                          |
| Tham số cấu hình                | Các ngưỡng xử lý như ngưỡng confidence của mô hình phát hiện, ngưỡng xác định ô bị chiếm, tốc độ cập nhật, thông tin màu hiển thị trên giao diện. |

---

## 2.3. Output

Hệ thống tạo ra các đầu ra sau:

| Nhóm output              | Mô tả                                                                                            |
| ------------------------ | ------------------------------------------------------------------------------------------------ |
| Video đã chú thích       | Video camera được hiển thị kèm bounding box phương tiện, trạng thái ô đỗ và thông tin trực quan. |
| Bounding box phương tiện | Vị trí phương tiện được phát hiện trong ảnh, kèm độ tin cậy của mô hình.                         |
| Trạng thái từng ô đỗ     | Mỗi ô đỗ được phân loại là trống, đã có xe, không chắc chắn hoặc đang được đề xuất.               |
| Bản đồ bãi xe 2D         | Sơ đồ mặt bằng được cập nhật theo thời gian thực, hiển thị trạng thái các ô đỗ.                  |
| Ô đỗ được đề xuất        | Mã ô đỗ phù hợp nhất cho tài xế, ví dụ E12.3.                                                    |
| Tuyến đường ngắn nhất    | Danh sách các điểm đường đi từ vị trí hiện tại đến ô đỗ được đề xuất.                            |
| Thông tin khoảng cách    | Tổng chiều dài tuyến đường hoặc chi phí đường đi trên đồ thị.                                    |

Quy ước màu hiển thị:

| Màu        | Ý nghĩa                            |
| ---------- | ---------------------------------- |
| Xanh lá    | Ô đỗ còn trống                     |
| Đỏ         | Ô đỗ đã có xe                      |
| Vàng       | Ô đỗ được hệ thống đề xuất         |
| Xanh dương | Tuyến đường ngắn nhất được đề xuất |

---

## 2.4. Requirements

### 2.4.1. Functional Requirements

| Mã yêu cầu | Tên yêu cầu                        | Mô tả                                                                                                                  |
| ---------- | ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| FR1        | Phân loại trạng thái ô đỗ          | Sau hiệu chỉnh ảnh nền rỗng, hệ thống phải xác định trạng thái `vacant`, `occupied` hoặc `unknown` của từng ô đỗ từ video camera giám sát. |
| FR2        | Đề xuất ô đỗ tối ưu                | Hệ thống chỉ được chọn các ô đã được xác nhận `vacant`, sau đó chọn ô phù hợp nhất dựa trên khoảng cách đường đi ngắn nhất. |
| FR3        | Cập nhật trạng thái thời gian thực | Hệ thống phải tự động cập nhật trạng thái ô đỗ khi xe đi vào hoặc rời khỏi ô đỗ.                                       |
| FR4        | Hiển thị trực quan                 | Hệ thống phải cung cấp giao diện hiển thị video chú thích, bản đồ 2D, trạng thái ô đỗ và tuyến đường được đề xuất.     |
| FR5        | Lưu cấu hình hiệu chỉnh            | Hệ thống phải lưu ảnh tham chiếu rỗng và cấu hình inference để dùng lại khi khởi động ứng dụng.                       |

---

### 2.4.2. Non-functional Requirements

| Mã yêu cầu | Tên yêu cầu             | Mô tả                                                                                                                         |
| ---------- | ----------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| NFR1       | Độ chính xác phân loại  | F1-score của bài toán phân loại trạng thái ô đỗ phải đạt tối thiểu 0.95 trên tập dữ liệu đánh giá.                            |
| NFR2       | Độ chính xác định tuyến | Tuyến đường được đề xuất phải đúng với đường đi ngắn nhất trên đồ thị đã cấu hình.                                            |
| NFR3       | Thời gian phản hồi      | Trạng thái ô đỗ phải được cập nhật với độ trễ trung bình không vượt quá 3 giây kể từ khi xe chiếm ít nhất 50% diện tích ô đỗ. |
| NFR4       | Hiệu năng xử lý video   | Hệ thống phải xử lý video với tốc độ tối thiểu 15 FPS trong điều kiện phần cứng thử nghiệm.                                   |
| NFR5       | Tính đồng bộ hiển thị   | Video chú thích và bản đồ 2D phải được cập nhật đồng bộ, với độ lệch hiển thị không vượt quá 2 giây.                          |
| NFR6       | Tính ổn định            | Hệ thống không được thay đổi trạng thái ô đỗ liên tục do nhiễu trong một khoảng thời gian ngắn.                               |

---

## 2.5. Constraints

Các ràng buộc kỹ thuật của hệ thống:

| Nhóm ràng buộc     | Nội dung                                                                                          |
| ------------------ | ------------------------------------------------------------------------------------------------- |
| Camera             | Hệ thống sử dụng 1 camera cố định, gắn ở độ cao tối thiểu 3m, hướng xuống khu vực đỗ xe.          |
| Độ phân giải       | Camera có độ phân giải tối thiểu 720p, khuyến nghị 1080p để tăng khả năng phát hiện phương tiện.  |
| Góc nhìn           | Camera phải bao quát đầy đủ các ô đỗ thuộc phạm vi giám sát, hạn chế điểm mù.                     |
| Che khuất          | Phương tiện không được bị che khuất nghiêm trọng bởi cột, tường, xe khác hoặc vật cản lớn.        |
| Ánh sáng           | Môi trường bãi đỗ có ánh sáng tương đối ổn định, độ rọi tối thiểu khoảng 30 lux.                  |
| Kết nối            | Camera và máy chủ xử lý phải có kết nối mạng ổn định để truyền và xử lý video gần thời gian thực. |
| Bản đồ             | Sơ đồ bãi đỗ phải được cấu hình trước, bao gồm tọa độ ô đỗ và đồ thị đường đi.                    |
| Hiệu chỉnh         | Hệ thống tự quét video để học appearance rỗng của ô ở các thời điểm detector không thấy xe; ô chưa từng quan sát đủ rõ được xem là `unknown`. |
| Phạm vi định tuyến | Hệ thống chỉ định tuyến trên một tầng bãi đỗ, không xử lý định tuyến giữa nhiều tầng.             |

---

## 2.6. Assumptions

Các giả định được sử dụng trong phạm vi bài toán:

| Giả định | Nội dung                                                                                                                               |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| A1       | Mỗi ô đỗ chỉ chứa tối đa một xe ô tô.                                                                                                  |
| A2       | Tài xế tuân thủ chỉ dẫn của hệ thống và đỗ đúng vào ô được đề xuất.                                                                    |
| A3       | Sơ đồ vật lý của bãi đỗ không thay đổi trong quá trình hệ thống vận hành.                                                              |
| A4       | Bãi xe chỉ có một lối vào chính trong phạm vi bài toán.                                                                                |
| A5       | Các phương tiện đi vào theo thứ tự đủ phân biệt, không xảy ra nhiều xe đồng thời tranh chấp cùng một ô trong cùng một thời điểm xử lý. |
| A6       | Camera không bị thay đổi vị trí, góc quay hoặc tiêu cự sau khi hệ thống đã được cấu hình.                                              |
| A7       | Các ô đỗ đã được định nghĩa chính xác bằng polygon trong bản đồ cấu hình.                                                              |

---

## 2.7. Scope

### 2.7.1. In-scope

Các chức năng thuộc phạm vi hệ thống:

| Chức năng                 | Mô tả                                                                                |
| ------------------------- | ------------------------------------------------------------------------------------ |
| Nhận diện trạng thái ô đỗ | So sánh từng ô với ảnh tham chiếu rỗng, kết hợp detection tùy chọn và trả về cả trạng thái không chắc chắn. |
| Đề xuất ô đỗ              | Chọn ô đỗ còn trống có khoảng cách đường đi ngắn nhất từ vị trí hiện tại.            |
| Tìm đường trong bãi xe    | Sử dụng đồ thị trọng số và thuật toán tìm đường ngắn nhất để tạo tuyến đường.        |
| Giao diện trực quan       | Hiển thị video đã chú thích, bản đồ 2D, trạng thái ô đỗ và tuyến đường.              |
| Cập nhật thời gian thực   | Cập nhật trạng thái ô đỗ và giao diện khi có thay đổi.                               |
| Lưu dữ liệu cơ bản        | Lưu cấu hình polygon, đồ thị và ảnh tham chiếu rỗng phục vụ inference sau khi khởi động lại. |

---

### 2.7.2. Out-of-scope

Các chức năng không thuộc phạm vi hệ thống:

| Chức năng ngoài phạm vi    | Mô tả                                                                            |
| -------------------------- | -------------------------------------------------------------------------------- |
| Thanh toán và thu phí      | Không xử lý tính tiền gửi xe, hóa đơn hoặc giao dịch thanh toán.                 |
| Nhận diện biển số          | Không thực hiện ALPR/ANPR, không đọc hoặc lưu biển số xe.                        |
| Nhận diện khuôn mặt        | Không nhận diện danh tính người dùng hoặc người lái xe.                          |
| Giám sát an ninh           | Không phát hiện va chạm, cháy nổ, trộm cắp hoặc hành vi bất thường.              |
| Bãi xe nhiều tầng          | Không hỗ trợ định tuyến qua ram dốc hoặc giữa nhiều tầng.                        |
| Điều khiển thiết bị vật lý | Không điều khiển barrier, đèn tín hiệu vật lý hoặc hệ thống khóa chỗ đỗ tự động. |

---

# 3. Decomposition Hierarchy / Breakdown Tree

## 3.1. Mô tả tổng quan

Bài toán chính được phân rã thành bốn nhóm bài toán con:

1. Phát hiện phương tiện từ video camera.
2. Xác định trạng thái từng ô đỗ.
3. Đề xuất ô đỗ và tuyến đường ngắn nhất.
4. Hiển thị kết quả trên video và bản đồ 2D.

Mỗi bài toán con có input, output rõ ràng và được giải quyết bằng một khối xử lý riêng trong pipeline tổng thể.

---

## 3.2. Nội dung hình Decomposition Tree

**Tên hình:** Hình 1. Cây phân rã bài toán Smart Parking Detection & Navigation

**Gợi ý thiết kế hình:**
Nên vẽ dưới dạng cây phân cấp ngang, dùng các khối bo góc, màu nền nhẹ. Node gốc đặt ở trên cùng. Bốn nhóm bài toán con đặt ở hàng thứ hai. Các node lá đặt ở hàng thứ ba.

---

### Node gốc

**P0 – Smart Parking Detection & Navigation**

**Input:**
Video stream từ camera, bản đồ bãi đỗ, vị trí hiện tại của xe, tín hiệu kích hoạt.

**Output:**
Trạng thái từng ô đỗ, ô đỗ được đề xuất, tuyến đường ngắn nhất, video chú thích, bản đồ 2D cập nhật.

---

### Nhánh 1: Vehicle Detection

**SP1 – Phát hiện và theo dõi phương tiện**

**Input:**
Frame video từ camera giám sát.

**Output:**
Danh sách bounding box phương tiện, loại phương tiện và độ tin cậy phát hiện.

Node lá:

| Node  | Tên node               | Input                   | Output                                                          | Giải pháp                                 |
| ----- | ---------------------- | ----------------------- | --------------------------------------------------------------- | ----------------------------------------- |
| SP1.1 | Chuẩn bị frame đầu vào | Frame video gốc         | Frame đã được resize, chuẩn hóa màu và sẵn sàng đưa vào mô hình | OpenCV preprocessing                      |
| SP1.2 | Phát hiện phương tiện  | Frame đã chuẩn hóa      | Bounding box, class, confidence của phương tiện                 | YOLO26 pretrained hoặc weights fine-tune tại bãi xe |
| SP1.3 | Theo dõi qua video     | Danh sách detection     | Detection liên tục hơn qua các frame                            | ByteTrack để giảm bỏ sót ngắn hạn |

---

### Nhánh 2: Slot Occupancy Classification

**SP2 – Phân loại trạng thái ô đỗ**

**Input:**
Frame video, ảnh tham chiếu rỗng theo polygon và bounding box phương tiện nếu detector được bật.

**Output:**
Trạng thái của từng ô đỗ: `vacant`, `occupied` hoặc `unknown`.

Node lá:

| Node  | Tên node                  | Input                                  | Output                              | Giải pháp                                              |
| ----- | ------------------------- | -------------------------------------- | ----------------------------------- | ------------------------------------------------------ |
| SP2.1 | Tự hiệu chỉnh ảnh nền     | Toàn bộ video, polygon, track xe       | Baseline appearance cho từng ô      | Chọn mẫu không overlap xe; lấy median nhiều mẫu        |
| SP2.2 | Ước lượng occupancy       | Frame hiện tại, baseline, detection    | Score và trạng thái thô             | Background change hợp nhất với overlap detector       |
| SP2.3 | Làm ổn định trạng thái    | Chuỗi trạng thái theo thời gian        | Trạng thái an toàn, giảm nhấp nháy  | Hysteresis; xác nhận `vacant` chậm hơn `occupied`      |
| SP2.4 | Xử lý không chắc chắn     | Ô thiếu baseline hoặc evidence mơ hồ   | Trạng thái `unknown`                | Không đưa ô `unknown` vào danh sách đề xuất            |

---

### Nhánh 3: Parking Recommendation & Routing

**SP3 – Đề xuất ô đỗ và tìm đường ngắn nhất**

**Input:**
Trạng thái các ô đỗ, bản đồ đồ thị bãi xe, vị trí hiện tại của xe.

**Output:**
Ô đỗ được đề xuất, tuyến đường ngắn nhất và tổng khoảng cách.

Node lá:

| Node  | Tên node                        | Input                                      | Output                                 | Giải pháp                                                           |
| ----- | ------------------------------- | ------------------------------------------ | -------------------------------------- | ------------------------------------------------------------------- |
| SP3.1 | Mô hình hóa bãi xe thành đồ thị | Bản đồ bãi đỗ, waypoint, entrance, ô đỗ    | Đồ thị có trọng số                     | Graph modeling                                                      |
| SP3.2 | Lọc danh sách ô trống           | Trạng thái từng ô đỗ                       | Danh sách ô đỗ có thể đề xuất          | Lọc các slot có trạng thái vacant                                   |
| SP3.3 | Tìm đường đến các ô trống       | Đồ thị, vị trí hiện tại, danh sách ô trống | Khoảng cách ngắn nhất đến từng ô trống | Dijkstra trên đồ thị trọng số dương                                 |
| SP3.4 | Chọn ô đỗ tối ưu                | Khoảng cách đến các ô trống                | Ô đỗ tốt nhất và tuyến đường tương ứng | Chọn ô có khoảng cách nhỏ nhất; nếu bằng nhau, chọn theo ID ưu tiên |

---

### Nhánh 4: Visualization & User Interface

**SP4 – Hiển thị và giao diện người dùng**

**Input:**
Frame video, bounding box, trạng thái ô đỗ, ô đỗ đề xuất và tuyến đường.

**Output:**
Video chú thích, bản đồ 2D cập nhật, thông tin chỉ đường cho người dùng.

Node lá:

| Node  | Tên node                     | Input                                 | Output                              | Giải pháp                                          |
| ----- | ---------------------------- | ------------------------------------- | ----------------------------------- | -------------------------------------------------- |
| SP4.1 | Chú thích video              | Frame, bounding box, trạng thái ô đỗ  | Video frame đã vẽ overlay           | OpenCV annotation                                  |
| SP4.2 | Render bản đồ 2D             | Bản đồ bãi xe, trạng thái slot, route | Sơ đồ 2D trực quan                  | SVG hoặc Canvas rendering                          |
| SP4.3 | Đồng bộ dữ liệu hiển thị     | Kết quả xử lý video và dữ liệu bản đồ | Video và map cập nhật gần đồng thời | WebSocket hoặc SocketIO                            |
| SP4.4 | Hiển thị thông tin hướng dẫn | Ô đề xuất, route, khoảng cách         | Giao diện chỉ đường cho tài xế      | UI panel hiển thị slot ID, khoảng cách và hướng đi |

---

# 4. Evaluation

## 4.1. Mục tiêu đánh giá

Phần đánh giá nhằm chứng minh rằng hệ thống có thể đáp ứng các yêu cầu đã đặt ra trong định nghĩa bài toán. Việc đánh giá tập trung vào năm khía cạnh chính:

1. Độ chính xác phân loại trạng thái ô đỗ.
2. Độ đúng của tuyến đường và ô đỗ được đề xuất.
3. Độ trễ cập nhật trạng thái.
4. Hiệu năng xử lý video thời gian thực.
5. Độ đồng bộ giữa video chú thích và bản đồ 2D.

---

## 4.2. Bảng tiêu chí đánh giá

| Mã metric | Tiêu chí đánh giá                  | Công thức / cách đo                                                                                        | Target   | Liên quan |
| --------- | ---------------------------------- | ---------------------------------------------------------------------------------------------------------- | -------- | --------- |
| M1        | F1-score phân loại trạng thái ô đỗ | Đánh giá dựa trên Precision và Recall giữa trạng thái dự đoán và nhãn thực tế                              | ≥ 0.95   | FR1, NFR1 |
| M2        | Precision                          | Tỷ lệ ô được dự đoán có xe mà thực tế đúng là có xe                                                        | ≥ 0.95   | FR1, NFR1 |
| M3        | Recall                             | Tỷ lệ ô thực tế có xe được hệ thống phát hiện đúng                                                         | ≥ 0.95   | FR1, NFR1 |
| M4        | Routing Accuracy                   | Tỷ lệ kịch bản mà hệ thống chọn đúng ô đỗ và đúng tuyến đường ngắn nhất                                    | 100%     | FR2, NFR2 |
| M5        | Response Latency                   | Thời gian từ khi xe chiếm tối thiểu 50% diện tích ô đỗ đến khi hệ thống cập nhật trạng thái trên giao diện | ≤ 3 giây | FR3, NFR3 |
| M6        | FPS                                | Số frame xử lý được trung bình mỗi giây                                                                    | ≥ 15 FPS | FR4, NFR4 |
| M7        | Sync Delay                         | Độ lệch thời gian giữa cập nhật trên video chú thích và bản đồ 2D                                          | ≤ 2 giây | FR4, NFR5 |
| M8        | Stability Rate                     | Tỷ lệ trạng thái ô đỗ không bị thay đổi sai do nhiễu trong khoảng thời gian ngắn                           | ≥ 95%    | NFR6      |
| M9        | Classification Coverage            | Tỷ lệ dự đoán không rơi vào trạng thái `unknown` trên tập đánh giá                                          | ≥ 95%    | FR1, NFR1 |

---

## 4.3. Dữ liệu đánh giá

Vì hệ thống sử dụng camera tại một bãi đỗ cụ thể nên dữ liệu đánh giá cần phản ánh đúng điều kiện triển khai thực tế. Nếu không có sẵn bộ dữ liệu phù hợp, nhóm sẽ tự thu thập và gán nhãn dữ liệu.

| Loại dữ liệu           | Dùng cho metric        | Phương án thu thập và chuẩn bị                                                                                                                                                                                |
| ---------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Video giám sát bãi đỗ  | M1, M2, M3, M5, M6, M8 | Video camera cố định bất kỳ sau khi cấu hình polygon; dữ liệu nên có thời điểm từng ô rỗng để auto-learn và các tình huống: bãi đông, xe đi vào, xe rời đi, che khuất, thay đổi ánh sáng. |
| Nhãn trạng thái ô đỗ   | M1, M2, M3             | Trích frame từ video theo chu kỳ 5-10 giây, sau đó gán nhãn thủ công trạng thái từng ô là vacant hoặc occupied.                                                                                               |
| Kịch bản định tuyến    | M4                     | Tạo ít nhất 30 kịch bản gồm vị trí bắt đầu, danh sách ô trống và kết quả đường đi đúng được tính thủ công trên đồ thị.                                                                                        |
| Log thời gian xử lý    | M5, M6, M7             | Ghi lại timestamp tại các bước: nhận frame, xử lý xong detection, cập nhật trạng thái, hiển thị video và cập nhật bản đồ 2D.                                                                                  |
| Cấu hình bản đồ bãi xe | M4, M7                 | Sử dụng file bản đồ đã định nghĩa gồm danh sách node, edge, trọng số đường đi và vị trí các ô đỗ.                                                                                                             |

---

## 4.4. Bảng ánh xạ metric với yêu cầu bài toán

| Metric           | Functional Requirement | Non-functional Requirement | Ý nghĩa đánh giá                                                                                              |
| ---------------- | ---------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------- |
| F1-score         | FR1                    | NFR1                       | Đánh giá tổng hợp độ chính xác của việc phân loại trạng thái ô đỗ, cân bằng giữa phát hiện sai và bỏ sót.     |
| Precision        | FR1                    | NFR1                       | Đảm bảo hệ thống hạn chế báo nhầm ô có xe khi thực tế ô còn trống.                                            |
| Recall           | FR1                    | NFR1                       | Đảm bảo hệ thống hạn chế báo nhầm ô trống khi thực tế đã có xe, tránh rủi ro tài xế đi đến ô không còn trống. |
| Routing Accuracy | FR2                    | NFR2                       | Chứng minh hệ thống chọn đúng ô đỗ và tuyến đường ngắn nhất theo đồ thị cấu hình.                             |
| Response Latency | FR3                    | NFR3                       | Đảm bảo trạng thái ô đỗ được cập nhật đủ nhanh để phục vụ điều hướng thời gian thực.                          |
| FPS              | FR4                    | NFR4                       | Đảm bảo video được xử lý mượt, không gây giật lag nghiêm trọng trên giao diện.                                |
| Sync Delay       | FR4                    | NFR5                       | Đảm bảo video chú thích và bản đồ 2D không hiển thị lệch trạng thái quá lâu.                                  |
| Stability Rate   | FR1, FR3               | NFR6                       | Đảm bảo trạng thái ô đỗ không bị nhấp nháy liên tục do nhiễu hình ảnh hoặc detection không ổn định.           |
| Coverage         | FR1                    | NFR1                       | Tránh đạt F1 cao bằng cách trả về `unknown` quá nhiều thay vì phân loại được ô đỗ.                            |

---

## 4.5. Kế hoạch kiểm thử

| Nhóm kiểm thử              | Mục tiêu                                             | Cách thực hiện                                                                                       |
| -------------------------- | ---------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Kiểm thử phân loại ô đỗ    | Đánh giá khả năng xác định vacant / occupied         | Hiệu chỉnh bằng frame rỗng tách biệt, sau đó so sánh dự đoán với nhãn thủ công; báo cáo thêm tỷ lệ `unknown`. |
| Kiểm thử định tuyến        | Đánh giá tính đúng của ô đỗ và đường đi được đề xuất | So sánh kết quả Dijkstra của hệ thống với kết quả ground truth tính thủ công.                        |
| Kiểm thử thời gian thực    | Đánh giá độ trễ và FPS                               | Chạy hệ thống trên video thực tế và ghi log thời gian xử lý.                                         |
| Kiểm thử đồng bộ giao diện | Đánh giá độ lệch giữa video và map                   | So sánh timestamp của cập nhật video với timestamp cập nhật bản đồ 2D.                               |
| Kiểm thử độ ổn định        | Đánh giá khả năng chống nhấp nháy trạng thái         | Quan sát chuỗi trạng thái theo thời gian và tính tỷ lệ trạng thái thay đổi sai trong thời gian ngắn. |

---

# 5. Solution

## 5.1. Ý tưởng giải pháp tổng thể

Giải pháp tổng thể được xây dựng cho video camera cố định bất kỳ sau khi người dùng định nghĩa polygon ô đỗ. Khi tải video, hệ thống dùng YOLO26 + ByteTrack để quét các frame, tự thu mẫu appearance của từng ô tại thời điểm không quan sát thấy xe và tạo baseline. Mỗi frame vận hành được so sánh với baseline, hợp nhất detection, làm ổn định trạng thái theo thời gian, rồi chỉ định tuyến tới ô đã xác nhận `vacant`.

Các khối trong pipeline tương ứng trực tiếp với các sub-problem trong Decomposition Tree. Điều này giúp đảm bảo rằng bài toán chính được giải quyết thông qua việc kết hợp các lời giải cho từng bài toán con.

---

## 5.2. Nội dung hình Solution Pipeline

**Tên hình:** Hình 2. Pipeline giải pháp tổng thể của hệ thống bãi đỗ xe thông minh

**Gợi ý thiết kế hình:**
Nên vẽ theo dạng flow ngang từ trái sang phải, gồm các khối xử lý chính. Mỗi khối có icon nhỏ minh họa, ví dụ camera, AI detection, slot status, graph routing, UI display. Không nên dùng quá nhiều chữ trong hình. Phần mô tả chi tiết để ở bên dưới hình.

---

### Các khối trong hình Solution Pipeline

| Thứ tự | Khối xử lý                    | Input                                   | Output                                     | Vai trò                                                             |
| ------ | ----------------------------- | --------------------------------------- | ------------------------------------------ | ------------------------------------------------------------------- |
| 1      | Camera Input                  | Video stream từ camera                  | Frame video theo thời gian thực            | Cung cấp dữ liệu hình ảnh đầu vào cho hệ thống.                     |
| 2      | Video Auto-calibration        | Video, polygon và vehicle tracks        | Appearance baseline theo từng ô            | Tự học từ video mới, không yêu cầu toàn bãi trống cùng lúc.          |
| 3      | Hybrid Occupancy Estimation   | Frame, baseline, detection/tracking     | `occupied` / `vacant` / `unknown`          | Phát hiện thay đổi trong ô và hợp nhất evidence từ mô hình.          |
| 4      | Temporal Hysteresis           | Chuỗi trạng thái ô đỗ qua nhiều frame   | Trạng thái an toàn, ổn định                | Xác nhận ô trống thận trọng hơn ô đã có xe.                          |
| 5      | Parking Graph Model           | Bản đồ bãi xe, waypoint, entrance, ô đỗ | Đồ thị trọng số của bãi xe                 | Mô hình hóa các đường đi hợp lệ trong bãi xe.                       |
| 6      | Slot Recommendation & Routing | Đồ thị, vị trí xe, danh sách ô trống    | Ô đỗ đề xuất và tuyến đường ngắn nhất      | Chọn ô đỗ phù hợp nhất và tạo route hướng dẫn.                      |
| 7      | Visualization & UI            | Frame, trạng thái slot, route           | Video chú thích và bản đồ 2D               | Hiển thị kết quả trực quan cho người dùng.                          |
| 8      | Calibration Persistence       | Frame tham chiếu và cấu hình            | File reference và inference config         | Giữ calibration khi ứng dụng khởi động lại.                          |

---

## 5.3. Mô tả chi tiết giải pháp

### 5.3.1. Auto-calibration và Vehicle Tracking

Vì camera cố định, nguồn evidence chính là sự thay đổi appearance trong từng polygon so với appearance rỗng của chính ô đó. Ứng dụng tự quét các frame trong video và dùng detection/tracking để loại các frame đang có xe khỏi tập mẫu baseline. Thao tác **Calibrate** thủ công vẫn tồn tại để bổ sung cho ô không từng xuất hiện rỗng trong video.

Detector mặc định là Ultralytics YOLO26 với ByteTrack trong chế độ `hybrid`. Detector tự chạy CPU/GPU theo môi trường và có thể được thay bằng weights fine-tune theo camera để tăng recall. Nếu detector không khả dụng, hệ thống chỉ có thể dùng baseline đã hiệu chỉnh thủ công; không tự tuyên bố ô chưa biết là trống.

---

### 5.3.2. Slot Occupancy Classification

Mỗi ô đỗ được biểu diễn bằng polygon. Hệ thống lưu crop rỗng của từng ô, sau đó tính độ thay đổi màu trong không gian LAB và thay đổi biên giữa frame hiện tại với crop tham chiếu. Nhiều frame rỗng có thể được tích lũy để lấy median, giảm nhiễu camera.

Khi detector được bật, overlap giữa bounding box xe và polygon là evidence dương mạnh cho `occupied`. Appearance score thấp và không có detection xác nhận `vacant`; vùng score không rõ ràng hoặc thiếu baseline cho kết quả `unknown`. Quy tắc fail-safe này tránh điều hướng tài xế tới một ô mà hệ thống chưa chắc là trống.

Kết quả ban đầu có thể dao động do ánh sáng, che khuất hoặc mô hình phát hiện không ổn định giữa các frame. Vì vậy hệ thống sử dụng cơ chế ổn định theo thời gian để tránh việc trạng thái ô đỗ bị đổi liên tục trong thời gian ngắn.

---

### 5.3.3. Temporal Stabilization

Temporal hysteresis làm mượt trạng thái của từng ô đỗ. Thay vì cập nhật trạng thái dựa trên một frame đơn lẻ, hệ thống yêu cầu evidence lặp lại trong nhiều frame.

Mặc định, `occupied` cần hai frame xác nhận liên tiếp, còn `vacant` cần bốn frame. Nếu một ô đang được đề xuất là trống nhưng evidence trở nên không chắc chắn, ô đó lập tức trở lại `unknown` và bị loại khỏi định tuyến.

Cơ chế này giúp giảm nhiễu khi detection bị mất trong một vài frame hoặc khi xe đang di chuyển qua vùng ranh giới giữa hai ô đỗ.

---

### 5.3.4. Parking Graph Modeling

Bãi đỗ xe được mô hình hóa thành đồ thị có trọng số. Trong đồ thị này:

| Thành phần | Ý nghĩa                                                   |
| ---------- | --------------------------------------------------------- |
| Node       | Lối vào, waypoint, giao điểm đường đi, vị trí gần ô đỗ    |
| Edge       | Đoạn đường xe có thể di chuyển giữa hai node              |
| Weight     | Chi phí di chuyển, thường là khoảng cách thực tế theo mét |
| Slot node  | Node đại diện cho vị trí tiếp cận một ô đỗ cụ thể         |

Cách mô hình hóa này giúp bài toán tìm đường trong bãi xe trở thành bài toán tìm đường ngắn nhất trên đồ thị. Do các cạnh có trọng số không âm, thuật toán Dijkstra phù hợp để tìm tuyến đường ngắn nhất từ vị trí hiện tại đến các ô đỗ còn trống.

---

### 5.3.5. Slot Recommendation & Routing

Sau khi có trạng thái ổn định, hệ thống chỉ lọc các ô có trạng thái `vacant`; `unknown` không phải ô trống. Từ vị trí hiện tại của xe, hệ thống tính khoảng cách ngắn nhất đến từng ô đủ điều kiện trên đồ thị bãi xe.

Ô đỗ được đề xuất là ô có tổng khoảng cách đường đi nhỏ nhất. Trong trường hợp nhiều ô có cùng khoảng cách, hệ thống sử dụng quy tắc ưu tiên cố định, ví dụ chọn ô có ID nhỏ hơn hoặc ô gần lối ra hơn tùy theo cấu hình. Quy tắc này giúp kết quả của hệ thống nhất quán và dễ kiểm chứng.

Kết quả cuối cùng của bước này bao gồm mã ô đỗ, tuyến đường đi qua các waypoint và tổng khoảng cách dự kiến.

---

### 5.3.6. Visualization & User Interface

Giao diện của hệ thống gồm hai phần chính: video giám sát đã chú thích và bản đồ bãi xe 2D.

Trên video, hệ thống hiển thị bounding box của phương tiện và overlay màu lên từng ô đỗ. Trên bản đồ 2D, hệ thống hiển thị trạng thái các ô đỗ, ô được đề xuất và tuyến đường ngắn nhất.

Thông tin hiển thị cho người dùng bao gồm:

| Thành phần      | Nội dung                                                 |
| --------------- | -------------------------------------------------------- |
| Mã ô đỗ đề xuất | Ví dụ: E12.3                                             |
| Trạng thái ô đỗ | Trống, đã có xe, không chắc chắn hoặc được đề xuất        |
| Tuyến đường     | Đường đi từ vị trí hiện tại đến ô đỗ                     |
| Khoảng cách     | Tổng chiều dài tuyến đường                               |
| Cảnh báo        | Thông báo khi không còn ô trống hoặc camera mất tín hiệu |

---

### 5.3.7. Calibration Persistence

Phiên bản hiện tại lưu polygon, đồ thị, tham số inference và ảnh baseline rỗng trong thư mục cấu hình. Việc lưu lịch sử trạng thái vận hành vào cơ sở dữ liệu chưa được triển khai và là phần mở rộng sau.

Hệ thống không nhận dạng hoặc lưu trữ biển số xe hay khuôn mặt người dùng.

---

## 5.4. Liên hệ giữa Solution và Breakdown Tree

| Khối solution                 | Sub-problem tương ứng      | Vai trò                                     |
| ----------------------------- | -------------------------- | ------------------------------------------- |
| Camera Input                  | P0                         | Cung cấp dữ liệu đầu vào cho toàn hệ thống. |
| Detection & Tracking          | SP1.1, SP1.2, SP1.3        | Tự học baseline và xác nhận ô có xe.        |
| Hybrid Occupancy Estimation   | SP2.1, SP2.2, SP2.4        | Xác định trạng thái an toàn từng ô đỗ.      |
| Temporal Hysteresis           | SP2.3                      | Làm ổn định kết quả theo thời gian.         |
| Parking Graph Model           | SP3.1                      | Biểu diễn bãi xe thành đồ thị.              |
| Slot Recommendation & Routing | SP3.2, SP3.3, SP3.4        | Chọn ô đỗ và tuyến đường ngắn nhất.         |
| Visualization & UI            | SP4.1, SP4.2, SP4.3, SP4.4 | Hiển thị kết quả cho người dùng.            |
| Calibration Persistence       | FR5                        | Lưu reference thủ công và cấu hình inference; auto-learn chạy lại khi mở video. |

---

## 5.5. Quy trình chạy với video thực tế bất kỳ

1. Đặt video camera cố định vào thư mục `dataset/`, mở giao diện thiết lập và vẽ polygon khít bên trong từng ô đỗ; không có thuật toán tin cậy để suy ra ô đỗ vô hình/không được định nghĩa trong mọi cảnh quay.
2. Tải video trong giao diện; **Auto Learn Video** tự chạy khi chưa có baseline và có thể chạy lại thủ công. Hệ thống lấy mẫu rải đều trong video, bỏ các frame detector thấy xe tại ô và tạo baseline bằng nhiều mẫu.
3. Nếu một ô luôn có xe trong toàn video hoặc detector không khả dụng, ô đó còn `unknown` khi không có bằng chứng chắc chắn. Có thể nhập ID ô rỗng tại một frame và bấm **Calibrate** để bổ sung.
4. Chạy video; màu xám/`?` là `unknown` và không được dùng để đề xuất đường đi. Nếu camera bị dịch chuyển hoặc đổi video, baseline phải được học lại.
5. Để đánh giá, dùng nhãn thực tế tách biệt và chạy `python evaluate.py --calibration-video dataset/<video>.mp4 --ground-truth <nhãn.json>`; pretrained detector không thay thế việc đo F1 trên video bãi thật.

Chạy offline bằng CLI: `python run_inference.py --video dataset/<video>.mp4 --output results/output.mp4`. CLI tự quét video để auto-calibrate; `--empty-reference`, `--calibrate-first-frame` và `--skip-auto-calibration` dành cho trường hợp kiểm soát riêng.

Đối với camera live không thể đọc trước tương lai, auto-calibration được tích lũy online: các ô chỉ chuyển từ `unknown` sang có thể đề xuất sau khi hệ thống quan sát đủ frame không có xe tại ô đó.

---

# 6. Ethical & Social Issues

## 6.1. Quyền riêng tư

Hệ thống sử dụng camera giám sát để xử lý hình ảnh trong bãi đỗ xe. Dù hệ thống không nhận diện biển số hay khuôn mặt, video vẫn có thể vô tình chứa hình ảnh người dùng hoặc phương tiện cá nhân. Vì vậy, quyền riêng tư là vấn đề cần được quan tâm.

Biện pháp giảm thiểu:

* Không thực hiện nhận diện khuôn mặt.
* Không đọc hoặc lưu biển số xe.
* Ưu tiên xử lý video trên máy chủ nội bộ.
* Không lưu video gốc dài hạn nếu không cần thiết.
* Chỉ lưu metadata như trạng thái ô đỗ, timestamp và route.
* Thông báo rõ ràng cho người dùng rằng khu vực có sử dụng camera AI.

---

## 6.2. An toàn người dùng

Nếu hệ thống phân loại sai trạng thái ô đỗ, tài xế có thể được hướng dẫn đến một ô đã có xe. Điều này có thể gây nhầm lẫn, tranh chấp hoặc rủi ro va chạm trong bãi xe.

Biện pháp giảm thiểu:

* Sử dụng ngưỡng phát hiện phù hợp.
* Làm ổn định trạng thái theo thời gian để giảm nhiễu.
* Hiển thị cảnh báo khi camera mất tín hiệu hoặc độ tin cậy thấp.
* Cho phép nhân viên bãi xe can thiệp thủ công khi cần.
* Không để hệ thống thay thế hoàn toàn trách nhiệm quan sát của tài xế.

---

## 6.3. Tính công bằng

Hệ thống thường đề xuất ô đỗ gần nhất để tối ưu thời gian di chuyển. Tuy nhiên, nếu không thiết kế cẩn thận, hệ thống có thể chưa xét đến các nhóm người dùng có nhu cầu đặc biệt, ví dụ người khuyết tật, người cao tuổi hoặc xe ưu tiên.

Biện pháp giảm thiểu:

* Có thể cấu hình vùng đỗ ưu tiên riêng.
* Không đề xuất ô ưu tiên cho người dùng thông thường nếu không phù hợp.
* Cho phép mở rộng tiêu chí đề xuất ngoài khoảng cách, ví dụ loại người dùng hoặc loại phương tiện.
* Công khai nguyên tắc đề xuất ô đỗ để tránh gây hiểu nhầm.

---

## 6.4. Thiên lệch mô hình

Mô hình phát hiện phương tiện có thể hoạt động tốt với các loại xe phổ biến nhưng kém ổn định hơn với xe có hình dạng đặc biệt, xe bị che khuất hoặc điều kiện ánh sáng kém. Điều này có thể dẫn đến việc bỏ sót hoặc nhận diện sai phương tiện.

Biện pháp giảm thiểu:

* Thu thập dữ liệu đánh giá từ chính môi trường triển khai.
* Kiểm thử với nhiều điều kiện ánh sáng và mật độ xe khác nhau.
* Cập nhật hoặc fine-tune mô hình nếu kết quả thực tế chưa đạt yêu cầu.
* Theo dõi các trường hợp lỗi để cải thiện hệ thống.

---

## 6.5. Tác động xã hội

Hệ thống có thể giúp giảm thời gian tìm chỗ đỗ, giảm ùn tắc trong bãi xe và giảm nhiên liệu tiêu hao do xe phải chạy vòng nhiều lần. Điều này tạo ra tác động tích cực đến trải nghiệm người dùng và môi trường.

Tuy nhiên, việc tự động hóa cũng có thể làm giảm nhu cầu nhân sự hướng dẫn trong bãi xe. Ngoài ra, người dùng không quen với công nghệ có thể gặp khó khăn nếu giao diện chỉ dẫn không đủ rõ ràng.

Biện pháp giảm thiểu:

* Thiết kế giao diện đơn giản, dễ hiểu.
* Duy trì nhân viên hỗ trợ trong giai đoạn triển khai.
* Không phụ thuộc hoàn toàn vào hệ thống tự động khi có sự cố.
* Cung cấp hướng dẫn rõ ràng cho người dùng.

---

## 6.6. Trách nhiệm và minh bạch

Khi hệ thống đưa ra đề xuất sai hoặc xảy ra tranh chấp, cần có cơ chế xác định nguyên nhân và trách nhiệm. Hệ thống cần lưu log để phục vụ kiểm tra, nhưng không nên lưu dữ liệu cá nhân không cần thiết.

Biện pháp giảm thiểu:

* Lưu log trạng thái hệ thống, timestamp và quyết định định tuyến.
* Cung cấp cơ chế phản hồi hoặc báo lỗi.
* Thông báo rõ hệ thống chỉ hỗ trợ điều hướng, tài xế vẫn cần quan sát thực tế.
* Có quy trình xử lý khi hệ thống gặp lỗi hoặc camera mất kết nối.

---

# 7. Kết luận

Poster trình bày bài toán xây dựng hệ thống bãi đỗ xe thông minh sử dụng camera giám sát và thuật toán tìm đường ngắn nhất. Hệ thống nhận video từ camera, phát hiện phương tiện, xác định trạng thái từng ô đỗ, đề xuất ô đỗ còn trống gần nhất và hiển thị tuyến đường trên bản đồ 2D.

Bài toán được phân rã thành các sub-problem rõ ràng, bao gồm phát hiện phương tiện, phân loại trạng thái ô đỗ, mô hình hóa đồ thị, định tuyến và hiển thị giao diện. Mỗi sub-problem có input, output và giải pháp tương ứng, giúp đảm bảo tính chặt chẽ trong thiết kế hệ thống.

Phần đánh giá sử dụng các tiêu chí định lượng như F1-score, Routing Accuracy, Response Latency, FPS và Sync Delay để chứng minh hệ thống đáp ứng các yêu cầu chức năng và phi chức năng. Ngoài ra, poster cũng xem xét các vấn đề đạo đức và xã hội như quyền riêng tư, an toàn, công bằng, thiên lệch mô hình và trách nhiệm khi hệ thống xảy ra lỗi.

---

# 8. Phụ lục: Gợi ý bố cục poster

## Bố cục đề xuất cho poster khổ A0 hoặc A1

### Cột 1: Problem Definition

* Introduction
* Input
* Output
* Requirements
* Constraints
* Assumptions
* Scope

### Cột 2: Decomposition & Solution

* Hình 1: Decomposition Tree
* Bảng giải thích node lá
* Hình 2: Solution Pipeline
* Mô tả ngắn các khối xử lý

### Cột 3: Evaluation & Ethics

* Evaluation Metrics
* Evaluation Data
* Mapping Metrics ↔ Requirements
* Ethical & Social Issues
* Conclusion

---

## Gợi ý thiết kế lại hình cho đẹp

### Hình 1: Decomposition Tree

Nên dùng bố cục:

* Node gốc màu xanh đậm.
* 5 node chính màu xanh nhạt:

  * Video Auto-calibration & Tracking
  * Hybrid Occupancy Estimation
  * Parking Recommendation & Routing
  * Visualization & UI
  * Calibration Persistence
* Node lá màu trắng, viền xanh.
* Mỗi node chỉ nên ghi:

  * Tên node
  * Input ngắn
  * Output ngắn
* Không đưa quá nhiều chữ vào hình.
* Phần giải pháp chi tiết để ở bảng bên dưới.

---

### Hình 2: Solution Pipeline

Nên dùng bố cục ngang:

Camera Input
→ Video Auto-calibration & Tracking
→ Hybrid Occupancy Estimation
→ Temporal Hysteresis
→ Slot Recommendation & Routing
→ Visualization & UI
→ Calibration Persistence

Mỗi khối nên có icon nhỏ:

* Camera cho input.
* Video/AI cho auto-calibration và tracking.
* Ô đỗ cho slot classification.
* Đồng hồ cho temporal hysteresis.
* Bản đồ cho routing.
* Màn hình cho UI.
* Database cho logging.

Màu nên dùng thống nhất:

* Xanh dương cho input và xử lý chính.
* Xanh lá cho trạng thái trống.
* Đỏ cho trạng thái có xe.
* Vàng cho ô được đề xuất.
* Xám nhạt cho database/logging.
