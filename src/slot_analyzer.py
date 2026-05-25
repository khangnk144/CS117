"""
Per-slot appearance analysis for a fixed parking camera.

The primary signal for a deployed fixed camera is the visual difference from
an empty reference for the same slot. Handcrafted absolute features remain as
a compatibility fallback until a reference has been captured.
"""

from typing import Dict, Iterable, List, Optional, Tuple

import cv2
import numpy as np


class SlotAnalyzer:
    """Estimate occupancy from per-slot background change."""

    def __init__(
        self,
        slots: List[Dict],
        edge_threshold: float = 0.08,
        variance_threshold: float = 25.0,
        texture_threshold: float = 50.0,
        combined_score_threshold: float = 0.45,
        background_difference_threshold: float = 0.08,
        max_reference_samples: int = 10,
        use_adaptive: bool = False,
    ):
        self.edge_threshold = edge_threshold
        self.variance_threshold = variance_threshold
        self.texture_threshold = texture_threshold
        self.combined_score_threshold = combined_score_threshold
        self.background_difference_threshold = background_difference_threshold
        self.max_reference_samples = max_reference_samples
        self.use_adaptive = use_adaptive

        self.slots = []
        for slot_def in slots:
            points = np.array(slot_def["polygon"], dtype=np.int32)
            self.slots.append(
                {
                    "id": slot_def["id"],
                    "polygon_points": slot_def["polygon"],
                    "pts": points,
                    "bbox": cv2.boundingRect(points),
                }
            )

        self.baselines: Dict[str, Dict] = {}
        self.reference_samples: Dict[str, List[np.ndarray]] = {
            slot["id"]: [] for slot in self.slots
        }
        self.reference_crops: Dict[str, np.ndarray] = {}
        self.reference_masks: Dict[str, np.ndarray] = {}

    @property
    def calibrated_slots(self) -> List[str]:
        return sorted(self.reference_crops.keys())

    def set_reference_frame(
        self,
        frame: np.ndarray,
        slot_ids: Optional[Iterable[str]] = None,
        append: bool = False,
    ):
        """Capture an empty reference frame for selected slots."""
        selected = set(slot_ids) if slot_ids is not None else {
            slot["id"] for slot in self.slots
        }
        for slot in self.slots:
            slot_id = slot["id"]
            if slot_id not in selected:
                continue
            crop, mask = self._crop_region(frame, slot)
            if crop is None:
                continue
            if not append:
                self.reference_samples[slot_id] = []
            samples = self.reference_samples[slot_id]
            samples.append(crop.astype(np.float32))
            if len(samples) > self.max_reference_samples:
                samples.pop(0)
            self.reference_crops[slot_id] = np.median(
                np.stack(samples, axis=0), axis=0
            ).astype(np.uint8)
            self.reference_masks[slot_id] = mask
            self.baselines[slot_id] = self._extract_features(frame, slot)

    def auto_calibrate(self, frame: np.ndarray):
        """Compatibility alias: the supplied frame must show empty slots."""
        self.set_reference_frame(frame)

    def calibrate_from_ground_truth(self, frame: np.ndarray, labels: Dict[str, str]):
        """Use only slots explicitly labelled vacant as empty references."""
        vacant_slots = [
            slot_id for slot_id, status in labels.items() if status == "vacant"
        ]
        self.set_reference_frame(frame, vacant_slots, append=True)

    def classify_all(self, frame: np.ndarray) -> List[Dict]:
        results = []
        for slot in self.slots:
            slot_id = slot["id"]
            features = self._extract_features(frame, slot)
            calibrated = slot_id in self.reference_crops
            if calibrated:
                score, changes = self._background_change_score(frame, slot)
                evidence = "empty_reference"
            else:
                score = self._absolute_feature_score(features)
                changes = {}
                evidence = "uncalibrated_features"

            results.append(
                {
                    "id": slot_id,
                    "status": (
                        "occupied"
                        if score >= self.combined_score_threshold
                        else "vacant"
                    ),
                    "score": round(score, 4),
                    "iou": round(score, 4),
                    "polygon": slot["polygon_points"],
                    "calibrated": calibrated,
                    "evidence": evidence,
                    "features": {
                        "edge_density": round(features["edge_density"], 4),
                        "color_variance": round(features["color_variance"], 2),
                        "texture_energy": round(features["texture_energy"], 2),
                        **changes,
                    },
                }
            )
        return results

    def _crop_region(
        self, frame: np.ndarray, slot: Dict
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        x, y, width, height = slot["bbox"]
        frame_height, frame_width = frame.shape[:2]
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(frame_width, x + width), min(frame_height, y + height)
        if x2 <= x1 or y2 <= y1:
            return None, None

        crop = frame[y1:y2, x1:x2].copy()
        mask = np.zeros((y2 - y1, x2 - x1), dtype=np.uint8)
        shifted_points = slot["pts"].copy()
        shifted_points[:, 0] -= x1
        shifted_points[:, 1] -= y1
        cv2.fillPoly(mask, [shifted_points], 255)
        if np.count_nonzero(mask) < 10:
            return None, None
        return crop, mask

    def _extract_features(self, frame: np.ndarray, slot: Dict) -> Dict:
        crop, mask = self._crop_region(frame, slot)
        if crop is None:
            return {
                "edge_density": 0.0,
                "color_variance": 0.0,
                "texture_energy": 0.0,
                "mean_color": [0.0, 0.0, 0.0],
            }

        valid_pixels = np.count_nonzero(mask)
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blurred, 50, 150)
        edge_density = np.count_nonzero(edges[mask > 0]) / valid_pixels
        masked_pixels = crop[mask > 0]
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        return {
            "edge_density": float(edge_density),
            "color_variance": float(np.mean(np.std(masked_pixels, axis=0))),
            "texture_energy": float(np.var(laplacian[mask > 0])),
            "mean_color": np.mean(masked_pixels, axis=0).tolist(),
        }

    def _absolute_feature_score(self, features: Dict) -> float:
        edge_score = min(1.0, features["edge_density"] / (self.edge_threshold * 2))
        variance_score = min(
            1.0, features["color_variance"] / (self.variance_threshold * 2)
        )
        texture_score = min(
            1.0, features["texture_energy"] / (self.texture_threshold * 4)
        )
        return float(0.40 * edge_score + 0.35 * variance_score + 0.25 * texture_score)

    def _background_change_score(self, frame: np.ndarray, slot: Dict) -> Tuple[float, Dict]:
        crop, mask = self._crop_region(frame, slot)
        reference = self.reference_crops[slot["id"]]
        reference_mask = self.reference_masks[slot["id"]]
        if crop is None:
            return 1.0, {"pixel_change": 1.0, "edge_change": 1.0}
        if crop.shape != reference.shape:
            reference = cv2.resize(reference, (crop.shape[1], crop.shape[0]))
            reference_mask = cv2.resize(
                reference_mask, (crop.shape[1], crop.shape[0]), interpolation=cv2.INTER_NEAREST
            )

        valid_mask = cv2.bitwise_and(mask, reference_mask)
        valid_mask = cv2.erode(valid_mask, np.ones((3, 3), np.uint8), iterations=1)
        valid = valid_mask > 0
        if np.count_nonzero(valid) < 10:
            return 1.0, {"pixel_change": 1.0, "edge_change": 1.0}

        current_lab = cv2.cvtColor(
            cv2.GaussianBlur(crop, (5, 5), 0), cv2.COLOR_BGR2LAB
        ).astype(np.float32)
        reference_lab = cv2.cvtColor(
            cv2.GaussianBlur(reference, (5, 5), 0), cv2.COLOR_BGR2LAB
        ).astype(np.float32)
        color_delta = np.linalg.norm(current_lab - reference_lab, axis=2)
        pixel_change = float(np.mean(color_delta[valid]) / (255.0 * np.sqrt(3.0)))

        current_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        reference_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
        current_edges = cv2.Canny(current_gray, 50, 150)
        reference_edges = cv2.Canny(reference_gray, 50, 150)
        edge_delta = cv2.absdiff(current_edges, reference_edges)
        edge_change = float(np.count_nonzero(edge_delta[valid]) / np.count_nonzero(valid))

        pixel_score = min(1.0, pixel_change / max(self.background_difference_threshold, 1e-6))
        edge_score = min(1.0, edge_change / max(self.edge_threshold * 2, 1e-6))
        score = float(np.clip(0.8 * pixel_score + 0.2 * edge_score, 0.0, 1.0))
        return score, {
            "pixel_change": round(pixel_change, 4),
            "edge_change": round(edge_change, 4),
        }
