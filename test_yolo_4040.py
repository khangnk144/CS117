from ultralytics import YOLO
import cv2
import numpy as np

model = YOLO('yolov8m.pt')
cap = cv2.VideoCapture('dataset/test.mp4')
cap.set(cv2.CAP_PROP_POS_FRAMES, 4040)
ret, frame = cap.read()
if ret:
    print(f"Frame shape: {frame.shape}, Max pixel: {np.max(frame)}, Min pixel: {np.min(frame)}")
    results = model.predict(frame, imgsz=1280, conf=0.1, classes=[2,5,7])
    print(f"Detections at imgsz=1280: {len(results[0].boxes)}")
