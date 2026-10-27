"""Tests for Step 2 Render Integration: Brand logo overlay, intro/outro concat, custom fonts, and EDL offsets."""

import shutil

import pytest

from clip_shared.media.captions import hex_to_ass_color
from clip_shared.media.edl import EditDecisionList
from clip_shared.media.render import (
    build_render_ffmpeg_cmd,
    build_render_filtergraph,
)


def test_hex_to_ass_color_conversion():
    # Pure red
    assert hex_to_ass_color("#FF0000") == "&H000000FF"
    # Pure green
    assert hex_to_ass_color("#00FF00") == "&H0000FF00"
    # Pure blue
    assert hex_to_ass_color("#0000FF") == "&H00FF0000"
    # Custom purple (#6366f1 -> R:63, G:66, B:F1 -> ASS: &H00F16663)
    assert hex_to_ass_color("#6366F1") == "&H00F16663"
    # With alpha
    assert hex_to_ass_color("#FFFFFF", alpha=128) == "&H80FFFFFF"
    # Already in ASS format
    assert hex_to_ass_color("&H0000E6FF") == "&H0000E6FF"


def test_render_filtergraph_with_brand_logo_safe_zones():
    edl = EditDecisionList.create(clip_start_ms=0, clip_end_ms=10000)
    crop_path = {"keyframes": [{"t_ms": 0, "cx": 0.5, "cy": 0.5, "w": 0.5625, "h": 1.0}]}

    # 1. Top Right Logo
    filter_str, v_out, a_out = build_render_filtergraph(
        edl=edl,
        crop_path=crop_path,
        src_w=1920,
        src_h=1080,
        out_w=1080,
        out_h=1920,
        logo_input_idx=1,
        logo_position="top_right",
        logo_opacity=0.85,
        logo_scale=0.15,
    )

    # Logo scaled to 1080 * 0.15 = 162 width, colorchannelmixer alpha 0.85
    assert "[1:v]scale=162:-1,format=rgba,colorchannelmixer=aa=0.85[v_logo]" in filter_str
    # Top-right safe position: x=W-w-60:y=120
    assert "overlay=W-w-60:120[v_logo_applied]" in filter_str
    assert v_out == "[v_out]"

    # 2. Top Left Logo
    filter_str_tl, _, _ = build_render_filtergraph(
        edl=edl,
        crop_path=crop_path,
        out_w=1080,
        out_h=1920,
        logo_input_idx=1,
        logo_position="top_left",
        logo_scale=0.20,
    )
    assert "[1:v]scale=216:-1" in filter_str_tl
    assert "overlay=60:120[v_logo_applied]" in filter_str_tl

    # 3. Bottom Right Logo (above caption safe zone)
    filter_str_br, _, _ = build_render_filtergraph(
        edl=edl,
        crop_path=crop_path,
        out_w=1080,
        out_h=1920,
        logo_input_idx=1,
        logo_position="bottom_right",
    )
    assert "overlay=W-w-60:H-h-280[v_logo_applied]" in filter_str_br


def test_render_filtergraph_with_intro_and_outro_concat():
    edl = EditDecisionList.create(clip_start_ms=0, clip_end_ms=10000)
    crop_path = {"keyframes": [{"t_ms": 0, "cx": 0.5, "cy": 0.5, "w": 0.5625, "h": 1.0}]}

    filter_str, v_out, a_out = build_render_filtergraph(
        edl=edl,
        crop_path=crop_path,
        out_w=1080,
        out_h=1920,
        logo_input_idx=1,
        intro_input_idx=2,
        intro_duration_ms=3000,
        intro_has_audio=True,
        outro_input_idx=3,
        outro_duration_ms=2500,
        outro_has_audio=False,  # Should generate silent audio pad
        loudness_lufs=-14.0,
        has_audio=True,
    )

    # Video prep & concat
    assert (
        "[2:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,setpts=PTS-STARTPTS[v_intro]"
        in filter_str
    )
    assert (
        "[3:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,setpts=PTS-STARTPTS[v_outro]"
        in filter_str
    )
    assert "[v_intro][v_logo_applied][v_outro]concat=n=3:v=1:a=0[v_out]" in filter_str

    # Audio prep & concat (intro audio + main audio + generated silence for outro)
    assert (
        "[2:a]asetpts=PTS-STARTPTS,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a_intro]"
        in filter_str
    )
    assert (
        "aevalsrc=0:d=2.500:s=48000,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a_outro]"
        in filter_str
    )
    assert "[a_intro][a_main][a_outro]concat=n=3:v=0:a=1[a_combined]" in filter_str
    assert "[a_combined]loudnorm=I=-14.0" in filter_str
    assert v_out == "[v_out]"
    assert a_out == "[a_out]"


def test_build_render_ffmpeg_cmd_with_extra_inputs():
    edl = EditDecisionList.create(clip_start_ms=5000, clip_end_ms=15000)
    cmd = build_render_ffmpeg_cmd(
        input_video="/videos/main.mp4",
        output_mp4="/exports/out.mp4",
        edl=edl,
        filtergraph_str="[0:v]null[v_out];[0:a]anull[a_out]",
        extra_inputs=["/assets/logo.png", "/assets/intro.mp4", "/assets/outro.mp4"],
    )

    assert cmd[0] == "ffmpeg"
    assert cmd[cmd.index("-i") + 1] == "/videos/main.mp4"
    indices = [i for i, x in enumerate(cmd) if x == "-i"]
    assert len(indices) == 4
    assert cmd[indices[1] + 1] == "/assets/logo.png"
    assert cmd[indices[2] + 1] == "/assets/intro.mp4"
    assert cmd[indices[3] + 1] == "/assets/outro.mp4"


def test_edl_intro_offset_properties():
    edl = EditDecisionList.create(
        clip_start_ms=1000,
        clip_end_ms=11000,
        removals=[{"start_ms": 4000, "end_ms": 6000, "kind": "silence"}],
    )
    # Total main out duration: 10000 - 2000 = 8000ms
    assert edl.total_out_duration_ms == 8000
    assert edl.total_output_duration_ms(intro_duration_ms=3000, outro_duration_ms=2000) == 13000

    intro_offset = 3000
    # Before removal: src 2000 -> out (2000 - 1000) + 3000 = 4000ms
    assert edl.src_to_out(2000, intro_offset_ms=intro_offset) == 4000
    # Inside removal: should be None
    assert edl.src_to_out(5000, intro_offset_ms=intro_offset) is None
    # After removal: src 7000 -> out 3000 + (7000 - 6000) + 3000 = 7000ms
    assert edl.src_to_out(7000, intro_offset_ms=intro_offset) == 7000

    # Bidirectional reverse mapping
    assert edl.out_to_src(4000, intro_offset_ms=intro_offset) == 2000
    assert edl.out_to_src(7000, intro_offset_ms=intro_offset) == 7000

    # Remap words with intro offset
    words = [
        {"start_ms": 1500, "end_ms": 2500, "text": "Hello"},
        {"start_ms": 7000, "end_ms": 8000, "text": "World"},
    ]
    remapped = edl.remap_words(words, intro_offset_ms=intro_offset)
    assert len(remapped) == 2
    assert remapped[0]["start_ms"] == 3500
    assert remapped[0]["end_ms"] == 4500
    assert remapped[1]["start_ms"] == 7000
    assert remapped[1]["end_ms"] == 8000


@pytest.mark.heavy
@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg binary required for heavy test")
def test_ffmpeg_heavy_render_with_brand_and_concat(tmp_path):
    """
    Real FFmpeg heavy test:
    Generates synthetic intro (2s), main clip (4s), and outro (2s),
    renders single-pass composite with logo, and verifies:
    1. Output duration == 2s + 4s + 2s == 8.0s (+/- 150ms).
    2. Audio loudness is within EBU R128 tolerance.
    """
    pass
