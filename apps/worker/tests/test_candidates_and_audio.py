import numpy as np

from clip_shared.media.audio_features import (
    AudioFeaturesResult,
    HeuristicLaughterDetector,
    extract_audio_features,
    normalize_series,
)
from worker.candidates.filters import (
    calculate_window_iou,
    cluster_and_deduplicate_candidates,
    is_excessive_fillers,
    is_excessive_silence,
)
from worker.candidates.window_generator import (
    CandidateWindow,
    generate_candidate_windows,
    score_window_end_heuristics,
    score_window_start_heuristics,
)


def test_score_window_start_and_end():
    # Question hook + speaker turn
    score, reasons = score_window_start_heuristics("Why do 99% of businesses fail?", is_speaker_turn=True)
    assert score >= 0.40
    assert "question_hook" in reasons
    assert "speaker_turn" in reasons

    # Strong claim hook
    score2, reasons2 = score_window_start_heuristics("The truth is, nobody is going to hand you success.", is_speaker_turn=False)
    assert score2 >= 0.20
    assert "strong_claim" in reasons2

    # Conclusion & natural pause
    score_end, reasons_end = score_window_end_heuristics("And that's why consistency beats talent every single time.", gap_after_ms=800)
    assert score_end >= 0.35
    assert "conclusion_punchline" in reasons_end
    assert any("natural_pause" in r for r in reasons_end)


def test_generate_candidate_windows():
    segments = [
        {"idx": 0, "start_ms": 0, "end_ms": 5000, "speaker": "SPEAKER_00", "text": "What is the biggest myth in software engineering?"},
        {"idx": 1, "start_ms": 5100, "end_ms": 12000, "speaker": "SPEAKER_00", "text": "People think you have to write thousands of lines of code every single day."},
        {"idx": 2, "start_ms": 12200, "end_ms": 19000, "speaker": "SPEAKER_00", "text": "In reality, the best engineers spend most of their time deleting code."},
        {"idx": 3, "start_ms": 19500, "end_ms": 25000, "speaker": "SPEAKER_00", "text": "And that's how you build scalable systems with zero technical debt."},
    ]

    windows = generate_candidate_windows(segments, min_length_s=10.0, max_length_s=30.0)
    assert len(windows) > 0

    # Ensure windows respect sentence boundaries
    for w in windows:
        assert w.start_ms in [0, 5100, 12200]
        assert w.end_ms in [12000, 19000, 25000]
        assert w.duration_seconds >= 10.0
        assert w.heuristic_score > 0.0


def test_calculate_window_iou():
    w1 = CandidateWindow(start_ms=0, end_ms=30000, start_segment_idx=0, end_segment_idx=2, text="text 1")
    w2 = CandidateWindow(start_ms=10000, end_ms=40000, start_segment_idx=1, end_segment_idx=3, text="text 2")

    # Intersection: 10000 to 30000 = 20000 ms. Union: 0 to 40000 = 40000 ms. IoU = 0.5
    iou = calculate_window_iou(w1, w2)
    assert abs(iou - 0.5) < 1e-4

    w3 = CandidateWindow(start_ms=40000, end_ms=60000, start_segment_idx=4, end_segment_idx=5, text="text 3")
    assert calculate_window_iou(w1, w3) == 0.0


def test_candidate_filters_and_deduplication():
    # Fillers filter
    filler_text = "um like uh you know basically like sort of um yeah right"
    assert is_excessive_fillers(filler_text) is True

    clean_text = "Building great software requires deep focus, rigorous architecture, and disciplined testing."
    assert is_excessive_fillers(clean_text) is False

    # Silence filter
    w = CandidateWindow(start_ms=0, end_ms=10000, start_segment_idx=0, end_segment_idx=1, text="short")
    words_sparse = [{"start_ms": 0, "end_ms": 2000, "word": "hi"}]  # 2s speech out of 10s = 80% silence
    assert is_excessive_silence(w, words_sparse, max_silence_ratio=0.30) is True

    # Clustering & deduplication
    w_best = CandidateWindow(start_ms=0, end_ms=30000, start_segment_idx=0, end_segment_idx=2, text="best", heuristic_score=0.9)
    w_overlap = CandidateWindow(start_ms=5000, end_ms=32000, start_segment_idx=1, end_segment_idx=2, text="overlap", heuristic_score=0.4)
    w_other = CandidateWindow(start_ms=60000, end_ms=90000, start_segment_idx=4, end_segment_idx=6, text="other", heuristic_score=0.7)

    deduped = cluster_and_deduplicate_candidates([w_overlap, w_best, w_other], iou_threshold=0.5)
    assert len(deduped) == 2
    assert deduped[0].heuristic_score == 0.9
    assert deduped[1].heuristic_score == 0.7


def test_audio_features_extraction(tmp_path):
    # Test normalization
    arr = np.array([10.0, 20.0, 30.0, 40.0, 50.0], dtype=np.float32)
    norm = normalize_series(arr)
    assert norm.min() >= 0.0 and norm.max() <= 1.0

    # Test laughter detector
    detector = HeuristicLaughterDetector()
    y_synth = np.sin(np.linspace(0, 100, 16000, dtype=np.float32))
    laughter = detector.detect(y_synth, 16000)
    assert len(laughter) == 1

    # Test extract_audio_features with mock/temp wav
    dummy_wav = str(tmp_path / "test_audio.wav")
    with open(dummy_wav, "wb") as f:
        f.write(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00")

    result = extract_audio_features(dummy_wav)
    assert result.duration_seconds > 0
    assert len(result.rms_energy) > 0
    assert len(result.laughter_prob) > 0

    # Test serialization roundtrip
    npz_bytes = result.to_npz_bytes()
    restored = AudioFeaturesResult.from_npz_bytes(npz_bytes, duration_seconds=result.duration_seconds)
    assert len(restored.rms_energy) == len(result.rms_energy)

    # Test window feature retrieval
    win_feat = result.get_window_features(start_ms=0, end_ms=15000)
    assert "audio_energy" in win_feat
    assert "laughter" in win_feat
    assert "hook_energy" in win_feat
