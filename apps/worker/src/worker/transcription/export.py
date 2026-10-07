import json

from worker.transcription.base import SegmentItem, TranscriptionResult


def _ms_to_srt_time(ms: int) -> str:
    """Format milliseconds to SRT timestamp: HH:MM:SS,mmm"""
    total_seconds, milliseconds = divmod(ms, 1000)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def _ms_to_vtt_time(ms: int) -> str:
    """Format milliseconds to WebVTT timestamp: HH:MM:SS.mmm"""
    total_seconds, milliseconds = divmod(ms, 1000)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def export_txt(segments: list[SegmentItem], speakers_map: dict[str, str] = None) -> str:
    """Export transcript as readable text with speaker labels."""
    speakers_map = speakers_map or {}
    lines = []
    current_speaker = None

    for seg in segments:
        speaker_label = speakers_map.get(seg.speaker or "", seg.speaker or "Speaker")
        if speaker_label != current_speaker:
            current_speaker = speaker_label
            time_str = _ms_to_vtt_time(seg.start_ms)[:8]
            lines.append(f"\n[{speaker_label}] ({time_str})")
        lines.append(seg.text)

    return "\n".join(lines).strip()


def export_srt(segments: list[SegmentItem], speakers_map: dict[str, str] = None) -> str:
    """Export transcript as SubRip (.srt) subtitle format."""
    speakers_map = speakers_map or {}
    entries = []

    for i, seg in enumerate(segments, 1):
        start = _ms_to_srt_time(seg.start_ms)
        end = _ms_to_srt_time(seg.end_ms)
        speaker = speakers_map.get(seg.speaker or "", seg.speaker)
        text = f"[{speaker}] {seg.text}" if speaker else seg.text

        entries.append(f"{i}\n{start} --> {end}\n{text}\n")

    return "\n".join(entries).strip()


def export_vtt(segments: list[SegmentItem], speakers_map: dict[str, str] = None) -> str:
    """Export transcript as WebVTT (.vtt) format."""
    speakers_map = speakers_map or {}
    entries = ["WEBVTT\n"]

    for i, seg in enumerate(segments, 1):
        start = _ms_to_vtt_time(seg.start_ms)
        end = _ms_to_vtt_time(seg.end_ms)
        speaker = speakers_map.get(seg.speaker or "", seg.speaker)
        text = f"<v {speaker}>{seg.text}" if speaker else seg.text

        entries.append(f"{i}\n{start} --> {end}\n{text}\n")

    return "\n".join(entries).strip()


def export_json(result: TranscriptionResult, speakers_map: dict[str, str] = None) -> str:
    """Export raw structured JSON with applied speaker display names."""
    speakers_map = speakers_map or {}
    data = result.to_dict()
    if speakers_map:
        for s in data.get("speakers", []):
            if s["label"] in speakers_map:
                s["display_name"] = speakers_map[s["label"]]
        for seg in data.get("segments", []):
            if seg.get("speaker") in speakers_map:
                seg["speaker_display_name"] = speakers_map[seg["speaker"]]
    return json.dumps(data, indent=2)
