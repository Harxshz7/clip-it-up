from unittest.mock import MagicMock, patch

import pytest

from clip_shared.media.ffmpeg import (
    MediaValidationError,
    check_disk_space,
    extract_audio,
    generate_proxy,
    probe_video,
)


def test_probe_video_file_not_found():
    with pytest.raises(MediaValidationError) as exc:
        probe_video("/non/existent/path/video.mp4")
    assert exc.value.code == "FILE_NOT_FOUND"


def test_probe_video_corrupt_file(tmp_path):
    dummy_file = tmp_path / "corrupt.mp4"
    dummy_file.write_bytes(b"invalid corrupt bytes")

    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = "Invalid data found when processing input"
        mock_run.return_value = mock_proc

        with pytest.raises(MediaValidationError) as exc:
            probe_video(str(dummy_file))
        assert exc.value.code == "CORRUPT_FILE"


def test_probe_video_too_long(tmp_path):
    dummy_file = tmp_path / "long.mp4"
    dummy_file.write_bytes(b"dummy")

    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = '{"streams": [{"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080}], "format": {"duration": "10000.0"}}'
        mock_run.return_value = mock_proc

        with pytest.raises(MediaValidationError) as exc:
            probe_video(str(dummy_file), max_duration_min=120)
        assert exc.value.code == "TOO_LONG"


def test_probe_video_no_video_stream(tmp_path):
    dummy_file = tmp_path / "audio_only.mp3"
    dummy_file.write_bytes(b"dummy")

    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = '{"streams": [{"codec_type": "audio", "codec_name": "mp3"}], "format": {"duration": "60.0"}}'
        mock_run.return_value = mock_proc

        with pytest.raises(MediaValidationError) as exc:
            probe_video(str(dummy_file))
        assert exc.value.code == "NO_VIDEO_STREAM"


def test_probe_video_valid(tmp_path):
    dummy_file = tmp_path / "valid.mp4"
    dummy_file.write_bytes(b"dummy")

    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = '{"streams": [{"codec_type": "video", "codec_name": "h264", "width": 1280, "height": 720, "avg_frame_rate": "30/1"}, {"codec_type": "audio", "codec_name": "aac"}], "format": {"duration": "120.5"}}'
        mock_run.return_value = mock_proc

        meta = probe_video(str(dummy_file))
        assert meta.has_video is True
        assert meta.has_audio is True
        assert meta.duration_seconds == 120.5
        assert meta.width == 1280
        assert meta.height == 720
        assert meta.fps == 30.0
        assert meta.video_codec == "h264"


def test_check_disk_space(tmp_path):
    # Valid disk check
    check_disk_space(str(tmp_path), 1024)

    # Exceeded disk check
    with patch("shutil.disk_usage") as mock_usage:
        mock_usage.return_value = MagicMock(free=100)
        with pytest.raises(MediaValidationError) as exc:
            check_disk_space(str(tmp_path), 100000000000)
        assert exc.value.code == "INSUFFICIENT_DISK_SPACE"


def test_ffmpeg_command_construction(tmp_path):
    input_v = str(tmp_path / "in.mp4")
    out_w = str(tmp_path / "out.wav")
    out_p = str(tmp_path / "out.mp4")

    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.stdout = ["progress=end\n"]
        mock_proc.communicate.return_value = ("", "")
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        extract_audio(input_v, out_w, duration_seconds=10.0)
        # Verify argument list was passed (never raw shell string)
        args, kwargs = mock_popen.call_args
        cmd = args[0]
        assert isinstance(cmd, list)
        assert cmd[0] == "ffmpeg"
        assert "-vn" in cmd
        assert "-ar" in cmd
        assert "16000" in cmd

        generate_proxy(input_v, out_p, duration_seconds=10.0)
        args_proxy, _ = mock_popen.call_args
        cmd_proxy = args_proxy[0]
        assert isinstance(cmd_proxy, list)
        assert "-movflags" in cmd_proxy
        assert "+faststart" in cmd_proxy
