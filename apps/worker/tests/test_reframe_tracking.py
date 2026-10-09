"""Comprehensive tests for face tracking, scene classification, speaker association, smoothing, and ffmpeg filter generation."""
import pytest
import numpy as np
from clip_shared.schemas.reframe import ReframeCropPath, ReframeKeyframe, SceneItem
from worker.analysis.active_speaker import AudioVisualSpeakerAssociator, SpeakerTurn
from worker.analysis.classifier import RuleBasedSceneClassifier
from worker.analysis.detector import FaceDetection, MockFaceDetector
from worker.analysis.scene import SceneCut
from worker.analysis.tracker import FaceTrackData, FaceTracker, compute_iou
from worker.reframe.ffmpeg_filter import crop_path_to_ffmpeg_filter
from worker.reframe.planner import calculate_normalized_9_16_crop_size, plan_clip_reframe
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
    assert res_slides.type == "screen_share_or_slides"


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
    assert plan.mode == "fit_blur"
    assert plan.flags.fallback_reason == "screen_share_detected"
