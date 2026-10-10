"""Scene boundary detection using PySceneDetect with OpenCV frame-diff fallback."""
import os
from dataclasses import dataclass

import cv2
import structlog

logger = structlog.get_logger()


@dataclass
class SceneCut:
    """Detected shot segment in milliseconds."""
    start_ms: int
    end_ms: int
    cut_type: str = "hard"  # hard | dissolve | default
    confidence: float = 1.0

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)


def detect_scenes(
    video_path: str,
    threshold: float = 27.0,
    min_scene_len_seconds: float = 0.8,
) -> list[SceneCut]:
    """
    Detect shot boundaries in video file.
    Returns list of contiguous SceneCut segments covering the video.
    """
    if not os.path.exists(video_path):
        logger.error(f"Video file not found for scene detection: {video_path}")
        return [SceneCut(start_ms=0, end_ms=1000)]

    # 1. Try PySceneDetect
    try:
        from scenedetect import SceneManager, open_video
        from scenedetect.detectors import ContentDetector

        video = open_video(video_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(
            ContentDetector(
                threshold=threshold,
                min_scene_len=int(video.frame_rate * min_scene_len_seconds),
            )
        )
        scene_manager.detect_scenes(video)
        scene_list = scene_manager.get_scene_list()

        total_duration_ms = int((video.duration.get_seconds() or 0.0) * 1000)

        if not scene_list:
            # Single continuous shot
            return [SceneCut(start_ms=0, end_ms=max(1000, total_duration_ms))]

        scenes: list[SceneCut] = []
        for start_tc, end_tc in scene_list:
            start_ms = int(start_tc.get_seconds() * 1000)
            end_ms = int(end_tc.get_seconds() * 1000)
            if end_ms > start_ms:
                scenes.append(SceneCut(start_ms=start_ms, end_ms=end_ms, cut_type="hard", confidence=0.95))

        if not scenes:
            return [SceneCut(start_ms=0, end_ms=max(1000, total_duration_ms))]

        # Ensure full duration coverage
        if scenes[-1].end_ms < total_duration_ms:
            scenes[-1].end_ms = total_duration_ms

        return scenes

    except Exception as e:
        logger.warning("PySceneDetect error, using OpenCV fallback", error=str(e))
        return _fallback_scene_detect(video_path, threshold=threshold)


def _fallback_scene_detect(video_path: str, threshold: float = 27.0) -> list[SceneCut]:
    """Lightweight OpenCV frame-difference scene detector."""
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return [SceneCut(start_ms=0, end_ms=10000)]

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        total_duration_ms = int((frame_count / fps) * 1000) if frame_count > 0 else 10000

        prev_gray = None
        cuts: list[int] = [0]  # millisecond cut timestamps

        # Sample every ~4 frames for fast scene change estimation
        sample_step = max(1, int(fps / 5.0))
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_step == 0:
                small = cv2.resize(frame, (160, 90))
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

                if prev_gray is not None:
                    diff = cv2.absdiff(gray, prev_gray)
                    mean_diff = float(diff.mean())
                    if mean_diff > (threshold * 1.5):
                        t_ms = int((frame_idx / fps) * 1000)
                        if (t_ms - cuts[-1]) >= 1000:  # minimum 1 second per shot
                            cuts.append(t_ms)
                prev_gray = gray

            frame_idx += 1

        cap.release()

        if cuts[-1] < total_duration_ms:
            cuts.append(total_duration_ms)

        if len(cuts) <= 1:
            return [SceneCut(start_ms=0, end_ms=max(1000, total_duration_ms))]

        scenes: list[SceneCut] = []
        for i in range(len(cuts) - 1):
            scenes.append(SceneCut(start_ms=cuts[i], end_ms=cuts[i + 1]))

        return scenes
    except Exception as e:
        logger.error("Fallback scene detection failed", error=str(e))
        return [SceneCut(start_ms=0, end_ms=10000)]
