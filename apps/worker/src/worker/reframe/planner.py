"""Per-clip 9:16 reframe planner with multi-person tracking, content-aware layouts, and fallback chain."""
from dataclasses import dataclass
from typing import Any

import numpy as np
import structlog

from clip_shared.schemas.reframe import (
    LayoutRegion,
    ReframeCropPath,
    ReframeFlags,
    ReframeKeyframe,
    ReframeLayout,
    ReframeMode,
    ReframeSegment,
    SceneItem,
)
from worker.analysis.active_speaker import SpeakerTurn
from worker.analysis.classifier import is_corner_thumbnail_face
from worker.reframe.smoother import CropSmoother

logger = structlog.get_logger()


@dataclass
class ReframePlan:
    mode: ReframeMode
    crop_path: ReframeCropPath
    confidence: float
    flags: ReframeFlags


def calculate_normalized_9_16_crop_size(src_w: int = 1280, src_h: int = 720) -> tuple[float, float]:
    """Calculate normalized width and height of a 9:16 vertical crop within a 16:9 source frame."""
    src_aspect = src_w / float(max(1, src_h))
    target_aspect = 9.0 / 16.0  # 0.5625

    if src_aspect >= target_aspect:
        crop_h = 1.0
        crop_w = target_aspect / src_aspect  # for 16:9, crop_w ≈ 0.3164
    else:
        crop_w = 1.0
        crop_h = src_aspect / target_aspect

    return float(crop_w), float(crop_h)


def snap_roi_to_text_bounds(
    raw_roi: tuple[float, float, float, float],
    padding_x: float = 0.04,
    padding_y: float = 0.04,
) -> tuple[float, float, float, float]:
    """
    Snap ROI crop to bounding block with safety padding so text lines are never cut through.
    Returns normalized (xmin, ymin, w, h).
    """
    rx, ry, rw, rh = raw_roi
    snap_x = max(0.0, rx - padding_x)
    snap_y = max(0.0, ry - padding_y)
    snap_w = min(1.0 - snap_x, rw + (padding_x * 2.0))
    snap_h = min(1.0 - snap_y, rh + (padding_y * 2.0))
    return snap_x, snap_y, snap_w, snap_h


def plan_clip_reframe(
    clip_start_ms: int,
    clip_end_ms: int,
    scenes: list[SceneItem],
    tracks: list[Any],  # FaceTrack or FaceTrackData objects
    src_w: int = 1280,
    src_h: int = 720,
    mode_override: str | None = None,
    min_speaker_hold_ms: int = 1500,
    speaker_turns: list[SpeakerTurn] | None = None,
    content_meta: dict[str, Any] | None = None,
    config_flags: dict[str, Any] | None = None,
) -> ReframePlan:
    """
    Generate normalized 9:16 crop path and layout specification for a clip.
    Supports Phase 7b multi-person framing, content-aware screen layouts, and anti-ping-pong smoothing.
    """
    clip_duration = max(100, clip_end_ms - clip_start_ms)
    crop_w, crop_h = calculate_normalized_9_16_crop_size(src_w, src_h)

    content_meta = content_meta or {}
    cfg = {
        "enable_split_stack": True,
        "enable_content_zoom": True,
        "enable_pip": True,
        "enable_stack": True,
        "enable_reaction_switching": False,
        "min_readability_text_height_px": 14.0,
        "cut_distance_threshold": 0.35,
    }
    if config_flags:
        cfg.update(config_flags)

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
    hard_cut_timestamps: list[int] = [s[0] for s in shot_segments]

    overall_confidences: list[float] = []
    has_multi_person = False
    has_face_cut_risk = False
    has_unreadable_text = False
    has_ping_pong_prevented = False
    has_reaction_cutaway = False
    primary_fallback_reason: str | None = None

    sample_step_ms = 200

    for seg_start, seg_end, scene_meta in shot_segments:
        shot_type = scene_meta.type if scene_meta else "talking_head"
        scene_conf = scene_meta.confidence if scene_meta else 0.90

        # Overlapping tracks in this segment
        seg_tracks = []
        for trk in tracks:
            t_start = getattr(trk, "start_ms", 0)
            t_end = getattr(trk, "end_ms", 0)
            if max(seg_start, t_start) < min(seg_end, t_end):
                seg_tracks.append(trk)

        if len(seg_tracks) >= 2:
            has_multi_person = True

        # Check speaker thumbnail in corners
        has_corner_face = any(
            is_corner_thumbnail_face(getattr(t, "summary", {}))
            for t in seg_tracks
        ) or content_meta.get("has_speaker_thumbnail", False)

        chosen_mode: ReframeMode | None = mode_override  # type: ignore
        fallback_reason = None
        seg_conf = scene_conf
        seg_layout: ReframeLayout | None = None

        # Mode selection logic
        if not chosen_mode:
            # A. HYBRID PIP OR SCREEN CONTENT WITH SPEAKER THUMBNAIL
            if (shot_type == "hybrid_pip" or has_corner_face) and (content_meta.get("has_screen_share") or shot_type in ("hybrid_pip", "screen_content", "screen_share_or_slides")):
                if cfg["enable_pip"] and seg_conf >= 0.70:
                    chosen_mode = "pip"
                    # Create PIP layout
                    seg_layout = ReframeLayout(
                        type="pip",
                        regions=[
                            LayoutRegion(src_x=0.0, src_y=0.0, src_w=1.0, src_h=1.0, dst_x=0.0, dst_y=0.21875, dst_w=1.0, dst_h=0.5625),
                            LayoutRegion(src_x=0.82, src_y=0.10, src_w=0.15, src_h=0.15, dst_x=0.68, dst_y=0.12, dst_w=0.28, dst_h=0.16, shape="rounded_rect", corner_radius=12.0),
                        ],
                    )
                else:
                    chosen_mode = "content_fit"
                    fallback_reason = "pip_low_confidence_or_disabled"

            # B. SCREEN CONTENT / SLIDES / CODE / WHITEBOARD
            elif shot_type in ("screen_content", "screen_share_or_slides", "whiteboard"):
                roi_box = content_meta.get("roi_box")
                min_font_px = content_meta.get("min_font_height_px", 24)

                # Check readability rule
                if roi_box:
                    roi_h = roi_box[3]
                    effective_font_px = min_font_px * (1920.0 / float(max(0.1, roi_h) * src_h))
                    if effective_font_px < cfg["min_readability_text_height_px"] or content_meta.get("unreadable_flag_expected"):
                        has_unreadable_text = True
                        chosen_mode = "content_fit"
                        fallback_reason = "unreadable_text_micro_font"
                        seg_layout = ReframeLayout(
                            type="content_fit",
                            regions=[LayoutRegion(src_x=0.0, src_y=0.0, src_w=1.0, src_h=1.0, dst_x=0.0, dst_y=0.21875, dst_w=1.0, dst_h=0.5625)],
                        )
                    elif cfg["enable_content_zoom"]:
                        chosen_mode = "content_zoom"
                        snapped_roi = snap_roi_to_text_bounds(roi_box)
                        seg_layout = ReframeLayout(
                            type="content_zoom",
                            regions=[LayoutRegion(src_x=snapped_roi[0], src_y=snapped_roi[1], src_w=snapped_roi[2], src_h=snapped_roi[3], dst_x=0.0, dst_y=0.0, dst_w=1.0, dst_h=1.0)],
                        )
                    else:
                        chosen_mode = "content_fit"
                        fallback_reason = "content_zoom_disabled"
                else:
                    chosen_mode = "content_fit"
                    fallback_reason = "screen_content_full_fit"
                    seg_layout = ReframeLayout(
                        type="content_fit",
                        regions=[LayoutRegion(src_x=0.0, src_y=0.0, src_w=1.0, src_h=1.0, dst_x=0.0, dst_y=0.21875, dst_w=1.0, dst_h=0.5625)],
                    )

            # C. GROUP / 3+ PERSON PANELS
            elif shot_type in ("group", "wide_multi") or len(seg_tracks) >= 3:
                # Check if all faces fit in balanced crop width
                cxs = [getattr(t, "summary", {}).get("mean_cx", 0.5) for t in seg_tracks]
                m_w = np.mean([getattr(t, "summary", {}).get("mean_w", 0.12) for t in seg_tracks])
                span = (max(cxs) - min(cxs)) + m_w

                if span <= (crop_w - 0.04):
                    chosen_mode = "balanced"
                elif content_meta.get("split_candidate") and cfg["enable_split_stack"] and len(seg_tracks) >= 2:
                    chosen_mode = "split_stack"
                    t0 = seg_tracks[0]
                    t1 = seg_tracks[-1]
                    seg_layout = ReframeLayout(
                        type="split_stack",
                        regions=[
                            LayoutRegion(src_x=getattr(t0, "summary", {}).get("mean_cx", 0.3) - 0.15, src_y=0.25, src_w=0.30, src_h=0.35, dst_x=0.0, dst_y=0.0, dst_w=1.0, dst_h=0.5),
                            LayoutRegion(src_x=getattr(t1, "summary", {}).get("mean_cx", 0.7) - 0.15, src_y=0.25, src_w=0.30, src_h=0.35, dst_x=0.0, dst_y=0.5, dst_w=1.0, dst_h=0.5),
                        ],
                    )
                else:
                    # Active speaker tracking
                    chosen_mode = "speaker_track"

            # D. TWO-SHOT (2 Faces)
            elif shot_type == "two_shot" and len(seg_tracks) == 2:
                t0_cx = getattr(seg_tracks[0], "summary", {}).get("mean_cx", 0.35)
                t1_cx = getattr(seg_tracks[1], "summary", {}).get("mean_cx", 0.65)
                span = abs(t1_cx - t0_cx) + (getattr(seg_tracks[0], "summary", {}).get("mean_w", 0.14) / 2.0) + (getattr(seg_tracks[1], "summary", {}).get("mean_w", 0.14) / 2.0)

                if span <= (crop_w - 0.04):
                    chosen_mode = "balanced"
                else:
                    chosen_mode = "speaker_track"

            # E. TALKING HEAD
            elif seg_tracks:
                chosen_mode = "speaker_track"
            else:
                chosen_mode = "center"
                fallback_reason = "no_faces_detected"

        # Ensure layout object exists for all modes
        if not seg_layout:
            if chosen_mode in ("fit_blur", "content_fit"):
                seg_layout = ReframeLayout(
                    type="content_fit",
                    regions=[LayoutRegion(src_x=0.0, src_y=0.0, src_w=1.0, src_h=1.0, dst_x=0.0, dst_y=0.21875, dst_w=1.0, dst_h=0.5625)],
                )
            elif chosen_mode == "split_stack":
                seg_layout = ReframeLayout(
                    type="split_stack",
                    regions=[
                        LayoutRegion(src_x=0.20, src_y=0.25, src_w=0.30, src_h=0.35, dst_x=0.0, dst_y=0.0, dst_w=1.0, dst_h=0.5),
                        LayoutRegion(src_x=0.65, src_y=0.25, src_w=0.30, src_h=0.35, dst_x=0.0, dst_y=0.5, dst_w=1.0, dst_h=0.5),
                    ],
                )
            elif chosen_mode == "stack":
                seg_layout = ReframeLayout(
                    type="stack",
                    regions=[
                        LayoutRegion(src_x=0.0, src_y=0.0, src_w=1.0, src_h=0.60, dst_x=0.0, dst_y=0.0, dst_w=1.0, dst_h=0.60),
                        LayoutRegion(src_x=0.35, src_y=0.25, src_w=0.30, src_h=0.40, dst_x=0.0, dst_y=0.60, dst_w=1.0, dst_h=0.40),
                    ],
                )
            elif chosen_mode == "pip":
                seg_layout = ReframeLayout(
                    type="pip",
                    regions=[
                        LayoutRegion(src_x=0.0, src_y=0.0, src_w=1.0, src_h=1.0, dst_x=0.0, dst_y=0.21875, dst_w=1.0, dst_h=0.5625),
                        LayoutRegion(src_x=0.82, src_y=0.10, src_w=0.15, src_h=0.15, dst_x=0.68, dst_y=0.12, dst_w=0.28, dst_h=0.16, shape="rounded_rect"),
                    ],
                )
            else:
                seg_layout = ReframeLayout(
                    type="crop",
                    regions=[LayoutRegion(src_x=0.5 - crop_w / 2.0, src_y=0.0, src_w=crop_w, src_h=crop_h, dst_x=0.0, dst_y=0.0, dst_w=1.0, dst_h=1.0)],
                )

        reframe_segments.append(ReframeSegment(
            start_ms=seg_start,
            end_ms=seg_end,
            mode=chosen_mode,
            confidence=seg_conf,
            fallback_reason=fallback_reason,
            layout=seg_layout,
        ))
        overall_confidences.append(seg_conf)

        if fallback_reason and not primary_fallback_reason:
            primary_fallback_reason = fallback_reason

        # Generate keyframes in this segment
        seg_timestamps = list(range(seg_start, seg_end, sample_step_ms))
        if not seg_timestamps or seg_timestamps[-1] < seg_end:
            seg_timestamps.append(seg_end)

        last_targeted_cx = 0.5
        last_switch_t = seg_start

        for t_ms in seg_timestamps:
            if chosen_mode in ("fit_blur", "content_fit", "center"):
                raw_keyframes.append(ReframeKeyframe(t_ms=t_ms, cx=0.5, cy=0.5, w=crop_w, h=crop_h))
            elif chosen_mode == "balanced" and len(seg_tracks) >= 2:
                t0_cx = getattr(seg_tracks[0], "summary", {}).get("mean_cx", 0.35)
                t1_cx = getattr(seg_tracks[1], "summary", {}).get("mean_cx", 0.65)
                mid_cx = (t0_cx + t1_cx) / 2.0
                raw_keyframes.append(ReframeKeyframe(t_ms=t_ms, cx=mid_cx, cy=0.5, w=crop_w, h=crop_h))
            elif chosen_mode in ("split_stack", "stack", "pip"):
                # Canvas center placeholder; layout compiler controls sub-regions
                raw_keyframes.append(ReframeKeyframe(t_ms=t_ms, cx=0.5, cy=0.5, w=crop_w, h=crop_h))
            elif chosen_mode == "content_zoom" and content_meta.get("roi_box"):
                rx, ry, rw, rh = content_meta["roi_box"]
                roi_cx = rx + (rw / 2.0)
                roi_cy = ry + (rh / 2.0)
                raw_keyframes.append(ReframeKeyframe(t_ms=t_ms, cx=roi_cx, cy=roi_cy, w=crop_w, h=crop_h))
            else:
                # speaker_track mode
                # Determine active speaker from speaker turns
                active_spk_turn = None
                if speaker_turns:
                    for st in speaker_turns:
                        if st.start_ms <= t_ms < st.end_ms:
                            active_spk_turn = st
                            break

                # Match active speaker to track
                target_track = None
                if active_spk_turn and active_spk_turn.speaker_label:
                    for trk in seg_tracks:
                        if getattr(trk, "speaker_label", None) == active_spk_turn.speaker_label:
                            target_track = trk
                            break

                if not target_track:
                    target_track = seg_tracks[0] if seg_tracks else None

                if target_track:
                    bbox = None
                    if hasattr(target_track, "get_bbox_at"):
                        bbox = target_track.get_bbox_at(t_ms)

                    if bbox is None:
                        sum_data = getattr(target_track, "summary", {})
                        cx = sum_data.get("mean_cx", 0.5)
                        cy = sum_data.get("mean_cy", 0.4)
                        bw = sum_data.get("mean_w", 0.15)
                        bh = sum_data.get("mean_h", 0.20)
                        bbox = (cx - (bw / 2.0), cy - (bh / 2.0), bw, bh)

                    face_boxes.append((t_ms, bbox))
                    fcx = bbox[0] + (bbox[2] / 2.0)
                    fcy = bbox[1] + (bbox[3] / 2.0)

                    # Look-room adjustment: speaker facing center
                    look_room = 0.03 if fcx < 0.5 else -0.03
                    target_cx = fcx + look_room

                    # Anti-ping-pong: minimum hold check
                    if abs(target_cx - last_targeted_cx) > 0.10:
                        hold_duration = t_ms - last_switch_t
                        if hold_duration < min_speaker_hold_ms:
                            has_ping_pong_prevented = True
                            target_cx = last_targeted_cx  # hold previous speaker
                        else:
                            # Cut vs pan decision by distance
                            if abs(target_cx - last_targeted_cx) > cfg["cut_distance_threshold"]:
                                hard_cut_timestamps.append(t_ms)
                            last_targeted_cx = target_cx
                            last_switch_t = t_ms

                    target_cy = min(0.65, max(0.35, fcy + 0.08))
                    raw_keyframes.append(ReframeKeyframe(t_ms=t_ms, cx=target_cx, cy=target_cy, w=crop_w, h=crop_h))
                else:
                    raw_keyframes.append(ReframeKeyframe(t_ms=t_ms, cx=0.5, cy=0.5, w=crop_w, h=crop_h))

    # 2. Smooth trajectory
    smoother = CropSmoother()
    smoothed_keyframes = smoother.smooth_trajectory(
        raw_keyframes=raw_keyframes,
        shot_boundaries=hard_cut_timestamps,
        face_boxes=face_boxes,
    )

    # 3. Overall mode and confidence
    primary_mode = reframe_segments[0].mode if reframe_segments else (mode_override or "speaker_track")
    mean_conf = float(np.mean(overall_confidences)) if overall_confidences else 0.90

    # 4. Check for face cut risk
    for t_ms, fbox in face_boxes:
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
        unreadable_text=has_unreadable_text,
        multi_speaker_conflict=False,
        low_roi_confidence=False,
        reaction_cutaway=has_reaction_cutaway,
        ping_pong_prevented=has_ping_pong_prevented,
        fallback_reason=primary_fallback_reason,
        suggested_fix="Switch to Fit (content_fit)" if (has_face_cut_risk or mean_conf < 0.65 or has_unreadable_text) else None,
    )

    crop_path = ReframeCropPath(
        keyframes=smoothed_keyframes,
        segments=reframe_segments,
        layout=reframe_segments[0].layout if reframe_segments else None,
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
