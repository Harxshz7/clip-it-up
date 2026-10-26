"""Benchmark fixture scenarios covering talking_head, two_shot, group, screen_content, whiteboard, hybrid_pip."""
from typing import Any
from clip_shared.schemas.reframe import SceneItem
from worker.analysis.active_speaker import SpeakerTurn
from worker.analysis.detector import FaceDetection
from worker.analysis.tracker import FaceTrackData, TrackedDetection


def get_eval_scenarios() -> list[dict[str, Any]]:
    """Return all 11 evaluation benchmark scenarios with full track and timing metadata."""
    scenarios = [
        # 1. Talking Head (Solo) - V1 Baseline
        {
            "id": "talking_head_single_speaker",
            "video_slug": "huberman_lab_solo",
            "scene_type": "talking_head",
            "expected_mode": "speaker_track",
            "clip_start_ms": 0,
            "clip_end_ms": 30000,
            "scenes": [SceneItem(start_ms=0, end_ms=30000, type="talking_head", confidence=0.98, num_faces=1)],
            "tracks": [
                FaceTrackData(
                    track_id=0,
                    start_ms=0,
                    end_ms=30000,
                    avg_conf=0.96,
                    speaker_label="SPEAKER_00",
                    summary={"mean_cx": 0.52, "mean_cy": 0.38, "mean_w": 0.18, "mean_h": 0.22, "min_cx": 0.48, "max_cx": 0.55, "mouth_variance": 0.08},
                )
            ],
            "speaker_turns": [SpeakerTurn(start_ms=0, end_ms=30000, speaker_label="SPEAKER_00")],
            "content_meta": {"text_regions": [], "has_screen_share": False},
        },
        # 2. Two-Person Balanced - V1 Baseline
        {
            "id": "two_person_balanced",
            "video_slug": "lex_altman_cozy",
            "scene_type": "two_shot",
            "expected_mode": "balanced",
            "clip_start_ms": 0,
            "clip_end_ms": 45000,
            "scenes": [SceneItem(start_ms=0, end_ms=45000, type="two_shot", confidence=0.94, num_faces=2)],
            "tracks": [
                FaceTrackData(
                    track_id=0,
                    start_ms=0,
                    end_ms=45000,
                    avg_conf=0.92,
                    speaker_label="SPEAKER_00",
                    summary={"mean_cx": 0.44, "mean_cy": 0.40, "mean_w": 0.14, "mean_h": 0.18, "mouth_variance": 0.06},
                ),
                FaceTrackData(
                    track_id=1,
                    start_ms=0,
                    end_ms=45000,
                    avg_conf=0.90,
                    speaker_label="SPEAKER_01",
                    summary={"mean_cx": 0.56, "mean_cy": 0.40, "mean_w": 0.14, "mean_h": 0.18, "mouth_variance": 0.07},
                ),
            ],
            "speaker_turns": [
                SpeakerTurn(start_ms=0, end_ms=22000, speaker_label="SPEAKER_00"),
                SpeakerTurn(start_ms=22000, end_ms=45000, speaker_label="SPEAKER_01"),
            ],
            "content_meta": {"text_regions": [], "has_screen_share": False},
        },
        # 3. Presentation Slides Fallback - V1 Baseline
        {
            "id": "presentation_slides_fallback",
            "video_slug": "mit_open_courseware_slides",
            "scene_type": "screen_content",
            "expected_mode": "content_fit",  # or fit_blur
            "clip_start_ms": 0,
            "clip_end_ms": 25000,
            "scenes": [SceneItem(start_ms=0, end_ms=25000, type="screen_content", confidence=0.92, num_faces=0)],
            "tracks": [],
            "speaker_turns": [SpeakerTurn(start_ms=0, end_ms=25000, speaker_label="SPEAKER_00")],
            "content_meta": {
                "has_screen_share": True,
                "text_density": 0.35,
                "static_ratio": 0.82,
                "min_font_height_px": 28,
            },
        },
        # 4. 4-Person Panel (Group)
        {
            "id": "panel_4_person_tech",
            "video_slug": "panel_ai_summit_4p",
            "scene_type": "group",
            "expected_mode": "speaker_track",
            "clip_start_ms": 0,
            "clip_end_ms": 24000,
            "scenes": [SceneItem(start_ms=0, end_ms=24000, type="group", confidence=0.95, num_faces=4)],
            "tracks": [
                FaceTrackData(
                    track_id=0,
                    start_ms=0,
                    end_ms=24000,
                    avg_conf=0.93,
                    speaker_label="SPEAKER_00",
                    summary={"mean_cx": 0.18, "mean_cy": 0.42, "mean_w": 0.11, "mean_h": 0.15, "mouth_variance": 0.02},
                ),
                FaceTrackData(
                    track_id=1,
                    start_ms=0,
                    end_ms=24000,
                    avg_conf=0.95,
                    speaker_label="SPEAKER_01",
                    summary={"mean_cx": 0.38, "mean_cy": 0.40, "mean_w": 0.12, "mean_h": 0.16, "mouth_variance": 0.09},
                ),
                FaceTrackData(
                    track_id=2,
                    start_ms=0,
                    end_ms=24000,
                    avg_conf=0.94,
                    speaker_label="SPEAKER_02",
                    summary={"mean_cx": 0.62, "mean_cy": 0.41, "mean_w": 0.11, "mean_h": 0.15, "mouth_variance": 0.08},
                ),
                FaceTrackData(
                    track_id=3,
                    start_ms=0,
                    end_ms=24000,
                    avg_conf=0.92,
                    speaker_label="SPEAKER_03",
                    summary={"mean_cx": 0.82, "mean_cy": 0.42, "mean_w": 0.11, "mean_h": 0.15, "mouth_variance": 0.01},
                ),
            ],
            "speaker_turns": [
                SpeakerTurn(start_ms=0, end_ms=8000, speaker_label="SPEAKER_01"),
                SpeakerTurn(start_ms=8000, end_ms=16000, speaker_label="SPEAKER_02"),
                SpeakerTurn(start_ms=16000, end_ms=24000, speaker_label="SPEAKER_01"),
            ],
            "content_meta": {"has_screen_share": False},
        },
        # 5. Group Podcast Wide (Split Stack or Wide Framing)
        {
            "id": "group_podcast_wide",
            "video_slug": "allin_podcast_wide_group",
            "scene_type": "group",
            "expected_mode": "split_stack",
            "clip_start_ms": 0,
            "clip_end_ms": 30000,
            "scenes": [SceneItem(start_ms=0, end_ms=30000, type="group", confidence=0.93, num_faces=3)],
            "tracks": [
                FaceTrackData(
                    track_id=0,
                    start_ms=0,
                    end_ms=30000,
                    avg_conf=0.91,
                    speaker_label="SPEAKER_00",
                    summary={"mean_cx": 0.18, "mean_cy": 0.42, "mean_w": 0.12, "mean_h": 0.16, "mouth_variance": 0.08},
                ),
                FaceTrackData(
                    track_id=1,
                    start_ms=0,
                    end_ms=30000,
                    avg_conf=0.93,
                    speaker_label="SPEAKER_01",
                    summary={"mean_cx": 0.50, "mean_cy": 0.42, "mean_w": 0.12, "mean_h": 0.16, "mouth_variance": 0.02},
                ),
                FaceTrackData(
                    track_id=2,
                    start_ms=0,
                    end_ms=30000,
                    avg_conf=0.92,
                    speaker_label="SPEAKER_02",
                    summary={"mean_cx": 0.82, "mean_cy": 0.42, "mean_w": 0.12, "mean_h": 0.16, "mouth_variance": 0.08},
                ),
            ],
            "speaker_turns": [
                SpeakerTurn(start_ms=0, end_ms=15000, speaker_label="SPEAKER_00"),
                SpeakerTurn(start_ms=15000, end_ms=30000, speaker_label="SPEAKER_02"),
            ],
            "content_meta": {"has_screen_share": False, "split_candidate": True},
        },
        # 6. Interview with Cutaway / Reaction
        {
            "id": "interview_cutaway_reaction",
            "video_slug": "tech_interview_cutaway",
            "scene_type": "two_shot",
            "expected_mode": "speaker_track",
            "clip_start_ms": 0,
            "clip_end_ms": 20000,
            "scenes": [SceneItem(start_ms=0, end_ms=20000, type="two_shot", confidence=0.92, num_faces=2)],
            "tracks": [
                FaceTrackData(
                    track_id=0,
                    start_ms=0,
                    end_ms=20000,
                    avg_conf=0.94,
                    speaker_label="SPEAKER_00",
                    summary={"mean_cx": 0.32, "mean_cy": 0.40, "mean_w": 0.15, "mean_h": 0.19, "mouth_variance": 0.08},
                ),
                FaceTrackData(
                    track_id=1,
                    start_ms=0,
                    end_ms=20000,
                    avg_conf=0.92,
                    speaker_label="SPEAKER_01",
                    summary={"mean_cx": 0.68, "mean_cy": 0.40, "mean_w": 0.15, "mean_h": 0.19, "mouth_variance": 0.01},
                ),
            ],
            "speaker_turns": [
                SpeakerTurn(start_ms=0, end_ms=8000, speaker_label="SPEAKER_00"),
                # Long pause / laughter cutaway opportunity
                SpeakerTurn(start_ms=11000, end_ms=20000, speaker_label="SPEAKER_00"),
            ],
            "content_meta": {"has_screen_share": False, "reaction_window_ms": (8000, 11000)},
        },
        # 7. Webinar with Speaker Thumbnail PIP
        {
            "id": "webinar_slides_thumbnail_pip",
            "video_slug": "aws_webinar_speaker_pip",
            "scene_type": "hybrid_pip",
            "expected_mode": "pip",
            "clip_start_ms": 0,
            "clip_end_ms": 30000,
            "scenes": [SceneItem(start_ms=0, end_ms=30000, type="hybrid_pip", confidence=0.94, num_faces=1)],
            "tracks": [
                FaceTrackData(
                    track_id=0,
                    start_ms=0,
                    end_ms=30000,
                    avg_conf=0.90,
                    speaker_label="SPEAKER_00",
                    summary={"mean_cx": 0.88, "mean_cy": 0.14, "mean_w": 0.09, "mean_h": 0.11, "is_thumbnail": True},
                )
            ],
            "speaker_turns": [SpeakerTurn(start_ms=0, end_ms=30000, speaker_label="SPEAKER_00")],
            "content_meta": {
                "has_screen_share": True,
                "has_speaker_thumbnail": True,
                "thumbnail_pos": "top_right",
                "text_density": 0.40,
                "static_ratio": 0.85,
            },
        },
        # 8. Screen Recording Code Demo (Content Zoom)
        {
            "id": "screen_recording_code_demo",
            "video_slug": "vscode_rust_demo",
            "scene_type": "screen_content",
            "expected_mode": "content_zoom",
            "clip_start_ms": 0,
            "clip_end_ms": 28000,
            "scenes": [SceneItem(start_ms=0, end_ms=28000, type="screen_content", confidence=0.96, num_faces=0)],
            "tracks": [],
            "speaker_turns": [SpeakerTurn(start_ms=0, end_ms=28000, speaker_label="SPEAKER_00")],
            "content_meta": {
                "has_screen_share": True,
                "roi_box": (0.05, 0.10, 0.60, 0.75),
                "cursor_track": [(0, 0.25, 0.30), (14000, 0.28, 0.45), (28000, 0.30, 0.60)],
                "text_density": 0.45,
                "static_ratio": 0.78,
                "min_font_height_px": 22,  # scaled > 28px on 1080w
            },
        },
        # 9. Screen Recording Unreadable Tiny Text (Content Fit Fallback)
        {
            "id": "screen_recording_unreadable_tiny",
            "video_slug": "analytics_dashboard_micro_text",
            "scene_type": "screen_content",
            "expected_mode": "content_fit",
            "clip_start_ms": 0,
            "clip_end_ms": 20000,
            "scenes": [SceneItem(start_ms=0, end_ms=20000, type="screen_content", confidence=0.93, num_faces=0)],
            "tracks": [],
            "speaker_turns": [SpeakerTurn(start_ms=0, end_ms=20000, speaker_label="SPEAKER_00")],
            "content_meta": {
                "has_screen_share": True,
                "roi_box": (0.02, 0.05, 0.95, 0.90),
                "text_density": 0.65,
                "static_ratio": 0.88,
                "min_font_height_px": 6,  # tiny! Scaled is < 12px, violates readability threshold
                "unreadable_flag_expected": True,
            },
        },
        # 10. Whiteboard Proofs & Diagrams
        {
            "id": "whiteboard_lecture_roi",
            "video_slug": "mit_physics_whiteboard",
            "scene_type": "whiteboard",
            "expected_mode": "content_zoom",
            "clip_start_ms": 0,
            "clip_end_ms": 35000,
            "scenes": [SceneItem(start_ms=0, end_ms=35000, type="whiteboard", confidence=0.91, num_faces=1)],
            "tracks": [
                FaceTrackData(
                    track_id=0,
                    start_ms=0,
                    end_ms=35000,
                    avg_conf=0.85,
                    speaker_label="SPEAKER_00",
                    summary={"mean_cx": 0.15, "mean_cy": 0.45, "mean_w": 0.08, "mean_h": 0.12},
                )
            ],
            "speaker_turns": [SpeakerTurn(start_ms=0, end_ms=35000, speaker_label="SPEAKER_00")],
            "content_meta": {
                "has_whiteboard": True,
                "roi_box": (0.20, 0.12, 0.58, 0.72),
                "text_density": 0.28,
                "stroke_color_variance": 0.15,
                "min_font_height_px": 32,
            },
        },
        # 11. Hybrid Speaker Intro Then Slides
        {
            "id": "hybrid_speaker_then_slides",
            "video_slug": "keynote_hybrid_intro_to_slides",
            "scene_type": "screen_content",
            "expected_mode": "speaker_track",  # primary mode from first shot
            "clip_start_ms": 0,
            "clip_end_ms": 35000,
            "scenes": [
                SceneItem(start_ms=0, end_ms=15000, type="talking_head", confidence=0.96, num_faces=1),
                SceneItem(start_ms=15000, end_ms=35000, type="screen_content", confidence=0.94, num_faces=0),
            ],
            "tracks": [
                FaceTrackData(
                    track_id=0,
                    start_ms=0,
                    end_ms=15000,
                    avg_conf=0.95,
                    speaker_label="SPEAKER_00",
                    summary={"mean_cx": 0.50, "mean_cy": 0.38, "mean_w": 0.18, "mean_h": 0.22},
                )
            ],
            "speaker_turns": [
                SpeakerTurn(start_ms=0, end_ms=35000, speaker_label="SPEAKER_00"),
            ],
            "content_meta": {
                "has_screen_share": True,
                "screen_share_start_ms": 15000,
                "roi_box": (0.05, 0.05, 0.90, 0.90),
                "min_font_height_px": 28,
            },
        },
    ]
    return scenarios
