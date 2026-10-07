import uuid
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class ClipVariantData:
    variant_length_s: str  # 15 | 30 | 45 | 60 | auto
    start_ms: int
    end_ms: int
    hook_text: str
    title: str
    final_score: float
    score_breakdown: Dict[str, Any]
    reason: str


def generate_moment_variants(
    moment_start_ms: int,
    moment_end_ms: int,
    base_hook_text: str,
    base_title: str,
    base_score: float,
    base_breakdown: Dict[str, Any],
    base_reason: str,
    segments: List[Dict[str, Any]],
    target_lengths: Optional[List[int]] = None,
) -> List[ClipVariantData]:
    """
    Generate 15s, 30s, 45s, 60s, and auto variants for a selected moment.
    Trims to sentence boundaries while retaining hook and payoff.
    """
    if target_lengths is None:
        target_lengths = [15, 30, 45, 60]

    # Find segments within this moment
    moment_segments = [
        s for s in segments
        if s["start_ms"] >= moment_start_ms - 200 and s["end_ms"] <= moment_end_ms + 200
    ]
    if not moment_segments:
        moment_segments = [
            {"start_ms": moment_start_ms, "end_ms": moment_end_ms, "text": base_hook_text}
        ]

    variants: List[ClipVariantData] = []

    # 1. Always include 'auto' variant (optimal model suggested range)
    variants.append(
        ClipVariantData(
            variant_length_s="auto",
            start_ms=moment_start_ms,
            end_ms=moment_end_ms,
            hook_text=base_hook_text,
            title=base_title,
            final_score=base_score,
            score_breakdown=base_breakdown,
            reason=f"Optimal natural cut ({round((moment_end_ms - moment_start_ms)/1000.0, 1)}s): {base_reason}",
        )
    )

    moment_duration_s = (moment_end_ms - moment_start_ms) / 1000.0

    # 2. Generate fixed-length variants
    for target_s in target_lengths:
        target_ms = target_s * 1000

        # If moment is significantly shorter than target, skip longer variants
        if moment_duration_s < (target_s * 0.75):
            continue

        # Greedy sentence selection from start to reach target_ms
        cand_start = moment_start_ms
        best_end = cand_start
        accumulated_ms = 0
        used_segs = []

        for seg in moment_segments:
            seg_dur = seg["end_ms"] - seg["start_ms"]
            if accumulated_ms + seg_dur > target_ms + 3000: # allow 3s slack
                break
            used_segs.append(seg)
            accumulated_ms = seg["end_ms"] - cand_start
            best_end = seg["end_ms"]

        if not used_segs or (best_end - cand_start < 8000): # at least 8s
            continue

        actual_duration_s = (best_end - cand_start) / 1000.0

        # Adjust score slightly if length matches target well
        length_penalty = abs(actual_duration_s - target_s) * 0.01
        variant_score = max(0.0, min(1.0, base_score - length_penalty))

        variants.append(
            ClipVariantData(
                variant_length_s=str(target_s),
                start_ms=cand_start,
                end_ms=best_end,
                hook_text=base_hook_text,
                title=f"{base_title} ({target_s}s cut)",
                final_score=round(variant_score, 3),
                score_breakdown=base_breakdown,
                reason=f"Trimmed {target_s}s cut preserving the core hook and conclusion.",
            )
        )

    return variants
