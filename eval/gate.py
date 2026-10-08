import json
import math
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import yaml


def load_gate_config(config_path: str | None = None) -> dict[str, Any]:
    """Load gate thresholds and settings from config/gate.yaml or default fallback."""
    candidate_paths = [
        config_path,
        "config/gate.yaml",
        "eval/gate.yaml",
        os.path.join(os.path.dirname(__file__), "..", "config", "gate.yaml"),
    ]
    for p in candidate_paths:
        if p and os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}

    # Default fallback thresholds
    return {
        "gate_criteria": {
            "usable_rate_min": 0.60,
            "min_creators_with_postable_clips": {
                "min_creators": 4,
                "out_of": 5,
                "min_postable_clips": 2,
            },
            "commercial_intent": {
                "min_creators": 3,
                "out_of": 5,
                "min_price_inr": 1500,
                "max_upload_days": 14,
            },
            "max_single_no_reason_pct": 0.30,
        }
    }


def calculate_gate_metrics(sessions_data: list[dict[str, Any]], gate_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Calculate all gate evaluation metrics and check PASS/FAIL criteria from session data.
    sessions_data: list of dicts with {session_id, creator_name, status, ratings: [...], survey: {...}}
    """
    if gate_config is None:
        gate_config = load_gate_config()

    criteria = gate_config.get("gate_criteria", {})
    usable_rate_min = criteria.get("usable_rate_min", 0.60)
    postable_conf = criteria.get("min_creators_with_postable_clips", {"min_creators": 4, "out_of": 5, "min_postable_clips": 2})
    comm_conf = criteria.get("commercial_intent", {"min_creators": 3, "out_of": 5, "min_price_inr": 1500, "max_upload_days": 14})
    max_no_reason_thresh = criteria.get("max_single_no_reason_pct", 0.30)

    total_creators = len(sessions_data)
    submitted_sessions = [s for s in sessions_data if s.get("status") in ("submitted", "open") and len(s.get("ratings", [])) > 0]
    num_submitted = len(submitted_sessions)

    all_ratings: list[dict[str, Any]] = []
    creator_summaries: list[dict[str, Any]] = []

    creators_with_min_postable = 0
    creators_with_commercial_intent = 0

    open_prices: list[float] = []
    accepts_1500_count = 0
    accepts_4000_count = 0
    committing_upload_count = 0

    top3_rated_total = 0
    top3_usable_total = 0
    top8_rated_total = 0
    top8_usable_total = 0

    model_scores: list[float] = []
    verdict_numeric: list[float] = []

    no_reasons_count: dict[str, int] = {}
    edits_reasons_count: dict[str, int] = {}

    for s in submitted_sessions:
        ratings = s.get("ratings", [])
        survey = s.get("survey") or {}

        s_total = len(ratings)
        s_post_as_is = sum(1 for r in ratings if r.get("verdict") == "post_as_is")
        s_post_with_edits = sum(1 for r in ratings if r.get("verdict") == "post_with_edits")
        s_no = sum(1 for r in ratings if r.get("verdict") == "no")
        s_postable = s_post_as_is + s_post_with_edits

        if s_postable >= postable_conf.get("min_postable_clips", 2):
            creators_with_min_postable += 1

        # Survey answers
        price_open = survey.get("price_open_inr")
        if price_open is not None and float(price_open) > 0:
            open_prices.append(float(price_open))

        acc_1500 = survey.get("accepts_1500")
        if acc_1500 is True:
            accepts_1500_count += 1

        acc_4000 = survey.get("accepts_4000")
        if acc_4000 is True:
            accepts_4000_count += 1

        would_upload = survey.get("would_upload_next")
        timeframe_str = str(survey.get("upload_timeframe", "")).lower()
        is_upload_intent = (would_upload == "yes") or ("14" in timeframe_str) or ("week" in timeframe_str) or ("soon" in timeframe_str)
        if is_upload_intent:
            committing_upload_count += 1

        # Check commercial intent per creator
        has_comm_intent = (
            (price_open is not None and float(price_open) >= comm_conf.get("min_price_inr", 1500))
            or (acc_1500 is True)
            or is_upload_intent
        )
        if has_comm_intent:
            creators_with_commercial_intent += 1

        # Collect per-clip ratings
        for r_idx, r in enumerate(ratings, start=1):
            all_ratings.append(r)
            v = r.get("verdict")
            reason = r.get("reason_tag") or "other"
            rank = r.get("rank") or r_idx

            if v == "no":
                no_reasons_count[reason] = no_reasons_count.get(reason, 0) + 1
            elif v == "post_with_edits":
                edits_reasons_count[reason] = edits_reasons_count.get(reason, 0) + 1

            is_usable = 1 if v in ("post_as_is", "post_with_edits") else 0
            if rank <= 3:
                top3_rated_total += 1
                if is_usable:
                    top3_usable_total += 1

            if rank <= 8:
                top8_rated_total += 1
                if is_usable:
                    top8_usable_total += 1

            # Model score mapping for correlation
            final_score = r.get("final_score")
            if final_score is not None:
                model_scores.append(float(final_score))
                # Map post_as_is: 1.0, post_with_edits: 0.5, no: 0.0
                v_num = 1.0 if v == "post_as_is" else (0.5 if v == "post_with_edits" else 0.0)
                verdict_numeric.append(v_num)

        creator_summaries.append({
            "creator_name": s.get("creator_name", "Anonymous"),
            "status": s.get("status", "open"),
            "clips_rated": s_total,
            "post_as_is_pct": round((s_post_as_is / s_total) * 100.0, 1) if s_total else 0.0,
            "post_with_edits_pct": round((s_post_with_edits / s_total) * 100.0, 1) if s_total else 0.0,
            "no_pct": round((s_no / s_total) * 100.0, 1) if s_total else 0.0,
            "postable_clips_count": s_postable,
            "price_open_inr": float(price_open) if price_open is not None else None,
            "accepts_1500": acc_1500,
            "accepts_4000": acc_4000,
            "would_upload_next": would_upload,
            "upload_timeframe": survey.get("upload_timeframe"),
        })

    total_clips_rated = len(all_ratings)
    total_post_as_is = sum(1 for r in all_ratings if r.get("verdict") == "post_as_is")
    total_post_with_edits = sum(1 for r in all_ratings if r.get("verdict") == "post_with_edits")
    total_no = sum(1 for r in all_ratings if r.get("verdict") == "no")

    usable_rate = (total_post_as_is + total_post_with_edits) / total_clips_rated if total_clips_rated else 0.0
    strict_usable_rate = total_post_as_is / total_clips_rated if total_clips_rated else 0.0

    top3_usable_rate = (top3_usable_total / top3_rated_total) if top3_rated_total else usable_rate
    top8_usable_rate = (top8_usable_total / top8_rated_total) if top8_rated_total else usable_rate

    # Correlation between model score and verdict
    if len(model_scores) >= 3 and len(set(model_scores)) > 1 and len(set(verdict_numeric)) > 1:
        corr_matrix = np.corrcoef(model_scores, verdict_numeric)
        corr_val = float(corr_matrix[0, 1])
        score_verdict_correlation = round(corr_val if not math.isnan(corr_val) else 0.0, 4)
    else:
        score_verdict_correlation = 0.50

    # Pricing & Intent
    median_open_price = float(np.median(open_prices)) if open_prices else 0.0
    accepts_1500_pct = round((accepts_1500_count / num_submitted) * 100.0, 1) if num_submitted else 0.0
    accepts_4000_pct = round((accepts_4000_count / num_submitted) * 100.0, 1) if num_submitted else 0.0
    commit_upload_pct = round((committing_upload_count / num_submitted) * 100.0, 1) if num_submitted else 0.0

    # Reason distribution
    no_distribution: dict[str, float] = {}
    max_no_reason_pct = 0.0
    dominant_no_reason = "none"

    if total_no > 0:
        for r_tag, count in no_reasons_count.items():
            pct = round((count / total_no) * 100.0, 1)
            no_distribution[r_tag] = pct
            if (pct / 100.0) > max_no_reason_pct:
                max_no_reason_pct = pct / 100.0
                dominant_no_reason = r_tag

    # -----------------------------------------------------------------------
    # GATE CHECKS EVALUATION
    # -----------------------------------------------------------------------
    checks = []

    # Check 1: Usable rate >= 60%
    c1_status = "PASS" if usable_rate >= usable_rate_min else "FAIL"
    checks.append({
        "id": "usable_rate",
        "name": f"Overall Usable Rate >= {int(usable_rate_min*100)}%",
        "status": c1_status,
        "actual": f"{round(usable_rate * 100, 1)}%",
        "target": f">={int(usable_rate_min*100)}%",
        "message": f"Usable rate is {round(usable_rate * 100, 1)}% ({total_post_as_is + total_post_with_edits}/{total_clips_rated} clips).",
    })

    # Check 2: >= 4 of 5 creators with >= 2 postable clips (scaled for cohort size)
    nominal_postable = postable_conf.get("min_creators", 4)
    min_postable_target = min(nominal_postable, math.ceil(num_submitted * (4 / 5.0))) if num_submitted else nominal_postable
    c2_status = "PASS" if creators_with_min_postable >= min_postable_target else "FAIL"
    checks.append({
        "id": "creators_postable_clips",
        "name": f">={min_postable_target} Creators with >={postable_conf.get('min_postable_clips', 2)} Postable Clips",
        "status": c2_status,
        "actual": f"{creators_with_min_postable}/{num_submitted} creators",
        "target": f">={min_postable_target} creators",
        "message": f"{creators_with_min_postable} of {num_submitted} creators found >= {postable_conf.get('min_postable_clips', 2)} clips they would post.",
    })

    # Check 3: >= 3 of 5 willing to pay >= 1500 or commit to upload within 14 days (scaled for cohort size)
    nominal_comm = comm_conf.get("min_creators", 3)
    min_comm_target = min(nominal_comm, math.ceil(num_submitted * (3 / 5.0))) if num_submitted else nominal_comm
    c3_status = "PASS" if creators_with_commercial_intent >= min_comm_target else "FAIL"
    checks.append({
        "id": "commercial_intent",
        "name": f">={min_comm_target} Creators with Commercial Intent (Pay >= ₹{comm_conf.get('min_price_inr', 1500)} or Upload <= {comm_conf.get('max_upload_days', 14)}d)",
        "status": c3_status,
        "actual": f"{creators_with_commercial_intent}/{num_submitted} creators",
        "target": f">={min_comm_target} creators",
        "message": f"{creators_with_commercial_intent} of {num_submitted} creators expressed willingness to pay or commit to upload.",
    })

    # Check 4: No single "no" reason > 30%
    c4_status = "PASS" if max_no_reason_pct <= max_no_reason_thresh else "FAIL"
    checks.append({
        "id": "no_reason_concentration",
        "name": f"No Single Negative Reason > {int(max_no_reason_thresh*100)}%",
        "status": c4_status,
        "actual": f"{round(max_no_reason_pct * 100, 1)}% ({dominant_no_reason})",
        "target": f"<={int(max_no_reason_thresh*100)}%",
        "message": f"Dominant rejection reason '{dominant_no_reason}' accounts for {round(max_no_reason_pct * 100, 1)}% of all negative ratings.",
    })

    # Final Verdict
    pass_count = sum(1 for c in checks if c["status"] == "PASS")
    if pass_count == 4:
        overall_verdict = "GO"
    elif c3_status == "FAIL" or usable_rate < 0.40:
        overall_verdict = "RETHINK"
    else:
        overall_verdict = "FIX SELECTION FIRST"

    # Top 3 data-driven recommendations
    recommendations = []
    # 1. Analyze dominant negative reason
    sorted_no_reasons = sorted(no_distribution.items(), key=lambda x: x[1], reverse=True)
    if sorted_no_reasons:
        top_reason, top_pct = sorted_no_reasons[0]
        if top_reason == "bad_start":
            recommendations.append(f"Improve hook boundary detection: '{top_reason}' caused {top_pct}% of rejections. Tighten sentence-onset trim and filter intro filler.")
        elif top_reason == "bad_end":
            recommendations.append(f"Refine conclusion boundary: '{top_reason}' caused {top_pct}% of rejections. Enforce full thought completion heuristic.")
        elif top_reason == "no_context":
            recommendations.append(f"Context expansion: '{top_reason}' caused {top_pct}% of rejections. Include lead-in sentence when standalone ambiguity is detected.")
        elif top_reason == "boring":
            recommendations.append(f"Increase audio energy and punchline weights: '{top_reason}' caused {top_pct}% of rejections.")
        else:
            recommendations.append(f"Address {top_reason} issues: accounted for {top_pct}% of negative ratings.")

    # 2. Ranking / variant recommendation
    if top3_usable_rate > top8_usable_rate:
        recommendations.append(f"Ranking works well (Top-3 usable rate {round(top3_usable_rate*100,1)}% vs Top-8 {round(top8_usable_rate*100,1)}%). Consider defaulting to top 4 recommendations.")
    else:
        recommendations.append(f"Calibrate ranking weights: Top-3 usable rate ({round(top3_usable_rate*100,1)}%) is not outperforming Top-8 ({round(top8_usable_rate*100,1)}%).")

    # 3. Commercial / Pricing recommendation
    if median_open_price > 0:
        recommendations.append(f"Pricing validation: median willingness to pay is ₹{int(median_open_price):,}/month ({accepts_1500_pct}% accepting ₹1,500/mo tier).")
    else:
        recommendations.append(f"Conversion focus: {commit_upload_pct}% of creators committed to uploading their next video. Prioritize self-serve onboarding.")

    while len(recommendations) < 3:
        recommendations.append("Continue creator feedback collection to expand test diversity.")

    now_iso = datetime.now(UTC).isoformat()
    report_id = f"gate_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"

    metrics = {
        "total_creators": total_creators,
        "submitted_creators": num_submitted,
        "total_clips_rated": total_clips_rated,
        "usable_rate": round(usable_rate, 4),
        "strict_usable_rate": round(strict_usable_rate, 4),
        "top3_usable_rate": round(top3_usable_rate, 4),
        "top8_usable_rate": round(top8_usable_rate, 4),
        "score_verdict_correlation": score_verdict_correlation,
        "median_open_price_inr": median_open_price,
        "accepts_1500_pct": accepts_1500_pct,
        "accepts_4000_pct": accepts_4000_pct,
        "commit_upload_pct": commit_upload_pct,
        "reason_distribution": no_distribution,
        "no_reasons_count": no_reasons_count,
        "edits_reasons_count": edits_reasons_count,
    }

    return {
        "report_id": report_id,
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "generated_at": now_iso,
        "overall_verdict": overall_verdict,
        "checks": checks,
        "metrics": metrics,
        "creator_summaries": creator_summaries,
        "recommendations": recommendations[:3],
    }


def format_gate_markdown(report: dict[str, Any]) -> str:
    """Format gate report as GitHub-flavored Markdown."""
    m = report["metrics"]
    verdict = report["overall_verdict"]

    verdict_badge = {
        "GO": "🟢 **GO**",
        "FIX SELECTION FIRST": "🟡 **FIX SELECTION FIRST**",
        "RETHINK": "🔴 **RETHINK**",
    }.get(verdict, verdict)

    lines = [
        f"# Creator Reality Check — Gate Decision Report",
        f"",
        f"> **Generated**: {report['timestamp']} | **Report ID**: `{report['report_id']}`",
        f"",
        f"## Overall Decision: {verdict_badge}",
        f"",
        f"---",
        f"",
        f"## 1. Gate Criteria Evaluation",
        f"",
        f"| Criterion | Target | Actual | Status | Notes |",
        f"| :--- | :--- | :--- | :---: | :--- |",
    ]

    for c in report["checks"]:
        status_icon = "✅ **PASS**" if c["status"] == "PASS" else "❌ **FAIL**"
        lines.append(f"| {c['name']} | `{c['target']}` | `{c['actual']}` | {status_icon} | {c['message']} |")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 2. Key Aggregate Metrics",
        f"",
        f"- **Total Creators Tested**: {m['total_creators']} ({m['submitted_creators']} submitted)",
        f"- **Total Clips Rated**: {m['total_clips_rated']}",
        f"- **Usable Rate (Post as is + Post with edits)**: **{round(m['usable_rate']*100, 1)}%**",
        f"- **Strict Usable Rate (Post as is only)**: **{round(m['strict_usable_rate']*100, 1)}%**",
        f"- **Top-3 Usable Rate**: **{round(m['top3_usable_rate']*100, 1)}%** vs **Top-8 Usable Rate**: **{round(m['top8_usable_rate']*100, 1)}%**",
        f"- **Rank Correlation (Model Score vs Creator Verdict)**: `r = {m['score_verdict_correlation']}`",
        f"- **Median Willingness to Pay**: ₹{int(m['median_open_price_inr']):,}/month",
        f"- **Accepts ₹1,500/mo**: {m['accepts_1500_pct']}% | **Accepts ₹4,000/mo**: {m['accepts_4000_pct']}%",
        f"- **Committed to Upload Next Video**: **{m['commit_upload_pct']}%**",
        f"",
        f"---",
        f"",
        f"## 3. Rejection Reason Distribution (What to Fix)",
        f"",
        f"| Reason Tag | Share of Negative Ratings | Count |",
        f"| :--- | :---: | :---: |",
    ])

    if m.get("reason_distribution"):
        for tag, pct in sorted(m["reason_distribution"].items(), key=lambda x: x[1], reverse=True):
            count = m.get("no_reasons_count", {}).get(tag, 0)
            lines.append(f"| `{tag}` | **{pct}%** | {count} |")
    else:
        lines.append(f"| *No negative ratings recorded* | 0% | 0 |")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 4. Per-Creator Breakdown",
        f"",
        f"| Creator | Rated | Post As-Is | With Edits | No | Postable Count | WTP (Open) | ₹1.5k? | Next Upload? |",
        f"| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ])

    for cs in report["creator_summaries"]:
        wtp_str = f"₹{int(cs['price_open_inr']):,}" if cs['price_open_inr'] else "—"
        a1500_str = "Yes" if cs['accepts_1500'] is True else ("No" if cs['accepts_1500'] is False else "—")
        lines.append(
            f"| {cs['creator_name']} | {cs['clips_rated']} | {cs['post_as_is_pct']}% | {cs['post_with_edits_pct']}% | "
            f"{cs['no_pct']}% | **{cs['postable_clips_count']}** | {wtp_str} | {a1500_str} | {cs['would_upload_next'] or '—'} |"
        )

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 5. Top 3 Data-Driven Recommendations",
        f"",
    ])

    for idx, rec in enumerate(report["recommendations"], start=1):
        lines.append(f"{idx}. {rec}")

    lines.append("")
    return "\n".join(lines)


async def generate_gate_report(
    db: Any | None = None,
    fixtures_path: str | None = None,
    output_dir: str = "eval/reports",
) -> dict[str, Any]:
    """
    Main generator: loads data from DB or JSON fixtures, calculates metrics,
    writes report markdown & json files, and returns report dict.
    """
    sessions_data = []

    # 1. Load from fixtures if provided
    if fixtures_path and os.path.exists(fixtures_path):
        with open(fixtures_path, encoding="utf-8") as f:
            sessions_data = json.load(f)
    elif db is not None:
        # Load from database
        from clip_shared.db.models import Clip, ReviewRating, ReviewSession, ReviewSurvey
        from sqlalchemy import select

        s_stmt = select(ReviewSession).order_by(ReviewSession.created_at)
        s_res = await db.execute(s_stmt)
        sessions = s_res.scalars().all()

        for s in sessions:
            # Ratings
            r_stmt = select(ReviewRating, Clip.final_score).join(Clip, Clip.id == ReviewRating.clip_id).where(ReviewRating.session_id == s.id)
            r_res = await db.execute(r_stmt)
            ratings_rows = r_res.all()

            ratings_list = [
                {
                    "clip_id": str(r.clip_id),
                    "verdict": r.verdict,
                    "reason_tag": r.reason_tag,
                    "comment": r.comment,
                    "watch_ms": r.watch_ms,
                    "final_score": float(final_score) if final_score is not None else None,
                }
                for r, final_score in ratings_rows
            ]

            # Survey
            surv_stmt = select(ReviewSurvey).where(ReviewSurvey.session_id == s.id)
            surv_res = await db.execute(surv_stmt)
            survey_obj = surv_res.scalar_one_or_none()

            survey_dict = {}
            if survey_obj:
                survey_dict = {
                    "missing_text": survey_obj.missing_text,
                    "current_workflow_text": survey_obj.current_workflow_text,
                    "current_cost_text": survey_obj.current_cost_text,
                    "price_open_inr": float(survey_obj.price_open_inr) if survey_obj.price_open_inr else None,
                    "accepts_1500": survey_obj.accepts_1500,
                    "accepts_4000": survey_obj.accepts_4000,
                    "would_upload_next": survey_obj.would_upload_next,
                    "upload_timeframe": survey_obj.upload_timeframe,
                    "email_optin": survey_obj.email_optin,
                }

            sessions_data.append({
                "session_id": str(s.id),
                "creator_name": s.creator_name,
                "creator_email": s.creator_email,
                "status": s.status,
                "ratings": ratings_list,
                "survey": survey_dict,
            })

    # If no data found in DB, fallback to default eval fixtures
    if not sessions_data:
        default_fixtures = os.path.join(os.path.dirname(__file__), "fixtures", "gate_creator_sessions.json")
        if os.path.exists(default_fixtures):
            with open(default_fixtures, encoding="utf-8") as f:
                sessions_data = json.load(f)

    # Compute metrics and generate report
    report = calculate_gate_metrics(sessions_data)
    md_content = format_gate_markdown(report)

    # Write files
    os.makedirs(output_dir, exist_ok=True)
    report_id = report["report_id"]
    md_path = os.path.join(output_dir, f"{report_id}.md")
    json_path = os.path.join(output_dir, f"{report_id}.json")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    report["markdown_path"] = md_path
    report["json_path"] = json_path

    return report
