from ultralytics import YOLO
import cv2

try:
    model = YOLO('yolov8m-visdrone.pt')
    cap = cv2.VideoCapture('dataset/test.mp4')
    cap.set(cv2.CAP_PROP_POS_FRAMES, 4040)
    ret, frame = cap.read()
    if ret:
        results = model.predict(frame, imgsz=1280, conf=0.1)
        print(f"VisDrone Detections: {len(results[0].boxes)}")
except Exception as e:
    print(e)
