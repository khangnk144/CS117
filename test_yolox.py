from ultralytics import YOLO
import cv2

model = YOLO('yolov8x.pt')
cap = cv2.VideoCapture('dataset/test.mp4')
cap.set(cv2.CAP_PROP_POS_FRAMES, 4040)
ret, frame = cap.read()
if ret:
    results = model.predict(frame, imgsz=1280, conf=0.05, classes=[2,5,7])
    print(f"X model Detections: {len(results[0].boxes)}")
