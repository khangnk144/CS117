import cv2, json
from ultralytics import YOLO

# Mở video
cap = cv2.VideoCapture("dataset/test.mp4")
ret, frame = cap.read()
cap.release()

if not ret:
    print("Lỗi không đọc được video!")
    exit(1)

h, w = frame.shape[:2]

# Chạy YOLO detect xe để lấy vị trí
model = YOLO("yolov8s.pt")
results = model(frame, conf=0.1)

slots = []
for idx, box in enumerate(results[0].boxes):
    cls_id = int(box.cls[0])
    if cls_id in [2, 7]: # car, truck
        x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
        # Tạo polygon hình chữ nhật
        poly = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
        slots.append({"id": f"S{idx+1}", "polygon": poly})

print(f"Đã tự động tìm thấy {len(slots)} xe (tương ứng {len(slots)} slots).")

nodes = [{"id": "E1", "type": "entrance", "x": w//2, "y": 30}]
nodes.append({"id": "W1", "type": "waypoint", "x": w//2, "y": h//2})
edges = [{"from": "E1", "to": "W1", "weight": 5.0}]

for slot in slots:
    poly = slot["polygon"]
    cx, cy = int(sum(p[0] for p in poly)/4), int(sum(p[1] for p in poly)/4)
    nodes.append({"id": slot["id"], "type": "slot", "x": cx, "y": cy})
    edges.append({"from": slot["id"], "to": "W1", "weight": 5.0})

config = {
    "parking_lot": "AutoTest",
    "weather": "Unknown",
    "video_path": "dataset/test.mp4",
    "image_size": {"width": w, "height": h},
    "slots": slots,
    "graph": {"nodes": nodes, "edges": edges},
    "model": {"name": "yolov8s.pt", "conf_threshold": 0.25, "iou_threshold": 0.3}
}

with open("config/parking_lot.json", "w") as f:
    json.dump(config, f, indent=2)
print("Đã tạo xong config/parking_lot.json!")
