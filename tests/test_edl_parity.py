import json
from pathlib import Path

from clip_shared.media.edl import EditDecisionList


def test_edl_python_parity_with_shared_vectors():
    fixture_path = Path(__file__).parent / "fixtures" / "edl_parity_vectors.json"
    assert fixture_path.exists(), f"Fixture not found at {fixture_path}"

    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)

    # 1. Test cases
    for case in data["cases"]:
        edl = EditDecisionList.create(
            clip_start_ms=case["clip_start_ms"],
            clip_end_ms=case["clip_end_ms"],
            removals=case["removals"],
        )

        assert edl.total_out_duration_ms == case["expected_out_duration_ms"], (
            f"Failed on case {case['name']}: out_duration mismatch"
        )
        assert edl.removed_duration_ms == case["expected_removed_ms"], (
            f"Failed on case {case['name']}: removed_ms mismatch"
        )

        assert len(edl.keep_segments) == len(case["expected_keep_segments"]), (
            f"Failed on case {case['name']}: segment count mismatch"
        )

        for actual_seg, exp_seg in zip(edl.keep_segments, case["expected_keep_segments"]):
            assert actual_seg.src_start_ms == exp_seg["src_start_ms"]
            assert actual_seg.src_end_ms == exp_seg["src_end_ms"]
            assert actual_seg.out_start_ms == exp_seg["out_start_ms"]
            assert actual_seg.out_end_ms == exp_seg["out_end_ms"]

    # 2. Test words remapping
    w_data = data["words_fixture"]
    edl_w = EditDecisionList.create(
        clip_start_ms=w_data["clip_start_ms"],
        clip_end_ms=w_data["clip_end_ms"],
        removals=w_data["removals"],
    )
    remapped = edl_w.remap_words(w_data["words"])
    assert len(remapped) == len(w_data["expected_remapped_words"])

    for actual_w, exp_w in zip(remapped, w_data["expected_remapped_words"]):
        assert actual_w["text"] == exp_w["text"]
        assert actual_w["start_ms"] == exp_w["start_ms"]
        assert actual_w["end_ms"] == exp_w["end_ms"]
        assert actual_w["src_start_ms"] == exp_w["src_start_ms"]
        assert actual_w["src_end_ms"] == exp_w["src_end_ms"]
