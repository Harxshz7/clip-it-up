from typing import Any


def calculate_moment_iou(m1_start: int, m1_end: int, m2_start: int, m2_end: int) -> float:
    """Calculate temporal Intersection over Union (IoU) of two moment ranges."""
    intersection_start = max(m1_start, m2_start)
    intersection_end = min(m1_end, m2_end)
    intersection = max(0, intersection_end - intersection_start)

    union_start = min(m1_start, m2_start)
    union_end = max(m1_end, m2_end)
    union = max(1, union_end - union_start)

    return intersection / union


def select_top_moments(
    scored_moments: list[dict[str, Any]],
    max_selected: int = 10,
    iou_threshold: float = 0.30,
    diversity_window_minutes: float = 5.0,
    max_clips_per_window: int = 2,
    diversity_score_override: float = 0.85,
) -> list[dict[str, Any]]:
    """
    Select and rank the top moments enforcing:
    1. Score descending order
    2. Overlap deduplication: IoU <= 0.3 against already selected moments
    3. Diversity rule: max 2 clips from the same 5-minute region (unless score >= 0.85)
    """
    if not scored_moments:
        return []

    # Sort descending by final score
    sorted_moments = sorted(scored_moments, key=lambda m: m.get("final_score", 0.0), reverse=True)
    selected: list[dict[str, Any]] = []

    window_ms = int(diversity_window_minutes * 60 * 1000)

    for cand in sorted_moments:
        cand_start = cand["start_ms"]
        cand_end = cand["end_ms"]
        cand_score = cand.get("final_score", 0.0)

        # 1. Deduplication check against already selected
        has_overlap = False
        for sel in selected:
            iou = calculate_moment_iou(cand_start, cand_end, sel["start_ms"], sel["end_ms"])
            if iou > iou_threshold:
                has_overlap = True
                break

        if has_overlap:
            continue

        # 2. Diversity check: count selections in the same 5-minute bucket
        if cand_score < diversity_score_override:
            bucket_start = (cand_start // window_ms) * window_ms
            bucket_end = bucket_start + window_ms
            clips_in_bucket = sum(
                1 for s in selected
                if not (s["end_ms"] < bucket_start or s["start_ms"] > bucket_end)
            )
            if clips_in_bucket >= max_clips_per_window:
                continue

        selected.append(cand)
        if len(selected) >= max_selected:
            break

    # Assign ranks (1-indexed)
    for idx, item in enumerate(selected):
        item["rank"] = idx + 1
        item["status"] = "selected"

    return selected
