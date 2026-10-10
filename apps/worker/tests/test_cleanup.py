import numpy as np

from clip_shared.media.cleanup import (
    detect_filler_removals,
    detect_silence_removals,
    plan_clip_cleanup,
    snap_cut_point,
)


def test_detect_filler_removals_english_and_multiword():
    """Verify single and multi-word filler detection (um, uh, you know, i mean)."""
    words = [
        {"text": "Hey", "start_ms": 1200, "end_ms": 1500},
        {"text": "um", "start_ms": 1600, "end_ms": 1900},
        {"text": "everyone", "start_ms": 2000, "end_ms": 2500},
        {"text": "you", "start_ms": 2600, "end_ms": 2800},
        {"text": "know", "start_ms": 2800, "end_ms": 3100},
        {"text": "today", "start_ms": 3200, "end_ms": 3600},
    ]

    fillers = detect_filler_removals(words, language="en", clip_start_ms=0, clip_end_ms=5000)
    assert len(fillers) == 2
    assert fillers[0].start_ms == 1600
    assert fillers[0].end_ms == 1900
    assert fillers[0].text == "um"

    assert fillers[1].start_ms == 2600
    assert fillers[1].end_ms == 3100
    assert fillers[1].text == "you know"


def test_filler_contextual_like():
    """Verify 'like' is only detected when preceded/followed by a pause or filler."""
    words = [
        # Legitimate verb 'I like pizza' -> NOT a filler
        {"text": "I", "start_ms": 1200, "end_ms": 1300},
        {"text": "like", "start_ms": 1300, "end_ms": 1400},
        {"text": "pizza", "start_ms": 1400, "end_ms": 1800},
        # Hesitation filler 'like ... you know' with 300ms pause after -> IS a filler
        {"text": "and", "start_ms": 2500, "end_ms": 2700},
        {"text": "like", "start_ms": 2700, "end_ms": 2900},
        {"text": "this", "start_ms": 3300, "end_ms": 3600},  # 400ms pause after 'like'
    ]

    fillers = detect_filler_removals(words, language="en", clip_start_ms=0, clip_end_ms=5000)
    assert len(fillers) == 1
    assert fillers[0].start_ms == 2700
    assert fillers[0].end_ms == 2900


def test_detect_silence_shortening_not_deletion():
    """Verify gaps > 700ms are shortened to 250ms rather than deleted entirely."""
    words = [
        {"text": "First", "start_ms": 1200, "end_ms": 1600},
        # Gap: 1600 to 2800 = 1200ms pause
        {"text": "Second", "start_ms": 2800, "end_ms": 3200},
        # Gap: 3200 to 3500 = 300ms pause (< 700ms -> should NOT be cut)
        {"text": "Third", "start_ms": 3500, "end_ms": 3900},
    ]

    silences = detect_silence_removals(words, max_silence_ms=700, target_silence_ms=250, clip_start_ms=0)
    assert len(silences) == 1
    rem = silences[0]
    # Total gap was 1200ms. Target is 250ms. Removed should be 950ms.
    # Buffer half = 125ms -> start = 1600 + 125 = 1725, end = 2800 - 125 = 2675
    assert rem.start_ms == 1725
    assert rem.end_ms == 2675
    assert rem.duration_ms == 950


def test_hook_protection_first_one_second():
    """Verify first 1.0s hook words are protected from filler/silence cut."""
    words = [
        {"text": "um", "start_ms": 200, "end_ms": 500},        # Inside first 1s hook -> protected
        {"text": "Start", "start_ms": 600, "end_ms": 900},
        {"text": "um", "start_ms": 1500, "end_ms": 1800},      # After hook -> removed
    ]

    fillers = detect_filler_removals(words, clip_start_ms=0)
    assert len(fillers) == 1
    assert fillers[0].start_ms == 1500


def test_snap_cut_point_to_zero_crossing():
    """Verify cut snapping finds exact zero crossings in audio sample."""
    sr = 16000
    # Create sine wave where zero crossing occurs at exact known sample
    t = np.linspace(0, 1.0, sr, dtype=np.float32)
    audio = np.sin(2 * np.pi * 10 * t)  # 10 Hz wave -> zero crossings every 50ms

    # Query timestamp 105ms -> nearest zero crossing is at 100ms
    snapped = snap_cut_point(timestamp_ms=105, audio_data=audio, sr=sr, search_window_ms=30)
    assert abs(snapped - 100) <= 2


def test_plan_clip_cleanup_safety_cap():
    """Verify cleanup enforces max 25% removal ratio cap."""
    # 10s clip -> max 2500ms can be removed
    words = [
        {"text": "Hook", "start_ms": 100, "end_ms": 800},
        {"text": "A", "start_ms": 1500, "end_ms": 2000},
        # Huge 5000ms gap
        {"text": "B", "start_ms": 7000, "end_ms": 7500},
    ]

    res = plan_clip_cleanup(
        clip_start_ms=0,
        clip_end_ms=10000,
        words=words,
        max_removal_ratio=0.25,
    )

    assert res.saved_ms <= 2500
    assert res.clean_duration_ms >= 7500
    assert res.savings_ratio <= 0.25
