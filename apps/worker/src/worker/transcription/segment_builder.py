import re
from typing import List
from worker.transcription.base import WordItem, SegmentItem


def build_segments_from_words(
    words: List[WordItem],
    max_words: int = 18,
    max_duration_ms: int = 7000,
    pause_threshold_ms: int = 1200,
) -> List[SegmentItem]:
    """
    Group sequential words into clean sentence/clause level segments.
    Boundary conditions:
    1. Sentence-ending punctuation (. ? ! ...)
    2. Speaker change
    3. Long speech pause (> pause_threshold_ms)
    4. Max words reached or max duration exceeded
    """
    if not words:
        return []

    segments: List[SegmentItem] = []
    current_words: List[WordItem] = []
    current_speaker = words[0].speaker
    segment_idx = 0

    def flush_segment():
        nonlocal segment_idx, current_words, current_speaker
        if not current_words:
            return

        seg_start = current_words[0].start_ms
        seg_end = current_words[-1].end_ms
        seg_text = " ".join(w.word for w in current_words).strip()

        # Clean multiple spaces
        seg_text = re.sub(r'\s+', ' ', seg_text)

        segment = SegmentItem(
            idx=segment_idx,
            start_ms=seg_start,
            end_ms=seg_end,
            speaker=current_speaker,
            text=seg_text,
            words=list(current_words),
        )
        segments.append(segment)
        segment_idx += 1
        current_words = []

    for i, word in enumerate(words):
        is_speaker_change = word.speaker != current_speaker
        prev_word = words[i - 1] if i > 0 else None
        is_pause = (word.start_ms - prev_word.end_ms) >= pause_threshold_ms if prev_word else False

        # If speaker changed or significant pause occurred, flush previous words first
        if current_words and (is_speaker_change or is_pause):
            flush_segment()
            current_speaker = word.speaker

        current_words.append(word)

        # Check for sentence punctuation ending
        has_terminal_punct = bool(re.search(r'[.!?…]+$', word.word.strip()))
        duration_exceeded = (word.end_ms - current_words[0].start_ms) >= max_duration_ms
        count_exceeded = len(current_words) >= max_words

        if has_terminal_punct or duration_exceeded or count_exceeded:
            flush_segment()
            if i + 1 < len(words):
                current_speaker = words[i + 1].speaker

    flush_segment()
    return segments
