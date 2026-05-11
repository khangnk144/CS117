"""
Parking Slot Classifier with improved occupancy logic using tracking.
"""

import numpy as np
from shapely.geometry import Polygon, Point, box as shapely_box
from typing import List, Dict, Tuple


class SlotClassifier:
    """Classifies parking slots as occupied/vacant based on vehicle detections and tracking."""

    def __init__(self, slots: List[Dict], iou_threshold: float = 0.2,
                 center_dist_threshold: float = 0.5):
        """
        Args:
            slots: List of slot definitions.
            iou_threshold: Minimum IoU (or overlap score) to consider occupied.
            center_dist_threshold: Max ratio of distance(track center, slot center) /
                                   average slot radius to mark occupied when track is inside.
        """
        self.iou_threshold = iou_threshold
        self.center_dist_threshold = center_dist_threshold
        self.slots = []
        for slot_def in slots:
            poly = Polygon(slot_def["polygon"])
            centroid = poly.centroid
            # Compute approximate radius (average distance from centroid to vertices)
            radius = np.mean([centroid.distance(Point(p)) for p in slot_def["polygon"]])
            self.slots.append({
                "id": slot_def["id"],
                "polygon_points": slot_def["polygon"],
                "polygon": poly,
                "centroid": centroid,
                "radius": radius,
            })

    def classify(self, detections: List[Dict],
                 tracked_objects: Dict[int, List[Tuple[float, float]]] = None) -> List[Dict]:
        """
        Classify all slots given current detections and optional tracked object positions.

        Args:
            detections: List of vehicle detections (with bbox).
            tracked_objects: Dict track_id -> list of (cx, cy) positions from recent frames.

        Returns:
            List of slot statuses.
        """
        if tracked_objects is None:
            tracked_objects = {}

        results = []
        for slot in self.slots:
            slot_poly = slot["polygon"]
            max_score = 0.0

            # 1. Check current detections
            for det in detections:
                x1, y1, x2, y2 = det["bbox"]
                vbox = shapely_box(x1, y1, x2, y2)
                # Overlap score (max of intersection/slot_area, intersection/box_area)
                overlap = self._compute_overlap_score(slot_poly, vbox)
                # Bonus for center inside slot
                center = Point((x1+x2)/2, (y1+y2)/2)
                if slot_poly.contains(center):
                    overlap = max(overlap, 0.8)
                max_score = max(max_score, overlap)

            # 2. Use tracking info if available
            for track_id, positions in tracked_objects.items():
                for (cx, cy) in positions:
                    pt = Point(cx, cy)
                    if slot_poly.contains(pt):
                        # strong evidence
                        max_score = max(max_score, 0.9)
                    else:
                        # check distance to centroid
                        dist = slot["centroid"].distance(pt)
                        if dist < slot["radius"] * self.center_dist_threshold:
                            max_score = max(max_score, 0.5)

            status = "occupied" if max_score >= self.iou_threshold else "vacant"
            results.append({
                "id": slot["id"],
                "status": status,
                "iou": round(max_score, 4),
                "polygon": slot["polygon_points"],
            })

        return results

    @staticmethod
    def _compute_overlap_score(poly_a: Polygon, poly_b: Polygon) -> float:
        """Compute max of Intersection over Area of A or B."""
        if not poly_a.is_valid or not poly_b.is_valid:
            return 0.0
        try:
            intersection = poly_a.intersection(poly_b).area
            score_a = intersection / poly_a.area if poly_a.area > 0 else 0
            score_b = intersection / poly_b.area if poly_b.area > 0 else 0
            return max(score_a, score_b)
        except Exception:
            return 0.0