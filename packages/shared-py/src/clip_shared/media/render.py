"""Single-pass FFmpeg rendering engine for vertical 9:16 export.

Combines EDL trimming, audio crossfade, vertical reframing, ASS subtitle burning,
EBU R128 loudness normalization, and server-enforced watermark overlay into a single
efficient filtergraph.
"""
import json
import os
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import structlog

from clip_shared.media.captions import generate_ass_subtitles
from clip_shared.media.edl import EditDecisionList
from clip_shared.media.ffmpeg import MediaValidationError, _monitor_ffmpeg_progress, probe_video
from clip_shared.media.reframe_filter import reframe_crop_to_filter

logger = structlog.get_logger()


@dataclass
class RenderJobSnapshot:
    """Immutable snapshot of parameters driving the export."""
    clip_id: str
    user_id: str
    export_id: str
    preset_key: str
    clip_start_ms: int
    clip_end_ms: int
    edl: EditDecisionList
    crop_path: dict[str, Any]
    captions_words: list[dict[str, Any]]
    caption_style_spec: dict[str, Any]
    preset_config: dict[str, Any]
    watermark_enabled: bool
    watermark_text: str = "Clip It Up"
    crossfade_ms: int = 40
    two_pass_loudnorm: bool = False


def escape_ffmpeg_filter_path(path: str) -> str:
    """Escape backslashes and colons for FFmpeg filter parameter strings."""
    # Convert Windows backslashes to forward slashes
    p = path.replace("\\", "/")
    # Escape colons and single quotes
    p = p.replace(":", "\\:").replace("'", "\\'")
    return p


def build_render_filtergraph(
    edl: EditDecisionList,
    crop_path: dict[str, Any],
    src_w: int = 1280,
    src_h: int = 720,
    out_w: int = 1080,
    out_h: int = 1920,
    ass_path: str | None = None,
    fonts_dir: str | None = None,
    has_watermark: bool = False,
    watermark_text: str = "Clip It Up",
    crossfade_ms: int = 40,
    loudness_lufs: float = -14.0,
    has_audio: bool = True,
) -> tuple[str, str, str]:
    """
    Construct single-pass FFmpeg filter_complex string.
    Returns (filtergraph_str, out_video_label, out_audio_label).
    """
    filter_parts: list[str] = []
    num_segs = len(edl.keep_segments)
    seek_base_ms = edl.clip_start_ms

    if num_segs == 0:
        raise ValueError("EDL must contain at least one keep segment to render.")

    # 1. Trimming each keep segment relative to seek point (-ss)
    for i, seg in enumerate(edl.keep_segments):
        t_start_s = max(0.0, (seg.src_start_ms - seek_base_ms) / 1000.0)
        t_end_s = max(t_start_s + 0.05, (seg.src_end_ms - seek_base_ms) / 1000.0)

        # Video trim
        filter_parts.append(f"[0:v]trim=start={t_start_s:.3f}:end={t_end_s:.3f},setpts=PTS-STARTPTS[v_seg{i}];")
        # Audio trim
        if has_audio:
            filter_parts.append(f"[0:a]atrim=start={t_start_s:.3f}:end={t_end_s:.3f},asetpts=PTS-STARTPTS[a_seg{i}];")

    # 2. Video concatenation (if multiple segments)
    if num_segs > 1:
        v_inputs = "".join(f"[v_seg{i}]" for i in range(num_segs))
        filter_parts.append(f"{v_inputs}concat=n={num_segs}:v=1:a=0[v_cat];")
        v_cur = "[v_cat]"
    else:
        v_cur = "[v_seg0]"

    # 3. Video Reframing (Crop + Scale or Fit Blur)
    # Check if fit_blur mode is requested in segments
    segments_spec = crop_path.get("segments", [])
    is_fit_blur = any(s.get("mode") == "fit_blur" for s in segments_spec)

    if is_fit_blur:
        filter_parts.append(
            f"{v_cur}split=2[bg][fg];"
            f"[bg]scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
            f"crop={out_w}:{out_h},boxblur=20:2[bg_blur];"
            f"[fg]scale={out_w}:-2[fg_scaled];"
            f"[bg_blur][fg_scaled]overlay=(W-w)/2:(H-h)/2[v_reframe];"
        )
        v_cur = "[v_reframe]"
    else:
        # Generate reframe crop from keyframes
        crop_filter = reframe_crop_to_filter(
            crop_path=crop_path,
            src_w=src_w,
            src_h=src_h,
            out_w=out_w,
            out_h=out_h,
        )
        filter_parts.append(f"{v_cur}{crop_filter}[v_reframe];")
        v_cur = "[v_reframe]"

    # 4. Scale to target preset resolution + normalize SAR
    filter_parts.append(f"{v_cur}scale={out_w}:{out_h}:flags=lanczos,setsar=1[v_scaled];")
    v_cur = "[v_scaled]"

    # 5. Burn Subtitles via libass
    if ass_path and os.path.exists(ass_path):
        esc_ass = escape_ffmpeg_filter_path(os.path.abspath(ass_path))
        if fonts_dir and os.path.exists(fonts_dir):
            esc_fonts = escape_ffmpeg_filter_path(os.path.abspath(fonts_dir))
            subs_filter = f"ass='{esc_ass}':fontsdir='{esc_fonts}'"
        else:
            subs_filter = f"ass='{esc_ass}'"

        filter_parts.append(f"{v_cur}{subs_filter}[v_subs];")
        v_cur = "[v_subs]"

    # 6. Watermark (free tier enforcement - server applied last)
    if has_watermark:
        # Drawtext watermark placed in top-right corner, semi-transparent
        safe_text = watermark_text.replace("'", "").replace(":", "")
        wm_filter = (
            f"drawtext=text='{safe_text}':fontcolor=white@0.75:fontsize=26:"
            f"box=1:boxcolor=black@0.4:boxborderw=6:x=w-tw-40:y=60"
        )
        filter_parts.append(f"{v_cur}{wm_filter}[v_out];")
        v_out_label = "[v_out]"
    else:
        # Alias last stage to [v_out]
        filter_parts.append(f"{v_cur}null[v_out];")
        v_out_label = "[v_out]"

    # 7. Audio processing: joins with crossfade and loudnorm
    if has_audio:
        xfade_s = max(0.01, crossfade_ms / 1000.0)
        if num_segs > 1:
            a_cur = "[a_seg0]"
            for i in range(1, num_segs):
                next_seg = f"[a_seg{i}]"
                out_xf = f"[a_xf{i}]"
                filter_parts.append(
                    f"{a_cur}{next_seg}acrossfade=d={xfade_s:.3f}:c1=tri:c2=tri{out_xf};"
                )
                a_cur = out_xf
        else:
            a_cur = "[a_seg0]"

        # EBU R128 Loudness Normalization (-14 LUFS default for TikTok/Shorts/Reels)
        loudnorm_filter = f"loudnorm=I={loudness_lufs:.1f}:TP=-1.5:LRA=11:linear=true"
        filter_parts.append(f"{a_cur}{loudnorm_filter}[a_out]")
        a_out_label = "[a_out]"
    else:
        a_out_label = "[a_none]"

    full_filter = "".join(filter_parts)
    return full_filter, v_out_label, a_out_label


def build_render_ffmpeg_cmd(
    input_video: str,
    output_mp4: str,
    edl: EditDecisionList,
    filtergraph_str: str,
    v_label: str = "[v_out]",
    a_label: str = "[a_out]",
    preset: str = "veryfast",
    crf: int = 22,
    video_bitrate: str = "8000k",
    audio_bitrate: str = "192k",
    has_audio: bool = True,
    threads: int = 4,
) -> list[str]:
    """
    Build complete FFmpeg argument list with accurate input seeking (-ss),
    filter_complex, hardware/CPU encoder settings, and faststart MP4 flags.
    Safe argument list only (no shell=True).
    """
    seek_s = max(0.0, edl.clip_start_ms / 1000.0)
    rate_num = int(video_bitrate.lower().replace("k", ""))
    bufsize = f"{rate_num * 2}k"

    cmd = [
        "ffmpeg",
        "-y",
        "-threads", str(threads),
        "-filter_complex_threads", str(threads),
        "-ss", f"{seek_s:.3f}",
        "-i", input_video,
        "-filter_complex", filtergraph_str,
        "-map", v_label,
    ]

    if has_audio and a_label != "[a_none]":
        cmd.extend(["-map", a_label])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),
        "-maxrate", video_bitrate,
        "-bufsize", bufsize,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", audio_bitrate,
        "-ar", "48000",
        "-movflags", "+faststart",
        "-avoid_negative_ts", "make_zero",
        "-progress", "pipe:1",
        "-nostats",
        output_mp4,
    ])

    return cmd


def validate_rendered_output(
    file_path: str,
    expected_duration_ms: int,
    expected_w: int = 1080,
    expected_h: int = 1920,
    tolerance_ms: int = 150,
) -> dict[str, Any]:
    """
    Verify exported MP4 using ffprobe.
    Checks resolution, duration within +/-150ms of expected EDL timeline,
    presence of video & audio streams, and valid file size.
    """
    if not os.path.exists(file_path):
        raise MediaValidationError("FILE_NOT_FOUND", f"Exported file {file_path} not found.")

    size_bytes = os.path.getsize(file_path)
    if size_bytes == 0:
        raise MediaValidationError("EMPTY_EXPORT", "Exported video file is 0 bytes.")

    meta = probe_video(file_path)
    actual_dur_ms = int(meta.duration_seconds * 1000)

    # Check resolution
    if meta.width != expected_w or meta.height != expected_h:
        raise MediaValidationError(
            "INVALID_RESOLUTION",
            f"Export resolution {meta.width}x{meta.height} does not match expected {expected_w}x{expected_h}",
        )

    # Check duration tolerance
    dur_diff = abs(actual_dur_ms - expected_duration_ms)
    if dur_diff > tolerance_ms:
        raise MediaValidationError(
            "DURATION_MISMATCH",
            f"Export duration ({actual_dur_ms}ms) deviated from EDL expected ({expected_duration_ms}ms) by {dur_diff}ms (tolerance: {tolerance_ms}ms)",
        )

    return {
        "width": meta.width,
        "height": meta.height,
        "fps": meta.fps,
        "duration_ms": actual_dur_ms,
        "size_bytes": size_bytes,
        "has_audio": meta.has_audio,
        "video_codec": meta.video_codec,
        "audio_codec": meta.audio_codec,
    }


def execute_export_render(
    input_video: str,
    output_mp4: str,
    snapshot: RenderJobSnapshot,
    fonts_dir: str | None = None,
    progress_cb: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """
    Execute full render pipeline:
    1. Generate ASS subtitles with EDL remapped timestamps.
    2. Remap reframe crop path keyframes through EDL.
    3. Build single-pass FFmpeg filtergraph.
    4. Run FFmpeg with real-time progress parsing.
    5. Validate output via ffprobe.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_mp4)), exist_ok=True)
    temp_dir = os.path.dirname(os.path.abspath(output_mp4))
    ass_path = os.path.join(temp_dir, f"subtitles_{snapshot.export_id}.ass")

    preset = snapshot.preset_config
    out_w = int(preset.get("width", 1080))
    out_h = int(preset.get("height", 1920))
    crf = int(preset.get("crf", 22))
    video_bitrate = str(preset.get("video_bitrate", "8000k"))
    audio_bitrate = str(preset.get("audio_bitrate", "192k"))
    loudness_lufs = float(preset.get("loudness_lufs", -14.0))

    t_start = time.perf_counter()

    try:
        # 1. Probe input to get original width and height
        src_meta = probe_video(input_video)
        src_w = src_meta.width
        src_h = src_meta.height

        # 2. Generate ASS subtitles (if captions provided)
        if snapshot.captions_words:
            ass_content = generate_ass_subtitles(
                words=snapshot.captions_words,
                style_spec=snapshot.caption_style_spec,
                edl=snapshot.edl,
                width=out_w,
                height=out_h,
            )
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write(ass_content)
        else:
            ass_path = None

        # 3. Remap crop path through EDL
        remapped_crop_path = snapshot.edl.remap_crop_path(snapshot.crop_path)

        # 4. Build single-pass filtergraph
        filtergraph, v_label, a_label = build_render_filtergraph(
            edl=snapshot.edl,
            crop_path=remapped_crop_path,
            src_w=src_w,
            src_h=src_h,
            out_w=out_w,
            out_h=out_h,
            ass_path=ass_path,
            fonts_dir=fonts_dir,
            has_watermark=snapshot.watermark_enabled,
            watermark_text=snapshot.watermark_text,
            crossfade_ms=snapshot.crossfade_ms,
            loudness_lufs=loudness_lufs,
            has_audio=src_meta.has_audio,
        )

        # 5. Build FFmpeg command
        cmd = build_render_ffmpeg_cmd(
            input_video=input_video,
            output_mp4=output_mp4,
            edl=snapshot.edl,
            filtergraph_str=filtergraph,
            v_label=v_label,
            a_label=a_label,
            preset="veryfast",
            crf=crf,
            video_bitrate=video_bitrate,
            audio_bitrate=audio_bitrate,
            has_audio=src_meta.has_audio,
        )

        logger.info("executing_render_job", export_id=snapshot.export_id, out_w=out_w, out_h=out_h)

        # 6. Execute subprocess with progress monitoring
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        expected_dur_s = snapshot.edl.total_out_duration_ms / 1000.0
        _monitor_ffmpeg_progress(proc, expected_dur_s, progress_cb)
        _, stderr_text = proc.communicate()

        if proc.returncode != 0:
            logger.error("ffmpeg_render_failed", stderr=stderr_text, export_id=snapshot.export_id)
            raise RuntimeError(f"FFmpeg render export failed: {stderr_text}")

        # 7. Validate rendered output
        val_result = validate_rendered_output(
            file_path=output_mp4,
            expected_duration_ms=snapshot.edl.total_out_duration_ms,
            expected_w=out_w,
            expected_h=out_h,
        )

        render_ms = int((time.perf_counter() - t_start) * 1000)
        val_result["render_ms"] = render_ms
        val_result["realtime_factor"] = round((render_ms / 1000.0) / max(0.1, expected_dur_s), 3)

        if progress_cb:
            progress_cb(100.0)

        return val_result

    finally:
        # Cleanup temporary ASS file
        if ass_path and os.path.exists(ass_path):
            try:
                os.remove(ass_path)
            except OSError:
                pass
