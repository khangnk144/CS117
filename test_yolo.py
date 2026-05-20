from ultralytics import YOLO
import cv2

model = YOLO('yolov8m.pt')
cap = cv2.VideoCapture('dataset/test.mp4')
ret, frame = cap.read()
if ret:
    results = model.predict(frame, imgsz=1920, conf=0.01)
    if len(results[0].boxes) > 0:
        for box in results[0].boxes:
            print(f"Detected class: {model.names[int(box.cls[0])]} with conf {box.conf[0]:.2f}")
    else:
        print("No detections at all.")
