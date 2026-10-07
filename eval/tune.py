import copy
import os
import sys

import yaml

# Ensure project packages on python path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in [
    os.path.join(repo_root, "packages", "shared-py", "src"),
    os.path.join(repo_root, "apps", "api", "src"),
    os.path.join(repo_root, "apps", "worker", "src"),
    repo_root,
]:
    if p not in sys.path:
        sys.path.insert(0, p)

from clip_shared.config import load_scoring_weights  # noqa: E402
from eval.run import run_evaluation  # noqa: E402

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))


def tune_weights(iterations: int = 15) -> tuple[dict[str, float], float, float]:
    """
    Coordinate search over signal weights to maximize Precision@5 on rated eval dataset.
    Does not auto-apply; outputs a candidate YAML file for human review.
    """
    base_config = load_scoring_weights()
    current_weights = copy.deepcopy(base_config.get("weights", {}))

    print("\n================================================================================")
    print("  CLIP-IT-UP WEIGHT TUNING HELPER (COORDINATE SEARCH)")
    print("================================================================================\n")

    # Evaluate baseline
    print("Evaluating baseline weights configuration...")
    base_eval = run_evaluation(custom_weights=current_weights)
    best_p5 = base_eval["precision_at_5"]
    best_auc = base_eval["auc_roc"]
    best_weights = copy.deepcopy(current_weights)

    print(f"Baseline Precision@5: {best_p5*100:.1f}% | AUC: {best_auc:.3f}\n")
    print("Starting coordinate optimization iterations...")

    param_grid = {
        "hook": [0.20, 0.25, 0.30, 0.35, 0.40],
        "payoff": [0.15, 0.20, 0.25, 0.30],
        "coherence": [0.15, 0.20, 0.25],
        "emotion": [0.10, 0.15, 0.20],
        "novelty": [0.05, 0.10, 0.15],
        "audio_energy": [0.05, 0.10, 0.15],
        "laughter": [0.00, 0.05, 0.10],
        "pause_penalty": [0.10, 0.15, 0.20],
        "flag_penalty": [0.20, 0.30, 0.40],
    }

    for param, values in param_grid.items():
        for val in values:
            candidate_weights = copy.deepcopy(best_weights)
            candidate_weights[param] = val

            # Fast eval run
            eval_res = run_evaluation(custom_weights=candidate_weights)
            cand_p5 = eval_res["precision_at_5"]
            cand_auc = eval_res["auc_roc"]

            if cand_p5 > best_p5 or (cand_p5 == best_p5 and cand_auc > best_auc):
                print(f"  [IMPROVEMENT] {param}: {best_weights[param]} -> {val} | P@5: {cand_p5*100:.1f}% | AUC: {cand_auc:.3f}")
                best_p5 = cand_p5
                best_auc = cand_auc
                best_weights = candidate_weights

    gain_pct = round((best_p5 - base_eval["precision_at_5"]) * 100.0, 1)

    # Output candidate YAML to eval/tuned_weights.yaml
    output_yaml_path = os.path.join(EVAL_DIR, "tuned_weights.yaml")
    output_payload = {
        "version": "v1_tuned",
        "precision_at_5": best_p5,
        "auc_roc": best_auc,
        "gain_precision_at_5_pct": gain_pct,
        "weights": best_weights,
        "thresholds": base_config.get("thresholds", {}),
        "hook_energy_boost": base_config.get("hook_energy_boost", 0.15),
    }

    with open(output_yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(output_payload, f, default_flow_style=False)

    print("\n================================================================================")
    print(f"  TUNING FINISHED: Optimal Precision@5 = {best_p5*100:.1f}% (Gain: +{gain_pct}%)")
    print(f"  Optimized AUC = {best_auc:.3f}")
    print(f"  Candidate configuration saved to: {output_yaml_path}")
    print("================================================================================\n")

    return best_weights, best_p5, gain_pct


if __name__ == "__main__":
    tune_weights()
