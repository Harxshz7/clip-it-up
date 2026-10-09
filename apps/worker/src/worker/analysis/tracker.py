"""Face tracking engine with IoU + Centroid matching, gap bridging, and trajectory statistics."""
from dataclasses import dataclass, field
from typing import Any
import numpy as np
from worker.analysis.detector import FaceDetection


@dataclass
class TrackedDetection:
    t_ms: int
    frame_idx: int
    detection: FaceDetection


@dataclass
class FaceTrackData:
    """Full trajectory and statistics for a tracked face across video duration."""
    track_id: int
    start_ms: int
    end_ms: int
    avg_conf: float
    speaker_label: str | None = None
    detections: list[TrackedDetection] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def get_bbox_at(self, t_ms: int) -> tuple[float, float, float, float] | None:
        """
        Interpolate or retrieve normalized bbox (xmin, ymin, w, h) at given timestamp.
        Returns None if timestamp is well outside track lifespan.
        """
        if not self.detections:
            return None

        if t_ms < self.start_ms - 500 or t_ms > self.end_ms + 500:
            return None

        # Binary search or closest match
        times = [d.t_ms for d in self.detections]
        idx = int(np.searchsorted(times, t_ms))

        if idx == 0:
            return self.detections[0].detection.bbox
        if idx >= len(self.detections):
            return self.detections[-1].detection.bbox

        # Linear interpolation between adjacent detections if gap is small
        d_prev = self.detections[idx - 1]
        d_next = self.detections[idx]
        gap = d_next.t_ms - d_prev.t_ms

        if gap <= 1000 and gap > 0:
            alpha = (t_ms - d_prev.t_ms) / float(gap)
            alpha = max(0.0, min(1.0, alpha))
            b0 = d_prev.detection.bbox
            b1 = d_next.detection.bbox
            return (
                b0[0] + alpha * (b1[0] - b0[0]),
                b0[1] + alpha * (b1[1] - b0[1]),
                b0[2] + alpha * (b1[2] - b0[2]),
                b0[3] + alpha * (b1[3] - b0[3]),
            )
        return d_prev.detection.bbox


def compute_iou(boxA: tuple[float, float, float, float], boxB: tuple[float, float, float, float]) -> float:
    """Compute Intersection over Union (IoU) between two bboxes (xmin, ymin, w, h)."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[0] + boxA[2], boxB[0] + boxB[2])
    yB = min(boxA[1] + boxA[3], boxB[1] + boxB[3])

    interW = max(0.0, xB - xA)
    interH = max(0.0, yB - yA)
    interArea = interW * interH

    boxAArea = boxA[2] * boxA[3]
    boxBArea = boxB[2] * boxB[3]
    unionArea = boxAArea + boxBArea - interArea

    if unionArea <= 0:
        return 0.0
    return interArea / unionArea


class FaceTracker:
    """Kalman/Centroid and IoU tracker with gap bridging (< 500ms)."""

    def __init__(
        self,
        min_iou_threshold: float = 0.25,
        max_centroid_dist: float = 0.25,
        max_gap_ms: int = 600,
        min_track_duration_ms: int = 500,
    ):
        self.min_iou_threshold = min_iou_threshold
        self.max_centroid_dist = max_centroid_dist
        self.max_gap_ms = max_gap_ms
        self.min_track_duration_ms = min_track_duration_ms
        self.next_track_id = 0
        self._active_tracks: dict[int, list[TrackedDetection]] = {}
        self._completed_tracks: list[FaceTrackData] = []

    def update(self, frame_idx: int, t_ms: int, detections: list[FaceDetection]) -> None:
        """Process detections for a new frame timestamp."""
        active_ids = list(self._active_tracks.keys())

        if not active_ids:
            # Initialize new tracks for all detections
            for det in detections:
                tid = self.next_track_id
                self.next_track_id += 1
                self._active_tracks[tid] = [TrackedDetection(t_ms=t_ms, frame_idx=frame_idx, detection=det)]
            return

        # Compute cost matrix between active tracks and current detections
        cost_matrix = np.zeros((len(active_ids), len(detections)), dtype=np.float32)
        for r, tid in enumerate(active_ids):
            last_det = self._active_tracks[tid][-1].detection
            last_cx, last_cy = last_det.cx, last_det.cy
            for c, det in enumerate(detections):
                iou = compute_iou(last_det.bbox, det.bbox)
                dist = np.hypot(last_cx - det.cx, last_cy - det.cy)
                # Score: higher IoU and lower distance is better
                score = (iou * 0.7) + (max(0.0, 1.0 - (dist / self.max_centroid_dist)) * 0.3)
                cost_matrix[r, c] = score

        assigned_tracks: set[int] = set()
        assigned_dets: set[int] = set()

        if detections:
            # Greedy matching
            while True:
                if cost_matrix.size == 0:
                    break
                max_idx = np.unravel_index(np.argmax(cost_matrix), cost_matrix.shape)
                best_score = cost_matrix[max_idx]

                if best_score < self.min_iou_threshold and best_score < 0.35:
                    break

                r, c = max_idx
                tid = active_ids[r]

                if tid not in assigned_tracks and c not in assigned_dets:
                    assigned_tracks.add(tid)
                    assigned_dets.add(c)
                    self._active_tracks[tid].append(TrackedDetection(t_ms=t_ms, frame_idx=frame_idx, detection=detections[c]))

                cost_matrix[r, :] = -1.0
                cost_matrix[:, c] = -1.0

        # Unassigned detections become new tracks
        for c, det in enumerate(detections):
            if c not in assigned_dets:
                tid = self.next_track_id
                self.next_track_id += 1
                self._active_tracks[tid] = [TrackedDetection(t_ms=t_ms, frame_idx=frame_idx, detection=det)]

        # Check for expired tracks exceeding max_gap_ms
        expired_ids = []
        for tid, track_dets in self._active_tracks.items():
            if tid not in assigned_tracks:
                gap = t_ms - track_dets[-1].t_ms
                if gap > self.max_gap_ms:
                    expired_ids.append(tid)

        for tid in expired_ids:
            self._finalize_track(tid)

    def _finalize_track(self, tid: int) -> None:
        track_dets = self._active_tracks.pop(tid, None)
        if not track_dets:
            return

        start_ms = track_dets[0].t_ms
        end_ms = track_dets[-1].t_ms
        duration = end_ms - start_ms

        if duration < self.min_track_duration_ms and len(track_dets) < 3:
            # Filter noise tracks
            return

        confs = [d.detection.confidence for d in track_dets]
        avg_conf = float(np.mean(confs)) if confs else 0.0

        cxs = [d.detection.cx for d in track_dets]
        cys = [d.detection.cy for d in track_dets]
        widths = [d.detection.width for d in track_dets]
        heights = [d.detection.height for d in track_dets]
        mouths = [d.detection.mouth_openness for d in track_dets if d.detection.mouth_openness > 0]

        summary = {
            "detection_count": len(track_dets),
            "duration_ms": duration,
            "mean_cx": float(np.mean(cxs)),
            "mean_cy": float(np.mean(cys)),
            "mean_w": float(np.mean(widths)),
            "mean_h": float(np.mean(heights)),
            "min_cx": float(np.min(cxs)),
            "max_cx": float(np.max(cxs)),
            "mouth_variance": float(np.var(mouths)) if mouths else 0.0,
            "mouth_mean": float(np.mean(mouths)) if mouths else 0.0,
        }

        self._completed_tracks.append(FaceTrackData(
            track_id=tid,
            start_ms=start_ms,
            end_ms=end_ms,
            avg_conf=avg_conf,
            detections=track_dets,
            summary=summary,
        ))

    def finalize(self) -> list[FaceTrackData]:
        """Finish all remaining active tracks and return sorted track data list."""
        for tid in list(self._active_tracks.keys()):
            self._finalize_track(tid)
        return sorted(self._completed_tracks, key=lambda t: t.start_ms)
