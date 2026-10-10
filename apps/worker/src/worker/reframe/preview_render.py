"""Preview renderer generating quick low-res 360x640 vertical MP4 preview using FFmpeg."""
import subprocess
from typing import Any

import structlog

from clip_shared.schemas.reframe import ReframeCropPath
from worker.reframe.ffmpeg_filter import crop_path_to_ffmpeg_filter

logger = structlog.get_logger()


def render_reframe_preview(
    video_path: str,
    crop_path: ReframeCropPath | dict[str, Any],
    start_ms: int,
    end_ms: int,
    out_path: str,
    out_w: int = 360,
    out_h: int = 640,
) -> str:
    """
    Render a fast low-res 9:16 preview MP4 for QA contact sheets and tests.
    """
    start_s = start_ms / 1000.0
    duration_s = max(0.5, (end_ms - start_ms) / 1000.0)

    # Probe dimensions or default to 1280x720
    src_w = 1280
    src_h = 720
    if isinstance(crop_path, dict):
        src_w = crop_path.get("source_width") or 1280
        src_h = crop_path.get("source_height") or 720
    else:
        src_w = crop_path.source_width or 1280
        src_h = crop_path.source_height or 720

    filter_str = crop_path_to_ffmpeg_filter(crop_path, src_w=src_w, src_h=src_h, out_w=out_w, out_h=out_h)

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", f"{start_s:.3f}",
        "-t", f"{duration_s:.3f}",
        "-i", video_path,
        "-vf", filter_str,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "28",
        "-c:a", "aac",
        "-b:a", "64k",
        "-movflags", "+faststart",
        out_path,
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return out_path
    except subprocess.CalledProcessError as e:
        logger.error("FFmpeg reframe preview render failed", error=e.stderr)
        raise RuntimeError(f"FFmpeg preview render failed: {e.stderr}")
