"""Per-clip 9:16 reframe planner with shot segmentation, speaker tracking, and fallback chain."""
from dataclasses import dataclass
from typing import Any

import numpy as np
import structlog

from clip_shared.schemas.reframe import (
    ReframeCropPath,
    ReframeFlags,
    ReframeKeyframe,
    ReframeSegment,
    SceneItem,
)
from worker.reframe.smoother import CropSmoother

logger = structlog.get_logger()


@dataclass
class ReframePlan:
    mode: str
    crop_path: ReframeCropPath
    confidence: float
    flags: ReframeFlags


def calculate_normalized_9_16_crop_size(src_w: int = 1280, src_h: int = 720) -> tuple[float, float]:
    """
    Calculate normalized width and height of a 9:16 vertical crop within a 16:9 source frame.
    For standard 16:9 video: height is 1.0 (full height), width is (src_h / src_w) * (9 / 16).
    """
    src_aspect = src_w / float(max(1, src_h))
    target_aspect = 9.0 / 16.0  # 0.5625

    if src_aspect >= target_aspect:
        # Wider than 9:16 (standard landscape)
        crop_h = 1.0
        crop_w = (target_aspect / src_aspect)  # for 16:9, crop_w = (9/16)/(16/9) = 81/256 ≈ 0.3164
    else:
        # Taller than 9:16
        crop_w = 1.0
        crop_h = (src_aspect / target_aspect)

    return float(crop_w), float(crop_h)


def plan_clip_reframe(
    clip_start_ms: int,
    clip_end_ms: int,
    scenes: list[SceneItem],
    tracks: list[Any],  # FaceTrack or FaceTrackData objects
    src_w: int = 1280,
    src_h: int = 720,
    mode_override: str | None = None,
    min_speaker_hold_ms: int = 1500,
) -> ReframePlan:
    """
    Generate normalized 9:16 crop path for a clip.
    """
    clip_duration = max(100, clip_end_ms - clip_start_ms)
    crop_w, crop_h = calculate_normalized_9_16_crop_size(src_w, src_h)

    # 1. Segment clip by scene cuts
    shot_segments: list[tuple[int, int, SceneItem | None]] = []
    if not scenes:
        shot_segments.append((clip_start_ms, clip_end_ms, None))
    else:
        for sc in scenes:
            seg_start = max(clip_start_ms, sc.start_ms)
            seg_end = min(clip_end_ms, sc.end_ms)
            if seg_end > seg_start:
                shot_segments.append((seg_start, seg_end, sc))

        if not shot_segments:
            shot_segments.append((clip_start_ms, clip_end_ms, None))

    raw_keyframes: list[ReframeKeyframe] = []
    reframe_segments: list[ReframeSegment] = []
    face_boxes: list[tuple[int, tuple[float, float, float, float]]] = []

    overall_confidences: list[float] = []
    has_multi_person = False
    has_face_cut_risk = False
    primary_fallback_reason: str | None = None

    # Sample keyframe timestamps every ~200ms
    sample_step_ms = 200

    for seg_start, seg_end, scene_meta in shot_segments:
        shot_type = scene_meta.type if scene_meta else "talking_head"
        scene_conf = scene_meta.confidence if scene_meta else 0.9

        # Filter tracks active in this segment
        seg_tracks = []
        for trk in tracks:
            t_start = getattr(trk, "start_ms", 0)
            t_end = getattr(trk, "end_ms", 0)
            if max(seg_start, t_start) < min(seg_end, t_end):
                seg_tracks.append(trk)

        if len(seg_tracks) >= 2:
            has_multi_person = True

        # Choose mode
        chosen_mode = mode_override
        fallback_reason = None
        seg_conf = scene_conf

        if not chosen_mode:
            if shot_type == "screen_share_or_slides":
                chosen_mode = "fit_blur"
                fallback_reason = "screen_share_detected"
            elif shot_type == "talking_head" and seg_tracks:
                chosen_mode = "speaker_track"
            elif shot_type == "two_shot" and len(seg_tracks) == 2:
                # Check if both fit in crop_w
                t0_cx = getattr(seg_tracks[0], "summary", {}).get("mean_cx", 0.3)
                t1_cx = getattr(seg_tracks[1], "summary", {}).get("mean_cx", 0.7)
                span = abs(t1_cx - t0_cx) + (getattr(seg_tracks[0], "summary", {}).get("mean_w", 0.15) / 2.0) + (getattr(seg_tracks[1], "summary", {}).get("mean_w", 0.15) / 2.0)

                if span <= (crop_w - 0.04):
                    chosen_mode = "balanced"
                else:
                    chosen_mode = "speaker_track"
            elif len(seg_tracks) >= 3:
                chosen_mode = "fit_blur"
                fallback_reason = "wide_multi_faces"
            elif seg_tracks:
                chosen_mode = "speaker_track"
            else:
                chosen_mode = "center"
                fallback_reason = "no_faces_detected"

        reframe_segments.append(ReframeSegment(
            start_ms=seg_start,
            end_ms=seg_end,
            mode=chosen_mode,
            confidence=seg_conf,
            fallback_reason=fallback_reason,
        ))
        overall_confidences.append(seg_conf)

        if fallback_reason and not primary_fallback_reason:
            primary_fallback_reason = fallback_reason

        # Generate per-timestamp raw keyframes in this segment
        seg_timestamps = list(range(seg_start, seg_end, sample_step_ms))
        if not seg_timestamps or seg_timestamps[-1] < seg_end:
            seg_timestamps.append(seg_end)

        for t_ms in seg_timestamps:
            if chosen_mode == "fit_blur":
                # Full frame centered
                raw_keyframes.append(ReframeKeyframe(
                    t_ms=t_ms,
                    cx=0.5,
                    cy=0.5,
                    w=crop_w,
                    h=crop_h,
                ))
            elif chosen_mode == "center":
                raw_keyframes.append(ReframeKeyframe(
                    t_ms=t_ms,
                    cx=0.5,
                    cy=0.5,
                    w=crop_w,
                    h=crop_h,
                ))
            elif chosen_mode == "balanced" and len(seg_tracks) >= 2:
                t0_cx = getattr(seg_tracks[0], "summary", {}).get("mean_cx", 0.35)
                t1_cx = getattr(seg_tracks[1], "summary", {}).get("mean_cx", 0.65)
                mid_cx = (t0_cx + t1_cx) / 2.0
                raw_keyframes.append(ReframeKeyframe(
                    t_ms=t_ms,
                    cx=mid_cx,
                    cy=0.5,
                    w=crop_w,
                    h=crop_h,
                ))
            else:
                # speaker_track
                target_track = seg_tracks[0] if seg_tracks else None
                if target_track:
                    # Get bbox from track if available
                    bbox = None
                    if hasattr(target_track, "get_bbox_at"):
                        bbox = target_track.get_bbox_at(t_ms)

                    if bbox is None:
                        # Fallback to mean summary
                        sum_data = getattr(target_track, "summary", {})
                        cx = sum_data.get("mean_cx", 0.5)
                        cy = sum_data.get("mean_cy", 0.4)
                        bw = sum_data.get("mean_w", 0.15)
                        bh = sum_data.get("mean_h", 0.20)
                        bbox = (cx - (bw / 2.0), cy - (bh / 2.0), bw, bh)

                    face_boxes.append((t_ms, bbox))
                    fcx = bbox[0] + (bbox[2] / 2.0)
                    fcy = bbox[1] + (bbox[3] / 2.0)

                    # Position cy so face sits near top third (reserve bottom for captions)
                    target_cy = min(0.65, max(0.35, fcy + 0.08))

                    raw_keyframes.append(ReframeKeyframe(
                        t_ms=t_ms,
                        cx=fcx,
                        cy=target_cy,
                        w=crop_w,
                        h=crop_h,
                    ))
                else:
                    raw_keyframes.append(ReframeKeyframe(
                        t_ms=t_ms,
                        cx=0.5,
                        cy=0.5,
                        w=crop_w,
                        h=crop_h,
                    ))

    # 2. Smooth trajectory
    smoother = CropSmoother()
    shot_cut_times = [s[0] for s in shot_segments]
    smoothed_keyframes = smoother.smooth_trajectory(
        raw_keyframes=raw_keyframes,
        shot_boundaries=shot_cut_times,
        face_boxes=face_boxes,
    )

    # 3. Overall mode and confidence
    primary_mode = reframe_segments[0].mode if reframe_segments else (mode_override or "speaker_track")
    mean_conf = float(np.mean(overall_confidences)) if overall_confidences else 0.90

    # 4. Check for face cut risk
    for t_ms, fbox in face_boxes:
        # Find matching keyframe
        kf = next((k for k in smoothed_keyframes if abs(k.t_ms - t_ms) < sample_step_ms), None)
        if kf:
            f_xmin, f_ymin, f_w, f_h = fbox
            f_xmax = f_xmin + f_w
            c_xmin = kf.cx - (kf.w / 2.0)
            c_xmax = kf.cx + (kf.w / 2.0)
            if f_xmin < (c_xmin - 0.02) or f_xmax > (c_xmax + 0.02):
                has_face_cut_risk = True
                break

    flags = ReframeFlags(
        face_cut_risk=has_face_cut_risk,
        low_confidence=mean_conf < 0.65,
        multi_person=has_multi_person,
        fallback_reason=primary_fallback_reason,
        suggested_fix="Switch to Fit (fit_blur)" if (has_face_cut_risk or mean_conf < 0.65) else None,
    )

    crop_path = ReframeCropPath(
        keyframes=smoothed_keyframes,
        segments=reframe_segments,
        easing="ease_in_out",
        source_width=src_w,
        source_height=src_h,
        target_aspect="9:16",
    )

    return ReframePlan(
        mode=primary_mode,
        crop_path=crop_path,
        confidence=round(mean_conf, 2),
        flags=flags,
    )
