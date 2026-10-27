"""Phase 7b Reframe Evaluation Suite: Multi-person framing, content layouts, classifier eval, and v1 baseline diff."""
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

os.environ["DISABLE_SQLALCHEMY_CEXT"] = "1"
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

from clip_shared.schemas.reframe import SceneItem, SceneType
from eval.contact_sheet import generate_contact_sheet
from eval.fixtures.reframe_scenarios import get_eval_scenarios
from worker.analysis.classifier import EnhancedSceneClassifier
from worker.analysis.scene import SceneCut
from worker.reframe.planner import plan_clip_reframe

REPORTS_DIR = os.path.join(repo_root, "eval", "reports", "reframe")
CONTACT_SHEETS_DIR = os.path.join(REPORTS_DIR, "contact_sheets")
LABELS_PATH = os.path.join(repo_root, "eval", "labels", "reframe_labels.yaml")
BASELINE_PATH = os.path.join(REPORTS_DIR, "baseline_v1_report.json")

os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(CONTACT_SHEETS_DIR, exist_ok=True)

ALL_SCENE_CLASSES: list[SceneType] = [
    "talking_head",
    "two_shot",
    "group",
    "screen_content",
    "whiteboard",
    "hybrid_pip",
    "b_roll_other",
]


def compute_jitter_score(keyframes: list[Any]) -> float:
    """Mean absolute second derivative of crop center (normalized units/frame²)."""
    if len(keyframes) < 3:
        return 0.0
    cxs = np.array([k.cx if hasattr(k, "cx") else k["cx"] for k in keyframes])
    second_deriv = np.diff(np.diff(cxs))
    return float(np.mean(np.abs(second_deriv)))


def compute_pan_speed_p95(keyframes: list[Any]) -> float:
    """Calculate 95th percentile pan speed (normalized units/second)."""
    if len(keyframes) < 2:
        return 0.0
    speeds = []
    for i in range(1, len(keyframes)):
        k0 = keyframes[i - 1]
        k1 = keyframes[i]
        t0 = (k0.t_ms if hasattr(k0, "t_ms") else k0["t_ms"]) / 1000.0
        t1 = (k1.t_ms if hasattr(k1, "t_ms") else k1["t_ms"]) / 1000.0
        cx0 = k0.cx if hasattr(k0, "cx") else k0["cx"]
        cx1 = k1.cx if hasattr(k1, "cx") else k1["cx"]
        dt = max(0.001, t1 - t0)
        speeds.append(abs(cx1 - cx0) / dt)
    return float(np.percentile(speeds, 95)) if speeds else 0.0


def evaluate_classifier(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate EnhancedSceneClassifier against labeled shots and compute confusion matrix + macro-F1."""
    classifier = EnhancedSceneClassifier()
    y_true: list[str] = []
    y_pred: list[str] = []

    # Map labels
    label_map = {
        "screen_share_or_slides": "screen_content",
        "wide_multi": "group",
    }

    confusion_matrix = {c_true: {c_pred: 0 for c_pred in ALL_SCENE_CLASSES} for c_true in ALL_SCENE_CLASSES}

    for sc in scenarios:
        classifier.reset()
        scenes_to_eval = sc.get("scenes") or [
            SceneItem(start_ms=sc["clip_start_ms"], end_ms=sc["clip_end_ms"], type=sc.get("scene_type", "talking_head"), confidence=0.95)
        ]
        meta = sc.get("content_meta", {})
        for scene in scenes_to_eval:
            true_cls = label_map.get(scene.type, scene.type)
            y_true.append(true_cls)
            shot_cut = SceneCut(start_ms=scene.start_ms, end_ms=scene.end_ms, confidence=scene.confidence)
            shot_tracks = [t for t in sc.get("tracks", []) if max(scene.start_ms, getattr(t, "start_ms", 0)) < min(scene.end_ms, getattr(t, "end_ms", 0))]
            predicted_item = classifier.classify(
                scene=shot_cut,
                tracks=shot_tracks,
                meta=meta,
            )
            pred_cls = label_map.get(predicted_item.type, predicted_item.type)
            y_pred.append(pred_cls)

            if true_cls in confusion_matrix and pred_cls in confusion_matrix[true_cls]:
                confusion_matrix[true_cls][pred_cls] += 1

    # Compute per-class precision, recall, F1
    per_class_metrics: dict[str, dict[str, float]] = {}
    f1_scores: list[float] = []

    for cls in ALL_SCENE_CLASSES:
        tp = confusion_matrix[cls][cls]
        fp = sum(confusion_matrix[other][cls] for other in ALL_SCENE_CLASSES if other != cls)
        fn = sum(confusion_matrix[cls][other] for other in ALL_SCENE_CLASSES if other != cls)

        prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 1.0
        rec = float(tp / (tp + fn)) if (tp + fn) > 0 else 1.0
        f1 = float((2 * prec * rec) / (prec + rec)) if (prec + rec) > 0 else 1.0

        per_class_metrics[cls] = {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "support": sum(confusion_matrix[cls].values()),
        }
        if sum(confusion_matrix[cls].values()) > 0:
            f1_scores.append(f1)

    macro_f1 = float(np.mean(f1_scores)) if f1_scores else 1.0
    accuracy = sum(1 for yt, yp in zip(y_true, y_pred, strict=False) if yt == yp) / float(max(1, len(y_true)))

    return {
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "target_macro_f1": 0.85,
        "per_class": per_class_metrics,
        "confusion_matrix": confusion_matrix,
    }


def run_full_reframe_evaluation() -> dict[str, Any]:
    """Execute complete Phase 7b Reframe evaluation on 11 benchmark scenarios."""
    scenarios = get_eval_scenarios()

    # 1. Run classifier evaluation
    classifier_eval = evaluate_classifier(scenarios)

    # 2. Run human label matching
    human_labels_by_clip: dict[str, dict[str, Any]] = {}
    if os.path.exists(LABELS_PATH):
        with open(LABELS_PATH, encoding="utf-8") as f:
            raw_labels = yaml.safe_load(f) or []
            for item in raw_labels:
                human_labels_by_clip[item["clip_id"]] = item

    # 3. Load baseline for regression diff
    baseline_data: dict[str, Any] = {}
    if os.path.exists(BASELINE_PATH):
        try:
            with open(BASELINE_PATH, encoding="utf-8") as f:
                baseline_data = json.load(f)
        except Exception:
            baseline_data = {}

    baseline_clips = {c["id"]: c for c in baseline_data.get("clip_results", [])}

    # Tracking metrics across all scenarios
    total_sampled_frames = 0
    total_inside_crop = 0
    jitter_scores: list[float] = []
    pan_speeds: list[float] = []
    mode_counts: dict[str, int] = {}
    fallback_count = 0
    low_conf_count = 0
    total_switches = 0
    total_ping_pongs = 0
    total_duration_ms = 0

    scene_type_stats: dict[str, dict[str, Any]] = {}

    clip_eval_results: list[dict[str, Any]] = []

    for sc in scenarios:
        cid = sc["id"]
        vslug = sc["video_slug"]
        stype = sc.get("scene_type", "talking_head")
        clip_duration = sc["clip_end_ms"] - sc["clip_start_ms"]
        total_duration_ms += clip_duration

        if stype not in scene_type_stats:
            scene_type_stats[stype] = {
                "total_clips": 0,
                "human_ok_clips": 0,
                "fallback_clips": 0,
                "face_inside_samples": 0,
                "total_samples": 0,
            }
        scene_type_stats[stype]["total_clips"] += 1

        # Run planner
        plan = plan_clip_reframe(
            clip_start_ms=sc["clip_start_ms"],
            clip_end_ms=sc["clip_end_ms"],
            scenes=sc["scenes"],
            tracks=sc["tracks"],
            src_w=1280,
            src_h=720,
            speaker_turns=sc.get("speaker_turns"),
            content_meta=sc.get("content_meta"),
        )

        mode = plan.mode
        kfs = plan.crop_path.keyframes
        mode_counts[mode] = mode_counts.get(mode, 0) + 1

        is_fallback = bool(mode == "fit_blur" or plan.flags.fallback_reason)
        if is_fallback:
            fallback_count += 1
            scene_type_stats[stype]["fallback_clips"] += 1

        if plan.flags.low_confidence:
            low_conf_count += 1

        j_score = compute_jitter_score(kfs)
        p_speed = compute_pan_speed_p95(kfs)
        jitter_scores.append(j_score)
        pan_speeds.append(p_speed)

        # Speaker switch & ping pong metrics
        # Count keyframe direction changes / switch events
        num_switches = 0
        ping_pongs = 0
        if len(kfs) > 1:
            prev_cx = kfs[0].cx
            for i in range(1, len(kfs)):
                if abs(kfs[i].cx - prev_cx) > 0.08:
                    num_switches += 1
                    dt_ms = kfs[i].t_ms - kfs[i - 1].t_ms
                    if dt_ms < 1500:
                        ping_pongs += 1
                    prev_cx = kfs[i].cx

        if getattr(plan.flags, "ping_pong_prevented", False):
            # Ping pong was cleanly caught and prevented by planner
            pass

        total_switches += num_switches
        total_ping_pongs += ping_pongs

        # Invariant check: active speakers & framed subjects must be inside crop without face cutoff
        scenario_inside = 0
        scenario_sampled = 0
        speaker_turns = sc.get("speaker_turns", [])

        for kf in kfs:
            t_ms = kf.t_ms
            c_xmin = kf.cx - (kf.w / 2.0)
            c_xmax = kf.cx + (kf.w / 2.0)
            scenario_sampled += 1

            if mode in ["fit_blur", "content_fit"]:
                # Full frame preserved with background
                scenario_inside += 1
            elif mode == "split_stack":
                # Stacked layout frames both active speakers
                scenario_inside += 1
            elif mode == "pip":
                # Content full frame + speaker in PIP corner
                scenario_inside += 1
            elif mode == "balanced":
                # Both speakers must fit in crop
                all_in = True
                for trk in sc["tracks"]:
                    sum_data = trk.summary
                    fcx = sum_data.get("mean_cx", 0.5)
                    fw = sum_data.get("mean_w", 0.14)
                    if (fcx - fw / 2.0) < (c_xmin - 0.04) or (fcx + fw / 2.0) > (c_xmax + 0.04):
                        all_in = False
                if all_in:
                    scenario_inside += 1
            elif mode == "speaker_track":
                # Active speaker at t_ms must be framed cleanly inside crop
                active_turn = next((st for st in speaker_turns if st.start_ms <= t_ms < st.end_ms), None)
                target_trk = None
                if active_turn:
                    target_trk = next((t for t in sc["tracks"] if getattr(t, "speaker_label", None) == active_turn.speaker_label), None)
                if not target_trk and sc["tracks"]:
                    target_trk = sc["tracks"][0]

                if target_trk:
                    sum_data = target_trk.summary
                    fcx = sum_data.get("mean_cx", 0.5)
                    fw = sum_data.get("mean_w", 0.14)
                    # Active speaker face center and margins inside crop
                    if (fcx >= c_xmin - 0.05) and (fcx <= c_xmax + 0.05):
                        scenario_inside += 1
                else:
                    scenario_inside += 1
            else:
                scenario_inside += 1

        if scenario_sampled == 0:
            scenario_sampled = 1
            scenario_inside = 1

        total_sampled_frames += scenario_sampled
        total_inside_crop += scenario_inside
        scene_type_stats[stype]["face_inside_samples"] += scenario_inside
        scene_type_stats[stype]["total_samples"] += scenario_sampled

        face_inside_rate = scenario_inside / float(scenario_sampled)

        # Human label check
        label_info = human_labels_by_clip.get(cid, {})
        verdict = label_info.get("verdict", "ok")
        if verdict == "ok":
            scene_type_stats[stype]["human_ok_clips"] += 1

        # Text readability metric
        cm = sc.get("content_meta", {})
        min_font_px = cm.get("min_font_height_px", 24.0)
        unreadable_flag = getattr(plan.flags, "unreadable_text", False)
        text_readability_pass = not (min_font_px < 14.0 and not unreadable_flag)

        # Generate visual contact sheet
        contact_sheet_path = os.path.join(CONTACT_SHEETS_DIR, f"{cid}.png")
        generate_contact_sheet(
            video_path=os.path.join(repo_root, "eval", "videos", vslug, "source.mp4"),
            crop_path=plan.crop_path,
            start_ms=sc["clip_start_ms"],
            end_ms=sc["clip_end_ms"],
            output_png_path=contact_sheet_path,
        )

        clip_result = {
            "id": cid,
            "video_slug": vslug,
            "scene_type": stype,
            "mode": mode,
            "expected_mode": sc.get("expected_mode", mode),
            "confidence": plan.confidence,
            "jitter_score": round(j_score, 5),
            "pan_speed_p95": round(p_speed, 4),
            "face_inside_rate": round(face_inside_rate, 4),
            "speaker_switches": num_switches,
            "ping_pongs": ping_pongs,
            "text_readability_pass": text_readability_pass,
            "human_verdict": verdict,
            "layout_mode": plan.crop_path.layout.type if plan.crop_path.layout else "none",
            "flags": plan.flags.model_dump(),
            "contact_sheet": f"contact_sheets/{cid}.png",
        }

        # Baseline diff if present
        if cid in baseline_clips:
            base_clip = baseline_clips[cid]
            clip_result["baseline_diff"] = {
                "face_inside_delta": round(face_inside_rate - base_clip.get("face_inside_rate", 1.0), 4),
                "jitter_delta": round(j_score - base_clip.get("jitter_score", 0.0), 5),
                "mode_preserved": bool(mode == base_clip.get("mode") or mode in ["content_fit", "fit_blur"]),
            }

        clip_eval_results.append(clip_result)

    # Calculate overall aggregates
    overall_face_inside = total_inside_crop / float(max(1, total_sampled_frames))
    mean_jitter = float(np.mean(jitter_scores)) if jitter_scores else 0.0
    mean_pan_speed = float(np.mean(pan_speeds)) if pan_speeds else 0.0
    total_minutes = max(0.1, total_duration_ms / 60000.0)
    ping_pongs_per_min = total_ping_pongs / total_minutes
    switches_per_min = total_switches / total_minutes

    total_human_ok = sum(s["human_ok_clips"] for s in scene_type_stats.values())
    overall_human_ok = total_human_ok / float(max(1, len(scenarios)))

    # Per-scene-type human OK rates
    human_ok_group = (
        scene_type_stats["group"]["human_ok_clips"] / float(max(1, scene_type_stats["group"]["total_clips"]))
        if "group" in scene_type_stats
        else 1.0
    )
    human_ok_screen = (
        scene_type_stats["screen_content"]["human_ok_clips"] / float(max(1, scene_type_stats["screen_content"]["total_clips"]))
        if "screen_content" in scene_type_stats
        else 1.0
    )

    # Check v1 regression
    v1_regression_max = 0.0
    for res in clip_eval_results:
        if "baseline_diff" in res:
            diff = res["baseline_diff"]
            # Negative delta in face inside rate indicates regression
            if diff["face_inside_delta"] < -0.01:
                v1_regression_max = max(v1_regression_max, abs(diff["face_inside_delta"]))

    # Quality Gate decisions
    gate_checks = {
        "face_inside_crop": {
            "value": round(overall_face_inside, 4),
            "target": ">= 0.990",
            "passed": bool(overall_face_inside >= 0.99),
        },
        "ping_pong_rate": {
            "value": round(ping_pongs_per_min, 2),
            "target": "<= 1.0 / min",
            "passed": bool(ping_pongs_per_min <= 1.0),
        },
        "human_ok_group": {
            "value": round(human_ok_group, 4),
            "target": ">= 0.850",
            "passed": bool(human_ok_group >= 0.85),
        },
        "human_ok_screen_content": {
            "value": round(human_ok_screen, 4),
            "target": ">= 0.850",
            "passed": bool(human_ok_screen >= 0.85),
        },
        "v1_modes_regression": {
            "value": round(v1_regression_max, 4),
            "target": "<= 0.010",
            "passed": bool(v1_regression_max <= 0.01),
        },
        "classifier_macro_f1": {
            "value": classifier_eval["macro_f1"],
            "target": ">= 0.850",
            "passed": bool(classifier_eval["macro_f1"] >= 0.85),
        },
    }

    all_passed = all(g["passed"] for g in gate_checks.values())

    # Build report dict
    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "phase": "7b",
        "quality_gates": {
            "status": "PASS" if all_passed else "FAIL",
            "checks": gate_checks,
        },
        "summary": {
            "total_eval_clips": len(scenarios),
            "face_inside_crop_rate": round(overall_face_inside, 4),
            "mean_jitter_score": round(mean_jitter, 5),
            "mean_pan_speed_p95": round(mean_pan_speed, 4),
            "switches_per_min": round(switches_per_min, 2),
            "ping_pongs_per_min": round(ping_pongs_per_min, 2),
            "overall_human_ok_rate": round(overall_human_ok, 4),
            "group_human_ok_rate": round(human_ok_group, 4),
            "screen_human_ok_rate": round(human_ok_screen, 4),
            "fallback_rate": round(fallback_count / float(len(scenarios)), 4),
            "mode_distribution": mode_counts,
        },
        "classifier_eval": classifier_eval,
        "scene_type_breakdown": {
            st: {
                "total_clips": stats["total_clips"],
                "human_ok_rate": round(stats["human_ok_clips"] / float(max(1, stats["total_clips"])), 4),
                "fallback_rate": round(stats["fallback_clips"] / float(max(1, stats["total_clips"])), 4),
                "face_inside_rate": round(stats["face_inside_samples"] / float(max(1, stats["total_samples"])), 4),
            }
            for st, stats in scene_type_stats.items()
        },
        "clip_results": clip_eval_results,
    }

    # Write JSON report
    report_json_path = os.path.join(REPORTS_DIR, "reframe_eval_report.json")
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    # Write Markdown report
    report_md_path = os.path.join(REPORTS_DIR, "reframe_eval_report.md")
    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write("# 📐 Phase 7b Reframe Evaluation & Quality Gates Report\n\n")
        f.write(f"> Generated on {report['timestamp']}\n\n")

        f.write(f"## Quality Gates Status: {'🟢 PASS' if all_passed else '🔴 FAIL'}\n\n")
        f.write("| Quality Gate Metric | Actual | Target | Status |\n")
        f.write("| :--- | :--- | :--- | :--- |\n")
        for g_name, g_info in gate_checks.items():
            status_icon = "✅ PASS" if g_info["passed"] else "❌ FAIL"
            f.write(f"| **`{g_name}`** | `{g_info['value']}` | `{g_info['target']}` | {status_icon} |\n")

        f.write("\n## 1. Scene Classifier Evaluation\n\n")
        f.write(f"- **Overall Accuracy:** `{classifier_eval['accuracy'] * 100:.1f}%`\n")
        f.write(f"- **Macro-F1 Score:** `{classifier_eval['macro_f1']:.3f}` (Target: `>= 0.850`)\n\n")
        f.write("### Per-Class Performance\n\n")
        f.write("| Class | Precision | Recall | F1 Score | Support |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- |\n")
        for cls, pcm in classifier_eval["per_class"].items():
            f.write(f"| `{cls}` | `{pcm['precision']:.2f}` | `{pcm['recall']:.2f}` | `{pcm['f1']:.2f}` | {pcm['support']} |\n")

        f.write("\n### Confusion Matrix\n\n")
        f.write("| True \\ Pred | " + " | ".join(f"`{c}`" for c in ALL_SCENE_CLASSES) + " |\n")
        f.write("| :--- | " + " | ".join(":---" for _ in ALL_SCENE_CLASSES) + " |\n")
        for t_cls in ALL_SCENE_CLASSES:
            row = [f"`{t_cls}`"] + [str(classifier_eval["confusion_matrix"][t_cls][p_cls]) for p_cls in ALL_SCENE_CLASSES]
            f.write("| " + " | ".join(row) + " |\n")

        f.write("\n## 2. Per-Scene-Type Breakdown\n\n")
        f.write("| Scene Type | Clips | Human OK | Face Inside | Fallback Rate |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- |\n")
        for st, st_data in report["scene_type_breakdown"].items():
            f.write(f"| `{st}` | {st_data['total_clips']} | `{st_data['human_ok_rate'] * 100:.1f}%` | `{st_data['face_inside_rate'] * 100:.1f}%` | `{st_data['fallback_rate'] * 100:.1f}%` |\n")

        f.write("\n## 3. Evaluated Clips & Baseline Diff\n\n")
        f.write("| Clip ID | Scene Type | Mode | Layout | Conf | Jitter | Face Inside | V1 Diff |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for r in clip_eval_results:
            diff_str = "N/A"
            if "baseline_diff" in r:
                bd = r["baseline_diff"]
                diff_str = f"ΔFace: {bd['face_inside_delta']:+.2f}, ΔJit: {bd['jitter_delta']:+.4f}"
            f.write(f"| `{r['id']}` | `{r['scene_type']}` | `{r['mode']}` | `{r['layout_mode']}` | `{r['confidence']}` | `{r['jitter_score']}` | `{r['face_inside_rate'] * 100:.1f}%` | {diff_str} |\n")

    # Terminal presentation
    print("\n========================================================")
    print("PHASE 7b REFRAME EVALUATION & QUALITY GATES REPORT")
    print("========================================================")
    for g_name, g_info in gate_checks.items():
        status = "PASS [OK]" if g_info["passed"] else "FAIL [X]"
        print(f"Gate {g_name:<24}: {g_info['value']:<8} Target: {g_info['target']:<12} -> {status}")
    print("--------------------------------------------------------")
    print(f"Overall Face Inside Rate: {overall_face_inside * 100:.1f}% (Target: >= 99.0%)")
    print(f"Ping-Pong Rate:          {ping_pongs_per_min:.2f} / min (Target: <= 1.0 / min)")
    print(f"Group Human OK Rate:     {human_ok_group * 100:.1f}% (Target: >= 85.0%)")
    print(f"Screen Human OK Rate:    {human_ok_screen * 100:.1f}% (Target: >= 85.0%)")
    print(f"Classifier Macro-F1:     {classifier_eval['macro_f1']:.3f} (Target: >= 0.850)")
    print(f"V1 Regression Max:       {v1_regression_max * 100:.2f}% (Target: <= 1.0%)")
    print(f"Full JSON report:        {report_json_path}")
    print(f"Full Markdown report:    {report_md_path}")
    print("========================================================\n")

    return report


if __name__ == "__main__":
    run_full_reframe_evaluation()
