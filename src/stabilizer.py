"""
Video Frame Stabilizer for Parking Lot Cameras.

Compensates for camera shake / vibration / slight viewpoint shifts
using a multi-strategy approach:

    1. ECC (Enhanced Correlation Coefficient) alignment — affine or
       euclidean transform to align each frame to a reference.
    2. Feature-based alignment — ORB keypoints + homography estimation
       for larger shifts.
    3. Temporal smoothing — rolling average of transform parameters
       to avoid jitter in the stabilized output.

Usage in the pipeline:
    stabilizer = FrameStabilizer(method='ecc')
    stabilizer.set_reference(first_frame)
    stabilized = stabilizer.stabilize(current_frame)

This module addresses the key limitation that the current system
only works reliably with static, non-shaking cameras.
"""

import cv2
import numpy as np
from typing import Optional, Tuple, List
from collections import deque


class FrameStabilizer:
    """
    Stabilizes video frames by aligning them to a reference frame.

    Supports multiple alignment strategies:
        - 'ecc': ECC-based affine/euclidean alignment (best for small jitter)
        - 'feature': ORB feature matching + homography (best for larger shifts)
        - 'hybrid': Try ECC first, fall back to feature matching if it fails

    Also applies temporal smoothing to the transform matrix to reduce
    frame-to-frame jitter in the stabilized output.
    """

    def __init__(self, method: str = "hybrid",
                 motion_model: str = "affine",
                 temporal_smooth_window: int = 5,
                 ecc_max_iterations: int = 100,
                 ecc_epsilon: float = 1e-5,
                 feature_max_features: int = 500,
                 feature_match_ratio: float = 0.75,
                 enabled: bool = True):
        """
        Args:
            method: 'ecc', 'feature', or 'hybrid'.
            motion_model: 'affine', 'euclidean', or 'homography'.
            temporal_smooth_window: Number of frames for rolling average.
            ecc_max_iterations: Max iterations for ECC convergence.
            ecc_epsilon: ECC convergence threshold.
            feature_max_features: Max ORB keypoints to detect.
            feature_match_ratio: Lowe's ratio test threshold.
            enabled: If False, passthrough without any stabilization.
        """
        self.method = method
        self.motion_model = motion_model
        self.temporal_smooth_window = temporal_smooth_window
        self.ecc_max_iterations = ecc_max_iterations
        self.ecc_epsilon = ecc_epsilon
        self.feature_max_features = feature_max_features
        self.feature_match_ratio = feature_match_ratio
        self.enabled = enabled

        # Reference frame (grayscale)
        self._ref_gray: Optional[np.ndarray] = None
        self._ref_frame: Optional[np.ndarray] = None

        # ORB detector for feature-based alignment
        self._orb = cv2.ORB_create(nfeatures=feature_max_features)
        self._bf_matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

        # Reference keypoints/descriptors (cached)
        self._ref_kp = None
        self._ref_desc = None

        # Transform history for temporal smoothing
        self._transform_history: deque = deque(maxlen=temporal_smooth_window)

        # ECC motion type flag
        if motion_model == "euclidean":
            self._ecc_motion = cv2.MOTION_EUCLIDEAN
        elif motion_model == "affine":
            self._ecc_motion = cv2.MOTION_AFFINE
        else:
            self._ecc_motion = cv2.MOTION_HOMOGRAPHY

        # Statistics
        self.total_frames = 0
        self.ecc_successes = 0
        self.feature_successes = 0
        self.failures = 0

    def set_reference(self, frame: np.ndarray):
        """
        Set the reference frame that all future frames will be aligned to.

        Should be called once with a clean, stable frame (e.g., first frame
        or a known-good frame from the video).

        Args:
            frame: BGR image to use as the alignment reference.
        """
        self._ref_frame = frame.copy()
        self._ref_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Pre-compute reference ORB features
        self._ref_kp, self._ref_desc = self._orb.detectAndCompute(
            self._ref_gray, None)

        # Clear transform history
        self._transform_history.clear()

    def stabilize(self, frame: np.ndarray) -> np.ndarray:
        """
        Stabilize a frame by aligning it to the reference.

        Args:
            frame: BGR input frame.

        Returns:
            Stabilized BGR frame (same size as input).
        """
        if not self.enabled or self._ref_gray is None:
            return frame

        self.total_frames += 1
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = frame.shape[:2]

        transform = None

        if self.method == "ecc":
            transform = self._align_ecc(gray)
        elif self.method == "feature":
            transform = self._align_features(gray)
        elif self.method == "hybrid":
            # Try ECC first (faster, more precise for small shifts)
            transform = self._align_ecc(gray)
            if transform is None:
                # Fall back to feature matching
                transform = self._align_features(gray)

        if transform is None:
            self.failures += 1
            return frame  # Return original if alignment fails

        # Apply temporal smoothing
        smoothed = self._smooth_transform(transform)

        # Warp the frame
        if smoothed.shape == (3, 3):
            stabilized = cv2.warpPerspective(frame, smoothed, (w, h),
                                              flags=cv2.INTER_LINEAR,
                                              borderMode=cv2.BORDER_REPLICATE)
        else:
            stabilized = cv2.warpAffine(frame, smoothed, (w, h),
                                         flags=cv2.INTER_LINEAR,
                                         borderMode=cv2.BORDER_REPLICATE)

        return stabilized

    def _align_ecc(self, gray: np.ndarray) -> Optional[np.ndarray]:
        """
        Align using Enhanced Correlation Coefficient (ECC).

        Best for small camera jitter / vibration.
        Fast and sub-pixel accurate.
        """
        try:
            if self.motion_model == "homography":
                warp_matrix = np.eye(3, 3, dtype=np.float32)
            else:
                warp_matrix = np.eye(2, 3, dtype=np.float32)

            criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
                        self.ecc_max_iterations, self.ecc_epsilon)

            _, warp_matrix = cv2.findTransformECC(
                self._ref_gray, gray, warp_matrix,
                self._ecc_motion, criteria,
                inputMask=None, gaussFiltSize=5
            )

            self.ecc_successes += 1
            return warp_matrix

        except cv2.error:
            return None

    def _align_features(self, gray: np.ndarray) -> Optional[np.ndarray]:
        """
        Align using ORB feature matching + RANSAC.

        More robust for larger shifts but noisier for small jitter.
        """
        if self._ref_desc is None or self._ref_kp is None:
            return None

        kp, desc = self._orb.detectAndCompute(gray, None)
        if desc is None or len(kp) < 4:
            return None

        # Match features using KNN
        matches = self._bf_matcher.knnMatch(self._ref_desc, desc, k=2)

        # Apply Lowe's ratio test
        good_matches = []
        for m_group in matches:
            if len(m_group) == 2:
                m, n = m_group
                if m.distance < self.feature_match_ratio * n.distance:
                    good_matches.append(m)

        if len(good_matches) < 4:
            return None

        # Extract matched point coordinates
        src_pts = np.float32([
            self._ref_kp[m.queryIdx].pt for m in good_matches
        ]).reshape(-1, 1, 2)
        dst_pts = np.float32([
            kp[m.trainIdx].pt for m in good_matches
        ]).reshape(-1, 1, 2)

        if self.motion_model == "homography":
            H, mask = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)
            if H is not None:
                self.feature_successes += 1
                return H
        else:
            # Estimate affine transform
            M, mask = cv2.estimateAffine2D(dst_pts, src_pts,
                                            method=cv2.RANSAC,
                                            ransacReprojThreshold=5.0)
            if M is not None:
                self.feature_successes += 1
                return M

        return None

    def _smooth_transform(self, transform: np.ndarray) -> np.ndarray:
        """
        Apply temporal smoothing via rolling average of transform matrices.

        Reduces frame-to-frame jitter in the stabilized output.
        """
        self._transform_history.append(transform.copy())

        if len(self._transform_history) == 1:
            return transform

        # Average all transforms in history
        stacked = np.stack(list(self._transform_history), axis=0)
        smoothed = np.mean(stacked, axis=0)

        return smoothed.astype(np.float32)

    def transform_point(self, point: Tuple[float, float],
                        transform: Optional[np.ndarray] = None) -> Tuple[float, float]:
        """
        Transform a point from the original frame coordinates to
        stabilized frame coordinates.

        Useful for mapping slot polygon points after stabilization.

        Args:
            point: (x, y) in original frame.
            transform: Warp matrix (uses latest smoothed if None).

        Returns:
            (x', y') in stabilized frame.
        """
        if transform is None:
            if not self._transform_history:
                return point
            stacked = np.stack(list(self._transform_history), axis=0)
            transform = np.mean(stacked, axis=0).astype(np.float32)

        pt = np.array([point[0], point[1], 1.0], dtype=np.float32)

        if transform.shape == (3, 3):
            result = transform @ pt
            return (result[0] / result[2], result[1] / result[2])
        else:
            result = transform @ pt
            return (result[0], result[1])

    def get_stats(self) -> dict:
        """Return stabilization statistics."""
        return {
            "total_frames": self.total_frames,
            "ecc_successes": self.ecc_successes,
            "feature_successes": self.feature_successes,
            "failures": self.failures,
            "success_rate": (
                (self.ecc_successes + self.feature_successes) /
                max(self.total_frames, 1)
            ),
        }

    def reset(self):
        """Reset the stabilizer state (clear reference and history)."""
        self._ref_gray = None
        self._ref_frame = None
        self._ref_kp = None
        self._ref_desc = None
        self._transform_history.clear()
        self.total_frames = 0
        self.ecc_successes = 0
        self.feature_successes = 0
        self.failures = 0
