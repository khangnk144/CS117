"""
Lightweight CNN Parking Slot Occupancy Classifier.

A compact convolutional neural network trained on PKLotSegmented images
to classify individual parking slot crops as 'occupied' or 'empty'.

Architecture: 3 conv blocks (Conv2D → BatchNorm → ReLU → MaxPool)
followed by global average pooling and a 2-class FC head.

This classifier can replace or complement the handcrafted CV features
in SlotAnalyzer for improved generalization across weather/lighting.
"""

import os
import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple

# Try to import PyTorch; fallback gracefully if not available
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


def check_torch():
    """Raise an error if PyTorch is not installed."""
    if not TORCH_AVAILABLE:
        raise ImportError(
            "PyTorch is required for the CNN classifier. "
            "Install with: pip install torch torchvision"
        )


class ParkingSlotCNN(nn.Module if TORCH_AVAILABLE else object):
    """
    Lightweight CNN for binary parking slot classification.

    Input: 64×64 RGB image (cropped parking slot)
    Output: 2 logits (empty, occupied)

    Architecture:
        Conv2D(3→32, 3×3) → BN → ReLU → MaxPool(2×2)
        Conv2D(32→64, 3×3) → BN → ReLU → MaxPool(2×2)
        Conv2D(64→128, 3×3) → BN → ReLU → AdaptiveAvgPool(4×4)
        Flatten → FC(128*4*4 → 256) → ReLU → Dropout(0.3) → FC(256 → 2)

    Total params: ~550K — suitable for CPU inference.
    """

    def __init__(self):
        check_torch()
        super().__init__()

        self.features = nn.Sequential(
            # Block 1: 64×64 → 32×32
            nn.Conv2d(3, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),

            # Block 2: 32×32 → 16×16
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),

            # Block 3: 16×16 → adaptive 4×4
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((4, 4)),
        )

        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128 * 4 * 4, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(256, 2),
        )

    def forward(self, x):
        x = self.features(x)
        x = self.classifier(x)
        return x


class CNNSlotClassifier:
    """
    High-level wrapper for using the CNN model to classify parking slots.

    Handles:
        - Model loading (from .pth checkpoint)
        - Preprocessing (crop → resize → normalize)
        - Batch inference on all slots in a frame
        - Graceful fallback if model is not available
    """

    # Class labels matching PKLotSegmented folder structure
    CLASSES = ["empty", "occupied"]
    INPUT_SIZE = 64

    def __init__(self, model_path: Optional[str] = None,
                 device: str = "cpu",
                 confidence_threshold: float = 0.6):
        """
        Args:
            model_path: Path to trained .pth model weights.
            device: 'cpu' or 'cuda'.
            confidence_threshold: Min probability to classify as occupied.
        """
        check_torch()
        self.device = torch.device(device)
        self.confidence_threshold = confidence_threshold
        self.model = None
        self._ready = False

        if model_path and os.path.exists(model_path):
            self.load_model(model_path)

    def load_model(self, model_path: str):
        """Load model weights from a checkpoint file."""
        check_torch()
        self.model = ParkingSlotCNN()
        state = torch.load(model_path, map_location=self.device, weights_only=True)
        # Support both raw state_dict and checkpoint dict
        if isinstance(state, dict) and "model_state_dict" in state:
            self.model.load_state_dict(state["model_state_dict"])
        else:
            self.model.load_state_dict(state)
        self.model.to(self.device)
        self.model.eval()
        self._ready = True
        print(f"CNN classifier loaded from {model_path} (device: {self.device})")

    @property
    def is_ready(self) -> bool:
        return self._ready

    def preprocess(self, crop: np.ndarray) -> "torch.Tensor":
        """
        Preprocess a cropped slot image for the CNN.

        Args:
            crop: BGR image (numpy array, any size).

        Returns:
            Tensor of shape (1, 3, 64, 64), normalized to [0, 1].
        """
        # Resize to INPUT_SIZE × INPUT_SIZE
        resized = cv2.resize(crop, (self.INPUT_SIZE, self.INPUT_SIZE))
        # BGR → RGB
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        # Normalize to [0, 1]
        tensor = torch.from_numpy(rgb).float() / 255.0
        # HWC → CHW
        tensor = tensor.permute(2, 0, 1)
        # ImageNet-style normalization
        mean = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
        std = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
        tensor = (tensor - mean) / std
        return tensor.unsqueeze(0)  # Add batch dimension

    def classify_crop(self, crop: np.ndarray) -> Tuple[str, float]:
        """
        Classify a single cropped slot image.

        Args:
            crop: BGR image of a parking slot.

        Returns:
            Tuple of (status: 'occupied'/'vacant', confidence: float).
        """
        if not self._ready:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        tensor = self.preprocess(crop).to(self.device)
        with torch.no_grad():
            logits = self.model(tensor)
            probs = F.softmax(logits, dim=1)
            occupied_prob = probs[0, 1].item()  # Index 1 = occupied

        if occupied_prob >= self.confidence_threshold:
            return "occupied", occupied_prob
        else:
            return "vacant", 1.0 - occupied_prob

    def classify_all_slots(self, frame: np.ndarray,
                           slots: List[Dict]) -> List[Dict]:
        """
        Classify all slots in a frame using batched CNN inference.

        Args:
            frame: Full BGR frame from camera.
            slots: List of slot dicts with 'id', 'polygon', 'pts', 'bbox'.

        Returns:
            List of slot status dicts compatible with SlotAnalyzer output.
        """
        if not self._ready:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        fh, fw = frame.shape[:2]
        crops = []
        valid_indices = []

        for i, slot in enumerate(slots):
            x, y, w, h = slot["bbox"]
            x1 = max(0, x)
            y1 = max(0, y)
            x2 = min(fw, x + w)
            y2 = min(fh, y + h)

            if x2 <= x1 or y2 <= y1:
                continue

            crop = frame[y1:y2, x1:x2].copy()

            # Apply polygon mask to zero-out pixels outside the slot
            mask = np.zeros((y2 - y1, x2 - x1), dtype=np.uint8)
            shifted_pts = slot["pts"].copy()
            shifted_pts[:, 0] -= x1
            shifted_pts[:, 1] -= y1
            cv2.fillPoly(mask, [shifted_pts], 255)
            crop[mask == 0] = 0

            crops.append(crop)
            valid_indices.append(i)

        if not crops:
            return [{
                "id": s["id"],
                "status": "vacant",
                "score": 0.0,
                "iou": 0.0,
                "polygon": s["polygon_points"],
            } for s in slots]

        # Batch preprocess
        batch_tensors = []
        for crop in crops:
            tensor = self.preprocess(crop)
            batch_tensors.append(tensor)
        batch = torch.cat(batch_tensors, dim=0).to(self.device)

        # Batch inference
        with torch.no_grad():
            logits = self.model(batch)
            probs = F.softmax(logits, dim=1)

        # Build results
        results = []
        valid_set = set(valid_indices)
        valid_iter = iter(range(len(valid_indices)))

        for i, slot in enumerate(slots):
            if i in valid_set:
                j = next(valid_iter)
                occupied_prob = probs[j, 1].item()
                if occupied_prob >= self.confidence_threshold:
                    status = "occupied"
                    score = occupied_prob
                else:
                    status = "vacant"
                    score = 1.0 - occupied_prob
            else:
                status = "vacant"
                score = 0.0

            results.append({
                "id": slot["id"],
                "status": status,
                "score": round(score, 4),
                "iou": round(score, 4),  # Compatibility key
                "polygon": slot["polygon_points"],
                "features": {"cnn_confidence": round(score, 4)},
            })

        return results
