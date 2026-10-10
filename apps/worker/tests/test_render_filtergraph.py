from unittest.mock import patch

import pytest

from clip_shared.media.edl import EditDecisionList
from clip_shared.media.ffmpeg import MediaValidationError, VideoMetadata
from clip_shared.media.render import (
    build_render_ffmpeg_cmd,
    build_render_filtergraph,
    validate_rendered_output,
)


def test_build_render_filtergraph_single_segment_with_watermark_and_subtitles():
    """Verify filtergraph construction for single keep segment + subtitles + watermark."""
    edl = EditDecisionList.create(clip_start_ms=5000, clip_end_ms=15000)
    crop_path = {
        "keyframes": [{"t_ms": 0, "cx": 0.5, "cy": 0.5, "w": 0.5625, "h": 1.0}],
    }

    filter_str, v_out, a_out = build_render_filtergraph(
        edl=edl,
        crop_path=crop_path,
        src_w=1920,
        src_h=1080,
        out_w=1080,
        out_h=1920,
        ass_path="/tmp/test_subs.ass",
        has_watermark=True,
        watermark_text="Clip It Up",
        loudness_lufs=-14.0,
        has_audio=True,
    )

    assert "[0:v]trim=start=0.000:end=10.000,setpts=PTS-STARTPTS[v_seg0]" in filter_str
    assert "[0:a]atrim=start=0.000:end=10.000,asetpts=PTS-STARTPTS[a_seg0]" in filter_str
    assert "scale=1080:1920" in filter_str
    assert "drawtext=text='Clip It Up'" in filter_str
    assert "loudnorm=I=-14.0" in filter_str
    assert v_out == "[v_out]"
    assert a_out == "[a_out]"


def test_build_render_filtergraph_multi_segment_with_audio_crossfade():
    """Verify filtergraph with cuts generates video concat and audio acrossfade chain."""
    edl = EditDecisionList.create(
        clip_start_ms=0,
        clip_end_ms=10000,
        removals=[{"start_ms": 3000, "end_ms": 5000, "kind": "silence"}],
    )
    crop_path = {"keyframes": [{"t_ms": 0, "cx": 0.5, "cy": 0.5, "w": 0.5625, "h": 1.0}]}

    filter_str, v_out, a_out = build_render_filtergraph(
        edl=edl,
        crop_path=crop_path,
        src_w=1920,
        src_h=1080,
        out_w=1080,
        out_h=1920,
        has_watermark=False,
        crossfade_ms=40,
        has_audio=True,
    )

    # Check 2 video trims and concat
    assert "[v_seg0][v_seg1]concat=n=2:v=1:a=0[v_cat]" in filter_str
    # Check audio acrossfade
    assert "acrossfade=d=0.040:c1=tri:c2=tri[a_xf1]" in filter_str
    assert "loudnorm=I=-14.0" in filter_str


def test_build_render_ffmpeg_cmd_structure():
    """Verify safe FFmpeg argument list with -ss, -filter_complex, CRF, and bitrates."""
    edl = EditDecisionList.create(clip_start_ms=10500, clip_end_ms=30500)
    cmd = build_render_ffmpeg_cmd(
        input_video="/videos/source.mp4",
        output_mp4="/exports/out.mp4",
        edl=edl,
        filtergraph_str="[0:v]null[v_out];[0:a]anull[a_out]",
        v_label="[v_out]",
        a_label="[a_out]",
        preset="veryfast",
        crf=21,
        video_bitrate="8500k",
        audio_bitrate="192k",
    )

    assert cmd[0] == "ffmpeg"
    assert "-ss" in cmd
    ss_idx = cmd.index("-ss")
    assert cmd[ss_idx + 1] == "10.500"
    assert "-filter_complex" in cmd
    assert "-crf" in cmd
    assert cmd[cmd.index("-crf") + 1] == "21"
    assert "-maxrate" in cmd
    assert cmd[cmd.index("-maxrate") + 1] == "8500k"
    assert "-c:v" in cmd
    assert cmd[cmd.index("-c:v") + 1] == "libx264"
    assert "-c:a" in cmd
    assert cmd[cmd.index("-c:a") + 1] == "aac"
    assert cmd[-1] == "/exports/out.mp4"


@patch("os.path.exists", return_value=True)
@patch("os.path.getsize", return_value=1024 * 1024)
@patch("clip_shared.media.render.probe_video")
def test_validate_rendered_output_success(mock_probe, mock_getsize, mock_exists):
    """Verify validate_rendered_output accepts matching output dimensions and duration."""
    mock_probe.return_value = VideoMetadata(
        duration_seconds=20.05,
        width=1080,
        height=1920,
        fps=30.0,
        has_audio=True,
        has_video=True,
        video_codec="h264",
        audio_codec="aac",
    )

    res = validate_rendered_output(
        file_path="/dummy/out.mp4",
        expected_duration_ms=20000,
        expected_w=1080,
        expected_h=1920,
        tolerance_ms=150,
    )

    assert res["width"] == 1080
    assert res["height"] == 1920
    assert res["has_audio"] is True


@patch("os.path.exists", return_value=True)
@patch("os.path.getsize", return_value=1024 * 1024)
@patch("clip_shared.media.render.probe_video")
def test_validate_rendered_output_duration_mismatch(mock_probe, mock_getsize, mock_exists):
    """Verify validation fails if duration exceeds tolerance."""
    mock_probe.return_value = VideoMetadata(
        duration_seconds=25.0,
        width=1080,
        height=1920,
        fps=30.0,
        has_audio=True,
        has_video=True,
        video_codec="h264",
        audio_codec="aac",
    )

    with pytest.raises(MediaValidationError) as exc:
        validate_rendered_output(
            file_path="/dummy/out.mp4",
            expected_duration_ms=20000,  # 5000ms difference > 150ms
        )
    assert exc.value.code == "DURATION_MISMATCH"
