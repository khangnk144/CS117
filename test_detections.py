import json
import cv2
from src.detector import VehicleDetector

with open("dataset/ground_truth.json") as f:
    ground_truth = json.load(f)

detector = VehicleDetector(model_name="yolov8m.pt", conf_threshold=0.1)

total_gt_occupied = 0
total_detections = 0

for gt_entry in ground_truth[:20]:
    img_path = gt_entry["image_path"]
    frame = cv2.imread(img_path)
    if frame is None: continue
    
    gt_labels = gt_entry["labels"]
    occupied_count = sum(1 for status in gt_labels.values() if status == "occupied")
    total_gt_occupied += occupied_count
    
    detections = detector.detect(frame)
    total_detections += len(detections)

print(f"Total GT Occupied in 20 frames: {total_gt_occupied}")
print(f"Total YOLO Detections in 20 frames: {total_detections}")
