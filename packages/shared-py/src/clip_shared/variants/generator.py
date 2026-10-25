"""Combinatorics engine and LLM generator for Auto-Variants.

Generates edit-doc forks across {hook, caption style, CTA} combinations.
Guarantees baseline inclusion, duplicate elimination, token/cost tracking, and caching.
"""
import copy
import hashlib
import uuid
from typing import Any

import structlog

from clip_shared.config import get_settings
from clip_shared.prompts.variants_v1 import (
    CTACandidate,
    HookCandidate,
    VariantGenerationBatchResponse,
    build_variant_generation_prompt,
)

logger = structlog.get_logger(__name__)
settings = get_settings()

# In-memory response cache: cache_key -> (VariantGenerationBatchResponse, in_tokens, out_tokens)
_VARIANTS_LLM_CACHE: dict[str, tuple[VariantGenerationBatchResponse, int, int]] = {}

DEFAULT_CTA_TEMPLATES = {
    "follow": [
        "Follow for daily insights 🚀",
        "Drop a follow if this helped you!",
        "Follow for Part 2 👆",
    ],
    "link_in_bio": [
        "Grab the full template in bio 🔗",
        "Full guide linked in bio!",
        "Check link in bio for more details",
    ],
    "subscribe": [
        "Subscribe for weekly breakdowns 🔔",
        "Hit subscribe to never miss an update",
        "Join the community — subscribe now!",
    ],
    "comment": [
        "What do you think? Comment below 👇",
        "Drop your questions in the comments!",
        "Let me know your thoughts below!",
    ],
    "engagement": [
        "Share this with someone who needs it 📲",
        "Save this video for later reference!",
        "Double tap if you found this valuable!",
    ],
}

BUILTIN_STYLES = ["bold_pop", "clean_minimal", "karaoke_dynamic"]


def compute_variant_cache_key(clip_id: str, original_hook: str, cta_goal: str, count: int) -> str:
    """Compute deterministic SHA256 cache key for LLM variant generation."""
    h = hashlib.sha256()
    h.update(clip_id.encode("utf-8"))
    h.update(b":")
    h.update(original_hook.strip().encode("utf-8"))
    h.update(b":")
    h.update(cta_goal.strip().lower().encode("utf-8"))
    h.update(b":")
    h.update(str(count).encode("utf-8"))
    return h.hexdigest()


def call_variant_llm(
    clip_id: str,
    clip_text: str,
    original_hook: str,
    cta_goal: str = "follow",
    count: int = 4,
    cache_enabled: bool = True,
) -> tuple[VariantGenerationBatchResponse, int, int, float, bool]:
    """
    Generate hooks and CTAs using structured LLM call with deterministic caching.
    Returns: (parsed_response, in_tokens, out_tokens, cost_inr, is_cache_hit)
    """
    cache_key = compute_variant_cache_key(clip_id, original_hook, cta_goal, count)
    if cache_enabled and cache_key in _VARIANTS_LLM_CACHE:
        cached_resp, in_tok, out_tok = _VARIANTS_LLM_CACHE[cache_key]
        return cached_resp, in_tok, out_tok, 0.0, True

    # Check if Anthropic API should be used or mock fallback
    if settings.LLM_SCORER_BACKEND == "anthropic" and settings.ANTHROPIC_API_KEY:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            prompt = build_variant_generation_prompt(clip_text, original_hook, cta_goal, count)
            resp = client.messages.create(
                model=settings.LLM_PASS1_MODEL,
                max_tokens=1024,
                system="You are an expert short-form video growth editor. Respond ONLY in valid JSON matching the schema.",
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = resp.content[0].text
            parsed = VariantGenerationBatchResponse.model_validate_json(raw_text)
            in_tokens = resp.usage.input_tokens
            out_tokens = resp.usage.output_tokens
            # Standard rate ~₹0.15 INR per variant generation
            cost_inr = 0.15
            if cache_enabled:
                _VARIANTS_LLM_CACHE[cache_key] = (parsed, in_tokens, out_tokens)
            return parsed, in_tokens, out_tokens, cost_inr, False
        except Exception as e:
            logger.warning("Anthropic variant generation failed, using mock generator", error=str(e))

    # Mock / Offline deterministic generator
    mock_hooks = [
        HookCandidate(text=f"The real truth about {original_hook[:24]}...", angle="intrigue", predicted_score=0.92),
        HookCandidate(text=f"Stop scrolling if you want to understand this:", angle="pattern_interrupt", predicted_score=0.88),
        HookCandidate(text=f"Why 99% of people get this completely backwards:", angle="contrarian", predicted_score=0.95),
        HookCandidate(text=f"Wait until you see how this ends...", angle="curiosity_gap", predicted_score=0.86),
        HookCandidate(text=f"The #1 shortcut nobody talks about:", angle="bold_claim", predicted_score=0.90),
    ]

    goal_key = cta_goal.lower() if cta_goal.lower() in DEFAULT_CTA_TEMPLATES else "follow"
    mock_ctas = [
        CTACandidate(text=t, goal=goal_key)
        for t in DEFAULT_CTA_TEMPLATES[goal_key]
    ]

    parsed = VariantGenerationBatchResponse(hooks=mock_hooks[:max(count, 4)], ctas=mock_ctas)
    in_tokens = 380
    out_tokens = 160
    cost_inr = 0.15

    if cache_enabled:
        _VARIANTS_LLM_CACHE[cache_key] = (parsed, in_tokens, out_tokens)

    return parsed, in_tokens, out_tokens, cost_inr, False


def generate_clip_variants(
    base_edit_doc: dict[str, Any],
    clip_id: str,
    original_hook: str,
    transcript_text: str = "",
    alt_hooks: list[str] | None = None,
    brand_kit: dict[str, Any] | None = None,
    count: int = 4,
    dimensions: list[str] | None = None,
    cta_goal: str = "follow",
    include_baseline: bool = True,
    cache_enabled: bool = True,
) -> tuple[list[dict[str, Any]], int, int, float, bool]:
    """
    Generate up to `count` non-duplicate clip variants by combinatorially
    exploring {hook, caption style, CTA} dimensions.

    Returns: (variants_list, total_input_tokens, total_output_tokens, total_cost_inr, is_cache_hit)
    """
    dimensions = dimensions or ["hook", "style", "cta"]
    count = max(1, min(10, count))

    # 1. Fetch LLM hooks and CTAs
    llm_resp, in_tok, out_tok, cost_inr, is_cache = call_variant_llm(
        clip_id=clip_id,
        clip_text=transcript_text or original_hook,
        original_hook=original_hook,
        cta_goal=cta_goal,
        count=count,
        cache_enabled=cache_enabled,
    )

    # 2. Gather Hook pool
    hook_pool: list[str] = [original_hook]
    if alt_hooks:
        for ah in alt_hooks:
            if ah and ah.strip() and ah.strip() not in hook_pool:
                hook_pool.append(ah.strip())
    for hk in llm_resp.hooks:
        if hk.text and hk.text.strip() not in hook_pool:
            hook_pool.append(hk.text.strip())

    # 3. Gather Style pool
    style_pool: list[str] = list(BUILTIN_STYLES)
    if brand_kit and brand_kit.get("caption_style_key"):
        brand_style = brand_kit["caption_style_key"]
        if brand_style not in style_pool:
            style_pool.insert(0, brand_style)

    # 4. Gather CTA pool
    goal_key = cta_goal.lower() if cta_goal.lower() in DEFAULT_CTA_TEMPLATES else "follow"
    cta_pool: list[str] = [c.text for c in llm_resp.ctas] or DEFAULT_CTA_TEMPLATES[goal_key]

    variants: list[dict[str, Any]] = []
    seen_combos: set[tuple[str, str, str | None]] = set()

    base_style = base_edit_doc.get("captions", {}).get("style_key", "bold_pop")
    base_cta = base_edit_doc.get("cta", {}).get("text") if base_edit_doc.get("cta") else None

    # Step 5: Always include baseline as Variant A if requested
    if include_baseline:
        baseline_doc = copy.deepcopy(base_edit_doc)
        combo_key = (original_hook, base_style, base_cta)
        seen_combos.add(combo_key)

        variants.append({
            "id": uuid.uuid4(),
            "label": "Variant A (Baseline)",
            "hook_text": original_hook,
            "caption_style_key": base_style,
            "cta_text": base_cta,
            "cta_style": "overlay" if base_cta else None,
            "score_hint": 1.0,
            "edit_doc": baseline_doc,
        })

    # Step 6: Combinatorial expansion
    letters = ["B", "C", "D", "E", "F", "G", "H", "I", "J"]
    labels_pool = [
        "Curiosity Hook",
        "Dynamic Captions",
        "High-Conversion CTA",
        "Pattern Interrupt",
        "Contrarian Take",
        "Bold Aesthetic",
        "Minimal Pacing",
        "Social Proof CTA",
    ]

    h_idx = 1 if len(hook_pool) > 1 else 0
    s_idx = 1 if len(style_pool) > 1 else 0
    c_idx = 0

    while len(variants) < count:
        curr_hook = hook_pool[h_idx % len(hook_pool)] if "hook" in dimensions else original_hook
        curr_style = style_pool[s_idx % len(style_pool)] if "style" in dimensions else base_style
        curr_cta = cta_pool[c_idx % len(cta_pool)] if "cta" in dimensions else base_cta

        combo_key = (curr_hook, curr_style, curr_cta)
        if combo_key not in seen_combos:
            seen_combos.add(combo_key)
            var_idx = len(variants)
            letter = letters[var_idx - 1] if var_idx <= len(letters) else f"V{var_idx+1}"
            label_desc = labels_pool[(var_idx - 1) % len(labels_pool)]
            label = f"Variant {letter} ({label_desc})"

            # Build edit_doc fork
            v_doc = copy.deepcopy(base_edit_doc)
            v_doc.setdefault("hook", {})["text"] = curr_hook
            if curr_hook != original_hook:
                v_doc["hook"]["title_card"] = True
                v_doc["hook"]["title_card_duration_s"] = 2.5

            v_doc.setdefault("captions", {})["style_key"] = curr_style

            if curr_cta:
                v_doc["cta"] = {
                    "text": curr_cta,
                    "style": "overlay",
                    "duration_s": 2.0,
                }
            else:
                v_doc["cta"] = None

            variants.append({
                "id": uuid.uuid4(),
                "label": label,
                "hook_text": curr_hook,
                "caption_style_key": curr_style,
                "cta_text": curr_cta,
                "cta_style": "overlay" if curr_cta else None,
                "score_hint": round(0.95 - (var_idx * 0.02), 2),
                "edit_doc": v_doc,
            })

        # Advance combinator indices
        h_idx += 1
        s_idx += 1
        c_idx += 1

        # Break early if we looped through all reasonable possibilities
        if h_idx > 50:
            break

    return variants, in_tok, out_tok, cost_inr, is_cache
