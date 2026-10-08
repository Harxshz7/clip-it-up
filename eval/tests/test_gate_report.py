import json
import os
import tempfile

import pytest

from eval.gate import calculate_gate_metrics, format_gate_markdown, generate_gate_report


def test_gate_metrics_fixture_hand_calculated_numbers():
    """Verify exact hand-computed metric formulas, percentages, and PASS/FAIL gate checks."""
    fixtures_path = os.path.join(
        os.path.dirname(__file__), "..", "fixtures", "gate_creator_sessions.json"
    )
    with open(fixtures_path, encoding="utf-8") as f:
        sessions_data = json.load(f)

    report = calculate_gate_metrics(sessions_data)
    m = report["metrics"]

    # 1. Basic counts
    assert m["total_creators"] == 5
    assert m["submitted_creators"] == 5
    assert m["total_clips_rated"] == 40  # 5 creators * 8 clips

    # 2. Hand-calculated Usable Rates
    # Post as is (14) + Post with edits (12) = 26 postable clips out of 40 = 65.0%
    assert round(m["usable_rate"], 2) == 0.65
    # Strict usable rate: 14 / 40 = 35.0%
    assert round(m["strict_usable_rate"], 2) == 0.35
    # Top 3 usable rate: 15 / 15 = 100.0%
    assert round(m["top3_usable_rate"], 2) == 1.00

    # 3. Willingness to Pay
    # Prices: [2500, 3000, 5000, 1500, 2000] -> median is 2500
    assert m["median_open_price_inr"] == 2500.0
    assert m["accepts_1500_pct"] == 100.0
    assert m["commit_upload_pct"] == 100.0

    # 4. Check all 4 gate checks PASS
    check_map = {c["id"]: c["status"] for c in report["checks"]}
    assert check_map["usable_rate"] == "PASS"
    assert check_map["creators_postable_clips"] == "PASS"
    assert check_map["commercial_intent"] == "PASS"
    assert check_map["no_reason_concentration"] == "PASS"

    # 5. Final verdict is GO
    assert report["overall_verdict"] == "GO"
    assert len(report["recommendations"]) == 3


def test_gate_decision_branch_fix_selection_and_rethink():
    """Verify gate decision logic correctly triggers 'FIX SELECTION FIRST' and 'RETHINK'."""
    # Scenario A: Usable rate < 60% with high 'bad_start' rejections
    low_usable_sessions = [
        {
            "creator_name": "Test Creator 1",
            "status": "submitted",
            "ratings": [
                {"verdict": "no", "reason_tag": "bad_start", "rank": 1},
                {"verdict": "no", "reason_tag": "bad_start", "rank": 2},
                {"verdict": "no", "reason_tag": "bad_start", "rank": 3},
                {"verdict": "no", "reason_tag": "bad_start", "rank": 4},
                {"verdict": "post_as_is", "rank": 5},
            ],
            "survey": {"price_open_inr": 2000, "accepts_1500": True, "would_upload_next": "yes"},
        }
    ]
    report_a = calculate_gate_metrics(low_usable_sessions)
    assert report_a["overall_verdict"] == "FIX SELECTION FIRST"

    # Scenario B: Zero commercial intent
    zero_intent_sessions = [
        {
            "creator_name": "Freebie User",
            "status": "submitted",
            "ratings": [
                {"verdict": "no", "rank": 1},
                {"verdict": "no", "rank": 2},
            ],
            "survey": {"price_open_inr": 0, "accepts_1500": False, "accepts_4000": False, "would_upload_next": "no"},
        }
    ]
    report_b = calculate_gate_metrics(zero_intent_sessions)
    assert report_b["overall_verdict"] == "RETHINK"


@pytest.mark.asyncio
async def test_generate_gate_report_file_output():
    """Verify generate_gate_report writes valid markdown and JSON files."""
    fixtures_path = os.path.join(
        os.path.dirname(__file__), "..", "fixtures", "gate_creator_sessions.json"
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        report = await generate_gate_report(fixtures_path=fixtures_path, output_dir=tmpdir)
        assert os.path.exists(report["markdown_path"])
        assert os.path.exists(report["json_path"])

        with open(report["markdown_path"], encoding="utf-8") as f:
            md_text = f.read()
            assert "# Creator Reality Check" in md_text
            assert "Overall Decision: 🟢 **GO**" in md_text
            assert "Usable Rate" in md_text
