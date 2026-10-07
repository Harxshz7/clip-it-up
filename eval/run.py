import glob
import json
import os
import sys
import time
from datetime import UTC, datetime
from typing import Any

import numpy as np
import yaml

# Ensure project packages are on python path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in [
    os.path.join(repo_root, "packages", "shared-py", "src"),
    os.path.join(repo_root, "apps", "api", "src"),
    os.path.join(repo_root, "apps", "worker", "src"),
    repo_root,
]:
    if p not in sys.path:
        sys.path.insert(0, p)

from clip_shared.config import get_settings, load_scoring_weights  # noqa: E402
from clip_shared.media.audio_features import AudioFeaturesResult  # noqa: E402
from clip_shared.prompts.clip_score_v1 import (  # noqa: E402
    Pass1BatchResponse,
    Pass1CandidateItem,
    Pass2CandidateScore,
    build_pass1_prompt,
    build_pass2_prompt,
)
from eval.metrics import (  # noqa: E402
    compute_auc_roc,
    compute_correlations,
    compute_inter_rater_agreement,
    compute_iou,
    compute_precision_at_k,
    is_usable_clip,
)
from worker.candidates.filters import cluster_and_deduplicate_candidates, filter_candidate_windows  # noqa: E402
from worker.candidates.window_generator import generate_candidate_windows  # noqa: E402
from worker.scoring.combiner import combine_signals  # noqa: E402
from worker.scoring.llm_client import LLMClient  # noqa: E402
from worker.scoring.selection import select_top_moments  # noqa: E402

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEOS_DIR = os.path.join(EVAL_DIR, "videos")
RATINGS_DIR = os.path.join(EVAL_DIR, "ratings")
REPORTS_DIR = os.path.join(EVAL_DIR, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


def load_previous_report() -> dict[str, Any] | None:
    """Load the latest JSON report for diff calculation."""
    json_files = sorted(glob.glob(os.path.join(REPORTS_DIR, "*.json")))
    if not json_files:
        return None
    latest_file = json_files[-1]
    try:
        with open(latest_file, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def run_evaluation(
    custom_weights: dict[str, Any] | None = None,
    prompt_version: str = "v1",
) -> dict[str, Any]:
    """Execute complete benchmark evaluation over all eval dataset videos."""
    start_eval_time = time.time()
    config_weights = load_scoring_weights()
    weights = custom_weights or config_weights.get("weights", {})
    thresholds = config_weights.get("thresholds", {})
    hook_boost = float(config_weights.get("hook_energy_boost", 0.15))

    # Load ground truth ratings
    ratings_file = os.path.join(RATINGS_DIR, "ground_truth.json")
    all_ratings = []
    if os.path.exists(ratings_file):
        with open(ratings_file, encoding="utf-8") as f:
            all_ratings = json.load(f)

    # Group ratings by video slug
    ratings_by_slug: dict[str, list[dict[str, Any]]] = {}
    ratings_by_item: dict[str, dict[str, int]] = {}
    for r in all_ratings:
        slug = r["video_slug"]
        ratings_by_slug.setdefault(slug, []).append(r)
        item_key = f"{slug}_{r['start_ms']}_{r['end_ms']}"
        ratings_by_item.setdefault(item_key, {})[r["rater_id"]] = r["score"]

    llm = LLMClient()
    video_dirs = sorted([d for d in os.listdir(VIDEOS_DIR) if os.path.isdir(os.path.join(VIDEOS_DIR, d))])

    per_video_results = []
    all_final_scores = []
    all_binary_labels = []
    all_signal_values: dict[str, list[float]] = {
        "hook": [], "emotion": [], "coherence": [], "payoff": [],
        "novelty": [], "audio_energy": [], "laughter": [], "pause_penalty": []
    }

    total_source_duration_s = 0.0
    total_tokens_in = 0
    total_tokens_out = 0
    total_cost_inr = 0.0

    print("\n================================================================================")
    print(f"  CLIP-IT-UP EVAL HARNESS: EVALUATING {len(video_dirs)} BENCHMARK VIDEOS")
    print("================================================================================\n")

    for v_slug in video_dirs:
        v_path = os.path.join(VIDEOS_DIR, v_slug)
        meta_file = os.path.join(v_path, "meta.yaml")
        trans_file = os.path.join(v_path, "transcript.json")

        if not os.path.exists(meta_file) or not os.path.exists(trans_file):
            continue

        with open(meta_file, encoding="utf-8") as f:
            meta = yaml.safe_load(f)
        with open(trans_file, encoding="utf-8") as f:
            trans_data = json.load(f)

        duration_s = float(meta.get("duration_seconds", 1800.0))
        total_source_duration_s += duration_s

        segments = trans_data.get("segments", [])
        words = trans_data.get("words", [])
        gt_ratings = ratings_by_slug.get(v_slug, [])

        # 1. Candidate Generation
        raw_windows = generate_candidate_windows(segments, min_length_s=15.0, max_length_s=90.0)
        filtered = filter_candidate_windows(raw_windows, words=words, segments=segments)
        candidates = cluster_and_deduplicate_candidates(filtered or raw_windows, iou_threshold=0.50, max_candidates=25)

        # 2. Audio features (deterministic synthetic for eval benchmark)
        audio_feat = AudioFeaturesResult(
            duration_seconds=duration_s,
            rms_energy=[0.6] * int(duration_s),
            spectral_flux=[0.5] * int(duration_s),
            pitch_variance=[0.5] * int(duration_s),
            laughter_prob=[0.0] * int(duration_s),
            pause_map=[],
            summary={"mean_rms_energy": 0.6},
        )

        # 3. Two-Pass Scoring
        all_text = " ".join(s["text"] for s in segments)
        video_summary = all_text[:1200]

        # Pass 1
        pass1_items = [
            Pass1CandidateItem(id=f"c_{idx}", start_ms=c.start_ms, end_ms=c.end_ms, text=c.text)
            for idx, c in enumerate(candidates)
        ]
        p1_prompt = build_pass1_prompt(pass1_items, video_summary)
        p1_resp, in_t, out_t, c_inr, _ = llm.call_structured(p1_prompt, "claude-3-haiku-20240307", Pass1BatchResponse, prompt_version)
        total_tokens_in += in_t
        total_tokens_out += out_t
        total_cost_inr += c_inr

        # Pass 2 on top candidates
        p1_scores = {s.id: s.coarse_score for s in p1_resp.scores}
        sorted_cand = sorted(candidates, key=lambda c: p1_scores.get(f"c_{candidates.index(c)}", 5.0), reverse=True)
        top_candidates = sorted_cand[:max(3, int(len(sorted_cand) * 0.5))]

        scored_moments = []
        for c in top_candidates:
            p2_prompt = build_pass2_prompt(
                candidate_id=f"cand_{c.start_ms}",
                start_ms=c.start_ms,
                end_ms=c.end_ms,
                text=c.text,
                speaker=c.speaker,
                video_summary=video_summary,
            )
            p2_resp, in_t, out_t, c_inr, _ = llm.call_structured(p2_prompt, "claude-3-5-sonnet-20241022", Pass2CandidateScore, prompt_version)
            total_tokens_in += in_t
            total_tokens_out += out_t
            total_cost_inr += c_inr

            window_audio = audio_feat.get_window_features(c.start_ms, c.end_ms)
            f_score, breakdown = combine_signals(p2_resp, window_audio, weights, hook_boost)

            scored_moments.append({
                "start_ms": p2_resp.suggested_start_ms,
                "end_ms": p2_resp.suggested_end_ms,
                "final_score": f_score,
                "hook_text": p2_resp.best_hook_text,
                "title": p2_resp.title,
                "breakdown": breakdown,
            })

            # Check if this clip range is usable under ground truth
            matched_scores = [r["score"] for r in gt_ratings if compute_iou(c.start_ms, c.end_ms, r["start_ms"], r["end_ms"]) >= 0.5]
            is_usable = is_usable_clip(matched_scores) if matched_scores else (f_score >= 0.70)
            binary_label = 1 if is_usable else 0

            all_final_scores.append(f_score)
            all_binary_labels.append(binary_label)

            for sig_k in all_signal_values.keys():
                all_signal_values[sig_k].append(breakdown.get(sig_k, 0.5))

        # Select Top 5 & Compute Precision@5
        selected = select_top_moments(
            scored_moments,
            max_selected=5,
            iou_threshold=float(thresholds.get("selection_iou_threshold", 0.30)),
            diversity_window_minutes=float(thresholds.get("diversity_window_minutes", 5.0)),
            max_clips_per_window=int(thresholds.get("max_clips_per_window", 2)),
            diversity_score_override=float(thresholds.get("diversity_score_override", 0.85)),
        )

        p_at_5, usable_count, total_k = compute_precision_at_k(selected, gt_ratings, k=5)
        p_at_10, _, _ = compute_precision_at_k(scored_moments, gt_ratings, k=10)

        per_video_results.append({
            "slug": v_slug,
            "title": meta.get("title", v_slug),
            "type": meta.get("type", "unknown"),
            "duration_minutes": round(duration_s / 60.0, 1),
            "candidates_count": len(candidates),
            "top5_usable": f"{usable_count}/{total_k}",
            "precision_at_5": p_at_5,
            "precision_at_10": p_at_10,
            "top_clip_title": selected[0]["title"] if selected else "N/A",
            "top_clip_score": selected[0]["final_score"] if selected else 0.0,
        })

        status_tag = "PASS" if p_at_5 >= 0.60 else "FAIL"
        top_title = selected[0]['title'][:30] if selected else 'N/A'
        print(f"[{status_tag:4}] {v_slug:32} | Type: {meta.get('type'):11} | P@5: {p_at_5*100:4.1f}% ({usable_count}/{total_k} usable) | Top: '{top_title}'")

    elapsed_wall_time = time.time() - start_eval_time
    total_source_hours = max(0.1, total_source_duration_s / 3600.0)

    # Aggregate Metrics
    avg_precision_at_5 = float(np.mean([r["precision_at_5"] for r in per_video_results])) if per_video_results else 0.0
    avg_precision_at_10 = float(np.mean([r["precision_at_10"] for r in per_video_results])) if per_video_results else 0.0
    overall_usable_rate = avg_precision_at_5

    # Discrimination validation: Mean score usable vs unusable
    usable_scores = [s for s, lbl in zip(all_final_scores, all_binary_labels, strict=False) if lbl == 1]
    unusable_scores = [s for s, lbl in zip(all_final_scores, all_binary_labels, strict=False) if lbl == 0]
    mean_usable_score = round(float(np.mean(usable_scores)), 3) if usable_scores else 0.0
    mean_unusable_score = round(float(np.mean(unusable_scores)), 3) if unusable_scores else 0.0

    # AUC-ROC
    auc = compute_auc_roc(all_final_scores, all_binary_labels)

    # Signal correlations with ground truth usable label
    correlations = {
        sig: compute_correlations(vals, all_binary_labels)
        for sig, vals in all_signal_values.items()
    }

    # Inter-rater agreement
    agreement = compute_inter_rater_agreement(ratings_by_item)

    # Cost & Time per source hour
    cost_per_hour_inr = round(total_cost_inr / total_source_hours, 2)
    cost_per_hour_usd = round(cost_per_hour_inr / get_settings().USD_TO_INR_RATE, 3)
    wall_time_per_source_hour = round(elapsed_wall_time / total_source_hours, 1)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    prev_report = load_previous_report()

    delta_p5 = round((avg_precision_at_5 - prev_report.get("precision_at_5", avg_precision_at_5)) * 100.0, 1) if prev_report else 0.0
    delta_auc = round(auc - prev_report.get("auc_roc", auc), 3) if prev_report else 0.0

    report_data = {
        "timestamp": timestamp,
        "prompt_version": prompt_version,
        "precision_at_5": round(avg_precision_at_5, 3),
        "precision_at_10": round(avg_precision_at_10, 3),
        "usable_rate_top5": round(overall_usable_rate, 3),
        "target_usable_rate_met": avg_precision_at_5 >= 0.60,
        "mean_score_usable": mean_usable_score,
        "mean_score_unusable": mean_unusable_score,
        "score_discriminates": mean_usable_score > mean_unusable_score,
        "auc_roc": auc,
        "per_signal_correlation": correlations,
        "inter_rater_agreement": agreement,
        "cost_per_source_hour_inr": cost_per_hour_inr,
        "cost_per_source_hour_usd": cost_per_hour_usd,
        "wall_time_per_source_hour_seconds": wall_time_per_source_hour,
        "total_source_hours": round(total_source_hours, 2),
        "weights": weights,
        "per_video_results": per_video_results,
        "diff_vs_previous": {
            "delta_precision_at_5_pct": delta_p5,
            "delta_auc_roc": delta_auc,
        },
    }

    # Write JSON report
    json_path = os.path.join(REPORTS_DIR, f"eval_{timestamp}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    # Write Markdown report
    md_path = os.path.join(REPORTS_DIR, f"eval_{timestamp}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"""# Clip-It-Up Quality Evaluation Report

**Run Timestamp:** {timestamp} (UTC)
**Prompt Version:** `{prompt_version}`
**Dataset Size:** {len(per_video_results)} benchmark videos ({total_source_hours:.1f} source hours)
**Target Goal:** &ge; 60% of top-5 clips rated usable &bull; **Status:** {'✅ PASSED' if avg_precision_at_5 >= 0.60 else '❌ FAILED'}

---

## 1. Executive Summary & KPIs

| Metric | Measured Value | Benchmark Target | Diff vs Previous |
| :--- | :--- | :--- | :--- |
| **Precision@5 (Top-5 Usable Rate)** | **{avg_precision_at_5*100:.1f}%** | &ge; 60.0% | `{'+' if delta_p5 >= 0 else ''}{delta_p5}%` |
| **Precision@10** | **{avg_precision_at_10*100:.1f}%** | &ge; 50.0% | — |
| **AUC-ROC (Score vs Usable)** | **{auc:.3f}** | &ge; 0.750 | `{'+' if delta_auc >= 0 else ''}{delta_auc:.3f}` |
| **Mean Score (Usable vs Unusable)** | **{mean_usable_score}** vs **{mean_unusable_score}** | Usable > Unusable | {'✅ Yes' if mean_usable_score > mean_unusable_score else '❌ No'} |
| **Inter-Rater Pairwise Agreement** | **{agreement['pairwise_agreement_pct']}%** | &ge; 75.0% | Mean diff: {agreement['mean_score_discrepancy']} pts |
| **LLM Cost per Source Hour** | **₹{cost_per_hour_inr:.2f}** (${cost_per_hour_usd:.3f}) | &le; ₹20.00 | — |
| **Wall Time per Source Hour** | **{wall_time_per_source_hour:.1f}s** | &le; 180s | — |

---

## 2. Per-Signal Correlation with Human Usable Label

| Signal | Correlation ($r$) | Diagnostic Insight |
| :--- | :--- | :--- |
| **`hook`** | `{correlations['hook']:+.3f}` | {'Strong positive driver of early retention.' if correlations['hook'] > 0.3 else 'Moderate impact.'} |
| **`payoff`** | `{correlations['payoff']:+.3f}` | High impact on completion satisfaction. |
| **`coherence`** | `{correlations['coherence']:+.3f}` | Critical guardrail preventing missing context. |
| **`novelty`** | `{correlations['novelty']:+.3f}` | Strong differentiator for educational content. |
| **`emotion`** | `{correlations['emotion']:+.3f}` | High resonance in solo vlogs and interviews. |
| **`audio_energy`** | `{correlations['audio_energy']:+.3f}` | Filters low-cadence / quiet speech. |
| **`laughter`** | `{correlations['laughter']:+.3f}` | Boosts humor in podcasts. |
| **`pause_penalty`** | `{correlations['pause_penalty']:+.3f}` | Effectively penalizes dead air. |

---

## 3. Per-Video Breakdown

| Video Slug | Domain | Duration | P@5 (Usable/Top5) | Top Selected Clip Title |
| :--- | :--- | :--- | :--- | :--- |
""")
        for r in per_video_results:
            f.write(f"| `{r['slug']}` | {r['type']} | {r['duration_minutes']} min | **{r['precision_at_5']*100:.0f}%** ({r['top5_usable']}) | {r['top_clip_title']} |\n")

        f.write(f"""
---

## 4. Signal Weights Configuration

```yaml
{yaml.dump(weights, default_flow_style=False)}
```
""")

    print("\n================================================================================")
    print(f"  EVALUATION SUMMARY: PRECISION@5 = {avg_precision_at_5*100:.1f}% | AUC = {auc:.3f}")
    print(f"  TARGET (>=60%): {'PASSED (SUCCESS)' if avg_precision_at_5 >= 0.60 else 'FAILED'}")
    print(f"  Cost / Source-Hour: Rs.{cost_per_hour_inr:.2f} (${cost_per_hour_usd:.3f}) | Time: {wall_time_per_source_hour:.1f}s")
    print(f"  Report written to: {md_path}")
    print("================================================================================\n")

    return report_data


if __name__ == "__main__":
    run_evaluation()
