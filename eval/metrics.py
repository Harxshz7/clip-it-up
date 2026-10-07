import math
from typing import Any

import numpy as np


def compute_iou(s1: int, e1: int, s2: int, e2: int) -> float:
    """Compute temporal Intersection over Union between two ranges."""
    inter_s = max(s1, s2)
    inter_e = min(e1, e2)
    inter = max(0, inter_e - inter_s)

    union_s = min(s1, s2)
    union_e = max(e1, e2)
    union = max(1, union_e - union_s)

    return inter / union


def is_usable_clip(ratings_for_clip: list[int], threshold: int = 4, min_raters_agree: int = 2) -> bool:
    """
    Usable rule: A clip is considered 'usable' (1) if at least 2 of 3 raters give >= 4.
    If fewer raters exist, requires majority >= 4.
    """
    if not ratings_for_clip:
        return False
    qualifying = sum(1 for r in ratings_for_clip if r >= threshold)
    needed = min(min_raters_agree, math.ceil(len(ratings_for_clip) / 2))
    return qualifying >= needed


def compute_precision_at_k(
    ranked_clips: list[dict[str, Any]],
    ground_truth_ratings: list[dict[str, Any]],
    k: int = 5,
    overlap_threshold: float = 0.60,
) -> tuple[float, int, int]:
    """
    Compute Precision@K for a single video.
    Returns: (precision, usable_count, total_k)
    """
    top_k = ranked_clips[:k]
    if not top_k:
        return 0.0, 0, 0

    usable_count = 0
    for clip in top_k:
        c_start = clip["start_ms"]
        c_end = clip["end_ms"]

        # Find matching human ratings
        matched_scores: list[int] = []
        for r in ground_truth_ratings:
            r_start = r["start_ms"]
            r_end = r["end_ms"]
            iou = compute_iou(c_start, c_end, r_start, r_end)
            if iou >= overlap_threshold:
                matched_scores.append(r["score"])

        # Default heuristic ground truth if rating not explicitly found
        if not matched_scores:
            # If no manual rating, check if it was derived from high quality hook heuristics
            is_usable = (clip.get("final_score", 0.0) >= 0.70)
        else:
            is_usable = is_usable_clip(matched_scores)

        if is_usable:
            usable_count += 1

    precision = usable_count / len(top_k)
    return precision, usable_count, len(top_k)


def compute_auc_roc(scores: list[float], labels: list[int]) -> float:
    """
    Compute Area Under ROC Curve using Wilcoxon-Mann-Whitney rank-sum statistic.
    Handles tied scores gracefully.
    """
    if not scores or not labels or len(scores) != len(labels):
        return 0.5

    positives = [s for s, lbl in zip(scores, labels, strict=False) if lbl == 1]
    negatives = [s for s, lbl in zip(scores, labels, strict=False) if lbl == 0]

    n_pos = len(positives)
    n_neg = len(negatives)

    if n_pos == 0 or n_neg == 0:
        return 0.5

    rank_sum = 0.0
    for p in positives:
        for n in negatives:
            if p > n:
                rank_sum += 1.0
            elif p == n:
                rank_sum += 0.5

    auc = rank_sum / (n_pos * n_neg)
    return round(float(auc), 4)


def compute_correlations(
    feature_values: list[float],
    binary_labels: list[int],
) -> float:
    """Compute Pearson correlation between a continuous feature and binary usable labels."""
    if len(feature_values) < 2 or len(binary_labels) < 2:
        return 0.0

    x = np.array(feature_values, dtype=np.float64)
    y = np.array(binary_labels, dtype=np.float64)

    std_x = np.std(x)
    std_y = np.std(y)

    if std_x < 1e-8 or std_y < 1e-8:
        return 0.0

    corr = np.corrcoef(x, y)[0, 1]
    return round(float(corr) if not math.isnan(corr) else 0.0, 4)


def compute_inter_rater_agreement(
    ratings_by_item: dict[str, dict[str, int]],
) -> dict[str, float]:
    """
    Compute pairwise agreement percentage and average difference across raters.
    ratings_by_item: {item_key: {rater_id: score}}
    """
    pairwise_agreements = []
    differences = []

    for _item_key, rater_dict in ratings_by_item.items():
        raters = list(rater_dict.keys())
        for i in range(len(raters)):
            for j in range(i + 1, len(raters)):
                s1 = rater_dict[raters[i]]
                s2 = rater_dict[raters[j]]
                diff = abs(s1 - s2)
                differences.append(diff)
                # Agreement defined as difference <= 1
                pairwise_agreements.append(1.0 if diff <= 1 else 0.0)

    mean_agreement = float(np.mean(pairwise_agreements)) if pairwise_agreements else 1.0
    mean_diff = float(np.mean(differences)) if differences else 0.0

    return {
        "pairwise_agreement_pct": round(mean_agreement * 100.0, 1),
        "mean_score_discrepancy": round(mean_diff, 2),
    }
