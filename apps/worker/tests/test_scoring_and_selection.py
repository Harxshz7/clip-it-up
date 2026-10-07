import uuid
import pytest
from worker.scoring.llm_client import LLMClient, compute_cache_key, _LLM_RESPONSE_CACHE
from worker.scoring.combiner import combine_signals
from worker.scoring.selection import select_top_moments, calculate_moment_iou
from worker.scoring.variants import generate_moment_variants
from clip_shared.prompts.clip_score_v1 import (
    Pass1BatchResponse,
    Pass2CandidateScore,
    ClipScoreFlags,
)


def test_llm_client_mock_and_caching():
    client = LLMClient(backend="mock", cache_enabled=True)

    prompt = 'Evaluate candidate: ID: cand_123 Range: 10000ms to 40000ms Transcript:\n"Why do most founders fail?"\n'
    resp1, in_tok1, out_tok1, cost1, is_cache1 = client.call_structured(
        prompt=prompt,
        model="claude-3-5-sonnet-20241022",
        response_schema=Pass2CandidateScore,
        prompt_version="v1",
    )

    assert is_cache1 is False
    assert resp1.hook >= 0.0 and resp1.hook <= 1.0
    assert resp1.best_hook_text != ""
    assert resp1.suggested_start_ms >= 10000

    # Second call with identical prompt must hit cache
    resp2, in_tok2, out_tok2, cost2, is_cache2 = client.call_structured(
        prompt=prompt,
        model="claude-3-5-sonnet-20241022",
        response_schema=Pass2CandidateScore,
        prompt_version="v1",
    )
    assert is_cache2 is True
    assert resp2.title == resp1.title


def test_signal_combiner():
    score_obj = Pass2CandidateScore(
        id="cand_1",
        hook=0.90,
        emotion=0.80,
        coherence=0.95,
        payoff=0.85,
        novelty=0.75,
        best_hook_text="Why do 90% of startups fail?",
        suggested_start_ms=0,
        suggested_end_ms=30000,
        title="Startup Survival",
        reason="Clear hook and actionable payoff.",
        flags=ClipScoreFlags(needs_context=False, off_topic=False, profanity=False, sensitive=False),
    )

    audio_feat = {
        "audio_energy": 0.80,
        "laughter": 0.20,
        "hook_energy": 0.85,
        "pause_ratio": 0.05,
    }

    weights = {
        "hook": 0.30,
        "emotion": 0.15,
        "coherence": 0.20,
        "payoff": 0.20,
        "novelty": 0.10,
        "audio_energy": 0.10,
        "laughter": 0.05,
        "pause_penalty": 0.15,
        "flag_penalty": 0.30,
    }

    final_score, breakdown = combine_signals(score_obj, audio_feat, weights, hook_energy_boost=0.15)
    assert final_score >= 0.75
    assert breakdown["hook"] > 0.85
    assert breakdown["pause_penalty"] > 0.0


def test_moment_selection_and_diversity():
    moments = [
        {"moment_id": uuid.uuid4(), "start_ms": 10000, "end_ms": 40000, "final_score": 0.92, "title": "Clip 1"},
        {"moment_id": uuid.uuid4(), "start_ms": 15000, "end_ms": 45000, "final_score": 0.88, "title": "Clip 2 Overlap"},  # IoU > 0.3 with Clip 1
        {"moment_id": uuid.uuid4(), "start_ms": 70000, "end_ms": 100000, "final_score": 0.85, "title": "Clip 3"},
        {"moment_id": uuid.uuid4(), "start_ms": 120000, "end_ms": 150000, "final_score": 0.80, "title": "Clip 4"},
        {"moment_id": uuid.uuid4(), "start_ms": 180000, "end_ms": 210000, "final_score": 0.75, "title": "Clip 5 (3rd in 5min bucket)"},
        {"moment_id": uuid.uuid4(), "start_ms": 600000, "end_ms": 630000, "final_score": 0.78, "title": "Clip 6"},
    ]

    selected = select_top_moments(
        moments,
        max_selected=5,
        iou_threshold=0.30,
        diversity_window_minutes=5.0,
        max_clips_per_window=2,
        diversity_score_override=0.90,
    )

    # Clip 2 must be dropped due to IoU overlap with Clip 1
    selected_titles = [s["title"] for s in selected]
    assert "Clip 1" in selected_titles
    assert "Clip 2 Overlap" not in selected_titles
    assert selected[0]["rank"] == 1


def test_variant_generation():
    segments = [
        {"start_ms": 0, "end_ms": 14000, "text": "Why is building startups so difficult?"},
        {"start_ms": 14200, "end_ms": 29000, "text": "Because distribution is always harder than product."},
        {"start_ms": 29200, "end_ms": 44000, "text": "If you don't talk to customers on day one, nobody will buy."},
        {"start_ms": 44200, "end_ms": 59000, "text": "And that is why early feedback determines everything."},
    ]

    variants = generate_moment_variants(
        moment_start_ms=0,
        moment_end_ms=59000,
        base_hook_text="Why is building startups so difficult?",
        base_title="Startup Distribution Secret",
        base_score=0.88,
        base_breakdown={"hook": 0.9},
        base_reason="Great advice",
        segments=segments,
        target_lengths=[15, 30, 45, 60],
    )

    variant_lengths = [v.variant_length_s for v in variants]
    assert "auto" in variant_lengths
    assert "15" in variant_lengths
    assert "30" in variant_lengths
    assert all(v.final_score > 0.0 for v in variants)
