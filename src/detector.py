"""
Vehicle Detector using YOLOv8 with COCO or VisDrone pretrained weights.
"""

from ultralytics import YOLO
import numpy as np
from typing import List, Dict
import cv2

# COCO class IDs
COCO_VEHICLE_CLASSES = {2: "car", 5: "bus", 7: "truck"}

# VisDrone class IDs
VISDRONE_VEHICLE_CLASSES = {3: "car", 4: "van", 5: "truck", 8: "bus"}

class VehicleDetector:
    """Wrapper around YOLOv8 for vehicle detection in parking lot frames."""

    def __init__(self, model_name: str = "yolov8n-visdrone.pt", conf_threshold: float = 0.15,
                 device: str = "cuda", imgsz: int = 1280):
        """
        Args:
            model_name: YOLOv8 model variant. Use 'yolov8n-visdrone.pt' for aerial views.
            conf_threshold: Minimum confidence to keep a detection.
            device: 'cuda' or 'cpu'.
            imgsz: Image size for YOLO inference. 1280 is better for small objects in drone footage.
        """
        print(f"Loading YOLO model: {model_name} on {device}")
        self.model = YOLO(model_name)
        self.conf_threshold = conf_threshold
        self.device = device
        self.imgsz = imgsz
        
        if "visdrone" in model_name.lower():
            self.class_mapping = VISDRONE_VEHICLE_CLASSES
        else:
            self.class_mapping = COCO_VEHICLE_CLASSES
            
        self.vehicle_class_ids = list(self.class_mapping.keys())

    def detect(self, frame: np.ndarray) -> List[Dict]:
        """
        Run vehicle detection on a single frame.

        Args:
            frame: BGR image (numpy array, HxWx3).

        Returns:
            List of detections, each dict with keys:
                - 'bbox': [x1, y1, x2, y2] in pixel coords
                - 'confidence': float
                - 'class_id': int
                - 'class_name': str
        """
        results = self.model.predict(
            source=frame,
            conf=self.conf_threshold,
            classes=self.vehicle_class_ids,
            device=self.device,
            imgsz=self.imgsz,
            verbose=False,
        )

        detections = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                
                # Manual filtering by class just in case
                if cls_id not in self.vehicle_class_ids:
                    continue
                    
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().tolist()
                        
                detections.append({
                    "bbox": [x1, y1, x2, y2],
                    "confidence": conf,
                    "class_id": cls_id,
                    "class_name": self.class_mapping.get(cls_id, "unknown"),
                })

        return detections