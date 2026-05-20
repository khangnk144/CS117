"""
End-to-end pipeline using YOLOv8 object detection.

Uses YOLOv8 to detect vehicles and computes Intersection over Area (IoA)
with parking slot polygons to determine occupancy.
"""

import cv2
import numpy as np
import time
from typing import Dict, List, Optional, Tuple

from src.detector import VehicleDetector
from src.pathfinder import ParkingGraph
from shapely.geometry import Polygon, Point


class ParkingPipeline:
    """Full parking lot occupancy detection and navigation pipeline using YOLOv8."""

    def __init__(self, config: Dict, device: str = "cuda",
                 model_name: str = "yolov8m.pt"):
        """
        Initialize the parking pipeline.

        Args:
            config: Parking lot configuration dict.
            device: 'cpu' or 'cuda' (for YOLO).
            model_name: YOLO model to use.
        """
        self.config = config
        self.slots_config = config["slots"]
        
        # Initialize YOLO detector
        self.detector = VehicleDetector(model_name=model_name, device=device)

        # Navigation graph
        self.graph = ParkingGraph(config["graph"])

        # Cache latest results
        self.last_slot_statuses = []
        self.last_nav_result = {}
        self.last_processing_time = 0.0

        # Temporal smoothing for slot statuses
        self._status_history: Dict[str, List[str]] = {}
        self._temporal_window = 3  # Number of frames to smooth over

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

        # Step 1: Detect vehicles
        detections = self.detector.detect(frame)

        # Step 2: Determine slot occupancy using IoA (Intersection over Area)
        raw_statuses = []
        for slot in self.slots_config:
            slot_poly = Polygon(slot["polygon"])
            is_occupied = False
            
            for det in detections:
                x1, y1, x2, y2 = det["bbox"]
                bbox_poly = Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])
                
                # Compute intersection
                try:
                    intersection_area = slot_poly.intersection(bbox_poly).area
                    ioa = intersection_area / slot_poly.area
                    
                    # Alternatively, check if the bottom center of the bbox is inside the slot
                    bottom_center = Point((x1 + x2) / 2, y2)
                    
                    # A slot is occupied if there's significant overlap or the vehicle's bottom center is in it
                    if ioa > 0.35 or (intersection_area > 0 and slot_poly.contains(bottom_center)):
                        is_occupied = True
                        break
                except Exception as e:
                    print(f"Error computing intersection: {e}")
            
            raw_statuses.append({
                "id": slot["id"],
                "status": "occupied" if is_occupied else "vacant",
                "polygon": slot["polygon"]
            })

        # Step 2.5: Temporal smoothing (reduces flicker)
        slot_statuses = self._apply_temporal_smoothing(raw_statuses)

        # Step 3: Navigation
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
            frame.copy(), slot_statuses, nav_result, detections
        )

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

    def _apply_temporal_smoothing(self, slot_statuses: List[Dict]) -> List[Dict]:
        """
        Apply temporal smoothing to reduce status flicker.
        """
        smoothed = []
        for slot in slot_statuses:
            sid = slot["id"]
            if sid not in self._status_history:
                self._status_history[sid] = []

            self._status_history[sid].append(slot["status"])
            if len(self._status_history[sid]) > self._temporal_window:
                self._status_history[sid].pop(0)

            # Majority vote
            history = self._status_history[sid]
            occupied_votes = sum(1 for s in history if s == "occupied")
            vacant_votes = len(history) - occupied_votes

            smoothed_status = "occupied" if occupied_votes > vacant_votes else "vacant"

            result = slot.copy()
            result["status"] = smoothed_status
            smoothed.append(result)

        return smoothed

    def annotate_frame(self, frame, slot_statuses, nav_result, detections):
        """Draw slot overlays, bounding boxes, and navigation info on the frame."""
        target_slot = nav_result.get("target_slot")

        # Draw vehicle bounding boxes
        for det in detections:
            x1, y1, x2, y2 = map(int, det["bbox"])
            conf = det["confidence"]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 165, 0), 2)  # Orange for vehicles
            cv2.putText(frame, f"{conf:.2f}", (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 165, 0), 1)

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