"""Parking occupancy pipeline for fixed-camera real-world video."""

import os
import time
from typing import Dict, Iterable, List, Optional, Tuple

import cv2
import numpy as np

from src.detector import DetectorUnavailable, VehicleDetector
from src.pathfinder import ParkingGraph
from src.slot_analyzer import SlotAnalyzer
from src.slot_classifier import SlotClassifier
from src.stabilizer import FrameStabilizer


class ParkingPipeline:
    """
    Fuse per-slot empty-reference change with optional vehicle detections.

    The pipeline fails safe: an uncalibrated or uncertain slot is `unknown`
    and is never offered as a vacant destination.
    """

    def __init__(
        self,
        config: Dict,
        device: str = "auto",
        model_name: Optional[str] = None,
    ):
        self.config = config
        self.slots_config = config["slots"]
        inference = config.get("inference", {})
        self.mode = inference.get("mode", "hybrid")

        appearance_cfg = inference.get("appearance", config.get("model", {}))
        self.appearance_enabled = appearance_cfg.get(
            "enabled", self.mode in {"hybrid", "appearance"}
        )
        self.appearance_occupied_threshold = appearance_cfg.get(
            "occupied_threshold",
            appearance_cfg.get("combined_score_threshold", 0.58),
        )
        self.appearance_vacant_threshold = appearance_cfg.get("vacant_threshold", 0.30)
        self.allow_uncalibrated_vacant = appearance_cfg.get(
            "allow_uncalibrated_vacant", False
        )
        self.analyzer = SlotAnalyzer(
            slots=self.slots_config,
            edge_threshold=appearance_cfg.get("edge_threshold", 0.08),
            variance_threshold=appearance_cfg.get("variance_threshold", 25.0),
            texture_threshold=appearance_cfg.get("texture_threshold", 50.0),
            combined_score_threshold=self.appearance_occupied_threshold,
            background_difference_threshold=appearance_cfg.get(
                "background_difference_threshold", 0.08
            ),
            max_reference_samples=appearance_cfg.get("max_reference_samples", 10),
        )

        detector_cfg = inference.get("detector", {})
        self.detector_occupied_threshold = detector_cfg.get(
            "overlap_occupied_threshold", 0.30
        )
        self.detector: Optional[VehicleDetector] = None
        self.detector_warning: Optional[str] = None
        detector_enabled = model_name is not None or detector_cfg.get(
            "enabled", self.mode in {"hybrid", "detector"}
        )
        if detector_enabled:
            detector_model = model_name or detector_cfg.get("model", "yolo26s.pt")
            try:
                self.detector = VehicleDetector(
                    model_name=detector_model,
                    conf_threshold=detector_cfg.get("confidence_threshold", 0.25),
                    device=detector_cfg.get("device", device),
                    imgsz=detector_cfg.get("image_size", 1280),
                    vehicle_class_ids=detector_cfg.get("vehicle_class_ids"),
                    tracking_enabled=detector_cfg.get("tracking_enabled", True),
                    tracker=detector_cfg.get("tracker", "bytetrack.yaml"),
                )
            except DetectorUnavailable as exc:
                self.detector_warning = str(exc)
                print(f"Detector disabled: {self.detector_warning}")
        self.detection_classifier = SlotClassifier(
            self.slots_config, iou_threshold=self.detector_occupied_threshold
        )

        stabilization_cfg = inference.get("stabilization", {})
        self.stabilizer = FrameStabilizer(
            method=stabilization_cfg.get("method", "hybrid"),
            motion_model=stabilization_cfg.get("motion_model", "affine"),
            temporal_smooth_window=stabilization_cfg.get("smooth_window", 5),
            enabled=stabilization_cfg.get("enabled", False),
        )
        self._stabilizer_has_reference = False

        temporal_cfg = inference.get("temporal", {})
        self.temporal_enabled = temporal_cfg.get("enabled", True)
        self.occupied_confirm_frames = temporal_cfg.get("occupied_confirm_frames", 2)
        self.vacant_confirm_frames = temporal_cfg.get("vacant_confirm_frames", 4)
        self._temporal_state: Dict[str, Dict] = {}

        self.graph = ParkingGraph(config["graph"])
        self.last_slot_statuses: List[Dict] = []
        self.last_nav_result: Dict = {}
        self.last_processing_time = 0.0

        calibration_cfg = inference.get("calibration", {})
        auto_calibration_cfg = calibration_cfg.get("automatic", {})
        self.auto_calibration_enabled = auto_calibration_cfg.get("enabled", True)
        self.auto_calibration_min_samples = auto_calibration_cfg.get("min_samples", 8)
        self.auto_calibration_scan_frames = auto_calibration_cfg.get("scan_frames", 120)
        self.auto_calibration_require_detector = auto_calibration_cfg.get(
            "require_detector", True
        )
        self._confirmed_calibrated_slots = set()
        self._automatic_sample_counts = {
            slot["id"]: 0 for slot in self.slots_config
        }
        reference_path = calibration_cfg.get("reference_image")
        if reference_path:
            self._load_reference(reference_path)
        for reference in calibration_cfg.get("references", []):
            self._load_reference(
                reference.get("image", ""),
                slot_ids=reference.get("slot_ids"),
                append=True,
            )

    @property
    def calibrated_slots(self) -> List[str]:
        return sorted(self._confirmed_calibrated_slots)

    def _load_reference(
        self,
        reference_path: str,
        slot_ids: Optional[Iterable[str]] = None,
        append: bool = False,
    ):
        if not reference_path or not os.path.exists(reference_path):
            return
        reference_frame = cv2.imread(reference_path)
        if reference_frame is not None:
            self.calibrate(reference_frame, slot_ids=slot_ids, append=append)

    def calibrate(
        self,
        empty_frame: np.ndarray,
        slot_ids: Optional[Iterable[str]] = None,
        append: bool = False,
    ) -> List[str]:
        """Register empty appearances for all or selected slots."""
        self.analyzer.set_reference_frame(empty_frame, slot_ids, append=append)
        selected_slots = slot_ids or [slot["id"] for slot in self.slots_config]
        self._confirmed_calibrated_slots.update(selected_slots)
        if self.stabilizer.enabled:
            self.stabilizer.set_reference(empty_frame)
            self._stabilizer_has_reference = True
        self._temporal_state.clear()
        return self.calibrated_slots

    def auto_calibrate_video(self, video_path: str, max_samples: Optional[int] = None) -> Dict:
        """
        Learn empty references from a video without requiring an all-empty frame.

        A slot contributes reference samples only on frames where the vehicle
        detector does not overlap that slot. Slots never observed clear remain
        uncalibrated and cannot be routed to as vacant.
        """
        report = {
            "enabled": self.auto_calibration_enabled,
            "calibrated_slots": self.calibrated_slots,
            "sample_counts": dict(self._automatic_sample_counts),
            "warning": None,
        }
        if not self.auto_calibration_enabled:
            report["warning"] = "Automatic calibration is disabled."
            return report
        if self.auto_calibration_require_detector and self.detector is None:
            report["warning"] = (
                "Automatic calibration requires an active vehicle detector; "
                "install/configure Ultralytics or calibrate selected empty slots manually."
            )
            return report

        capture = cv2.VideoCapture(video_path)
        if not capture.isOpened():
            report["warning"] = f"Could not open video for calibration: {video_path}"
            return report
        frame_total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        sample_limit = max_samples or self.auto_calibration_scan_frames
        sample_limit = max(1, sample_limit)
        frame_step = max(1, frame_total // sample_limit) if frame_total > 0 else 1
        frame_index = 0
        sampled_frames = 0
        while sampled_frames < sample_limit:
            if frame_total > 0:
                capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            success, frame = capture.read()
            if not success:
                break
            analysis_frame = self._stabilize(frame)
            detections = self._detect(analysis_frame)
            detection_results = (
                self.detection_classifier.classify(detections) if detections else []
            )
            self._collect_automatic_references(analysis_frame, detection_results)
            sampled_frames += 1
            frame_index += frame_step
            if len(self.calibrated_slots) == len(self.slots_config):
                break
        capture.release()
        self._temporal_state.clear()
        report.update(
            {
                "calibrated_slots": self.calibrated_slots,
                "sample_counts": dict(self._automatic_sample_counts),
                "sampled_frames": sampled_frames,
                "complete": len(self.calibrated_slots) == len(self.slots_config),
            }
        )
        return report

    def process_frame(
        self,
        frame: np.ndarray,
        start_node: str = "E1",
        user_position: Optional[Tuple[float, float]] = None,
    ) -> Dict:
        started = time.perf_counter()
        analysis_frame = self._stabilize(frame)

        detections = self._detect(analysis_frame)
        detection_results = (
            self.detection_classifier.classify(detections) if detections else []
        )
        self._collect_automatic_references(analysis_frame, detection_results)
        appearance_results = (
            self.analyzer.classify_all(analysis_frame) if self.appearance_enabled else []
        )
        raw_statuses = self._fuse_statuses(appearance_results, detection_results)
        slot_statuses = self._apply_temporal_hysteresis(raw_statuses)

        start = start_node
        if user_position:
            start = self._create_temporary_node(user_position)
        vacant_ids = [
            slot["id"] for slot in slot_statuses if slot["status"] == "vacant"
        ]
        nav_result = self.graph.find_nearest_vacant(start, vacant_ids)
        if user_position and start.startswith("TEMP_"):
            self._remove_temporary_node(start)

        processing_time_ms = (time.perf_counter() - started) * 1000
        annotated = self.annotate_frame(
            analysis_frame.copy(), slot_statuses, nav_result, detections
        )
        self.last_slot_statuses = slot_statuses
        self.last_nav_result = nav_result
        self.last_processing_time = processing_time_ms

        occupied = sum(1 for slot in slot_statuses if slot["status"] == "occupied")
        vacant = sum(1 for slot in slot_statuses if slot["status"] == "vacant")
        unknown = len(slot_statuses) - occupied - vacant
        return {
            "detections": detections,
            "slot_statuses": slot_statuses,
            "navigation": nav_result,
            "processing_time_ms": round(processing_time_ms, 2),
            "annotated_frame": annotated,
            "summary": {
                "total_slots": len(slot_statuses),
                "occupied": occupied,
                "vacant": vacant,
                "unknown": unknown,
                "target_slot": nav_result.get("target_slot"),
                "distance": nav_result.get("distance"),
                "calibrated_slots": len(self.calibrated_slots),
            },
            "diagnostics": {
                "mode": self.mode,
                "detector_active": self.detector is not None,
                "detector_warning": self.detector_warning,
                "calibrated_slots": self.calibrated_slots,
                "automatic_sample_counts": dict(self._automatic_sample_counts),
            },
        }

    def _stabilize(self, frame: np.ndarray) -> np.ndarray:
        if not self.stabilizer.enabled:
            return frame
        if not self._stabilizer_has_reference:
            self.stabilizer.set_reference(frame)
            self._stabilizer_has_reference = True
            return frame
        return self.stabilizer.stabilize(frame)

    def _detect(self, frame: np.ndarray) -> List[Dict]:
        if self.detector is None:
            return []
        try:
            return self.detector.detect(frame)
        except Exception as exc:
            self.detector_warning = f"Detector inference failed: {exc}"
            print(self.detector_warning)
            self.detector = None
            return []

    def _collect_automatic_references(
        self, frame: np.ndarray, detection_results: List[Dict]
    ):
        if not self.auto_calibration_enabled:
            return
        if self.auto_calibration_require_detector and self.detector is None:
            return
        detector_scores = {
            result["id"]: float(result.get("iou", 0.0))
            for result in detection_results
        }
        candidates = []
        for slot in self.slots_config:
            slot_id = slot["id"]
            if slot_id in self._confirmed_calibrated_slots:
                continue
            if detector_scores.get(slot_id, 0.0) >= self.detector_occupied_threshold:
                continue
            candidates.append(slot_id)
        if not candidates:
            return
        self.analyzer.set_reference_frame(frame, candidates, append=True)
        for slot_id in candidates:
            self._automatic_sample_counts[slot_id] += 1
            if self._automatic_sample_counts[slot_id] >= self.auto_calibration_min_samples:
                self._confirmed_calibrated_slots.add(slot_id)

    def _fuse_statuses(
        self, appearance_results: List[Dict], detection_results: List[Dict]
    ) -> List[Dict]:
        appearance_by_id = {item["id"]: item for item in appearance_results}
        detections_by_id = {item["id"]: item for item in detection_results}
        fused = []
        for slot in self.slots_config:
            slot_id = slot["id"]
            appearance = appearance_by_id.get(slot_id, {})
            detection_score = detections_by_id.get(slot_id, {}).get("iou", 0.0)
            appearance_score = float(appearance.get("score", 0.0))
            calibrated = slot_id in self._confirmed_calibrated_slots
            detector_positive = detection_score >= self.detector_occupied_threshold
            combined_score = 1.0 - (1.0 - appearance_score) * (1.0 - detection_score)

            if detector_positive:
                status = "occupied"
                evidence = "vehicle_detector"
            elif self.appearance_enabled and calibrated:
                if appearance_score >= self.appearance_occupied_threshold:
                    status = "occupied"
                elif appearance_score <= self.appearance_vacant_threshold:
                    status = "vacant"
                else:
                    status = "unknown"
                evidence = "empty_reference"
            elif self.allow_uncalibrated_vacant and self.appearance_enabled:
                status = appearance.get("status", "unknown")
                evidence = "uncalibrated_features"
            else:
                status = "unknown"
                evidence = "uncalibrated"

            fused.append(
                {
                    "id": slot_id,
                    "status": status,
                    "raw_status": status,
                    "score": round(combined_score, 4),
                    "appearance_score": round(appearance_score, 4),
                    "detector_score": round(float(detection_score), 4),
                    "calibrated": calibrated,
                    "evidence": evidence,
                    "features": appearance.get("features", {}),
                    "polygon": slot["polygon"],
                }
            )
        return fused

    def _apply_temporal_hysteresis(self, statuses: List[Dict]) -> List[Dict]:
        if not self.temporal_enabled:
            return statuses
        stabilized = []
        for slot in statuses:
            slot_id = slot["id"]
            raw_status = slot["raw_status"]
            state = self._temporal_state.setdefault(
                slot_id, {"status": "unknown", "candidate": None, "count": 0}
            )

            if raw_status == "unknown":
                if state["status"] == "vacant":
                    state["status"] = "unknown"
                state["candidate"] = None
                state["count"] = 0
            elif raw_status == state["status"]:
                state["candidate"] = None
                state["count"] = 0
            else:
                if state["candidate"] == raw_status:
                    state["count"] += 1
                else:
                    state["candidate"] = raw_status
                    state["count"] = 1
                required = (
                    self.occupied_confirm_frames
                    if raw_status == "occupied"
                    else self.vacant_confirm_frames
                )
                if state["count"] >= required:
                    state["status"] = raw_status
                    state["candidate"] = None
                    state["count"] = 0

            result = slot.copy()
            result["status"] = state["status"]
            result["pending_status"] = state["candidate"]
            result["pending_frames"] = state["count"]
            stabilized.append(result)
        return stabilized

    def annotate_frame(
        self, frame: np.ndarray, slot_statuses: List[Dict], nav_result: Dict, detections: List[Dict]
    ) -> np.ndarray:
        target_slot = nav_result.get("target_slot")
        for detection in detections:
            x1, y1, x2, y2 = map(int, detection["bbox"])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 165, 0), 2)
            cv2.putText(
                frame,
                f"{detection['class_name']} {detection['confidence']:.2f}",
                (x1, max(16, y1 - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 165, 0),
                1,
            )

        for slot in slot_statuses:
            points = np.array(slot["polygon"], dtype=np.int32)
            if slot["id"] == target_slot:
                color, thickness = (0, 255, 255), 3
            elif slot["status"] == "occupied":
                color, thickness = (0, 0, 255), 2
            elif slot["status"] == "vacant":
                color, thickness = (0, 255, 0), 2
            else:
                color, thickness = (128, 128, 128), 2
            cv2.polylines(frame, [points], True, color, thickness)
            overlay = frame.copy()
            cv2.fillPoly(overlay, [points], color)
            cv2.addWeighted(
                overlay, 0.30 if slot["id"] == target_slot else 0.15, frame, 0.70 if slot["id"] == target_slot else 0.85, 0, frame
            )
            center = np.mean(points, axis=0).astype(int)
            label = slot["id"] + (" ?" if slot["status"] == "unknown" else "")
            cv2.putText(
                frame, label, (center[0] - 12, center[1] + 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1
            )

        occupied = sum(1 for item in slot_statuses if item["status"] == "occupied")
        vacant = sum(1 for item in slot_statuses if item["status"] == "vacant")
        unknown = len(slot_statuses) - occupied - vacant
        cv2.putText(
            frame, f"Vacant: {vacant}/{len(slot_statuses)}  Uncertain: {unknown}", (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2
        )
        if target_slot:
            cv2.putText(
                frame, f"Go to: {target_slot} ({nav_result.get('distance', '?')}m)", (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2
            )
        return frame

    def _create_temporary_node(self, position: Tuple[float, float]) -> str:
        node_id = f"TEMP_{id(position)}"
        self.graph.nodes[node_id] = {
            "id": node_id, "type": "waypoint", "x": position[0], "y": position[1]
        }
        self.graph.adjacency[node_id] = []
        for other_id, node in self.graph.nodes.items():
            if other_id != node_id and not other_id.startswith("TEMP_"):
                distance = np.hypot(node["x"] - position[0], node["y"] - position[1])
                weight = round(distance * 0.05, 1)
                self.graph.adjacency[node_id].append((other_id, weight))
                self.graph.adjacency[other_id].append((node_id, weight))
        return node_id

    def _remove_temporary_node(self, node_id: str):
        if node_id not in self.graph.nodes:
            return
        for neighbor, _ in self.graph.adjacency[node_id]:
            self.graph.adjacency[neighbor] = [
                (identifier, weight)
                for identifier, weight in self.graph.adjacency[neighbor]
                if identifier != node_id
            ]
        del self.graph.adjacency[node_id]
        del self.graph.nodes[node_id]
