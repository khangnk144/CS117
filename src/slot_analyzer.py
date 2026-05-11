"""
Parking Slot Analyzer — Direct image analysis per slot.

Instead of detecting vehicles globally (YOLO) and matching to slots,
this module directly analyzes each slot's cropped region using
classical CV features (edges, texture, color variance) to determine
if a parking slot is occupied or vacant.

This approach is much more reliable for overhead fixed-camera parking
lots where vehicles appear at small scale from bird's-eye view.
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
from shapely.geometry import Polygon


class SlotAnalyzer:
    """
    Analyzes each parking slot region directly from the frame to determine
    occupancy status. Uses a combination of:
      1. Edge density (Canny edges)
      2. Color variance (standard deviation of color channels)
      3. Texture energy (Laplacian variance)

    Optionally learns a per-slot "empty" baseline from a reference frame
    for even more accurate classification via background comparison.
    """

    def __init__(self, slots: List[Dict],
                 edge_threshold: float = 0.08,
                 variance_threshold: float = 25.0,
                 texture_threshold: float = 50.0,
                 combined_score_threshold: float = 0.45,
                 use_adaptive: bool = True):
        """
        Args:
            slots: List of slot definitions with 'id' and 'polygon' keys.
            edge_threshold: Min edge pixel ratio to indicate occupancy.
            variance_threshold: Min color std dev to indicate occupancy.
            texture_threshold: Min Laplacian variance for occupancy.
            combined_score_threshold: Threshold on combined [0..1] score.
            use_adaptive: If True, learn per-slot empty baselines adaptively.
        """
        self.edge_threshold = edge_threshold
        self.variance_threshold = variance_threshold
        self.texture_threshold = texture_threshold
        self.combined_score_threshold = combined_score_threshold
        self.use_adaptive = use_adaptive

        self.slots = []
        for slot_def in slots:
            poly = Polygon(slot_def["polygon"])
            pts = np.array(slot_def["polygon"], dtype=np.int32)
            # Compute bounding rect for efficient cropping
            x, y, w, h = cv2.boundingRect(pts)
            self.slots.append({
                "id": slot_def["id"],
                "polygon_points": slot_def["polygon"],
                "polygon": poly,
                "pts": pts,
                "bbox": (x, y, w, h),
            })

        # Per-slot baselines (learned from "empty" reference or adaptively)
        self.baselines: Dict[str, Dict] = {}
        self.frame_count = 0
        # History for adaptive baseline (stores recent feature values)
        self.feature_history: Dict[str, List[Dict]] = {s["id"]: [] for s in self.slots}
        self.history_max_len = 30

    def set_reference_frame(self, frame: np.ndarray):
        """
        Learn per-slot empty baselines from a known-empty reference frame.
        Call this once during setup if you have a frame with all slots empty.

        Args:
            frame: BGR image (numpy array, HxWx3) with all slots empty.
        """
        for slot in self.slots:
            features = self._extract_features(frame, slot)
            self.baselines[slot["id"]] = {
                "edge_density": features["edge_density"],
                "color_variance": features["color_variance"],
                "texture_energy": features["texture_energy"],
                "mean_color": features["mean_color"],
            }

    def classify_all(self, frame: np.ndarray) -> List[Dict]:
        """
        Classify all slots in the given frame.

        Args:
            frame: BGR image (numpy array, HxWx3).

        Returns:
            List of slot statuses, each with:
                - 'id': slot ID
                - 'status': 'occupied' or 'vacant'
                - 'score': float [0..1] occupancy confidence
                - 'polygon': polygon points
                - 'features': dict of raw feature values
        """
        self.frame_count += 1
        results = []

        for slot in self.slots:
            features = self._extract_features(frame, slot)
            score = self._compute_occupancy_score(slot["id"], features)

            status = "occupied" if score >= self.combined_score_threshold else "vacant"

            # Update adaptive history
            if self.use_adaptive:
                self._update_history(slot["id"], features, status)

            results.append({
                "id": slot["id"],
                "status": status,
                "iou": round(score, 4),  # Keep 'iou' key for compatibility
                "score": round(score, 4),
                "polygon": slot["polygon_points"],
                "features": {
                    "edge_density": round(features["edge_density"], 4),
                    "color_variance": round(features["color_variance"], 2),
                    "texture_energy": round(features["texture_energy"], 2),
                },
            })

        return results

    def _extract_features(self, frame: np.ndarray, slot: Dict) -> Dict:
        """
        Extract visual features from a slot's region in the frame.

        Returns dict with:
            - edge_density: ratio of edge pixels to total pixels
            - color_variance: average std dev across color channels
            - texture_energy: Laplacian variance (measure of texture detail)
            - mean_color: mean BGR values
        """
        x, y, w, h = slot["bbox"]

        # Ensure bounding box is within frame
        fh, fw = frame.shape[:2]
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(fw, x + w)
        y2 = min(fh, y + h)

        if x2 <= x1 or y2 <= y1:
            return {
                "edge_density": 0.0,
                "color_variance": 0.0,
                "texture_energy": 0.0,
                "mean_color": [0.0, 0.0, 0.0],
            }

        # Crop the bounding rect
        crop = frame[y1:y2, x1:x2].copy()

        # Create a mask from the polygon (shifted to crop coordinates)
        mask = np.zeros((y2 - y1, x2 - x1), dtype=np.uint8)
        shifted_pts = slot["pts"].copy()
        shifted_pts[:, 0] -= x1
        shifted_pts[:, 1] -= y1
        cv2.fillPoly(mask, [shifted_pts], 255)

        # Count valid pixels
        valid_pixels = np.count_nonzero(mask)
        if valid_pixels < 10:
            return {
                "edge_density": 0.0,
                "color_variance": 0.0,
                "texture_energy": 0.0,
                "mean_color": [0.0, 0.0, 0.0],
            }

        # 1. Edge Density (Canny)
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        # Apply Gaussian blur to reduce noise
        gray_blur = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(gray_blur, 50, 150)
        # Apply mask
        edges_masked = cv2.bitwise_and(edges, edges, mask=mask)
        edge_pixels = np.count_nonzero(edges_masked)
        edge_density = edge_pixels / valid_pixels

        # 2. Color Variance (std dev per channel, masked)
        masked_pixels = crop[mask > 0]
        if len(masked_pixels) > 0:
            color_std = np.std(masked_pixels, axis=0)
            color_variance = float(np.mean(color_std))
        else:
            color_variance = 0.0

        # 3. Texture Energy (Laplacian variance)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        laplacian_masked = laplacian[mask > 0]
        if len(laplacian_masked) > 0:
            texture_energy = float(np.var(laplacian_masked))
        else:
            texture_energy = 0.0

        # 4. Mean color
        if len(masked_pixels) > 0:
            mean_color = np.mean(masked_pixels, axis=0).tolist()
        else:
            mean_color = [0.0, 0.0, 0.0]

        return {
            "edge_density": edge_density,
            "color_variance": color_variance,
            "texture_energy": texture_energy,
            "mean_color": mean_color,
        }

    def _compute_occupancy_score(self, slot_id: str, features: Dict) -> float:
        """
        Compute a combined occupancy score [0..1] from extracted features.

        If a baseline exists for this slot, scores are computed relative
        to the baseline (occupied slots differ significantly from empty baseline).
        Otherwise, absolute thresholds are used.
        """
        edge_d = features["edge_density"]
        color_v = features["color_variance"]
        texture_e = features["texture_energy"]

        if slot_id in self.baselines:
            # Relative scoring vs empty baseline
            base = self.baselines[slot_id]
            edge_ratio = edge_d / max(base["edge_density"], 0.001)
            color_ratio = color_v / max(base["color_variance"], 1.0)
            texture_ratio = texture_e / max(base["texture_energy"], 1.0)

            # Also check absolute color distance (mean color shift)
            color_dist = np.linalg.norm(
                np.array(features["mean_color"]) - np.array(base["mean_color"])
            )
            color_shift_score = min(1.0, color_dist / 60.0)

            # Combine relative scores
            edge_score = min(1.0, max(0.0, (edge_ratio - 1.0) / 2.0))
            variance_score = min(1.0, max(0.0, (color_ratio - 1.0) / 1.5))
            texture_score = min(1.0, max(0.0, (texture_ratio - 1.0) / 3.0))

            # Weighted combination
            score = (0.30 * edge_score +
                     0.25 * variance_score +
                     0.20 * texture_score +
                     0.25 * color_shift_score)

        else:
            # Absolute scoring (no baseline available)
            edge_score = min(1.0, edge_d / (self.edge_threshold * 2))
            variance_score = min(1.0, color_v / (self.variance_threshold * 2))
            texture_score = min(1.0, texture_e / (self.texture_threshold * 4))

            # Weighted combination
            score = (0.40 * edge_score +
                     0.35 * variance_score +
                     0.25 * texture_score)

        return float(np.clip(score, 0.0, 1.0))

    def _update_history(self, slot_id: str, features: Dict, status: str):
        """Update per-slot feature history for adaptive baseline learning."""
        self.feature_history[slot_id].append({
            "edge_density": features["edge_density"],
            "color_variance": features["color_variance"],
            "texture_energy": features["texture_energy"],
            "mean_color": features["mean_color"],
            "status": status,
        })
        if len(self.feature_history[slot_id]) > self.history_max_len:
            self.feature_history[slot_id].pop(0)

    def calibrate_from_ground_truth(self, frame: np.ndarray,
                                      labels: Dict[str, str]):
        """
        Calibrate baselines using a frame with known ground truth labels.
        Uses slots labeled as 'vacant' to establish empty baselines.

        Args:
            frame: BGR image.
            labels: Dict mapping slot_id -> 'occupied' or 'vacant'.
        """
        for slot in self.slots:
            if labels.get(slot["id"]) == "vacant":
                features = self._extract_features(frame, slot)
                if slot["id"] not in self.baselines:
                    self.baselines[slot["id"]] = {
                        "edge_density": features["edge_density"],
                        "color_variance": features["color_variance"],
                        "texture_energy": features["texture_energy"],
                        "mean_color": features["mean_color"],
                    }
                else:
                    # Running average
                    base = self.baselines[slot["id"]]
                    alpha = 0.3
                    base["edge_density"] = (1 - alpha) * base["edge_density"] + alpha * features["edge_density"]
                    base["color_variance"] = (1 - alpha) * base["color_variance"] + alpha * features["color_variance"]
                    base["texture_energy"] = (1 - alpha) * base["texture_energy"] + alpha * features["texture_energy"]
                    base["mean_color"] = [
                        (1 - alpha) * b + alpha * f
                        for b, f in zip(base["mean_color"], features["mean_color"])
                    ]

    def auto_calibrate(self, frame: np.ndarray):
        """
        Auto-calibrate by assuming all slots are empty in the given frame.
        Useful for initial setup with an empty parking lot frame.

        Args:
            frame: BGR image with all (or most) slots empty.
        """
        self.set_reference_frame(frame)
