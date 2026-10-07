import pytest
from eval.metrics import (
    is_usable_clip,
    compute_precision_at_k,
    compute_auc_roc,
    compute_correlations,
    compute_inter_rater_agreement,
)


def test_usable_clip_rule():
    # 2 of 3 raters give >= 4 -> Usable
    assert is_usable_clip([5, 4, 2]) is True
    assert is_usable_clip([4, 4, 3]) is True
    assert is_usable_clip([5, 5, 5]) is True

    # Less than 2 give >= 4 -> Not usable
    assert is_usable_clip([4, 3, 2]) is False
    assert is_usable_clip([3, 3, 3]) is False
    assert is_usable_clip([1, 2, 1]) is False


def test_compute_precision_at_k():
    ranked_clips = [
        {"start_ms": 10000, "end_ms": 40000, "final_score": 0.9},
        {"start_ms": 50000, "end_ms": 80000, "final_score": 0.8},
        {"start_ms": 90000, "end_ms": 120000, "final_score": 0.7},
    ]

    # Ground truth: first two are usable, third is not
    ratings = [
        {"start_ms": 10000, "end_ms": 40000, "score": 5},
        {"start_ms": 10000, "end_ms": 40000, "score": 4},
        {"start_ms": 50000, "end_ms": 80000, "score": 4},
        {"start_ms": 50000, "end_ms": 80000, "score": 4},
        {"start_ms": 90000, "end_ms": 120000, "score": 2},
        {"start_ms": 90000, "end_ms": 120000, "score": 2},
    ]

    p_at_3, usable_count, total = compute_precision_at_k(ranked_clips, ratings, k=3)
    assert usable_count == 2
    assert total == 3
    assert abs(p_at_3 - (2 / 3)) < 1e-4


def test_compute_auc_roc():
    # Perfect ranking
    scores_perfect = [0.95, 0.85, 0.75, 0.40, 0.20]
    labels_perfect = [1, 1, 1, 0, 0]
    assert compute_auc_roc(scores_perfect, labels_perfect) == 1.0

    # Inverted ranking
    scores_inv = [0.10, 0.20, 0.90]
    labels_inv = [1, 1, 0]
    assert compute_auc_roc(scores_inv, labels_inv) == 0.0


def test_compute_correlations_and_agreement():
    features = [0.9, 0.8, 0.3, 0.2]
    labels = [1, 1, 0, 0]
    corr = compute_correlations(features, labels)
    assert corr > 0.8

    ratings_by_item = {
        "item_1": {"r1": 5, "r2": 4, "r3": 5},
        "item_2": {"r1": 2, "r2": 2, "r3": 3},
    }
    agreement = compute_inter_rater_agreement(ratings_by_item)
    assert agreement["pairwise_agreement_pct"] == 100.0
