"""Helper script to register a new eval video and cache its transcript."""
import argparse
import json
import os
import sys
import yaml

# Ensure project packages on python path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in [
    os.path.join(repo_root, "packages", "shared-py", "src"),
    os.path.join(repo_root, "apps", "api", "src"),
    os.path.join(repo_root, "apps", "worker", "src"),
    repo_root,
]:
    if p not in sys.path:
        sys.path.insert(0, p)

from worker.transcription import get_transcription_backend

EVAL_DIR = os.path.join(repo_root, "eval")
VIDEOS_DIR = os.path.join(EVAL_DIR, "videos")


def add_eval_video(slug: str, title: str, v_type: str, audio_path: Optional[str] = None, source_url: Optional[str] = None):
    slug_dir = os.path.join(VIDEOS_DIR, slug)
    os.makedirs(slug_dir, exist_ok=True)

    meta = {
        "slug": slug,
        "title": title,
        "type": v_type,
        "language": "en",
        "duration_seconds": 1800.0,
        "source_url": source_url or "https://youtube.com",
        "speakers": ["Speaker 1", "Speaker 2"],
    }
    with open(os.path.join(slug_dir, "meta.yaml"), "w", encoding="utf-8") as f:
        yaml.dump(meta, f)

    if audio_path and os.path.exists(audio_path):
        backend = get_transcription_backend()
        result = backend.transcribe(audio_path)
        with open(os.path.join(slug_dir, "transcript.json"), "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2)
    else:
        # Starter transcript structure
        trans_mock = {
            "language": "en",
            "status": "ready",
            "model": "large-v3",
            "backend": "mock",
            "word_count": 50,
            "segments": [
                {"idx": 0, "start_ms": 0, "end_ms": 15000, "speaker": "SPEAKER_00", "text": "What is the single most important rule for creator success?"},
                {"idx": 1, "start_ms": 15200, "end_ms": 35000, "speaker": "SPEAKER_00", "text": "Relentless consistency and building a genuine connection with your audience."},
            ],
            "words": [],
            "speakers": [{"label": "SPEAKER_00", "display_name": "Speaker 1"}],
        }
        with open(os.path.join(slug_dir, "transcript.json"), "w", encoding="utf-8") as f:
            json.dump(trans_mock, f, indent=2)

    print(f"Successfully added eval video '{slug}' at: {slug_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add video to eval harness")
    parser.add_argument("--slug", required=True, help="Unique slug name")
    parser.add_argument("--title", required=True, help="Video title")
    parser.add_argument("--type", default="podcast", help="Video type (podcast|interview|educational|vlog)")
    parser.add_argument("--audio", help="Optional path to WAV audio for real transcription")
    parser.add_argument("--url", help="Optional source URL")
    args = parser.parse_args()

    add_eval_video(slug=args.slug, title=args.title, v_type=args.type, audio_path=args.audio, source_url=args.url)
