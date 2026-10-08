import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from clip_shared.media.ffmpeg import build_crude_clip_ffmpeg_cmd, export_crude_clip


def test_build_crude_clip_ffmpeg_cmd_horizontal():
    """Verify safe FFmpeg argument list construction for horizontal crude clip export."""
    cmd = build_crude_clip_ffmpeg_cmd(
        input_video="/tmp/input.mp4",
        output_mp4="/tmp/out_h.mp4",
        start_ms=10500,
        end_ms=35500,
        kind="horizontal",
        watermark_text="Preview",
    )

    # 1. Argument list only (safe list, not string for shell)
    assert isinstance(cmd, list)
    assert cmd[0] == "ffmpeg"

    # 2. Accurate seek
    assert "-ss" in cmd
    ss_idx = cmd.index("-ss")
    assert cmd[ss_idx + 1] == "10.500"

    assert "-t" in cmd
    t_idx = cmd.index("-t")
    assert cmd[t_idx + 1] == "25.000"

    # 3. Watermark filter present in horizontal
    assert "-vf" in cmd
    vf_idx = cmd.index("-vf")
    assert "drawtext=text='Preview'" in cmd[vf_idx + 1]

    # 4. Re-encoding parameters
    assert "-c:v" in cmd
    assert cmd[cmd.index("-c:v") + 1] == "libx264"
    assert "-c:a" in cmd
    assert cmd[cmd.index("-c:a") + 1] == "aac"
    assert "-movflags" in cmd
    assert cmd[cmd.index("-movflags") + 1] == "+faststart"
    assert cmd[-1] == "/tmp/out_h.mp4"


def test_build_crude_clip_ffmpeg_cmd_vertical_center():
    """Verify 9:16 naive center crop filter + watermark for vertical crude clip export."""
    cmd = build_crude_clip_ffmpeg_cmd(
        input_video="/tmp/input.mp4",
        output_mp4="/tmp/out_v.mp4",
        start_ms=0,
        end_ms=20000,
        kind="vertical_center",
        watermark_text="Preview",
    )

    assert isinstance(cmd, list)
    assert "-vf" in cmd
    vf_idx = cmd.index("-vf")
    vf_str = cmd[vf_idx + 1]

    # Check both crop and drawtext are composed in the filter graph
    assert "crop=" in vf_str
    assert "drawtext=text='Preview'" in vf_str


@patch("subprocess.Popen")
def test_export_crude_clip_execution_and_idempotency(mock_popen):
    """Verify export_crude_clip invokes subprocess and handles progress cleanly."""
    mock_process = MagicMock()
    mock_process.stdout = ["out_time_us=5000000\n", "progress=end\n"]
    mock_process.communicate.return_value = ("", "")
    mock_process.returncode = 0
    mock_popen.return_value = mock_process

    progress_events = []

    def on_progress(pct: float):
        progress_events.append(pct)

    export_crude_clip(
        input_video="/tmp/input.mp4",
        output_mp4="/tmp/out.mp4",
        start_ms=0,
        end_ms=10000,
        kind="vertical_center",
        progress_cb=on_progress,
    )

    assert mock_popen.called
    assert len(progress_events) > 0
    assert progress_events[-1] == 100.0


@pytest.mark.ffmpeg
def test_real_ffmpeg_crude_export_if_available():
    """Marked FFmpeg test that runs against real binary if present on host."""
    import shutil
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg binary not installed on host machine")

    # Generate a tiny test synthetic video using ffmpeg lavfi
    with tempfile.TemporaryDirectory() as tmpdir:
        synth_input = os.path.join(tmpdir, "synth.mp4")
        synth_out_h = os.path.join(tmpdir, "synth_h.mp4")
        synth_out_v = os.path.join(tmpdir, "synth_v.mp4")

        # Create 2s test video
        import subprocess
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=640x360:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=2",
            "-c:v", "libx264", "-c:a", "aac", synth_input
        ], check=True, capture_output=True)

        # Export horizontal
        export_crude_clip(synth_input, synth_out_h, start_ms=0, end_ms=1500, kind="horizontal")
        assert os.path.exists(synth_out_h)
        assert os.path.getsize(synth_out_h) > 0

        # Export vertical center (9:16 crop)
        export_crude_clip(synth_input, synth_out_v, start_ms=0, end_ms=1500, kind="vertical_center")
        assert os.path.exists(synth_out_v)
        assert os.path.getsize(synth_out_v) > 0
