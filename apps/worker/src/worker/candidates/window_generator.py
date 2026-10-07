import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class CandidateWindow:
    """Represents a prospective clip moment window bounded by sentences."""
    start_ms: int
    end_ms: int
    start_segment_idx: int
    end_segment_idx: int
    text: str
    speaker: Optional[str] = None
    heuristic_score: float = 0.0
    reasons: List[str] = field(default_factory=list)

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)

    @property
    def duration_seconds(self) -> float:
        return self.duration_ms / 1000.0


# Common English hook keywords and patterns
QUESTION_STARTERS = re.compile(
    r"^(why|how|what|who|when|where|is\s+it|can\s+you|have\s+you|do\s+you|are\s+we|did\s+you|should\s+you|would\s+you|could\s+you)\b",
    re.IGNORECASE,
)
STRONG_CLAIM_PATTERNS = re.compile(
    r"\b(the\s+truth\s+is|the\s+secret|nobody\s+talks\s+about|the\s+biggest\s+mistake|stop\s+doing|never\s+do|here\'s\s+why|here\'s\s+the\s+thing|the\s+problem\s+with|most\s+people\s+think|you\s+need\s+to\s+know|let\s+me\s+tell\s+you)\b",
    re.IGNORECASE,
)
STORY_OPENER_PATTERNS = re.compile(
    r"^(when\s+I|once\s+upon|back\s+in|so\s+I\s+was|I\s+remember|years\s+ago|the\s+first\s+time|I\s+used\s+to)\b",
    re.IGNORECASE,
)
CONCLUSION_PATTERNS = re.compile(
    r"\b(and\s+that\'s\s+why|in\s+conclusion|the\s+point\s+is|that\'s\s+how|bottom\s+line|at\s+the\s+end\s+of\s+the\s+day|that\'s\s+the\s+lesson)\b",
    re.IGNORECASE,
)


def score_window_start_heuristics(segment_text: str, is_speaker_turn: bool) -> tuple[float, list[str]]:
    """Score the start of a window based on hook strength."""
    score = 0.0
    reasons = []
    clean_text = segment_text.strip()

    if is_speaker_turn:
        score += 0.15
        reasons.append("speaker_turn")

    if clean_text.endswith("?") or QUESTION_STARTERS.search(clean_text):
        score += 0.25
        reasons.append("question_hook")

    if STRONG_CLAIM_PATTERNS.search(clean_text):
        score += 0.20
        reasons.append("strong_claim")

    if STORY_OPENER_PATTERNS.search(clean_text):
        score += 0.15
        reasons.append("story_opener")

    return score, reasons


def score_window_end_heuristics(segment_text: str, gap_after_ms: int) -> tuple[float, list[str]]:
    """Score the end of a window based on conclusion / punchline / natural pause."""
    score = 0.0
    reasons = []
    clean_text = segment_text.strip()

    if CONCLUSION_PATTERNS.search(clean_text):
        score += 0.20
        reasons.append("conclusion_punchline")

    if gap_after_ms >= 700:
        score += 0.20
        reasons.append(f"natural_pause_{gap_after_ms}ms")
    elif gap_after_ms >= 300:
        score += 0.10
        reasons.append(f"cadence_pause_{gap_after_ms}ms")

    return score, reasons


def generate_candidate_windows(
    segments: List[Dict[str, Any]],
    min_length_s: float = 15.0,
    max_length_s: float = 90.0,
    min_sentences: int = 1,
) -> List[CandidateWindow]:
    """
    Generate sliding sentence-boundary windows within [min_length_s, max_length_s].
    Never start or end mid-sentence.
    """
    if not segments:
        return []

    windows: List[CandidateWindow] = []
    num_segments = len(segments)

    for i in range(num_segments):
        start_seg = segments[i]
        start_ms = start_seg["start_ms"]
        is_speaker_turn = (i == 0) or (segments[i - 1].get("speaker") != start_seg.get("speaker"))
        
        start_score, start_reasons = score_window_start_heuristics(
            start_seg.get("text", ""),
            is_speaker_turn=is_speaker_turn,
        )

        for j in range(i, num_segments):
            end_seg = segments[j]
            end_ms = end_seg["end_ms"]
            duration_s = (end_ms - start_ms) / 1000.0

            if duration_s < min_length_s:
                continue
            if duration_s > max_length_s:
                # Exceeded maximum window length
                break

            num_sents = j - i + 1
            if num_sents < min_sentences:
                continue

            gap_after = 0
            if j + 1 < num_segments:
                gap_after = max(0, segments[j + 1]["start_ms"] - end_ms)

            end_score, end_reasons = score_window_end_heuristics(
                end_seg.get("text", ""),
                gap_after_ms=gap_after,
            )

            # Build concatenated text
            window_segments = segments[i : j + 1]
            window_text = " ".join(s.get("text", "").strip() for s in window_segments if s.get("text", "").strip())
            
            # Base length penalty / preference: sweet spot 30-60s
            length_bonus = 0.10 if 25.0 <= duration_s <= 65.0 else 0.0

            total_heuristic = min(1.0, start_score + end_score + length_bonus)
            all_reasons = start_reasons + end_reasons

            windows.append(
                CandidateWindow(
                    start_ms=start_ms,
                    end_ms=end_ms,
                    start_segment_idx=start_seg.get("idx", i),
                    end_segment_idx=end_seg.get("idx", j),
                    text=window_text,
                    speaker=start_seg.get("speaker"),
                    heuristic_score=round(total_heuristic, 3),
                    reasons=all_reasons,
                )
            )

    return windows
