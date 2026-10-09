"""Scene classifier assigning shot types: talking_head, two_shot, wide_multi, screen_share_or_slides, other."""
from abc import ABC, abstractmethod
from typing import Any
from clip_shared.schemas.reframe import SceneItem
from worker.analysis.scene import SceneCut
from worker.analysis.tracker import FaceTrackData


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
    """Rule-based heuristic scene classifier."""

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
            # Check if screen_share_or_slides or other
            return SceneItem(
                start_ms=shot_start,
                end_ms=shot_end,
                type="screen_share_or_slides",
                confidence=0.88,
                num_faces=0,
            )

        # 2. Count concurrent faces sampled at regular timestamps inside the shot
        sample_times = list(range(shot_start, shot_end, max(200, shot_duration // 10))) or [shot_start]
        concurrent_counts = []
        for t_ms in sample_times:
            count = sum(
                1 for trk in overlapping_tracks
                if (trk.get_bbox_at(t_ms) is not None or (trk.start_ms <= t_ms <= trk.end_ms))
            )
            concurrent_counts.append(count)

        max_concurrent = max(concurrent_counts) if concurrent_counts else len(overlapping_tracks)
        avg_concurrent = sum(concurrent_counts) / len(concurrent_counts) if concurrent_counts else 0.0

        # 3. Classify based on face counts and sizes
        if max_concurrent >= 3 or len(overlapping_tracks) >= 3:
            return SceneItem(
                start_ms=shot_start,
                end_ms=shot_end,
                type="wide_multi",
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
                type="other",
                confidence=0.75,
                num_faces=max_concurrent,
            )
