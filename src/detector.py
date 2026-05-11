"""
Vehicle Detector using YOLOv8s with COCO pretrained weights.
Detects cars and trucks in parking lot surveillance frames.
"""

from ultralytics import YOLO
import numpy as np
from typing import List, Tuple, Dict


# COCO class IDs for vehicles we care about
VEHICLE_CLASSES = {2: "car", 7: "truck"}


class VehicleDetector:
    """Wrapper around YOLOv8 for vehicle detection in parking lot frames."""

    def __init__(self, model_name: str = "yolov8m.pt", conf_threshold: float = 0.25,
                 device: str = "cuda"):
        """
        Args:
            model_name: YOLOv8 model variant. Default 'yolov8s.pt' (small).
                        Use 'yolov8n.pt' for nano if hardware is constrained.
            conf_threshold: Minimum confidence to keep a detection.
            device: 'cuda' or 'cpu'.
        """
        self.model = YOLO(model_name)
        self.conf_threshold = conf_threshold
        self.device = device
        # COCO class indices for car=2, truck=7
        self.vehicle_class_ids = list(VEHICLE_CLASSES.keys())

    def detect(self, frame: np.ndarray) -> List[Dict]:
        """
        Run vehicle detection on a single frame.

        Args:
            frame: BGR image (numpy array, HxWx3).

        Returns:
            List of detections, each dict with keys:
                - 'bbox': [x1, y1, x2, y2] in pixel coords
                - 'confidence': float
                - 'class_id': int (COCO class)
                - 'class_name': str ('car' or 'truck')
        """
        results = self.model.predict(
            source=frame,
            conf=self.conf_threshold,
            classes=self.vehicle_class_ids,
            imgsz=1280,
            device=self.device,
            verbose=False,
        )

        detections = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0])
                detections.append({
                    "bbox": box.xyxy[0].cpu().numpy().tolist(),  # [x1, y1, x2, y2]
                    "confidence": float(box.conf[0]),
                    "class_id": cls_id,
                    "class_name": VEHICLE_CLASSES.get(cls_id, "unknown"),
                })

        return detections
