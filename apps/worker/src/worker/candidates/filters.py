import math
import re
from collections import Counter
from typing import Any

from worker.candidates.window_generator import CandidateWindow

COMMON_FILLERS = {
    "um", "uh", "er", "ah", "like", "you know", "i mean", "sort of",
    "kind of", "basically", "actually", "literally", "right", "yeah", "okay"
}


def calculate_window_iou(w1: CandidateWindow, w2: CandidateWindow) -> float:
    """Calculate temporal Intersection over Union (IoU) of two windows."""
    intersection_start = max(w1.start_ms, w2.start_ms)
    intersection_end = min(w1.end_ms, w2.end_ms)
    intersection = max(0, intersection_end - intersection_start)

    union_start = min(w1.start_ms, w2.start_ms)
    union_end = max(w1.end_ms, w2.end_ms)
    union = max(1, union_end - union_start)

    return intersection / union


def compute_text_similarity(text1: str, text2: str) -> float:
    """Compute cheap term-frequency cosine similarity between two text halves."""
    tokens1 = re.findall(r"\b[a-zA-Z]{3,}\b", text1.lower())
    tokens2 = re.findall(r"\b[a-zA-Z]{3,}\b", text2.lower())

    if not tokens1 or not tokens2:
        return 0.5

    vec1 = Counter(tokens1)
    vec2 = Counter(tokens2)

    all_keys = set(vec1.keys()).union(set(vec2.keys()))
    dot = sum(vec1[k] * vec2[k] for k in all_keys)
    norm1 = math.sqrt(sum(v * v for v in vec1.values()))
    norm2 = math.sqrt(sum(v * v for v in vec2.values()))

    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def is_topic_coherent(text: str) -> bool:
    """
    Check if a candidate window spans unrelated topics abruptly.
    Splits the window into first half and second half and checks term overlap.
    """
    words = text.split()
    if len(words) < 20:
        return True

    mid = len(words) // 2
    first_half = " ".join(words[:mid])
    second_half = " ".join(words[mid:])

    sim = compute_text_similarity(first_half, second_half)
    # If there is near-zero vocabulary overlap in a long text, it likely jumps abruptly across topics
    return sim >= 0.04


def is_excessive_fillers(text: str, max_filler_ratio: float = 0.25) -> bool:
    """Check if the text is dominated by filler words."""
    words = re.findall(r"\b[a-zA-Z\']+\b", text.lower())
    if not words:
        return True

    filler_count = sum(1 for w in words if w in COMMON_FILLERS)
    ratio = filler_count / len(words)
    return ratio > max_filler_ratio


def is_excessive_silence(
    window: CandidateWindow,
    words: list[dict[str, Any]],
    max_silence_ratio: float = 0.30,
) -> bool:
    """Check if the window contains >30% silence (based on timed words)."""
    window_words = [
        w for w in words
        if w["start_ms"] >= window.start_ms and w["end_ms"] <= window.end_ms
    ]
    if not window_words:
        return True

    speech_ms = sum(max(0, w["end_ms"] - w["start_ms"]) for w in window_words)
    total_ms = max(1, window.end_ms - window.start_ms)
    silence_ratio = max(0.0, (total_ms - speech_ms) / total_ms)
    return silence_ratio > max_silence_ratio


def is_single_speaker_compliant(
    window: CandidateWindow,
    segments: list[dict[str, Any]],
    min_speaker_ratio: float = 0.90,
) -> bool:
    """
    In single speaker contexts, ensures that at least 90% of speech is from the primary speaker.
    """
    window_segs = [
        s for s in segments
        if s["start_ms"] >= window.start_ms and s["end_ms"] <= window.end_ms
    ]
    if not window_segs:
        return True

    speaker_times: Counter[str] = Counter()
    total_speech_ms = 0

    for s in window_segs:
        spk = s.get("speaker") or "UNKNOWN"
        dur = max(0, s["end_ms"] - s["start_ms"])
        speaker_times[spk] += dur
        total_speech_ms += dur

    if total_speech_ms == 0:
        return True

    most_common_spk, most_common_time = speaker_times.most_common(1)[0]
    ratio = most_common_time / total_speech_ms
    return ratio >= min_speaker_ratio


def filter_candidate_windows(
    windows: list[CandidateWindow],
    words: list[dict[str, Any]] | None = None,
    segments: list[dict[str, Any]] | None = None,
    require_single_speaker: bool = False,
) -> list[CandidateWindow]:
    """Apply all quality guardrails to candidate windows."""
    passed: list[CandidateWindow] = []

    for w in windows:
        # 1. Topic Coherence
        if not is_topic_coherent(w.text):
            continue

        # 2. Filler words
        if is_excessive_fillers(w.text):
            continue

        # 3. Silence check
        if words and is_excessive_silence(w, words):
            continue

        # 4. Speaker purity (if single speaker requested)
        if require_single_speaker and segments and not is_single_speaker_compliant(w, segments):
            continue

        passed.append(w)

    return passed


def cluster_and_deduplicate_candidates(
    windows: list[CandidateWindow],
    iou_threshold: float = 0.50,
    max_candidates: int = 60,
) -> list[CandidateWindow]:
    """
    Cluster overlapping windows (IoU > 0.5) and keep the highest scoring candidate per cluster.
    Caps results to max_candidates.
    """
    if not windows:
        return []

    # Sort by heuristic score descending
    sorted_windows = sorted(windows, key=lambda w: (w.heuristic_score, w.duration_seconds), reverse=True)
    selected: list[CandidateWindow] = []

    for cand in sorted_windows:
        overlap = False
        for s in selected:
            if calculate_window_iou(cand, s) > iou_threshold:
                overlap = True
                break

        if not overlap:
            selected.append(cand)
            if len(selected) >= max_candidates:
                break

    # Re-sort chronologically for downstream batching & UI flow
    selected.sort(key=lambda w: w.start_ms)
    return selected
