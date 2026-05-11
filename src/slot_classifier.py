"""
Parking Slot Classifier.
Determines occupancy status of each slot by computing IoU between
detected vehicle bounding boxes and pre-defined slot polygons.
"""

import numpy as np
from shapely.geometry import Polygon, box as shapely_box
from typing import List, Dict, Tuple


class SlotClassifier:
    """Classifies parking slots as occupied/vacant based on vehicle detections."""

    def __init__(self, slots: List[Dict], iou_threshold: float = 0.3):
        """
        Args:
            slots: List of slot definitions, each dict with:
                - 'id': str or int, unique slot identifier
                - 'polygon': list of [x, y] points defining the slot boundary
            iou_threshold: Minimum IoU between a vehicle bbox and slot polygon
                           to classify the slot as occupied. Default 0.3 per SRS.
        """
        self.iou_threshold = iou_threshold
        self.slots = []
        for slot_def in slots:
            poly = Polygon(slot_def["polygon"])
            self.slots.append({
                "id": slot_def["id"],
                "polygon_points": slot_def["polygon"],
                "polygon": poly,
            })

    def classify(self, detections: List[Dict]) -> List[Dict]:
        """
        Classify all slots given the current vehicle detections.

        Args:
            detections: List of vehicle detections from VehicleDetector.detect().
                        Each has 'bbox': [x1, y1, x2, y2].

        Returns:
            List of slot statuses, each dict with:
                - 'id': slot identifier
                - 'status': 'occupied' or 'vacant'
                - 'iou': max overlap score with any vehicle
                - 'polygon': list of [x, y] points
        """
        from shapely.geometry import Point
        
        results = []
        for slot in self.slots:
            slot_poly = slot["polygon"]
            max_iou = 0.0

            for det in detections:
                x1, y1, x2, y2 = det["bbox"]
                vbox = shapely_box(x1, y1, x2, y2)
                
                # Calculate overlap (max of IoS and IoB)
                iou = self._compute_iou(slot_poly, vbox)
                
                # Also check if center points are inside the slot
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2
                
                if slot_poly.contains(Point(cx, cy)):
                    iou = max(iou, 0.5)
                
                if slot_poly.contains(Point(cx, y2)):
                    iou = max(iou, 0.6)
                
                max_iou = max(max_iou, iou)

            status = "occupied" if max_iou >= self.iou_threshold else "vacant"
            results.append({
                "id": slot["id"],
                "status": status,
                "iou": round(max_iou, 4),
                "polygon": slot["polygon_points"],
            })

        return results

    @staticmethod
    def _compute_iou(poly_a: Polygon, poly_b: Polygon) -> float:
        """Compute max of Intersection over Slot Area and Intersection over Box Area."""
        if not poly_a.is_valid or not poly_b.is_valid:
            return 0.0
        try:
            intersection = poly_a.intersection(poly_b).area
            score_a = intersection / poly_a.area
            score_b = intersection / poly_b.area
            return max(score_a, score_b)
        except Exception:
            return 0.0
