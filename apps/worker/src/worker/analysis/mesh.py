"""Face mesh and lip landmark extraction for mouth openness and active speaker detection."""
from dataclasses import dataclass

import numpy as np
import structlog

logger = structlog.get_logger()


@dataclass
class MouthFeatures:
    """Extracted lip and mouth kinematics for a face track."""
    openness: float  # Normalized vertical opening [0.0, 1.0]
    aspect_ratio: float  # Height to width ratio
    variance: float = 0.0  # Temporal variance (movement energy)


class MouthOpennessExtractor:
    """Extracts mouth openness using MediaPipe Face Mesh on cropped/full frames."""

    def __init__(self, max_num_faces: int = 4, min_detection_confidence: float = 0.4):
        self.max_num_faces = max_num_faces
        self.min_detection_confidence = min_detection_confidence
        self._mesh = None
        self._init_mesh()

    def _init_mesh(self) -> None:
        try:
            import mediapipe as mp
            if hasattr(mp, "solutions") and hasattr(mp.solutions, "face_mesh"):
                self._mesh = mp.solutions.face_mesh.FaceMesh(
                    max_num_faces=self.max_num_faces,
                    refine_landmarks=True,
                    min_detection_confidence=self.min_detection_confidence,
                    min_tracking_confidence=self.min_detection_confidence,
                )
        except Exception as e:
            logger.info("MediaPipe FaceMesh not initialized, using optical flow fallback", error=str(e))
            self._mesh = None

    def compute_mouth_openness(self, frame_crop: np.ndarray) -> float:
        """
        Compute normalized mouth openness ratio [0.0, 1.0] for a face crop.
        Upper lip inner index: 13, Lower lip inner index: 14, Lip corners: 78, 308.
        """
        if frame_crop is None or frame_crop.size == 0:
            return 0.0

        if self._mesh is None:
            # Simple brightness/edge variance fallback on mouth region
            h, w = frame_crop.shape[:2]
            mouth_region = frame_crop[int(h * 0.65):int(h * 0.95), int(w * 0.25):int(w * 0.75)]
            if mouth_region.size > 0:
                std = float(np.std(mouth_region))
                return min(1.0, std / 64.0)
            return 0.0

        try:
            import cv2
            rgb = cv2.cvtColor(frame_crop, cv2.COLOR_BGR2RGB) if len(frame_crop.shape) == 3 else frame_crop
            results = self._mesh.process(rgb)

            if not results or not results.multi_face_landmarks:
                return 0.0

            landmarks = results.multi_face_landmarks[0].landmark
            # Key indices for inner lip distance
            # Top inner: 13, Bottom inner: 14, Left corner: 78, Right corner: 308
            p_top = np.array([landmarks[13].x, landmarks[13].y])
            p_bot = np.array([landmarks[14].x, landmarks[14].y])
            p_left = np.array([landmarks[78].x, landmarks[78].y])
            p_right = np.array([landmarks[308].x, landmarks[308].y])

            vertical_dist = float(np.linalg.norm(p_top - p_bot))
            horizontal_dist = float(np.linalg.norm(p_left - p_right))

            if horizontal_dist > 1e-4:
                # Mouth Aspect Ratio (MAR)
                mar = vertical_dist / horizontal_dist
                # Normalize typical speaking MAR (0.02 - 0.35) into [0.0, 1.0]
                return float(np.clip(mar * 3.0, 0.0, 1.0))
            return 0.0
        except Exception:
            return 0.0

    def close(self) -> None:
        if self._mesh and hasattr(self._mesh, "close"):
            try:
                self._mesh.close()
            except Exception:
                pass
            self._mesh = None
