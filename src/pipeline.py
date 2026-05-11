"""
End-to-end pipeline using direct slot image analysis.

Replaces the YOLO-based detection approach with direct per-slot
image analysis using classical CV features (edges, texture, color).
This is much more reliable for overhead fixed-camera parking lots.
"""

import cv2
import numpy as np
import time
from typing import Dict, List, Optional, Tuple, Any

from src.slot_analyzer import SlotAnalyzer
from src.pathfinder import ParkingGraph
from shapely.geometry import Polygon, Point


class ParkingPipeline:
    """Full parking lot occupancy detection and navigation pipeline."""

    def __init__(self, config: Dict, device: str = "cpu"):
        """
        Initialize the parking pipeline.

        Args:
            config: Parking lot configuration dict.
            device: Ignored (no GPU needed), kept for API compatibility.
        """
        analysis_cfg = config.get("model", {})
        edge_thresh = analysis_cfg.get("edge_threshold", 0.08)
        variance_thresh = analysis_cfg.get("variance_threshold", 25.0)
        texture_thresh = analysis_cfg.get("texture_threshold", 50.0)
        score_thresh = analysis_cfg.get("combined_score_threshold", 0.45)

        self.analyzer = SlotAnalyzer(
            slots=config["slots"],
            edge_threshold=edge_thresh,
            variance_threshold=variance_thresh,
            texture_threshold=texture_thresh,
            combined_score_threshold=score_thresh,
            use_adaptive=True,
        )
        self.graph = ParkingGraph(config["graph"])
        self.config = config

        # Cache latest results
        self.last_slot_statuses = []
        self.last_nav_result = {}
        self.last_processing_time = 0.0

        # Calibration state
        self._calibrated = False
        self._calibration_frames = 0
        self._max_calibration_frames = 5  # Auto-calibrate from first N frames

    def process_frame(self, frame: np.ndarray,
                      start_node: str = "E1",
                      user_position: Optional[Tuple[float, float]] = None) -> Dict:
        """
        Process a single frame through the full pipeline.

        Args:
            frame: BGR image (numpy array, HxWx3).
            start_node: Starting node for navigation.
            user_position: Optional (x, y) click position from user.

        Returns:
            Dict with slot_statuses, navigation, annotated_frame, etc.
        """
        t_start = time.perf_counter()

        # Auto-calibrate from first few frames if no baseline exists
        if not self._calibrated and self._calibration_frames < self._max_calibration_frames:
            self._calibration_frames += 1
            if self._calibration_frames == 1:
                # Use first frame as initial baseline (assume we need it)
                # The analyzer will work with absolute thresholds if no baseline set
                pass

        # Step 1: Classify all slots directly from the frame
        slot_statuses = self.analyzer.classify_all(frame)

        # Step 2: Navigation
        start = start_node
        if user_position:
            start = self._create_temporary_node(user_position)

        vacant_ids = [s["id"] for s in slot_statuses if s["status"] == "vacant"]
        nav_result = self.graph.find_nearest_vacant(start, vacant_ids)

        # Clean temp node if created
        if user_position and start.startswith("TEMP_"):
            self._remove_temporary_node(start)

        t_end = time.perf_counter()
        processing_time_ms = (t_end - t_start) * 1000

        # Annotation
        annotated = self.annotate_frame(
            frame.copy(), slot_statuses, nav_result
        )

        self.last_slot_statuses = slot_statuses
        self.last_nav_result = nav_result
        self.last_processing_time = processing_time_ms

        occupied_count = sum(1 for s in slot_statuses if s["status"] == "occupied")
        total_count = len(slot_statuses)
        vacant_count = total_count - occupied_count

        return {
            "detections": [],  # No vehicle detections (direct analysis)
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

    def annotate_frame(self, frame, slot_statuses, nav_result):
        """Draw slot overlays and navigation info on the frame."""
        target_slot = nav_result.get("target_slot")

        for slot in slot_statuses:
            pts = np.array(slot["polygon"], dtype=np.int32)

            if slot["id"] == target_slot:
                color = (0, 255, 255)  # yellow
                thickness = 3
            elif slot["status"] == "occupied":
                color = (0, 0, 255)  # red
                thickness = 2
            else:
                color = (0, 255, 0)  # green
                thickness = 2

            # Draw polygon outline
            cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=thickness)

            # Semi-transparent fill
            overlay = frame.copy()
            cv2.fillPoly(overlay, [pts], color)
            alpha = 0.15 if slot["id"] != target_slot else 0.3
            cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

            # Slot label
            cx = int(np.mean(pts[:, 0]))
            cy = int(np.mean(pts[:, 1]))
            cv2.putText(frame, slot["id"], (cx - 10, cy + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        # Summary text
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

    def _create_temporary_node(self, pos: Tuple[float, float]) -> str:
        """Add a temporary node at position to graph and return its ID."""
        tid = f"TEMP_{id(pos)}"
        self.graph.nodes[tid] = {"id": tid, "type": "waypoint", "x": pos[0], "y": pos[1]}
        self.graph.adjacency[tid] = []
        # Connect to all non-temp nodes (making it reachable)
        for nid, node in self.graph.nodes.items():
            if nid != tid and not nid.startswith("TEMP_"):
                dist = np.hypot(node["x"] - pos[0], node["y"] - pos[1])
                weight = dist * 0.05
                self.graph.adjacency[tid].append((nid, round(weight, 1)))
                self.graph.adjacency[nid].append((tid, round(weight, 1)))
        return tid

    def _remove_temporary_node(self, tid: str):
        """Remove a temporary node from the graph."""
        if tid in self.graph.nodes:
            for neighbor, _ in self.graph.adjacency[tid]:
                self.graph.adjacency[neighbor] = [
                    (n, w) for n, w in self.graph.adjacency[neighbor] if n != tid
                ]
            del self.graph.adjacency[tid]
            del self.graph.nodes[tid]