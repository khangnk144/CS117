"""
End-to-end pipeline: frame → detect → classify slots → find path → annotated output.
Connects VehicleDetector, SlotClassifier, and ParkingGraph.
"""

import cv2
import numpy as np
import time
from typing import Dict, List, Optional, Tuple

from src.detector import VehicleDetector
from src.slot_classifier import SlotClassifier
from src.pathfinder import ParkingGraph


class ParkingPipeline:
    """Full parking lot occupancy detection and navigation pipeline."""

    def __init__(self, config: Dict, device: str = "cuda"):
        """
        Args:
            config: Parking lot configuration dict with keys:
                - 'slots': list of slot definitions (id, polygon)
                - 'graph': walkway graph data (nodes, edges)
                - 'model': optional model config (name, conf_threshold)
        """
        model_cfg = config.get("model", {})
        model_name = model_cfg.get("name", "yolov8s.pt")
        conf_threshold = model_cfg.get("conf_threshold", 0.25)
        iou_threshold = model_cfg.get("iou_threshold", 0.3)

        self.detector = VehicleDetector(
            model_name=model_name,
            conf_threshold=conf_threshold,
            device=device,
        )
        self.classifier = SlotClassifier(
            slots=config["slots"],
            iou_threshold=iou_threshold,
        )
        self.graph = ParkingGraph(config["graph"])
        self.config = config

        # Cache latest results
        self.last_detections = []
        self.last_slot_statuses = []
        self.last_nav_result = {}
        self.last_processing_time = 0.0

    def process_frame(self, frame: np.ndarray,
                      start_node: str = "E1") -> Dict:
        """
        Process a single frame through the full pipeline.

        Args:
            frame: BGR image (numpy array).
            start_node: User's current position node ID.

        Returns:
            Dict with:
                - 'detections': list of vehicle detections
                - 'slot_statuses': list of slot statuses
                - 'navigation': nearest vacant slot + path info
                - 'processing_time_ms': end-to-end time in milliseconds
                - 'annotated_frame': frame with overlays
                - 'summary': quick text summary
        """
        t_start = time.perf_counter()

        # Step 1: Detect vehicles
        detections = self.detector.detect(frame)

        # Step 2: Classify slots
        slot_statuses = self.classifier.classify(detections)

        # Step 3: Find nearest vacant slot
        vacant_ids = [s["id"] for s in slot_statuses if s["status"] == "vacant"]
        nav_result = self.graph.find_nearest_vacant(start_node, vacant_ids)

        t_end = time.perf_counter()
        processing_time_ms = (t_end - t_start) * 1000

        # Step 4: Annotate frame
        annotated = self.annotate_frame(
            frame.copy(), detections, slot_statuses, nav_result
        )

        # Cache
        self.last_detections = detections
        self.last_slot_statuses = slot_statuses
        self.last_nav_result = nav_result
        self.last_processing_time = processing_time_ms

        occupied_count = sum(1 for s in slot_statuses if s["status"] == "occupied")
        total_count = len(slot_statuses)
        vacant_count = total_count - occupied_count

        return {
            "detections": detections,
            "slot_statuses": slot_statuses,
            "navigation": nav_result,
            "processing_time_ms": round(processing_time_ms, 2),
            "annotated_frame": annotated,
            "summary": {
                "total_slots": total_count,
                "occupied": occupied_count,
                "vacant": vacant_count,
                "target_slot": nav_result.get("target_slot"),
                "distance": nav_result.get("distance"),
            },
        }

    def annotate_frame(self, frame: np.ndarray,
                       detections: List[Dict],
                       slot_statuses: List[Dict],
                       nav_result: Dict) -> np.ndarray:
        """
        Draw overlays on the frame:
          - Slot polygons: green=vacant, red=occupied, yellow=recommended
          - Vehicle bounding boxes (thin blue)
        """
        target_slot = nav_result.get("target_slot")

        # Draw slot polygons
        for slot in slot_statuses:
            pts = np.array(slot["polygon"], dtype=np.int32)

            if slot["id"] == target_slot:
                # Recommended slot: yellow highlight
                color = (0, 255, 255)  # BGR yellow
                thickness = 3
            elif slot["status"] == "occupied":
                color = (0, 0, 255)  # BGR red
                thickness = 2
            else:
                color = (0, 255, 0)  # BGR green
                thickness = 2

            cv2.polylines(frame, [pts], isClosed=True, color=color,
                          thickness=thickness)

            # Semi-transparent fill
            overlay = frame.copy()
            fill_color = color
            cv2.fillPoly(overlay, [pts], fill_color)
            alpha = 0.15 if slot["id"] != target_slot else 0.3
            cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

            # Slot label
            cx = int(np.mean(pts[:, 0]))
            cy = int(np.mean(pts[:, 1]))
            label = f"{slot['id']}"
            cv2.putText(frame, label, (cx - 10, cy + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        # Draw vehicle bboxes (thin, for debugging)
        for det in detections:
            x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 200, 0), 1)

        # Info overlay
        occupied = sum(1 for s in slot_statuses if s["status"] == "occupied")
        total = len(slot_statuses)
        info_text = f"Vacant: {total - occupied}/{total}"
        cv2.putText(frame, info_text, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

        if target_slot:
            nav_text = f"Go to: {target_slot} ({nav_result.get('distance', '?')}m)"
            cv2.putText(frame, nav_text, (10, 65),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

        return frame
