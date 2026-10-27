"""Scene classifier assigning shot types: talking_head, two_shot, group, screen_content, whiteboard, hybrid_pip, b_roll_other."""

import math
from abc import ABC, abstractmethod
from typing import Any

import cv2
import numpy as np
import structlog

from clip_shared.schemas.reframe import SceneItem, SceneType
from worker.analysis.scene import SceneCut
from worker.analysis.tracker import FaceTrackData

logger = structlog.get_logger()


def detect_text_regions_lite(frame: np.ndarray) -> list[tuple[float, float, float, float]]:
    """
    Fast OCR-lite text-region detector using morphological gradient and Otsu thresholding.
    Returns list of normalized bounding boxes (xmin, ymin, w, h) in [0, 1] coords.
    Runs in < 5ms on a 640x360 proxy frame.
    """
    if frame is None or frame.size == 0:
        return []

    h, w = frame.shape[:2]
    if h == 0 or w == 0:
        return []

    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 and frame.shape[2] == 3 else frame

    # Use Sobel horizontal gradients and binary thresholding to find character stroke lines
    sobel_x = cv2.Sobel(gray, cv2.CV_8U, 1, 0, ksize=3)
    _, thresh_sobel = cv2.threshold(sobel_x, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    _, thresh_binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    thresh = cv2.bitwise_or(thresh_sobel, thresh_binary)

    # Close horizontal gaps between word fragments and characters into text lines
    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 3))
    connected = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, close_kernel)

    # Find contours
    contours, _ = cv2.findContours(connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    text_boxes: list[tuple[float, float, float, float]] = []
    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        # Filter for typical text line dimensions (min height 6px, max height 120px, aspect ratio >= 1.2)
        if 6 <= bh <= 120 and bw >= 12 and (bw / float(bh)) >= 1.1:
            # Check bounding area not full screen
            if (bw * bh) < (w * h * 0.85):
                text_boxes.append(
                    (
                        float(x / w),
                        float(y / h),
                        float(bw / w),
                        float(bh / h),
                    )
                )

    return text_boxes


def is_corner_thumbnail_face(face_summary: dict[str, Any]) -> bool:
    """
    Check if a face track is a small speaker thumbnail placed in a video corner.
    Typically: small area (width <= 0.20, height <= 0.22) and located near any of the 4 corners.
    """
    cx = face_summary.get("mean_cx", 0.5)
    cy = face_summary.get("mean_cy", 0.5)
    w = face_summary.get("mean_w", 0.2)
    h = face_summary.get("mean_h", 0.2)

    if face_summary.get("is_thumbnail"):
        return True

    # Face must be relatively small
    if w > 0.20 or h > 0.22:
        return False

    # Near corner margins
    is_left_corner = cx < 0.28
    is_right_corner = cx > 0.72
    is_top_corner = cy < 0.28
    is_bottom_corner = cy > 0.72

    return (is_left_corner or is_right_corner) and (is_top_corner or is_bottom_corner)


class BaseSceneClassifier(ABC):
    """Interface for classifying video shots."""

    @abstractmethod
    def classify(
        self,
        scene: SceneCut,
        tracks: list[FaceTrackData],
        meta: dict[str, Any] | None = None,
    ) -> SceneItem:
        pass


class RuleBasedSceneClassifier(BaseSceneClassifier):
    """Deterministic rule-based scene classifier (v1 baseline and feature source)."""

    def __init__(
        self,
        min_talking_head_height: float = 0.10,
        screen_share_silence_ratio: float = 0.75,
    ):
        self.min_talking_head_height = min_talking_head_height
        self.screen_share_silence_ratio = screen_share_silence_ratio

    def classify(
        self,
        scene: SceneCut,
        tracks: list[FaceTrackData],
        meta: dict[str, Any] | None = None,
    ) -> SceneItem:
        shot_start = scene.start_ms
        shot_end = scene.end_ms
        shot_duration = max(1, shot_end - shot_start)

        # 1. Filter tracks overlapping with this shot
        overlapping_tracks: list[FaceTrackData] = []
        for t in tracks:
            overlap = max(0, min(shot_end, t.end_ms) - max(shot_start, t.start_ms))
            if overlap > 0:
                overlapping_tracks.append(t)

        if not overlapping_tracks:
            return SceneItem(
                start_ms=shot_start,
                end_ms=shot_end,
                type="screen_content",  # maps screen_share_or_slides -> screen_content
                confidence=0.88,
                num_faces=0,
            )

        # 2. Count concurrent faces sampled at regular timestamps inside the shot
        sample_times = list(range(shot_start, shot_end, max(200, shot_duration // 10))) or [shot_start]
        concurrent_counts = []
        for t_ms in sample_times:
            count = sum(
                1
                for trk in overlapping_tracks
                if (trk.get_bbox_at(t_ms) is not None or (trk.start_ms <= t_ms <= trk.end_ms))
            )
            concurrent_counts.append(count)

        max_concurrent = max(concurrent_counts) if concurrent_counts else len(overlapping_tracks)

        # 3. Classify based on face counts and sizes
        if max_concurrent >= 3 or len(overlapping_tracks) >= 3:
            return SceneItem(
                start_ms=shot_start,
                end_ms=shot_end,
                type="group",  # maps wide_multi -> group
                confidence=0.85,
                num_faces=max_concurrent,
            )
        elif max_concurrent == 2 or len(overlapping_tracks) == 2:
            return SceneItem(
                start_ms=shot_start,
                end_ms=shot_end,
                type="two_shot",
                confidence=0.92,
                num_faces=2,
            )
        elif max_concurrent == 1 or len(overlapping_tracks) == 1:
            primary_track = overlapping_tracks[0]
            mean_h = primary_track.summary.get("mean_h", 0.2)
            conf = 0.95 if mean_h >= self.min_talking_head_height else 0.80
            return SceneItem(
                start_ms=shot_start,
                end_ms=shot_end,
                type="talking_head",
                confidence=conf,
                num_faces=1,
            )
        else:
            return SceneItem(
                start_ms=shot_start,
                end_ms=shot_end,
                type="b_roll_other",
                confidence=0.75,
                num_faces=max_concurrent,
            )


class EnhancedSceneClassifier(BaseSceneClassifier):
    """
    Upgraded Phase 7b multi-class scene classifier supporting:
    - talking_head
    - two_shot
    - group (3+ faces)
    - screen_content (slides, code, UI, dashboards)
    - whiteboard (diagrams/proofs with high lightness and stroke edges)
    - hybrid_pip (screen content with small speaker thumbnail)
    - b_roll_other

    Features:
    - Face count, mean size, center vs corner placement (thumbnail detector)
    - Edge density & OCR-lite text density
    - Motion energy & static region ratio
    - Sub-shot segmentation & hysteresis to prevent flicker
    """

    def __init__(
        self,
        hysteresis_margin: float = 0.15,
        min_talking_head_height: float = 0.10,
        sub_shot_window_ms: int = 4000,
    ):
        self.hysteresis_margin = hysteresis_margin
        self.min_talking_head_height = min_talking_head_height
        self.sub_shot_window_ms = sub_shot_window_ms
        self._prev_classification: str | None = None

    def classify(
        self,
        scene: SceneCut,
        tracks: list[FaceTrackData],
        meta: dict[str, Any] | None = None,
    ) -> SceneItem:
        shot_start = scene.start_ms
        shot_end = scene.end_ms
        shot_duration = max(1, shot_end - shot_start)
        meta = meta or {}

        # 1. Filter overlapping tracks
        overlapping_tracks: list[FaceTrackData] = []
        for t in tracks:
            overlap = max(0, min(shot_end, t.end_ms) - max(shot_start, t.start_ms))
            if overlap > 0:
                overlapping_tracks.append(t)

        # 2. Extract facial characteristics
        num_faces = len(overlapping_tracks)
        has_thumbnail = False
        non_thumbnail_tracks = []
        for t in overlapping_tracks:
            if is_corner_thumbnail_face(t.summary):
                has_thumbnail = True
            else:
                non_thumbnail_tracks.append(t)

        # 3. Content characteristics from meta / frame features
        has_screen_share = meta.get("has_screen_share", False)
        has_whiteboard = meta.get("has_whiteboard", False)
        text_density = float(meta.get("text_density", 0.0))
        static_ratio = float(meta.get("static_ratio", 0.0))
        motion_energy = float(meta.get("motion_energy", 0.10))

        # Check sub-shots for long scenes
        sub_shots: list[dict[str, Any]] = []
        if shot_duration >= (self.sub_shot_window_ms * 1.5):
            cur = shot_start
            while cur < shot_end:
                sub_end = min(shot_end, cur + self.sub_shot_window_ms)
                # Count tracks active in this sub-window
                sub_tracks = [t for t in overlapping_tracks if max(cur, t.start_ms) < min(sub_end, t.end_ms)]
                sub_type, sub_conf = self._score_classes(
                    num_tracks=len(sub_tracks),
                    tracks=sub_tracks,
                    has_thumbnail=any(is_corner_thumbnail_face(t.summary) for t in sub_tracks),
                    has_screen_share=has_screen_share,
                    has_whiteboard=has_whiteboard,
                    text_density=text_density,
                    static_ratio=static_ratio,
                    motion_energy=motion_energy,
                )
                sub_shots.append(
                    {
                        "start_ms": cur,
                        "end_ms": sub_end,
                        "type": sub_type,
                        "confidence": round(sub_conf, 2),
                    }
                )
                cur = sub_end

        # Primary classification across entire shot
        chosen_type, confidence = self._score_classes(
            num_tracks=len(non_thumbnail_tracks),
            tracks=overlapping_tracks,
            has_thumbnail=has_thumbnail,
            has_screen_share=has_screen_share,
            has_whiteboard=has_whiteboard,
            text_density=text_density,
            static_ratio=static_ratio,
            motion_energy=motion_energy,
        )

        # Apply hysteresis if previous classification is established
        if self._prev_classification and self._prev_classification != chosen_type:
            # Check if transition is sufficiently confident
            if confidence < (0.80 + self.hysteresis_margin):
                chosen_type = self._prev_classification  # prevent flicker

        self._prev_classification = chosen_type

        features_dict = {
            "num_faces": num_faces,
            "has_thumbnail": has_thumbnail,
            "text_density": text_density,
            "static_ratio": static_ratio,
            "motion_energy": motion_energy,
        }

        return SceneItem(
            start_ms=shot_start,
            end_ms=shot_end,
            type=chosen_type,
            confidence=round(confidence, 2),
            num_faces=num_faces,
            sub_shots=sub_shots,
            features=features_dict,
        )

    def reset(self) -> None:
        """Reset hysteresis state between independent videos or clips."""
        self._prev_classification = None

    def _score_classes(
        self,
        num_tracks: int,
        tracks: list[FaceTrackData],
        has_thumbnail: bool,
        has_screen_share: bool,
        has_whiteboard: bool,
        text_density: float,
        static_ratio: float,
        motion_energy: float,
    ) -> tuple[SceneType, float]:
        """Compute softmax probability over classes and return best class + confidence."""
        scores: dict[SceneType, float] = {
            "talking_head": 0.0,
            "two_shot": 0.0,
            "group": 0.0,
            "screen_content": 0.0,
            "whiteboard": 0.0,
            "hybrid_pip": 0.0,
            "b_roll_other": 0.0,
        }

        # 1. Whiteboard evidence
        if has_whiteboard:
            scores["whiteboard"] += 6.0
        elif text_density > 0.20 and static_ratio > 0.60 and num_tracks <= 1:
            scores["whiteboard"] += 1.5

        # 2. Hybrid PIP evidence (screen content + small thumbnail face)
        if has_thumbnail and (has_screen_share or text_density > 0.25 or static_ratio > 0.60):
            scores["hybrid_pip"] += 6.0
        elif has_thumbnail:
            scores["hybrid_pip"] += 3.5

        # 3. Multi-face geometry evidence (takes precedence when camera captures real people)
        if num_tracks >= 3:
            scores["group"] += 6.0
        elif num_tracks == 2:
            scores["two_shot"] += 6.0
        elif num_tracks == 1 and not has_thumbnail and not has_whiteboard:
            primary_h = tracks[0].summary.get("mean_h", 0.2) if tracks else 0.2
            if primary_h >= self.min_talking_head_height:
                scores["talking_head"] += 5.5
            else:
                scores["talking_head"] += 3.0
                scores["b_roll_other"] += 1.5

        # 4. Screen content evidence (slides, code, UI) when no multi-face conversation
        if (
            not has_whiteboard
            and not has_thumbnail
            and (has_screen_share or text_density > 0.25 or static_ratio > 0.70)
        ):
            if num_tracks == 0:
                scores["screen_content"] += 6.0
            elif num_tracks == 1:
                # Could be talking head presenting or slide with presenter
                scores["screen_content"] += 2.0

        if num_tracks == 0 and not (has_screen_share or text_density > 0.20 or static_ratio > 0.60 or has_whiteboard):
            scores["b_roll_other"] += 4.0

        # Compute softmax over scores
        max_s = max(scores.values())
        exp_scores = {k: math.exp(v - max_s) for k, v in scores.items()}
        sum_exp = sum(exp_scores.values())
        probs = {k: v / sum_exp for k, v in exp_scores.items()}

        best_class = max(probs, key=lambda k: probs[k])
        confidence = float(min(0.99, max(0.50, probs[best_class])))

        return best_class, confidence


def get_scene_classifier(mode: str = "enhanced", **kwargs: Any) -> BaseSceneClassifier:
    """Factory helper to obtain the requested scene classifier."""
    if mode == "rule_based":
        return RuleBasedSceneClassifier(**kwargs)
    return EnhancedSceneClassifier(**kwargs)
