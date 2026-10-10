import pytest

from clip_shared.media.edl import EditDecisionList, KeepSegment, Removal


def test_edl_no_removals():
    """Verify EDL with no removals creates a single identical keep segment."""
    edl = EditDecisionList.create(clip_start_ms=1000, clip_end_ms=11000)
    assert len(edl.keep_segments) == 1
    assert edl.total_src_duration_ms == 10000
    assert edl.total_out_duration_ms == 10000
    assert edl.removed_duration_ms == 0

    seg = edl.keep_segments[0]
    assert seg.src_start_ms == 1000
    assert seg.src_end_ms == 11000
    assert seg.out_start_ms == 0
    assert seg.out_end_ms == 10000

    # Time map checks
    assert edl.src_to_out(1000) == 0
    assert edl.src_to_out(5000) == 4000
    assert edl.src_to_out(11000) == 10000
    assert edl.out_to_src(0) == 1000
    assert edl.out_to_src(4000) == 5000
    assert edl.out_to_src(10000) == 11000


def test_edl_single_middle_removal():
    """Verify EDL with a single cut in the middle splits into 2 keep segments."""
    # Clip: 10s -> [0ms, 10000ms]
    # Remove: [4000ms, 6000ms] (2000ms cut)
    edl = EditDecisionList.create(
        clip_start_ms=0,
        clip_end_ms=10000,
        removals=[{"start_ms": 4000, "end_ms": 6000, "kind": "filler", "text": "um"}],
    )
    assert len(edl.keep_segments) == 2
    assert edl.total_src_duration_ms == 10000
    assert edl.total_out_duration_ms == 8000
    assert edl.removed_duration_ms == 2000

    # Segment 1: [0, 4000] -> out [0, 4000]
    assert edl.keep_segments[0].src_start_ms == 0
    assert edl.keep_segments[0].src_end_ms == 4000
    assert edl.keep_segments[0].out_start_ms == 0
    assert edl.keep_segments[0].out_end_ms == 4000

    # Segment 2: [6000, 10000] -> out [4000, 8000]
    assert edl.keep_segments[1].src_start_ms == 6000
    assert edl.keep_segments[1].src_end_ms == 10000
    assert edl.keep_segments[1].out_start_ms == 4000
    assert edl.keep_segments[1].out_end_ms == 8000

    # Test time map
    assert edl.src_to_out(2000) == 2000
    assert edl.src_to_out(5000) is None  # Inside cut
    assert edl.src_to_out(7000) == 5000

    # Test clamped time map
    assert edl.src_to_out_clamped(5000) == 4000  # Clamped to cut boundary
    assert edl.out_to_src(4000) == 6000          # Cut seam maps to next keep segment start
    assert edl.out_to_src(5000) == 7000


def test_edl_overlapping_and_adjacent_removals():
    """Verify overlapping and contiguous removal intervals are correctly merged."""
    removals = [
        {"start_ms": 2000, "end_ms": 4000, "kind": "filler"},
        {"start_ms": 3500, "end_ms": 5000, "kind": "silence"},  # Overlaps [2000, 4000] -> [2000, 5000]
        {"start_ms": 5000, "end_ms": 6000, "kind": "silence"},  # Touches [2000, 5000] -> [2000, 6000]
        {"start_ms": 8000, "end_ms": 9000, "kind": "filler"},
    ]
    edl = EditDecisionList.create(clip_start_ms=0, clip_end_ms=10000, removals=removals)
    assert len(edl.removals) == 2
    assert edl.removals[0].start_ms == 2000
    assert edl.removals[0].end_ms == 6000
    assert edl.removals[1].start_ms == 8000
    assert edl.removals[1].end_ms == 9000

    assert len(edl.keep_segments) == 3
    # Seg 0: [0, 2000] -> out [0, 2000]
    # Seg 1: [6000, 8000] -> out [2000, 4000]
    # Seg 2: [9000, 10000] -> out [4000, 5000]
    assert edl.total_out_duration_ms == 5000
    assert edl.removed_duration_ms == 5000


def test_edl_removals_at_boundaries():
    """Verify removals at exact clip start and clip end."""
    removals = [
        {"start_ms": 0, "end_ms": 2000, "kind": "silence"},
        {"start_ms": 8000, "end_ms": 10000, "kind": "silence"},
    ]
    edl = EditDecisionList.create(clip_start_ms=0, clip_end_ms=10000, removals=removals)
    assert len(edl.keep_segments) == 1
    assert edl.keep_segments[0].src_start_ms == 2000
    assert edl.keep_segments[0].src_end_ms == 8000
    assert edl.keep_segments[0].out_start_ms == 0
    assert edl.keep_segments[0].out_end_ms == 6000
    assert edl.total_out_duration_ms == 6000


def test_edl_removals_out_of_bounds():
    """Verify removals completely outside clip range are filtered or clamped."""
    removals = [
        {"start_ms": -5000, "end_ms": -100, "kind": "silence"},  # Outside left
        {"start_ms": 20000, "end_ms": 30000, "kind": "filler"}, # Outside right
        {"start_ms": 4000, "end_ms": 6000, "kind": "filler"},   # Valid inside
    ]
    edl = EditDecisionList.create(clip_start_ms=1000, clip_end_ms=10000, removals=removals)
    assert len(edl.removals) == 1
    assert edl.removals[0].start_ms == 4000
    assert edl.removals[0].end_ms == 6000
    assert edl.total_src_duration_ms == 9000
    assert edl.total_out_duration_ms == 7000


def test_edl_property_monotonic_and_invertible():
    """Property test: out_to_src is monotonic and perfectly inverts src_to_out for all kept points."""
    edl = EditDecisionList.create(
        clip_start_ms=5000,
        clip_end_ms=35000,
        removals=[
            {"start_ms": 8000, "end_ms": 10000},
            {"start_ms": 15000, "end_ms": 18000},
            {"start_ms": 25000, "end_ms": 27000},
        ],
    )

    prev_out = -1
    for t in range(5000, 35001, 100):
        out_t = edl.src_to_out(t)
        if out_t is not None:
            # Monotonicity
            assert out_t >= prev_out
            prev_out = out_t

            # Invertibility
            inverted_src = edl.out_to_src(out_t)
            assert inverted_src == t

    # Invertibility from output timeline
    for out_t in range(0, edl.total_out_duration_ms + 1, 100):
        src_t = edl.out_to_src(out_t)
        assert edl.clip_start_ms <= src_t <= edl.clip_end_ms
        mapped_out = edl.src_to_out(src_t)
        assert mapped_out == out_t


def test_edl_remap_words():
    """Verify word timestamp remapping through EDL."""
    words = [
        {"text": "Hello", "start_ms": 1000, "end_ms": 1500},
        {"text": "um", "start_ms": 2000, "end_ms": 2500},      # in removal
        {"text": "world", "start_ms": 3000, "end_ms": 3600},
    ]
    edl = EditDecisionList.create(
        clip_start_ms=0,
        clip_end_ms=5000,
        removals=[{"start_ms": 1800, "end_ms": 2800, "kind": "filler", "text": "um"}],
    )
    remapped = edl.remap_words(words)
    assert len(remapped) == 2
    assert remapped[0]["text"] == "Hello"
    assert remapped[0]["start_ms"] == 1000
    assert remapped[0]["end_ms"] == 1500

    assert remapped[1]["text"] == "world"
    # Cut was 1000ms [1800, 2800]. world (3000-1000) = 2000, (3600-1000) = 2600
    assert remapped[1]["start_ms"] == 2000
    assert remapped[1]["end_ms"] == 2600


def test_edl_remap_crop_path():
    """Verify crop path keyframe remapping through EDL."""
    crop_path = {
        "keyframes": [
            {"t_ms": 0, "cx": 0.5, "cy": 0.5, "w": 0.5625, "h": 1.0},
            {"t_ms": 3000, "cx": 0.6, "cy": 0.5, "w": 0.5625, "h": 1.0},
            {"t_ms": 5000, "cx": 0.7, "cy": 0.5, "w": 0.5625, "h": 1.0},
        ],
        "segments": [{"mode": "speaker_track"}],
    }
    edl = EditDecisionList.create(
        clip_start_ms=0,
        clip_end_ms=5000,
        removals=[{"start_ms": 1000, "end_ms": 2000, "kind": "silence"}],
    )
    remapped = edl.remap_crop_path(crop_path)
    assert remapped["duration_ms"] == 4000
    kfs = remapped["keyframes"]
    assert len(kfs) >= 3
    assert kfs[0]["t_ms"] == 0
    assert kfs[-1]["t_ms"] == 4000
