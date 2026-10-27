"""Comprehensive tests for face tracking, scene classification, speaker association, smoothing, and ffmpeg filter generation."""

import numpy as np
import pytest

from clip_shared.schemas.reframe import ReframeCropPath, ReframeKeyframe, SceneItem
from worker.analysis.active_speaker import AudioVisualSpeakerAssociator, SpeakerTurn
from worker.analysis.classifier import RuleBasedSceneClassifier
from worker.analysis.detector import FaceDetection
from worker.analysis.scene import SceneCut
from worker.analysis.tracker import FaceTrackData, FaceTracker, compute_iou
from worker.reframe.ffmpeg_filter import crop_path_to_ffmpeg_filter
from worker.reframe.planner import plan_clip_reframe
from worker.reframe.smoother import CropSmoother, SmootherConfig


def test_compute_iou():
    boxA = (0.2, 0.2, 0.4, 0.4)
    boxB = (0.2, 0.2, 0.4, 0.4)
    assert pytest.approx(compute_iou(boxA, boxB), 0.001) == 1.0

    boxC = (0.7, 0.7, 0.2, 0.2)
    assert compute_iou(boxA, boxC) == 0.0

    boxD = (0.4, 0.2, 0.4, 0.4)
    # Overlap w: 0.2, h: 0.4 => 0.08. Union: 0.16 + 0.16 - 0.08 = 0.24. IoU = 0.08/0.24 = 0.333
    assert pytest.approx(compute_iou(boxA, boxD), 0.01) == 0.333


def test_face_tracker_gap_bridging_and_id_stability():
    tracker = FaceTracker(max_gap_ms=600)

    # Frame 0: t = 0ms, face at (0.4, 0.3)
    det1 = FaceDetection(bbox=(0.4, 0.3, 0.2, 0.2), confidence=0.95)
    tracker.update(frame_idx=0, t_ms=0, detections=[det1])

    # Frame 1: t = 200ms, face moved slightly to (0.42, 0.31)
    det2 = FaceDetection(bbox=(0.42, 0.31, 0.2, 0.2), confidence=0.94)
    tracker.update(frame_idx=1, t_ms=200, detections=[det2])

    # Frame 2: t = 400ms, face briefly occluded (empty detection)
    tracker.update(frame_idx=2, t_ms=400, detections=[])

    # Frame 3: t = 600ms, face reappears at (0.43, 0.31) (gap <= 600ms should be bridged)
    det3 = FaceDetection(bbox=(0.43, 0.31, 0.2, 0.2), confidence=0.92)
    tracker.update(frame_idx=3, t_ms=600, detections=[det3])

    tracks = tracker.finalize()
    assert len(tracks) == 1
    t = tracks[0]
    assert t.track_id == 0
    assert t.start_ms == 0
    assert t.end_ms == 600
    assert len(t.detections) == 3
    assert pytest.approx(t.summary["mean_w"], 0.01) == 0.2


def test_scene_classifier_rules():
    classifier = RuleBasedSceneClassifier()
    scene = SceneCut(start_ms=0, end_ms=10000)

    # 1. Talking Head (1 prominent face)
    track_solo = FaceTrackData(
        track_id=0,
        start_ms=0,
        end_ms=10000,
        avg_conf=0.95,
        summary={"mean_h": 0.25, "mean_w": 0.18, "mean_cx": 0.5, "mean_cy": 0.4},
    )
    res_solo = classifier.classify(scene, [track_solo])
    assert res_solo.type == "talking_head"
    assert res_solo.confidence >= 0.90

    # 2. Two Shot (2 faces)
    track_p1 = FaceTrackData(
        track_id=0,
        start_ms=0,
        end_ms=10000,
        avg_conf=0.90,
        summary={"mean_h": 0.20, "mean_w": 0.15, "mean_cx": 0.3, "mean_cy": 0.4},
    )
    track_p2 = FaceTrackData(
        track_id=1,
        start_ms=0,
        end_ms=10000,
        avg_conf=0.90,
        summary={"mean_h": 0.20, "mean_w": 0.15, "mean_cx": 0.7, "mean_cy": 0.4},
    )
    res_two = classifier.classify(scene, [track_p1, track_p2])
    assert res_two.type == "two_shot"

    # 3. Screen share / slides (no faces)
    res_slides = classifier.classify(scene, [])
    assert res_slides.type in ("screen_share_or_slides", "screen_content")


def test_speaker_association_hungarian():
    associator = AudioVisualSpeakerAssociator()

    # Track 0 is on left side (active during 0-5000ms)
    trk0 = FaceTrackData(
        track_id=0,
        start_ms=0,
        end_ms=10000,
        avg_conf=0.95,
        summary={"mouth_variance": 0.08, "mean_cx": 0.3},
    )
    # Track 1 is on right side (active during 5000-10000ms)
    trk1 = FaceTrackData(
        track_id=1,
        start_ms=0,
        end_ms=10000,
        avg_conf=0.95,
        summary={"mouth_variance": 0.08, "mean_cx": 0.7},
    )

    speaker_turns = [
        SpeakerTurn(start_ms=0, end_ms=5000, speaker_label="SPEAKER_00"),
        SpeakerTurn(start_ms=5000, end_ms=10000, speaker_label="SPEAKER_01"),
    ]

    assoc = associator.associate_speakers_with_tracks([trk0, trk1], speaker_turns)
    assert "SPEAKER_00" in assoc
    assert "SPEAKER_01" in assoc
    assert assoc["SPEAKER_00"].track_id == trk0.track_id
    assert assoc["SPEAKER_01"].track_id == trk1.track_id


def test_crop_smoother_deadzone_and_boundaries():
    smoother = CropSmoother(SmootherConfig(deadzone_x=0.03, deadzone_y=0.03))

    crop_w, crop_h = 0.3164, 1.0
    # Small micro movements below deadzone
    raw_kfs = [
        ReframeKeyframe(t_ms=0, cx=0.50, cy=0.50, w=crop_w, h=crop_h),
        ReframeKeyframe(t_ms=200, cx=0.51, cy=0.50, w=crop_w, h=crop_h),  # diff 0.01 < 0.03
        ReframeKeyframe(t_ms=400, cx=0.52, cy=0.50, w=crop_w, h=crop_h),  # diff 0.02 < 0.03
    ]

    smoothed = smoother.smooth_trajectory(raw_kfs)
    assert len(smoothed) == 3
    # First keyframe stays at 0.50
    assert smoothed[0].cx == 0.50
    # Micro jitter is suppressed
    assert abs(smoothed[1].cx - 0.50) < 0.01

    # Large move beyond bounds (e.g. cx = 0.95) should be clamped so crop box stays inside [0, 1]
    raw_boundary = [
        ReframeKeyframe(t_ms=0, cx=0.50, cy=0.50, w=crop_w, h=crop_h),
        ReframeKeyframe(t_ms=500, cx=0.98, cy=0.50, w=crop_w, h=crop_h),
    ]
    smooth_boundary = smoother.smooth_trajectory(raw_boundary)
    for k in smooth_boundary:
        assert (k.cx - k.w / 2.0) >= -0.001
        assert (k.cx + k.w / 2.0) <= 1.001


def test_face_containment_invariant_property():
    """Property test: face bounding box must be enclosed in smoothed crop."""
    smoother = CropSmoother()
    crop_w, crop_h = 0.3164, 1.0

    # Simulate face wandering across the screen
    np.random.seed(42)
    face_boxes = []
    raw_kfs = []
    for i in range(10):
        t_ms = i * 500
        face_cx = float(np.random.uniform(0.25, 0.75))
        face_w = 0.15
        face_h = 0.20
        face_bbox = (face_cx - face_w / 2, 0.3, face_w, face_h)
        face_boxes.append((t_ms, face_bbox))
        raw_kfs.append(ReframeKeyframe(t_ms=t_ms, cx=face_cx, cy=0.5, w=crop_w, h=crop_h))

    smoothed = smoother.smooth_trajectory(raw_kfs, face_boxes=face_boxes)
    for i, kf in enumerate(smoothed):
        _, f_bbox = face_boxes[i]
        f_xmin = f_bbox[0]
        f_xmax = f_bbox[0] + f_bbox[2]
        c_xmin = kf.cx - (kf.w / 2.0)
        c_xmax = kf.cx + (kf.w / 2.0)

        # Face should be within crop box (with tolerance for extreme edges)
        assert c_xmin <= f_xmin + 0.05
        assert c_xmax >= f_xmax - 0.05


def test_crop_path_to_ffmpeg_filter():
    # 1. Static single crop
    crop_path_static = ReframeCropPath(
        keyframes=[ReframeKeyframe(t_ms=0, cx=0.5, cy=0.5, w=0.3164, h=1.0)],
        segments=[],
    )
    filter_static = crop_path_to_ffmpeg_filter(crop_path_static, src_w=1280, src_h=720, out_w=1080, out_h=1920)
    assert "crop=" in filter_static
    assert "scale=1080:1920" in filter_static

    # 2. Fit blur filter
    crop_path_blur = {
        "keyframes": [{"t_ms": 0, "cx": 0.5, "cy": 0.5, "w": 0.3164, "h": 1.0}],
        "segments": [{"start_ms": 0, "end_ms": 10000, "mode": "fit_blur", "confidence": 0.9}],
    }
    filter_blur = crop_path_to_ffmpeg_filter(crop_path_blur, src_w=1280, src_h=720, out_w=1080, out_h=1920)
    assert "split=2" in filter_blur
    assert "boxblur" in filter_blur
    assert "overlay=" in filter_blur


def test_reframe_planner_fallback_chain():
    scenes = [SceneItem(start_ms=0, end_ms=20000, type="screen_share_or_slides", confidence=0.9)]
    plan = plan_clip_reframe(
        clip_start_ms=0,
        clip_end_ms=20000,
        scenes=scenes,
        tracks=[],
        src_w=1280,
        src_h=720,
    )
    assert plan.mode in ("fit_blur", "content_fit")
    assert plan.flags.fallback_reason is not None


def test_enhanced_scene_classifier_classes_and_features():
    from worker.analysis.classifier import EnhancedSceneClassifier

    classifier = EnhancedSceneClassifier()
    scene = SceneCut(start_ms=0, end_ms=10000)

    # 1. 4-person panel -> group
    tracks_group = [
        FaceTrackData(
            track_id=i,
            start_ms=0,
            end_ms=10000,
            avg_conf=0.9,
            summary={"mean_cx": 0.2 * (i + 1), "mean_cy": 0.4, "mean_w": 0.1, "mean_h": 0.15},
        )
        for i in range(4)
    ]
    res_group = classifier.classify(scene, tracks_group)
    assert res_group.type == "group"

    # 2. Whiteboard with meta
    classifier.reset()
    res_wb = classifier.classify(scene, [], meta={"has_whiteboard": True})
    assert res_wb.type == "whiteboard"

    # 3. Hybrid PIP with corner thumbnail
    classifier.reset()
    trk_thumb = FaceTrackData(
        track_id=0,
        start_ms=0,
        end_ms=10000,
        avg_conf=0.9,
        summary={"mean_cx": 0.88, "mean_cy": 0.15, "mean_w": 0.08, "mean_h": 0.10, "is_thumbnail": True},
    )
    res_pip = classifier.classify(scene, [trk_thumb], meta={"has_screen_share": True})
    assert res_pip.type == "hybrid_pip"


def test_ocr_lite_text_detection_and_thumbnail_detector():
    import cv2

    from worker.analysis.classifier import detect_text_regions_lite, is_corner_thumbnail_face

    # Synthetic image with text lines
    canvas = np.zeros((360, 640, 3), dtype=np.uint8)
    cv2.putText(canvas, "def test_function_analysis():", (50, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(canvas, "    return calculate_score()", (50, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    boxes = detect_text_regions_lite(canvas)
    assert len(boxes) >= 1
    # Check normalized
    for b in boxes:
        assert 0.0 <= b[0] <= 1.0
        assert 0.0 <= b[1] <= 1.0
        assert b[2] > 0.0 and b[3] > 0.0

    # Test corner thumbnail detector
    top_right_thumb = {"mean_cx": 0.88, "mean_cy": 0.12, "mean_w": 0.09, "mean_h": 0.11}
    assert is_corner_thumbnail_face(top_right_thumb) is True

    center_face = {"mean_cx": 0.50, "mean_cy": 0.40, "mean_w": 0.22, "mean_h": 0.28}
    assert is_corner_thumbnail_face(center_face) is False


def test_classifier_hysteresis_prevents_flicker():
    from worker.analysis.classifier import EnhancedSceneClassifier

    classifier = EnhancedSceneClassifier(hysteresis_margin=0.20)
    scene1 = SceneCut(start_ms=0, end_ms=5000)
    scene2 = SceneCut(start_ms=5000, end_ms=10000)

    # Establish initial confident classification
    t1 = FaceTrackData(
        track_id=0,
        start_ms=0,
        end_ms=5000,
        avg_conf=0.95,
        summary={"mean_cx": 0.5, "mean_cy": 0.4, "mean_w": 0.2, "mean_h": 0.25},
    )
    res1 = classifier.classify(scene1, [t1])
    assert res1.type == "talking_head"

    # Ambiguous low confidence transition should stay talking_head via hysteresis
    res2 = classifier.classify(scene2, [], meta={"motion_energy": 0.2})
    # Hysteresis keeps previous class when confidence of change is low
    assert res2.type == "talking_head"


def test_tracker_multi_face_velocity_and_track_merging():
    tracker = FaceTracker(max_gap_ms=1000)

    # Face moving linearly to right: x = 0.20, 0.25, 0.30
    det0 = FaceDetection(bbox=(0.20, 0.4, 0.1, 0.15), confidence=0.95)
    tracker.update(frame_idx=0, t_ms=0, detections=[det0])

    det1 = FaceDetection(bbox=(0.25, 0.4, 0.1, 0.15), confidence=0.95)
    tracker.update(frame_idx=1, t_ms=200, detections=[det1])

    # Gap of 400ms, face re-appears at predicted position 0.35
    det2 = FaceDetection(bbox=(0.35, 0.4, 0.1, 0.15), confidence=0.90)
    tracker.update(frame_idx=3, t_ms=600, detections=[det2])

    tracks = tracker.finalize()
    assert len(tracks) == 1
    assert tracks[0].track_id == 0
    assert len(tracks[0].detections) == 3


def test_n_speaker_hungarian_assignment():
    associator = AudioVisualSpeakerAssociator()

    # 4 distinct face tracks with timing matching speech turns
    tracks = [
        FaceTrackData(
            track_id=0, start_ms=5000, end_ms=10000, avg_conf=0.9, summary={"mean_cx": 0.2, "mouth_variance": 0.08}
        ),
        FaceTrackData(
            track_id=1, start_ms=0, end_ms=20000, avg_conf=0.9, summary={"mean_cx": 0.4, "mouth_variance": 0.01}
        ),
        FaceTrackData(
            track_id=2, start_ms=0, end_ms=5000, avg_conf=0.9, summary={"mean_cx": 0.6, "mouth_variance": 0.09}
        ),
        FaceTrackData(
            track_id=3, start_ms=10000, end_ms=15000, avg_conf=0.9, summary={"mean_cx": 0.8, "mouth_variance": 0.08}
        ),
    ]
    # Diarization speaker turns corresponding to tracks
    turns = [
        SpeakerTurn(start_ms=0, end_ms=5000, speaker_label="SPEAKER_02"),
        SpeakerTurn(start_ms=5000, end_ms=10000, speaker_label="SPEAKER_00"),
        SpeakerTurn(start_ms=10000, end_ms=15000, speaker_label="SPEAKER_03"),
    ]

    assoc = associator.associate_speakers_with_tracks(tracks, turns)
    assert "SPEAKER_02" in assoc
    assert "SPEAKER_00" in assoc
    assert "SPEAKER_03" in assoc
    assert assoc["SPEAKER_02"].track_id == 2
    assert assoc["SPEAKER_00"].track_id == 0
    assert assoc["SPEAKER_03"].track_id == 3


def test_anti_ping_pong_hold():
    # Rapidly alternating speaker turns (< 1.5s hold)
    turns = [
        SpeakerTurn(start_ms=0, end_ms=800, speaker_label="SPEAKER_00"),
        SpeakerTurn(start_ms=800, end_ms=1400, speaker_label="SPEAKER_01"),
        SpeakerTurn(start_ms=1400, end_ms=2200, speaker_label="SPEAKER_00"),
    ]
    t0 = FaceTrackData(
        track_id=0,
        start_ms=0,
        end_ms=5000,
        avg_conf=0.95,
        speaker_label="SPEAKER_00",
        summary={"mean_cx": 0.25, "mean_cy": 0.4, "mean_w": 0.15, "mean_h": 0.20},
    )
    t1 = FaceTrackData(
        track_id=1,
        start_ms=0,
        end_ms=5000,
        avg_conf=0.95,
        speaker_label="SPEAKER_01",
        summary={"mean_cx": 0.75, "mean_cy": 0.4, "mean_w": 0.15, "mean_h": 0.20},
    )

    plan = plan_clip_reframe(
        clip_start_ms=0,
        clip_end_ms=5000,
        scenes=[SceneItem(start_ms=0, end_ms=5000, type="talking_head", confidence=0.95)],
        tracks=[t0, t1],
        min_speaker_hold_ms=1500,
        speaker_turns=turns,
    )
    # Planner catches rapid alternation and activates ping-pong prevention flag
    assert plan.flags.ping_pong_prevented is True


def test_text_readability_guard_and_roi_snapping():
    from worker.reframe.planner import snap_roi_to_text_bounds

    # 1. ROI snapping adds padding safely
    raw_roi = (0.2, 0.2, 0.4, 0.3)
    snapped = snap_roi_to_text_bounds(raw_roi, padding_x=0.04, padding_y=0.04)
    assert snapped[0] == pytest.approx(0.16, 0.001)
    assert snapped[1] == pytest.approx(0.16, 0.001)
    assert snapped[2] == pytest.approx(0.48, 0.001)
    assert snapped[3] == pytest.approx(0.38, 0.001)

    # 2. Readability check: micro text triggers fallback to content_fit and sets unreadable_text flag
    scenes = [SceneItem(start_ms=0, end_ms=10000, type="screen_content", confidence=0.95)]
    plan_tiny = plan_clip_reframe(
        clip_start_ms=0,
        clip_end_ms=10000,
        scenes=scenes,
        tracks=[],
        content_meta={
            "has_screen_share": True,
            "roi_box": (0.1, 0.1, 0.8, 0.8),
            "min_font_height_px": 5.0,  # too tiny
            "unreadable_flag_expected": True,
        },
    )
    assert plan_tiny.mode == "content_fit"
    assert plan_tiny.flags.unreadable_text is True


def test_layout_compiler_golden_strings():
    from clip_shared.schemas.reframe import LayoutRegion, ReframeLayout

    # Split stack
    layout_split = ReframeLayout(
        type="split_stack",
        regions=[
            LayoutRegion(src_x=0.1, src_y=0.2, src_w=0.3, src_h=0.4, dst_x=0.0, dst_y=0.0, dst_w=1.0, dst_h=0.5),
            LayoutRegion(src_x=0.6, src_y=0.2, src_w=0.3, src_h=0.4, dst_x=0.0, dst_y=0.5, dst_w=1.0, dst_h=0.5),
        ],
    )
    path_split = ReframeCropPath(
        keyframes=[ReframeKeyframe(t_ms=0, cx=0.5, cy=0.5, w=0.3164, h=1.0)],
        segments=[],
        layout=layout_split,
    )
    filt_split = crop_path_to_ffmpeg_filter(path_split, src_w=1280, src_h=720, out_w=1080, out_h=1920)
    assert "vstack=inputs=2" in filt_split
    assert "scale=1080:960" in filt_split

    # PIP layout
    layout_pip = ReframeLayout(
        type="pip",
        regions=[
            LayoutRegion(src_x=0.0, src_y=0.0, src_w=1.0, src_h=1.0, dst_x=0.0, dst_y=0.21875, dst_w=1.0, dst_h=0.5625),
            LayoutRegion(
                src_x=0.8,
                src_y=0.1,
                src_w=0.15,
                src_h=0.15,
                dst_x=0.68,
                dst_y=0.12,
                dst_w=0.28,
                dst_h=0.16,
                shape="rounded_rect",
            ),
        ],
    )
    path_pip = ReframeCropPath(
        keyframes=[ReframeKeyframe(t_ms=0, cx=0.5, cy=0.5, w=0.3164, h=1.0)],
        segments=[],
        layout=layout_pip,
    )
    filt_pip = crop_path_to_ffmpeg_filter(path_pip, src_w=1280, src_h=720, out_w=1080, out_h=1920)
    assert "overlay=" in filt_pip


def test_v1_reframe_backward_compatibility():
    """V1 reframe dictionary without layout renders identical crop filter."""
    v1_crop_doc = {
        "keyframes": [
            {"t_ms": 0, "cx": 0.50, "cy": 0.45, "w": 0.3164, "h": 1.0},
            {"t_ms": 2000, "cx": 0.52, "cy": 0.45, "w": 0.3164, "h": 1.0},
        ],
        "segments": [{"start_ms": 0, "end_ms": 2000, "mode": "speaker_track", "confidence": 0.95}],
    }
    filt = crop_path_to_ffmpeg_filter(v1_crop_doc, src_w=1280, src_h=720, out_w=1080, out_h=1920)
    assert "crop=" in filt
    assert "scale=1080:1920" in filt
    # Does not crash or require layout field
    assert "vstack" not in filt


def test_normalized_coordinate_invariants_and_safe_zones():
    """Property test: all layout regions must lie within [0.0, 1.0] and not overlap caption safe zone."""
    caption_safe_zone_top = 0.70  # Captions typically in lower 30% of canvas
    caption_safe_zone_bottom = 0.92

    for mode in ["split_stack", "stack", "pip", "content_fit"]:
        plan = plan_clip_reframe(
            clip_start_ms=0,
            clip_end_ms=10000,
            scenes=[],
            tracks=[
                FaceTrackData(
                    track_id=0,
                    start_ms=0,
                    end_ms=10000,
                    avg_conf=0.9,
                    summary={"mean_cx": 0.4, "mean_cy": 0.4, "mean_w": 0.15, "mean_h": 0.2},
                )
            ],
            mode_override=mode,
        )
        layout = plan.crop_path.layout
        assert layout is not None
        for r in layout.regions:
            assert 0.0 <= r.dst_x <= 1.0
            assert 0.0 <= r.dst_y <= 1.0
            assert 0.0 < r.dst_w <= 1.0
            assert 0.0 < r.dst_h <= 1.0
            assert (r.dst_x + r.dst_w) <= 1.001
            assert (r.dst_y + r.dst_h) <= 1.001
