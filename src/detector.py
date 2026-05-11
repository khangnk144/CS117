"""
Vehicle Detector using YOLOv8 with COCO pretrained weights.
Enhanced with ROI filtering and fallback mechanism.
"""

from ultralytics import YOLO
import numpy as np
from typing import List, Tuple, Dict
from shapely.geometry import Polygon, Point
import cv2

# COCO class IDs for vehicles we care about
VEHICLE_CLASSES = {2: "car", 5: "bus", 7: "truck"}


class VehicleDetector:
    """Wrapper around YOLOv8 for vehicle detection in parking lot frames."""

    def __init__(self, model_name: str = "yolov8l.pt", conf_threshold: float = 0.1,
                 device: str = "cuda",
                 slot_polygons: List[List[Tuple[int,int]]] = None):
        """
        Args:
            model_name: YOLOv8 model variant. Default 'yolov8l.pt'.
            conf_threshold: Minimum confidence to keep a detection.
            device: 'cuda' or 'cpu'.
            slot_polygons: List of slot polygons for ROI filtering.
        """
        print(f"DEBUG: Loading YOLO model: {model_name} on {device}")
        self.model = YOLO(model_name)  # tự động tải nếu chưa có
        self.conf_threshold = conf_threshold
        self.device = device
        self.vehicle_class_ids = list(VEHICLE_CLASSES.keys())
        self.slot_polygons = slot_polygons  # list of shapely Polygons
        self.roi_polygons = None
        self.roi_enabled = True
        self.fallback_counter = 0
        self.fallback_threshold = 5  # số frame liên tiếp không có detections thì tắt ROI

        if slot_polygons:
            # Expand each slot polygon by a margin to create ROI
            margin = 50  # pixels
            self.roi_polygons = [poly.buffer(margin) for poly in slot_polygons]

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
        print(f"DEBUG: Frame shape: {frame.shape}, Mean: {frame.mean():.2f}")
        
        results = self.model.predict(
            source=frame,
            conf=self.conf_threshold,
            # classes=self.vehicle_class_ids, # Remove to see all detections
            imgsz=640, # Changed from 1280 to 640
            device=self.device,
            verbose=False,
        )

        detections = []
        raw_count = 0
        for result in results:
            if result.boxes is None:
                continue
            raw_count += len(result.boxes)
            print(f"DEBUG: Found {len(result.boxes)} raw boxes in result.")
            for box in result.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                cls_name = self.model.names.get(cls_id, "unknown")
                print(f"DEBUG: Detected class {cls_id} ({cls_name}) with conf {conf:.2f}")
                
                # Manual filtering by class
                if cls_id not in self.vehicle_class_ids:
                    continue
                    
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().tolist()
                
                # ROI filtering (có thể tắt nếu không phát hiện được gì)
                if self.roi_enabled and self.roi_polygons:
                    center = Point((x1+x2)/2, (y1+y2)/2)
                    # Keep detection if center falls inside any ROI polygon
                    if not any(roi.contains(center) for roi in self.roi_polygons):
                        print(f"DEBUG: Detection filtered out by ROI")
                        continue
                        
                detections.append({
                    "bbox": [x1, y1, x2, y2],
                    "confidence": conf,
                    "class_id": cls_id,
                    "class_name": VEHICLE_CLASSES.get(cls_id, "unknown"),
                })

        print(f"DEBUG: Total raw detections: {raw_count}, Filtered detections: {len(detections)}")

        # Fallback mechanism: nếu liên tục không có detection, tắt ROI để kiểm tra
        if not detections:
            self.fallback_counter += 1
            if self.fallback_counter >= self.fallback_threshold and self.roi_enabled:
                self.roi_enabled = False
                print("⚠️  ROI filter disabled due to lack of detections (fallback).")
        else:
            self.fallback_counter = 0
            if not self.roi_enabled:
                # Nếu sau khi tắt ROI đã có detection, giữ nguyên trạng thái tắt
                pass

        return detections