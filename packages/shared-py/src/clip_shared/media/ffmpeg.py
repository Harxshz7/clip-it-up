import json
import os
import shutil
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass

import structlog

logger = structlog.get_logger()


class MediaValidationError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class VideoMetadata:
    duration_seconds: float
    width: int
    height: int
    fps: float
    has_audio: bool
    has_video: bool
    video_codec: str
    audio_codec: str | None = None


def check_disk_space(target_dir: str, required_bytes: int) -> None:
    """Ensure sufficient free disk space exists before downloading or processing."""
    os.makedirs(target_dir, exist_ok=True)
    usage = shutil.disk_usage(target_dir)
    # Require at least 1.5x of the required space plus 500MB safety buffer
    min_required = int(required_bytes * 1.5) + (500 * 1024 * 1024)
    if usage.free < min_required:
        raise MediaValidationError(
            code="INSUFFICIENT_DISK_SPACE",
            message=f"Insufficient worker disk space. Free: {usage.free / (1024*1024):.1f}MB, Required: {min_required / (1024*1024):.1f}MB",
        )


def probe_video(file_path: str, max_duration_min: int = 120) -> VideoMetadata:
    """
    Run ffprobe on file_path and extract metadata.
    Validates duration, video streams, audio streams, and detects corrupt files.
    """
    if not os.path.exists(file_path):
        raise MediaValidationError("FILE_NOT_FOUND", f"File {file_path} not found.")

    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration,size,bit_rate:stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,duration",
        "-print_format", "json",
        file_path,
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        # If ffprobe binary is missing in non-docker environment, raise FileNotFoundError
        raise FileNotFoundError("ffprobe binary not found in worker environment.") from None

    if proc.returncode != 0:
        err_stderr = proc.stderr.strip()
        logger.error("ffprobe_failed", stderr=err_stderr, file_path=file_path)
        raise MediaValidationError("CORRUPT_FILE", f"Unable to probe video: {err_stderr or 'Corrupt file header'}")

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise MediaValidationError("CORRUPT_FILE", "Invalid ffprobe JSON response.") from e

    streams = data.get("streams", [])
    format_info = data.get("format", {})

    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    if not video_streams:
        raise MediaValidationError("NO_VIDEO_STREAM", "The uploaded media does not contain a valid video stream.")

    v_stream = video_streams[0]
    has_audio = len(audio_streams) > 0
    audio_codec = audio_streams[0].get("codec_name") if has_audio else None
    video_codec = v_stream.get("codec_name", "unknown")

    # Extract duration
    raw_duration = format_info.get("duration") or v_stream.get("duration")
    if not raw_duration or float(raw_duration) <= 0:
        raise MediaValidationError("CORRUPT_FILE", "Media duration is zero or undetermined.")

    duration_sec = float(raw_duration)
    if duration_sec > (max_duration_min * 60):
        raise MediaValidationError(
            "TOO_LONG",
            f"Video duration ({duration_sec / 60:.1f} min) exceeds maximum limit of {max_duration_min} minutes.",
        )

    # Dimensions
    width = int(v_stream.get("width") or 0)
    height = int(v_stream.get("height") or 0)

    # FPS
    fps_str = v_stream.get("avg_frame_rate") or v_stream.get("r_frame_rate") or "30/1"
    try:
        if "/" in fps_str:
            num, den = fps_str.split("/")
            fps = float(num) / float(den) if float(den) != 0 else 30.0
        else:
            fps = float(fps_str)
    except Exception:
        fps = 30.0

    return VideoMetadata(
        duration_seconds=duration_sec,
        width=width,
        height=height,
        fps=fps,
        has_audio=has_audio,
        has_video=True,
        video_codec=video_codec,
        audio_codec=audio_codec,
    )


def _parse_time_to_seconds(time_str: str) -> float:
    """Parse FFmpeg time string HH:MM:SS.micro to float seconds."""
    try:
        parts = time_str.strip().split(":")
        if len(parts) == 3:
            hours = float(parts[0])
            mins = float(parts[1])
            secs = float(parts[2])
            return hours * 3600 + mins * 60 + secs
    except Exception:
        pass
    return 0.0


def _monitor_ffmpeg_progress(
    process: subprocess.Popen,
    total_duration_seconds: float,
    progress_cb: Callable[[float], None] | None,
) -> None:
    """Read pipe:1 stdout lines from FFmpeg and invoke progress callback."""
    if not process.stdout:
        return

    for line in process.stdout:
        line_str = line.strip()
        if not line_str:
            continue
        if "=" in line_str:
            key, val = line_str.split("=", 1)
            key = key.strip()
            val = val.strip()

            if key == "out_time_us":
                try:
                    us = int(val)
                    cur_sec = us / 1_000_000.0
                    if total_duration_seconds > 0 and progress_cb:
                        pct = min(100.0, max(0.0, (cur_sec / total_duration_seconds) * 100.0))
                        progress_cb(pct)
                except ValueError:
                    pass
            elif key == "out_time":
                cur_sec = _parse_time_to_seconds(val)
                if total_duration_seconds > 0 and progress_cb:
                    pct = min(100.0, max(0.0, (cur_sec / total_duration_seconds) * 100.0))
                    progress_cb(pct)
            elif key == "progress" and val == "end":
                if progress_cb:
                    progress_cb(100.0)


def extract_audio(
    input_video: str,
    output_wav: str,
    duration_seconds: float = 0.0,
    progress_cb: Callable[[float], None] | None = None,
) -> None:
    """
    Extract 16kHz mono 16-bit PCM WAV from input video using FFmpeg.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_wav)), exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_video,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        "-progress", "pipe:1",
        "-nostats",
        output_wav,
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    _monitor_ffmpeg_progress(proc, duration_seconds, progress_cb)
    _, stderr_text = proc.communicate()

    if proc.returncode != 0:
        logger.error("ffmpeg_audio_extract_failed", stderr=stderr_text)
        raise RuntimeError(f"FFmpeg audio extraction failed: {stderr_text}")

    if progress_cb:
        progress_cb(100.0)


def generate_proxy(
    input_video: str,
    output_mp4: str,
    duration_seconds: float = 0.0,
    progress_cb: Callable[[float], None] | None = None,
) -> None:
    """
    Generate 720p H.264 preview proxy with faststart for web playback.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_mp4)), exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_video,
        "-vf", "scale=-2:min(720\\,ih)",
        "-c:v", "libx264",
        "-crf", "23",
        "-preset", "veryfast",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        "-progress", "pipe:1",
        "-nostats",
        output_mp4,
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    _monitor_ffmpeg_progress(proc, duration_seconds, progress_cb)
    _, stderr_text = proc.communicate()

    if proc.returncode != 0:
        logger.error("ffmpeg_proxy_generation_failed", stderr=stderr_text)
        raise RuntimeError(f"FFmpeg proxy generation failed: {stderr_text}")

    if progress_cb:
        progress_cb(100.0)


def run_parallel_audio_and_proxy(
    input_video: str,
    output_wav: str,
    output_mp4: str,
    duration_seconds: float,
    progress_cb: Callable[[float], None] | None = None,
) -> None:
    """
    Run audio extraction and proxy generation concurrently and aggregate progress.
    """
    progress_audio = [0.0]
    progress_proxy = [0.0]

    def update_combined():
        if progress_cb:
            # Weight proxy 70% and audio 30% of total stage duration
            combined = (progress_audio[0] * 0.3) + (progress_proxy[0] * 0.7)
            progress_cb(combined)

    def audio_worker():
        def cb(pct):
            progress_audio[0] = pct
            update_combined()
        extract_audio(input_video, output_wav, duration_seconds, progress_cb=cb)

    def proxy_worker():
        def cb(pct):
            progress_proxy[0] = pct
            update_combined()
        generate_proxy(input_video, output_mp4, duration_seconds, progress_cb=cb)

    t_audio = threading.Thread(target=audio_worker)
    t_proxy = threading.Thread(target=proxy_worker)

    t_audio.start()
    t_proxy.start()

    t_audio.join()
    t_proxy.join()

    if progress_cb:
        progress_cb(100.0)


def build_crude_clip_ffmpeg_cmd(
    input_video: str,
    output_mp4: str,
    start_ms: int,
    end_ms: int,
    kind: str = "horizontal",
    watermark_text: str = "Preview",
) -> list[str]:
    """
    Construct safe FFmpeg argument list for crude clip export with accurate seek and re-encoding.
    Argument lists only (no shell=True).
    """
    start_s = max(0.0, start_ms / 1000.0)
    duration_s = max(0.1, (end_ms - start_ms) / 1000.0)

    # Watermark filter
    watermark_filter = (
        f"drawtext=text='{watermark_text}':fontsize=24:fontcolor=white@0.8:"
        "x=w-tw-20:y=20:box=1:boxcolor=black@0.5:boxborderw=4"
    )

    if kind == "vertical_center":
        # 9:16 naive center crop + watermark
        vf_filter = f"crop=min(iw\\,ih*9/16):min(ih\\,iw*16/9):(iw-min(iw\\,ih*9/16))/2:(ih-min(ih\\,iw*16/9))/2,{watermark_filter}"
    else:
        # Horizontal with watermark
        vf_filter = watermark_filter

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", f"{start_s:.3f}",
        "-i", input_video,
        "-t", f"{duration_s:.3f}",
        "-vf", vf_filter,
        "-c:v", "libx264",
        "-crf", "23",
        "-preset", "veryfast",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        "-avoid_negative_ts", "make_zero",
        "-progress", "pipe:1",
        "-nostats",
        output_mp4,
    ]
    return cmd


def export_crude_clip(
    input_video: str,
    output_mp4: str,
    start_ms: int,
    end_ms: int,
    kind: str = "horizontal",
    watermark_text: str = "Preview",
    progress_cb: Callable[[float], None] | None = None,
) -> None:
    """
    Export crude cut clip (horizontal or naive 9:16 vertical crop) from original video.
    Re-encodes H.264/AAC with watermark and cleans up properly. Idempotent rerun overwrites.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_mp4)), exist_ok=True)
    cmd = build_crude_clip_ffmpeg_cmd(
        input_video=input_video,
        output_mp4=output_mp4,
        start_ms=start_ms,
        end_ms=end_ms,
        kind=kind,
        watermark_text=watermark_text,
    )

    duration_s = max(0.1, (end_ms - start_ms) / 1000.0)

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        _monitor_ffmpeg_progress(proc, duration_s, progress_cb)
        _, stderr_text = proc.communicate()

        if proc.returncode != 0:
            logger.error("ffmpeg_crude_export_failed", stderr=stderr_text, kind=kind)
            # Fallback if drawtext is missing or filter fails: try without drawtext
            if "drawtext" in stderr_text:
                logger.warn("retrying_export_without_drawtext", kind=kind)
                fallback_cmd = [
                    "ffmpeg", "-y",
                    "-ss", f"{(start_ms/1000.0):.3f}",
                    "-i", input_video,
                    "-t", f"{duration_s:.3f}",
                ]
                if kind == "vertical_center":
                    fallback_cmd.extend(["-vf", "crop=min(iw\\,ih*9/16):min(ih\\,iw*16/9):(iw-min(iw\\,ih*9/16))/2:(ih-min(ih\\,iw*16/9))/2"])
                fallback_cmd.extend([
                    "-c:v", "libx264", "-crf", "23", "-preset", "veryfast",
                    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
                    "-avoid_negative_ts", "make_zero",
                    output_mp4,
                ])
                fb_proc = subprocess.run(fallback_cmd, capture_output=True, text=True, check=False)
                if fb_proc.returncode != 0:
                    raise RuntimeError(f"FFmpeg crude export fallback failed: {fb_proc.stderr}")
            else:
                raise RuntimeError(f"FFmpeg crude export failed: {stderr_text}")

        if progress_cb:
            progress_cb(100.0)
    except FileNotFoundError:
        raise FileNotFoundError("ffmpeg binary not found in worker environment.")

