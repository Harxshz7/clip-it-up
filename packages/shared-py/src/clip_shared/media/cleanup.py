"""Filler word and silence detection, cut snapping, and cleanup planner."""
import re
from dataclasses import dataclass
from typing import Any

from clip_shared.media.edl import EditDecisionList, Removal

# Default filler dictionaries by language
DEFAULT_FILLER_WORDS: dict[str, list[str | list[str]]] = {
    "en": [
        "um",
        "uh",
        "er",
        "ah",
        "hmm",
        "hm",
        "mhm",
        ["you", "know"],
        ["i", "mean"],
        # "like" is handled specially with context heuristics
    ],
    "hi": [
        "matlab",
        "yani",
        "haan",
        "toh",
        "achha",
        "um",
        "uh",
        ["matlab", "ki"],
    ],
    "kn": [
        "andre",
        "houdu",
        "matte",
        "adare",
        "um",
        "uh",
    ],
}


def _clean_token(w: str) -> str:
    """Normalize a word token by removing punctuation and lowercasing."""
    return re.sub(r"[^\w\s]", "", w).strip().lower()


def is_contextual_filler_like(idx: int, words: list[dict[str, Any]]) -> bool:
    """
    Context heuristic for 'like':
    Considered filler ONLY if:
    1. Preceded or followed by a pause (gap >= 150ms), OR
    2. Preceded by another filler (e.g. 'um like', 'and like'), OR
    3. It is at the beginning of a clause/sentence with a following hesitation.
    """
    curr = words[idx]
    clean_w = _clean_token(curr.get("text", curr.get("word", "")))
    if clean_w != "like":
        return False

    curr_start = int(curr.get("start_ms", 0))
    curr_end = int(curr.get("end_ms", 0))

    # Check pause before
    if idx > 0:
        prev = words[idx - 1]
        prev_end = int(prev.get("end_ms", 0))
        prev_text = _clean_token(prev.get("text", prev.get("word", "")))
        if curr_start - prev_end >= 150 or prev_text in ("um", "uh", "er", "ah", "and", "so"):
            return True

    # Check pause after
    if idx < len(words) - 1:
        nxt = words[idx + 1]
        nxt_start = int(nxt.get("start_ms", 0))
        if nxt_start - curr_end >= 150:
            return True

    return False


def detect_filler_removals(
    words: list[dict[str, Any]],
    language: str = "en",
    custom_filler_list: list[str] | None = None,
    clip_start_ms: int = 0,
    clip_end_ms: int | None = None,
) -> list[Removal]:
    """
    Detect filler words and multi-word filler sequences in word transcript.
    Respects first 1.0s hook protection.
    """
    if not words:
        return []

    lang = language.lower()[:2] if language else "en"
    fillers_config = custom_filler_list or DEFAULT_FILLER_WORDS.get(lang, DEFAULT_FILLER_WORDS["en"])

    single_fillers: set[str] = set()
    multi_fillers: list[list[str]] = []

    for f in fillers_config:
        if isinstance(f, str):
            parts = [_clean_token(p) for p in f.split()]
            if len(parts) == 1:
                single_fillers.add(parts[0])
            elif len(parts) > 1:
                multi_fillers.append(parts)
        elif isinstance(f, list):
            multi_fillers.append([_clean_token(p) for p in f])

    removals: list[Removal] = []
    n = len(words)
    i = 0
    hook_protect_until = clip_start_ms + 1000

    while i < n:
        curr_word = words[i]
        w_start = int(curr_word.get("start_ms", 0))
        w_end = int(curr_word.get("end_ms", 0))
        raw_text = curr_word.get("text", curr_word.get("word", ""))
        clean_text = _clean_token(raw_text)

        # Safety: Never remove within the first 1s hook of the clip
        if w_start < hook_protect_until:
            i += 1
            continue

        # If clip_end_ms specified, skip words outside clip
        if clip_end_ms is not None and w_end > clip_end_ms:
            i += 1
            continue

        # 1. Multi-word filler check
        matched_multi = False
        for seq in multi_fillers:
            k = len(seq)
            if i + k <= n:
                candidate_tokens = [_clean_token(words[i + j].get("text", words[i + j].get("word", ""))) for j in range(k)]
                if candidate_tokens == seq:
                    seq_start = int(words[i].get("start_ms", 0))
                    seq_end = int(words[i + k - 1].get("end_ms", 0))
                    seq_text = " ".join(seq)
                    removals.append(
                        Removal(
                            start_ms=seq_start,
                            end_ms=seq_end,
                            kind="filler",
                            text=seq_text,
                        )
                    )
                    i += k
                    matched_multi = True
                    break

        if matched_multi:
            continue

        # 2. Single-word filler check
        if clean_text in single_fillers:
            removals.append(
                Removal(
                    start_ms=w_start,
                    end_ms=w_end,
                    kind="filler",
                    text=raw_text,
                )
            )
            i += 1
            continue

        # 3. Contextual "like" check
        if clean_text == "like" and is_contextual_filler_like(i, words):
            removals.append(
                Removal(
                    start_ms=w_start,
                    end_ms=w_end,
                    kind="filler",
                    text=raw_text,
                )
            )
            i += 1
            continue

        i += 1

    return removals


def detect_silence_removals(
    words: list[dict[str, Any]],
    max_silence_ms: int = 700,
    target_silence_ms: int = 250,
    clip_start_ms: int = 0,
    clip_end_ms: int | None = None,
) -> list[Removal]:
    """
    Detect gaps between consecutive words > max_silence_ms (default 700ms)
    and shorten them to target_silence_ms (default 250ms).
    Never cuts inside words, protects first 1s hook.
    """
    if len(words) < 2:
        return []

    removals: list[Removal] = []
    hook_protect_until = clip_start_ms + 1000

    # Half of the target silence is placed at tail of previous word, half before next word
    buffer_half = target_silence_ms // 2

    for i in range(len(words) - 1):
        curr_w = words[i]
        nxt_w = words[i + 1]

        curr_end = int(curr_w.get("end_ms", 0))
        nxt_start = int(nxt_w.get("start_ms", 0))

        # Check bounds
        if curr_end < clip_start_ms:
            continue
        if clip_end_ms is not None and nxt_start > clip_end_ms:
            break

        gap_ms = nxt_start - curr_end
        if gap_ms > max_silence_ms:
            # Cut start and end
            cut_start = curr_end + buffer_half
            cut_end = nxt_start - (target_silence_ms - buffer_half)

            # Safety: Don't cut in first 1.0s
            if cut_start < hook_protect_until:
                cut_start = hook_protect_until

            if cut_end > cut_start:
                removals.append(
                    Removal(
                        start_ms=cut_start,
                        end_ms=cut_end,
                        kind="silence",
                        text=f"Pause ({gap_ms}ms -> {target_silence_ms}ms)",
                    )
                )

    return removals


def snap_cut_point(
    timestamp_ms: int,
    audio_data: Any | None = None,
    sr: int = 16000,
    search_window_ms: int = 30,
) -> int:
    """
    Snap a cut point to the nearest low-energy point or zero-crossing within +/- 30ms.
    Prevents audio clicks and pops at cut boundaries.
    """
    if audio_data is None:
        return timestamp_ms

    try:
        import numpy as np

        if isinstance(audio_data, np.ndarray) and len(audio_data) > 0:
            center_sample = int((timestamp_ms / 1000.0) * sr)
            win_samples = int((search_window_ms / 1000.0) * sr)

            start_idx = max(0, center_sample - win_samples)
            end_idx = min(len(audio_data) - 1, center_sample + win_samples)

            if end_idx <= start_idx:
                return timestamp_ms

            slice_audio = audio_data[start_idx:end_idx]

            # 1. Check zero crossings (where sign changes)
            signs = np.sign(slice_audio)
            zero_crossings = np.where(np.diff(signs))[0]

            if len(zero_crossings) > 0:
                # Pick zero crossing closest to center
                center_offset = center_sample - start_idx
                best_zc_idx = zero_crossings[np.argmin(np.abs(zero_crossings - center_offset))]
                best_sample = start_idx + best_zc_idx
                return int((best_sample / sr) * 1000.0)

            # 2. Fallback: lowest absolute amplitude
            min_amp_idx = int(np.argmin(np.abs(slice_audio)))
            best_sample = start_idx + min_amp_idx
            return int((best_sample / sr) * 1000.0)
    except Exception:
        pass

    return timestamp_ms


@dataclass
class CleanupPlanResult:
    """Result of analyzing and planning clip cleanup."""
    clip_start_ms: int
    clip_end_ms: int
    options: dict[str, Any]
    removals: list[Removal]
    edl: EditDecisionList
    original_duration_ms: int
    clean_duration_ms: int
    saved_ms: int
    cut_count: int
    filler_count: int
    silence_count: int
    savings_ratio: float


def plan_clip_cleanup(
    clip_start_ms: int,
    clip_end_ms: int,
    words: list[dict[str, Any]],
    options: dict[str, Any] | None = None,
    audio_data: Any | None = None,
    max_removal_ratio: float = 0.25,
) -> CleanupPlanResult:
    """
    Plan filler word and silence removals for a clip with safety constraints.
    - Never removes > max_removal_ratio (default 25%) of clip duration.
    - Never cuts inside first 1s hook.
    - Snaps cuts to low energy points.
    """
    opt = options or {}
    remove_fillers = bool(opt.get("remove_fillers", True))
    remove_silence = bool(opt.get("remove_silence", True))
    max_silence_ms = int(opt.get("max_silence_ms", 700))
    target_silence_ms = int(opt.get("target_silence_ms", 250))
    language = str(opt.get("language", "en"))
    custom_filler_list = opt.get("filler_list")
    snap_cuts = bool(opt.get("snap_cuts", True))

    clip_duration = clip_end_ms - clip_start_ms
    max_allowed_removal_ms = int(clip_duration * max_removal_ratio)

    candidate_removals: list[Removal] = []

    # 1. Detect fillers
    if remove_fillers:
        filler_rems = detect_filler_removals(
            words=words,
            language=language,
            custom_filler_list=custom_filler_list,
            clip_start_ms=clip_start_ms,
            clip_end_ms=clip_end_ms,
        )
        candidate_removals.extend(filler_rems)

    # 2. Detect silences
    if remove_silence:
        silence_rems = detect_silence_removals(
            words=words,
            max_silence_ms=max_silence_ms,
            target_silence_ms=target_silence_ms,
            clip_start_ms=clip_start_ms,
            clip_end_ms=clip_end_ms,
        )
        candidate_removals.extend(silence_rems)

    # 3. Optional manual additions from options
    manual_rems = opt.get("manual_removals", [])
    for m in manual_rems:
        candidate_removals.append(
            Removal(
                start_ms=int(m["start_ms"]),
                end_ms=int(m["end_ms"]),
                kind="manual",
                text=m.get("text"),
            )
        )

    # 4. Snap cut points if requested
    if snap_cuts and audio_data is not None:
        snapped_removals: list[Removal] = []
        for r in candidate_removals:
            s_start = snap_cut_point(r.start_ms, audio_data)
            s_end = snap_cut_point(r.end_ms, audio_data)
            if s_end > s_start:
                snapped_removals.append(
                    Removal(start_ms=s_start, end_ms=s_end, kind=r.kind, text=r.text)
                )
        candidate_removals = snapped_removals

    # 5. Enforce 25% safety cap if total removal exceeds threshold
    # Sort removals by duration descending (prioritize largest silences/fillers)
    candidate_removals.sort(key=lambda r: r.duration_ms, reverse=True)
    capped_removals: list[Removal] = []
    accumulated_removal_ms = 0

    for r in candidate_removals:
        if accumulated_removal_ms + r.duration_ms <= max_allowed_removal_ms:
            capped_removals.append(r)
            accumulated_removal_ms += r.duration_ms
        else:
            # Partial fit or drop
            rem_space = max_allowed_removal_ms - accumulated_removal_ms
            if rem_space >= 200 and r.kind == "silence":
                # Shorten silence removal to fit
                capped_removals.append(
                    Removal(
                        start_ms=r.start_ms,
                        end_ms=r.start_ms + rem_space,
                        kind=r.kind,
                        text=r.text,
                    )
                )
                accumulated_removal_ms += rem_space
            break

    # Build EDL
    edl = EditDecisionList.create(
        clip_start_ms=clip_start_ms,
        clip_end_ms=clip_end_ms,
        removals=capped_removals,
    )

    filler_count = sum(1 for r in edl.removals if "filler" in r.kind)
    silence_count = sum(1 for r in edl.removals if "silence" in r.kind)

    return CleanupPlanResult(
        clip_start_ms=clip_start_ms,
        clip_end_ms=clip_end_ms,
        options={
            "remove_fillers": remove_fillers,
            "remove_silence": remove_silence,
            "max_silence_ms": max_silence_ms,
            "target_silence_ms": target_silence_ms,
            "language": language,
            "crossfade_ms": opt.get("crossfade_ms", 40),
            "snap_cuts": snap_cuts,
        },
        removals=edl.removals,
        edl=edl,
        original_duration_ms=clip_duration,
        clean_duration_ms=edl.total_out_duration_ms,
        saved_ms=edl.removed_duration_ms,
        cut_count=len(edl.removals),
        filler_count=filler_count,
        silence_count=silence_count,
        savings_ratio=round(edl.removed_duration_ms / max(1, clip_duration), 4),
    )
