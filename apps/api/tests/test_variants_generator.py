"""Tests for Auto-Variants generator: baseline inclusion, deduplication, dimensions, caching."""
import pytest

from clip_shared.variants.generator import generate_clip_variants


def test_variants_generator_baseline_and_uniqueness():
    """Verify that Variant A is always the baseline and no variants are duplicates."""
    base_edit_doc = {
        "clip_id": "clip-123",
        "base_clip_id": "clip-123",
        "version": 1,
        "range": {"start_ms": 1000, "end_ms": 15000},
        "removals": [],
        "captions": {"style_key": "bold_pop", "words": [], "enabled": True},
        "hook": {"text": "Original Hook Line", "source": "auto", "start_ms": 0},
        "preset_key": "tiktok",
        "cleanup_options": {"remove_fillers": True, "remove_silence": True},
    }

    variants, in_tok, out_tok, cost_inr, is_cache = generate_clip_variants(
        base_edit_doc=base_edit_doc,
        clip_id="clip-123",
        original_hook="Original Hook Line",
        transcript_text="Transcript text explaining the main concept of the video.",
        alt_hooks=["Alternative Hook From Editor 1", "Alternative Hook From Editor 2"],
        count=4,
        dimensions=["hook", "style", "cta"],
        cta_goal="follow",
        include_baseline=True,
        cache_enabled=False,
    )

    # 1. Output count matches
    assert len(variants) == 4

    # 2. Variant A is baseline
    assert variants[0]["label"] == "Variant A (Baseline)"
    assert variants[0]["hook_text"] == "Original Hook Line"
    assert variants[0]["caption_style_key"] == "bold_pop"
    assert variants[0]["edit_doc"]["hook"]["text"] == "Original Hook Line"

    # 3. Check uniqueness across (hook, style, cta)
    tuples = [(v["hook_text"], v["caption_style_key"], v["cta_text"]) for v in variants]
    assert len(tuples) == len(set(tuples)), "Found duplicate variant combinations!"

    # 4. Token & cost tracking
    assert in_tok > 0
    assert out_tok > 0
    assert cost_inr == 0.15


def test_variants_generator_dimension_toggles():
    """Verify that when only 'style' is toggled, all variants keep the original hook."""
    base_edit_doc = {
        "clip_id": "clip-999",
        "base_clip_id": "clip-999",
        "version": 1,
        "range": {"start_ms": 0, "end_ms": 10000},
        "removals": [],
        "captions": {"style_key": "bold_pop", "words": [], "enabled": True},
        "hook": {"text": "Static Unchanging Hook", "source": "auto", "start_ms": 0},
        "preset_key": "tiktok",
    }

    variants, _, _, _, _ = generate_clip_variants(
        base_edit_doc=base_edit_doc,
        clip_id="clip-999",
        original_hook="Static Unchanging Hook",
        count=3,
        dimensions=["style"],  # Only style changes
        include_baseline=True,
        cache_enabled=False,
    )

    assert len(variants) == 3
    # All variants have same hook
    for v in variants:
        assert v["hook_text"] == "Static Unchanging Hook"

    # But styles differ
    styles = [v["caption_style_key"] for v in variants]
    assert len(set(styles)) > 1


def test_variants_generator_caching():
    """Verify that identical requests hit the LLM cache with 0 cost."""
    base_edit_doc = {
        "clip_id": "clip-cache-test",
        "base_clip_id": "clip-cache-test",
        "version": 1,
        "range": {"start_ms": 0, "end_ms": 10000},
        "captions": {"style_key": "bold_pop"},
        "hook": {"text": "Cacheable Hook"},
    }

    # First call - cache miss
    _, in1, out1, cost1, cache1 = generate_clip_variants(
        base_edit_doc=base_edit_doc,
        clip_id="clip-cache-test",
        original_hook="Cacheable Hook",
        count=3,
        cache_enabled=True,
    )
    assert cache1 is False
    assert cost1 > 0

    # Second call - cache hit
    _, in2, out2, cost2, cache2 = generate_clip_variants(
        base_edit_doc=base_edit_doc,
        clip_id="clip-cache-test",
        original_hook="Cacheable Hook",
        count=3,
        cache_enabled=True,
    )
    assert cache2 is True
    assert cost2 == 0.0
    assert in2 == in1
    assert out2 == out1
