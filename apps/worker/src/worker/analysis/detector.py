"""Face detection interface with MediaPipe primary backend, YOLOv8 adapter, and Mock engine."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger()


@dataclass
class FaceDetection:
    """Normalized face bounding box and keypoints [0.0, 1.0]."""
    # xmin, ymin, width, height (all normalized 0.0 to 1.0)
    bbox: tuple[float, float, float, float]
    confidence: float
    # Normalized keypoints: right_eye, left_eye, nose, mouth_center, right_ear, left_ear
    keypoints: dict[str, tuple[float, float]] = field(default_factory=dict)
    # Estimated mouth openness ratio [0.0, 1.0] if available
    mouth_openness: float = 0.0

    @property
    def xmin(self) -> float:
        return self.bbox[0]

    @property
    def ymin(self) -> float:
        return self.bbox[1]

    @property
    def width(self) -> float:
        return self.bbox[2]

    @property
    def height(self) -> float:
        return self.bbox[3]

    @property
    def cx(self) -> float:
        return self.xmin + (self.width / 2.0)

    @property
    def cy(self) -> float:
        return self.ymin + (self.height / 2.0)

    @property
    def xmax(self) -> float:
        return min(1.0, self.xmin + self.width)

    @property
    def ymax(self) -> float:
        return min(1.0, self.ymin + self.height)


class BaseFaceDetector(ABC):
    """Abstract interface for face detection on RGB/BGR video frames."""

    @abstractmethod
    def detect(self, frame: np.ndarray) -> list[FaceDetection]:
        """
        Detect faces in a single frame.
        Args:
            frame: uint8 numpy image array (H, W, 3) in BGR or RGB format.
        Returns:
            List of FaceDetection objects in normalized [0, 1] coordinates.
        """
        pass

    def close(self) -> None:
        """Release any underlying model resources."""
        pass


class MediaPipeFaceDetector(BaseFaceDetector):
    """MediaPipe face detector with keypoint extraction and small face filtering."""

    def __init__(
        self,
        min_confidence: float = 0.45,
        model_selection: int = 1,  # 0 for short-range (< 2m), 1 for full-range (< 5m)
        min_face_height_pct: float = 0.04,  # ignore faces smaller than 4% of frame height
    ):
        self.min_confidence = min_confidence
        self.model_selection = model_selection
        self.min_face_height_pct = min_face_height_pct
        self._detector = None
        self._init_detector()

    def _init_detector(self) -> None:
        try:
            import mediapipe as mp
            # Support both solutions.face_detection and new tasks API if present
            if hasattr(mp, "solutions") and hasattr(mp.solutions, "face_detection"):
                self._detector = mp.solutions.face_detection.FaceDetection(
                    min_detection_confidence=self.min_confidence,
                    model_selection=self.model_selection,
                )
            else:
                logger.warning("mediapipe.solutions.face_detection not available, using fallback")
                self._detector = None
        except Exception as e:
            logger.warning("Failed to initialize MediaPipe FaceDetection, falling back", error=str(e))
            self._detector = None

    def detect(self, frame: np.ndarray) -> list[FaceDetection]:
        if frame is None or frame.size == 0:
            return []

        h, w = frame.shape[:2]
        if h == 0 or w == 0:
            return []

        if self._detector is None:
            return self._fallback_opencv_detect(frame)

        try:
            import cv2
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) if len(frame.shape) == 3 and frame.shape[2] == 3 else frame
            results = self._detector.process(rgb)

            if not results or not results.detections:
                return []

            detections: list[FaceDetection] = []
            for det in results.detections:
                score = float(det.score[0]) if det.score else 0.0
                if score < self.min_confidence:
                    continue

                bbox_rel = det.location_data.relative_bounding_box
                xmin = max(0.0, float(bbox_rel.xmin))
                ymin = max(0.0, float(bbox_rel.ymin))
                width = min(1.0 - xmin, max(0.0, float(bbox_rel.width)))
                height = min(1.0 - ymin, max(0.0, float(bbox_rel.height)))

                # Reject tiny noise faces
                if height < self.min_face_height_pct or width < (self.min_face_height_pct * 0.5):
                    continue

                # Keypoints (right eye, left eye, nose, mouth center, right tragion, left tragion)
                keypoints: dict[str, tuple[float, float]] = {}
                kp_names = ["right_eye", "left_eye", "nose", "mouth_center", "right_ear", "left_ear"]
                for i, kp in enumerate(det.location_data.relative_keypoints):
                    if i < len(kp_names):
                        keypoints[kp_names[i]] = (float(kp.x), float(kp.y))

                detections.append(FaceDetection(
                    bbox=(xmin, ymin, width, height),
                    confidence=score,
                    keypoints=keypoints,
                ))

            return detections
        except Exception as e:
            logger.error("MediaPipe detection error, using fallback", error=str(e))
            return self._fallback_opencv_detect(frame)

    def _fallback_opencv_detect(self, frame: np.ndarray) -> list[FaceDetection]:
        """Simple OpenCV Haar cascade fallback if MediaPipe is unavailable or fails."""
        try:
            import cv2
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            face_cascade = cv2.CascadeClassifier(cascade_path)
            h, w = frame.shape[:2]
            min_size = (int(w * self.min_face_height_pct * 0.5), int(h * self.min_face_height_pct))
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=min_size)

            detections: list[FaceDetection] = []
            for (x, y, fw, fh) in faces:
                xmin = x / float(w)
                ymin = y / float(h)
                width = fw / float(w)
                height = fh / float(h)
                detections.append(FaceDetection(
                    bbox=(xmin, ymin, width, height),
                    confidence=0.85,
                    keypoints={
                        "right_eye": (xmin + (width * 0.3), ymin + (height * 0.35)),
                        "left_eye": (xmin + (width * 0.7), ymin + (height * 0.35)),
                        "nose": (xmin + (width * 0.5), ymin + (height * 0.55)),
                        "mouth_center": (xmin + (width * 0.5), ymin + (height * 0.8)),
                    }
                ))
            return detections
        except Exception:
            return []

    def close(self) -> None:
        if self._detector and hasattr(self._detector, "close"):
            try:
                self._detector.close()
            except Exception:
                pass
            self._detector = None


class YOLOv8FaceDetector(BaseFaceDetector):
    """Adapter for YOLOv8 face detection models (ultralytics)."""

    def __init__(self, model_path: str = "yolov8n-face.pt", min_confidence: float = 0.45):
        self.model_path = model_path
        self.min_confidence = min_confidence
        self._model = None
        self._init_model()

    def _init_model(self) -> None:
        try:
            from ultralytics import YOLO
            self._model = YOLO(self.model_path)
        except Exception as e:
            logger.info("YOLOv8FaceDetector not initialized (ultralytics or weights missing)", error=str(e))
            self._model = None

    def detect(self, frame: np.ndarray) -> list[FaceDetection]:
        if self._model is None or frame is None or frame.size == 0:
            return []

        h, w = frame.shape[:2]
        results = self._model(frame, conf=self.min_confidence, verbose=False)
        detections: list[FaceDetection] = []

        for r in results:
            boxes = r.boxes
            for box in boxes:
                xyxy = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0].cpu().numpy())
                xmin = float(xyxy[0] / w)
                ymin = float(xyxy[1] / h)
                width = float((xyxy[2] - xyxy[0]) / w)
                height = float((xyxy[3] - xyxy[1]) / h)
                detections.append(FaceDetection(
                    bbox=(xmin, ymin, width, height),
                    confidence=conf,
                ))
        return detections


class MockFaceDetector(BaseFaceDetector):
    """Deterministic mock detector for tests and synthetic scenes."""

    def __init__(self, detections_per_frame: list[list[FaceDetection]] | None = None, static_detections: list[FaceDetection] | None = None):
        self.detections_per_frame = detections_per_frame or []
        self.static_detections = static_detections or []
        self._call_count = 0

    def detect(self, frame: np.ndarray) -> list[FaceDetection]:
        if self.detections_per_frame and self._call_count < len(self.detections_per_frame):
            dets = self.detections_per_frame[self._call_count]
            self._call_count += 1
            return dets
        self._call_count += 1
        return list(self.static_detections)


def get_face_detector(backend: str = "mediapipe", **kwargs: Any) -> BaseFaceDetector:
    """Factory function for instantiating a face detector."""
    if backend == "mediapipe":
        return MediaPipeFaceDetector(**kwargs)
    elif backend == "yolo":
        return YOLOv8FaceDetector(**kwargs)
    elif backend == "mock":
        return MockFaceDetector(**kwargs)
    else:
        logger.warning(f"Unknown face detector backend '{backend}', defaulting to mediapipe")
        return MediaPipeFaceDetector(**kwargs)
