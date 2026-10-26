#!/usr/bin/env python3
"""Register evaluation benchmark videos and manage human QA labels for reframing."""
import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Any
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
VIDEOS_DIR = REPO_ROOT / "eval" / "videos"
LABELS_PATH_YAML = REPO_ROOT / "eval" / "labels" / "reframe_labels.yaml"
LABELS_PATH_CSV = REPO_ROOT / "eval" / "labels" / "reframe_labels.csv"

VALID_VERDICTS = {"ok", "bad"}
VALID_REASONS = {
    "none",
    "face_cut",
    "wrong_speaker",
    "jitter",
    "bad_zoom",
    "wrong_mode",
    "text_cut",
    "unreadable",
}
VALID_SCENE_TYPES = {
    "talking_head",
    "two_shot",
    "group",
    "screen_content",
    "whiteboard",
    "hybrid_pip",
    "b_roll_other",
}


def load_yaml_labels() -> list[dict[str, Any]]:
    if not LABELS_PATH_YAML.exists():
        return []
    with open(LABELS_PATH_YAML, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        return data if isinstance(data, list) else []


def save_yaml_labels(labels: list[dict[str, Any]]) -> None:
    LABELS_PATH_YAML.parent.mkdir(parents=True, exist_ok=True)
    with open(LABELS_PATH_YAML, "w", encoding="utf-8") as f:
        yaml.dump(labels, f, default_flow_style=False, sort_keys=False)


def export_labels_csv(labels: list[dict[str, Any]], out_path: Path = LABELS_PATH_CSV) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["clip_id", "video_slug", "scene_type", "expected_mode", "verdict", "reason", "notes"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in labels:
            row = {k: item.get(k, "") for k in fieldnames}
            writer.writerow(row)
    print(f"Exported labels CSV to {out_path}")


def import_labels_csv(csv_path: Path) -> list[dict[str, Any]]:
    if not csv_path.exists():
        print(f"Error: {csv_path} does not exist.")
        return []
    labels = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            verdict = row.get("verdict", "ok").strip().lower()
            reason = row.get("reason", "none").strip().lower()
            labels.append({
                "clip_id": row.get("clip_id", "").strip(),
                "video_slug": row.get("video_slug", "").strip(),
                "scene_type": row.get("scene_type", "talking_head").strip(),
                "expected_mode": row.get("expected_mode", "speaker_track").strip(),
                "verdict": verdict if verdict in VALID_VERDICTS else "ok",
                "reason": reason if reason in VALID_REASONS else "none",
                "notes": row.get("notes", "").strip(),
            })
    return labels


def register_video(
    slug: str,
    title: str,
    scene_type: str,
    duration_s: float = 60.0,
    source_url: str = "",
    speakers: list[str] | None = None,
    meta_extra: dict[str, Any] | None = None,
) -> Path:
    target_dir = VIDEOS_DIR / slug
    target_dir.mkdir(parents=True, exist_ok=True)
    meta_path = target_dir / "meta.yaml"

    meta_content = {
        "slug": slug,
        "title": title,
        "type": scene_type,
        "scene_type": scene_type,
        "duration_seconds": float(duration_s),
        "source_url": source_url or f"https://eval.clipitup.local/videos/{slug}",
        "speakers": speakers or ["Speaker 1"],
    }
    if meta_extra:
        meta_content.update(meta_extra)

    with open(meta_path, "w", encoding="utf-8") as f:
        yaml.dump(meta_content, f, default_flow_style=False, sort_keys=False)
    print(f"Registered video metadata at: {meta_path}")
    return meta_path


def add_or_update_label(
    clip_id: str,
    video_slug: str,
    scene_type: str,
    verdict: str,
    reason: str = "none",
    expected_mode: str = "speaker_track",
    notes: str = "",
) -> None:
    labels = load_yaml_labels()
    # Check if entry already exists
    existing_idx = next((i for i, item in enumerate(labels) if item.get("clip_id") == clip_id), None)

    entry = {
        "clip_id": clip_id,
        "video_slug": video_slug,
        "scene_type": scene_type,
        "expected_mode": expected_mode,
        "verdict": verdict,
        "reason": reason,
        "notes": notes,
    }

    if existing_idx is not None:
        labels[existing_idx] = entry
        print(f"Updated existing label for clip_id '{clip_id}'.")
    else:
        labels.append(entry)
        print(f"Added new label for clip_id '{clip_id}'.")

    save_yaml_labels(labels)
    export_labels_csv(labels)


def main() -> None:
    parser = argparse.ArgumentParser(description="Add evaluation benchmark video and label.")
    parser.add_argument("--slug", help="Unique video slug identifier")
    parser.add_argument("--title", default="Benchmark Video", help="Human-readable title")
    parser.add_argument("--scene-type", choices=list(VALID_SCENE_TYPES), default="talking_head", help="Scene type class")
    parser.add_argument("--duration", type=float, default=60.0, help="Duration in seconds")
    parser.add_argument("--source-url", default="", help="Source URL or test origin")
    parser.add_argument("--speakers", nargs="*", default=["Speaker 1"], help="List of speaker names")
    parser.add_argument("--clip-id", help="Clip ID for label entry")
    parser.add_argument("--verdict", choices=list(VALID_VERDICTS), default="ok", help="QA verdict (ok/bad)")
    parser.add_argument("--reason", choices=list(VALID_REASONS), default="none", help="Failure reason tag")
    parser.add_argument("--expected-mode", default="speaker_track", help="Expected framing mode")
    parser.add_argument("--notes", default="", help="Reviewer notes")
    parser.add_argument("--export-csv", action="store_true", help="Sync YAML labels to CSV template")
    parser.add_argument("--import-csv", type=str, help="Import labels from CSV file")

    args = parser.parse_args()

    if args.import_csv:
        imported = import_labels_csv(Path(args.import_csv))
        if imported:
            save_yaml_labels(imported)
            export_labels_csv(imported)
            print(f"Successfully imported {len(imported)} labels from {args.import_csv}")
        return

    if args.export_csv:
        labels = load_yaml_labels()
        export_labels_csv(labels)
        return

    if not args.slug:
        parser.print_help()
        sys.exit(1)

    register_video(
        slug=args.slug,
        title=args.title,
        scene_type=args.scene_type,
        duration_s=args.duration,
        source_url=args.source_url,
        speakers=args.speakers,
    )

    clip_id = args.clip_id or f"{args.slug}_clip01"
    add_or_update_label(
        clip_id=clip_id,
        video_slug=args.slug,
        scene_type=args.scene_type,
        verdict=args.verdict,
        reason=args.reason,
        expected_mode=args.expected_mode,
        notes=args.notes,
    )


if __name__ == "__main__":
    main()
