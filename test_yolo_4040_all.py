from ultralytics import YOLO
import cv2

model = YOLO('yolov8m.pt')
cap = cv2.VideoCapture('dataset/test.mp4')
cap.set(cv2.CAP_PROP_POS_FRAMES, 4040)
ret, frame = cap.read()
if ret:
    results = model.predict(frame, imgsz=1280, conf=0.01)
    if len(results[0].boxes) > 0:
        for box in results[0].boxes:
            print(f"Detected: {model.names[int(box.cls[0])]} at {box.conf[0]:.2f}")
    else:
        print("Literally no detections.")
