"""Ultralytics vehicle detector with optional video tracking."""

from typing import Dict, Iterable, List, Optional

import numpy as np


VEHICLE_LABELS = {
    "car",
    "truck",
    "bus",
    "van",
    "vehicle",
    "motorcycle",
    "motorbike",
}


class DetectorUnavailable(RuntimeError):
    """Raised when optional object detection cannot be initialized."""


class VehicleDetector:
    """Run an Ultralytics detector with class discovery and CPU fallback."""

    def __init__(
        self,
        model_name: str = "yolo26s.pt",
        conf_threshold: float = 0.25,
        device: str = "auto",
        imgsz: int = 1280,
        vehicle_class_ids: Optional[Iterable[int]] = None,
        tracking_enabled: bool = True,
        tracker: str = "bytetrack.yaml",
    ):
        try:
            import torch
            from ultralytics import YOLO
        except ImportError as exc:
            raise DetectorUnavailable(
                "Ultralytics is not installed; continuing without detector evidence."
            ) from exc

        self.device = (
            "cuda"
            if device == "auto" and torch.cuda.is_available()
            else "cpu"
            if device == "auto"
            else device
        )
        try:
            self.model = YOLO(model_name)
        except Exception as exc:
            raise DetectorUnavailable(
                f"Could not load detector model '{model_name}': {exc}"
            ) from exc
        self.conf_threshold = conf_threshold
        self.imgsz = imgsz
        self.tracking_enabled = tracking_enabled
        self.tracker = tracker
        self.class_mapping = self._resolve_classes(vehicle_class_ids)
        self.vehicle_class_ids = sorted(self.class_mapping.keys())
        if not self.vehicle_class_ids:
            raise DetectorUnavailable(
                f"Model '{model_name}' exposes no configured vehicle classes."
            )
        print(
            f"Loaded detector {model_name} on {self.device}; "
            f"classes={self.vehicle_class_ids}"
        )

    def _resolve_classes(self, configured_ids: Optional[Iterable[int]]) -> Dict[int, str]:
        model_names = self.model.names
        if isinstance(model_names, list):
            model_names = dict(enumerate(model_names))
        if configured_ids is not None:
            return {
                int(class_id): str(model_names.get(int(class_id), "vehicle"))
                for class_id in configured_ids
            }
        return {
            int(class_id): str(label)
            for class_id, label in model_names.items()
            if str(label).lower() in VEHICLE_LABELS
        }

    def detect(self, frame: np.ndarray) -> List[Dict]:
        inference_args = {
            "source": frame,
            "conf": self.conf_threshold,
            "classes": self.vehicle_class_ids,
            "device": self.device,
            "imgsz": self.imgsz,
            "verbose": False,
        }
        if self.tracking_enabled:
            results = self.model.track(
                **inference_args, persist=True, tracker=self.tracker
            )
        else:
            results = self.model.predict(**inference_args)
        detections = []
        for result in results:
            if result.boxes is None:
                continue
            for detected_box in result.boxes:
                class_id = int(detected_box.cls[0])
                if class_id not in self.vehicle_class_ids:
                    continue
                confidence = float(detected_box.conf[0])
                x1, y1, x2, y2 = detected_box.xyxy[0].cpu().numpy().tolist()
                detections.append(
                    {
                        "bbox": [x1, y1, x2, y2],
                        "confidence": confidence,
                        "class_id": class_id,
                        "class_name": self.class_mapping[class_id],
                        "track_id": (
                            int(detected_box.id[0])
                            if detected_box.id is not None
                            else None
                        ),
                    }
                )
        return detections
