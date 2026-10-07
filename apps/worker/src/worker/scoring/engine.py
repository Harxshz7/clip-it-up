import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional, Callable
import structlog
from sqlalchemy.orm import Session

from clip_shared.config import get_settings, load_scoring_weights
from clip_shared.db.base import utc_now
from clip_shared.db.models import (
    Clip,
    ClipMoment,
    ScoringRun,
    Transcript,
    TranscriptSegment,
    TranscriptWord,
    Video,
    AudioFeatures,
)
from clip_shared.media.audio_features import (
    AudioFeaturesResult,
    extract_audio_features,
)
from clip_shared.prompts.clip_score_v1 import (
    Pass1BatchResponse,
    Pass1CandidateItem,
    Pass2CandidateScore,
    build_pass1_prompt,
    build_pass2_prompt,
)
from clip_shared.pubsub.redis import publish_job_event_sync
from clip_shared.storage.s3 import get_s3_client
from worker.scoring.combiner import combine_signals
from worker.scoring.llm_client import LLMClient
from worker.scoring.selection import select_top_moments
from worker.scoring.variants import generate_moment_variants

logger = structlog.get_logger()
settings = get_settings()


def publish_clip_scored_event(
    job_id: uuid.UUID,
    video_id: uuid.UUID,
    moment_id: uuid.UUID,
    clip_id: uuid.UUID,
    final_score: float,
    hook_text: str,
    title: str,
    duration_s: float,
    scored_count: int,
    total_count: int,
) -> None:
    """Publish real-time clip_scored event over SSE / Redis for live progressive UI rendering."""
    payload = {
        "event": "clip_scored",
        "job_id": str(job_id),
        "video_id": str(video_id),
        "moment_id": str(moment_id),
        "clip_id": str(clip_id),
        "final_score": final_score,
        "hook_text": hook_text,
        "title": title,
        "duration_seconds": duration_s,
        "scored_count": scored_count,
        "total_count": total_count,
        "partial_results": {
            "clips_count": scored_count,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    publish_job_event_sync(str(job_id), payload)


def run_scoring_pipeline(
    video_id: uuid.UUID,
    job_id: uuid.UUID,
    db: Session,
    weights_override: Optional[Dict[str, Any]] = None,
    prompt_version_override: Optional[str] = None,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> Dict[str, Any]:
    """
    Two-pass virality and quality scoring pipeline:
    1. Load audio features & cached candidate moments.
    2. Build full-video summary context.
    3. Pass 1: Batched cheap coarse scoring -> keep top ~40%.
    4. Pass 2: Structured scoring per candidate with hook & boundary trims.
    5. Stream results progressively via SSE (clip_scored).
    6. Combine multi-modal signals (LLM + audio energy + laughter - penalties).
    7. Select top N moments enforcing diversity & deduplication.
    8. Generate 15/30/45/60s variants.
    9. Persist scoring_runs, clips, and return run statistics.
    """
    s3 = get_s3_client()
    config_weights = load_scoring_weights()
    active_weights = weights_override or config_weights.get("weights", {})
    prompt_version = prompt_version_override or settings.PROMPT_VERSION
    scorer_version = settings.SCORER_VERSION
    hook_boost = float(config_weights.get("hook_energy_boost", 0.15))

    thresholds = config_weights.get("thresholds", {})
    max_selected = int(thresholds.get("max_selected_clips", 10))
    iou_thresh = float(thresholds.get("selection_iou_threshold", 0.30))
    div_minutes = float(thresholds.get("diversity_window_minutes", 5.0))
    max_per_win = int(thresholds.get("max_clips_per_window", 2))
    div_override = float(thresholds.get("diversity_score_override", 0.85))

    # 1. Fetch Candidates
    candidates = (
        db.query(ClipMoment)
        .filter(ClipMoment.video_id == video_id, ClipMoment.status == "candidate")
        .order_by(ClipMoment.start_ms)
        .all()
    )

    if not candidates:
        logger.warning("no_candidates_found_for_scoring", video_id=str(video_id))
        return {
            "scored_count": 0,
            "selected_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_inr": 0.0,
        }

    # Fetch Transcript & Segments
    transcript = db.query(Transcript).filter(Transcript.video_id == video_id).first()
    segments_rows = (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.transcript_id == transcript.id)
        .order_by(TranscriptSegment.idx)
        .all() if transcript else []
    )
    segments = [
        {"idx": s.idx, "start_ms": s.start_ms, "end_ms": s.end_ms, "speaker": s.speaker, "text": s.text}
        for s in segments_rows
    ]

    # Fetch or Extract Audio Features
    audio_feat_record = (
        db.query(AudioFeatures)
        .filter(AudioFeatures.video_id == video_id, AudioFeatures.version == "v1")
        .first()
    )
    
    audio_feat_res: Optional[AudioFeaturesResult] = None
    if audio_feat_record:
        try:
            npz_bytes = s3.download_bytes(audio_feat_record.frames_key)
            audio_feat_res = AudioFeaturesResult.from_npz_bytes(
                npz_bytes,
                duration_seconds=float(audio_feat_record.summary.get("duration_seconds", 300.0)),
                summary=audio_feat_record.summary,
            )
        except Exception as ex:
            logger.warning("failed_loading_audio_features_from_s3", error=str(ex))

    if not audio_feat_res:
        # Fallback dummy audio features
        audio_feat_res = AudioFeaturesResult(
            duration_seconds=300.0,
            rms_energy=[],
            spectral_flux=[],
            pitch_variance=[],
            laughter_prob=[],
            pause_map=[],
            summary={"mean_rms_energy": 0.5},
        )

    # 2. Build full video summary
    all_text = " ".join(s["text"] for s in segments)
    video_summary = all_text[:1500] + ("..." if len(all_text) > 1500 else "")

    llm = LLMClient()
    total_in_tokens = 0
    total_out_tokens = 0
    total_cost_inr = Decimal("0.0000")

    if progress_cb:
        progress_cb(10)

    # 3. PASS 1: Batched Coarse Scoring
    pass1_items = [
        Pass1CandidateItem(
            id=str(c.id),
            start_ms=c.start_ms,
            end_ms=c.end_ms,
            text=" ".join(s["text"] for s in segments if s["start_ms"] >= c.start_ms and s["end_ms"] <= c.end_ms) or "Candidate text",
        )
        for c in candidates
    ]

    pass1_model = settings.LLM_PASS1_MODEL
    batch_size = 6
    pass1_scores_map: Dict[str, float] = {}

    for b_idx in range(0, len(pass1_items), batch_size):
        batch = pass1_items[b_idx : b_idx + batch_size]
        p1_prompt = build_pass1_prompt(batch, video_summary)
        
        parsed, in_tok, out_tok, cost, _ = llm.call_structured(
            prompt=p1_prompt,
            model=pass1_model,
            response_schema=Pass1BatchResponse,
            prompt_version=prompt_version,
        )
        total_in_tokens += in_tok
        total_out_tokens += out_tok
        total_cost_inr += Decimal(str(cost))

        for sc in parsed.scores:
            pass1_scores_map[sc.id] = sc.coarse_score

    if progress_cb:
        progress_cb(35)

    # Filter top ~40% for Pass 2 (min 3 candidates, max 25)
    sorted_pass1 = sorted(candidates, key=lambda c: pass1_scores_map.get(str(c.id), 5.0), reverse=True)
    pass2_count = max(3, min(len(sorted_pass1), int(len(sorted_pass1) * 0.45)))
    pass2_candidates = sorted_pass1[:pass2_count]

    # Create ScoringRun row in DB
    scoring_run_id = uuid.uuid4()
    scoring_run = ScoringRun(
        id=scoring_run_id,
        video_id=video_id,
        prompt_version=prompt_version,
        scorer_version=scorer_version,
        weights=active_weights,
        model=settings.LLM_PASS2_MODEL,
        input_tokens=total_in_tokens,
        output_tokens=total_out_tokens,
        cost_inr=total_cost_inr,
        created_at=utc_now(),
    )
    db.add(scoring_run)
    db.flush()

    # 4. PASS 2: Deep Structured Scoring & Streaming
    pass2_model = settings.LLM_PASS2_MODEL
    scored_moments_data: List[Dict[str, Any]] = []

    for i, cand in enumerate(pass2_candidates):
        cand_text = " ".join(s["text"] for s in segments if s["start_ms"] >= cand.start_ms and s["end_ms"] <= cand.end_ms)
        p2_prompt = build_pass2_prompt(
            candidate_id=str(cand.id),
            start_ms=cand.start_ms,
            end_ms=cand.end_ms,
            text=cand_text or "Transcript segment",
            speaker=None,
            video_summary=video_summary,
        )

        p2_parsed, in_tok, out_tok, cost, _ = llm.call_structured(
            prompt=p2_prompt,
            model=pass2_model,
            response_schema=Pass2CandidateScore,
            prompt_version=prompt_version,
        )
        total_in_tokens += in_tok
        total_out_tokens += out_tok
        total_cost_inr += Decimal(str(cost))

        # Extract window audio features
        window_audio = audio_feat_res.get_window_features(cand.start_ms, cand.end_ms)

        # Multi-modal Signal Combination
        final_score, breakdown = combine_signals(
            llm_score=p2_parsed,
            audio_features=window_audio,
            weights=active_weights,
            hook_energy_boost=hook_boost,
        )

        # Fine trim refinement
        refined_start = max(cand.start_ms, min(p2_parsed.suggested_start_ms, cand.end_ms - 10000))
        refined_end = min(cand.end_ms, max(p2_parsed.suggested_end_ms, refined_start + 10000))

        # Update candidate moment
        cand.final_score = final_score
        cand.status = "scored"
        cand.start_ms = refined_start
        cand.end_ms = refined_end
        db.flush()

        # Build initial auto clip
        clip_id = uuid.uuid4()
        duration_s = (refined_end - refined_start) / 1000.0

        moment_dict = {
            "moment_id": cand.id,
            "video_id": video_id,
            "start_ms": refined_start,
            "end_ms": refined_end,
            "final_score": final_score,
            "hook_text": p2_parsed.best_hook_text,
            "title": p2_parsed.title,
            "reason": p2_parsed.reason,
            "breakdown": breakdown,
            "model": pass2_model,
            "prompt_version": prompt_version,
            "scorer_version": scorer_version,
            "clip_id": clip_id,
        }
        scored_moments_data.append(moment_dict)

        # 5. STREAM SSE EVENT: clip_scored
        publish_clip_scored_event(
            job_id=job_id,
            video_id=video_id,
            moment_id=cand.id,
            clip_id=clip_id,
            final_score=final_score,
            hook_text=p2_parsed.best_hook_text,
            title=p2_parsed.title,
            duration_s=duration_s,
            scored_count=i + 1,
            total_count=len(pass2_candidates),
        )

        if progress_cb:
            current_pct = int(35 + (50 * (i + 1) / len(pass2_candidates)))
            progress_cb(current_pct)

    # 6. Selection with Deduplication and Diversity Enforcement
    selected_moments = select_top_moments(
        scored_moments_data,
        max_selected=max_selected,
        iou_threshold=iou_thresh,
        diversity_window_minutes=div_minutes,
        max_clips_per_window=max_per_win,
        diversity_score_override=div_override,
    )

    selected_moment_ids = {m["moment_id"] for m in selected_moments}

    # Mark non-selected as rejected
    for cand in candidates:
        if cand.id in selected_moment_ids:
            cand.status = "selected"
        elif cand.status == "scored":
            cand.status = "rejected"
    db.flush()

    # 7. Generate and Persist Variants for each Selected Moment
    all_created_clips: List[Clip] = []

    for sel in selected_moments:
        variants = generate_moment_variants(
            moment_start_ms=sel["start_ms"],
            moment_end_ms=sel["end_ms"],
            base_hook_text=sel["hook_text"],
            base_title=sel["title"],
            base_score=sel["final_score"],
            base_breakdown=sel["breakdown"],
            base_reason=sel["reason"],
            segments=segments,
        )

        for v in variants:
            clip = Clip(
                id=uuid.uuid4(),
                moment_id=sel["moment_id"],
                video_id=video_id,
                scoring_run_id=scoring_run_id,
                variant_length_s=v.variant_length_s,
                start_ms=v.start_ms,
                end_ms=v.end_ms,
                hook_text=v.hook_text,
                title=v.title,
                final_score=v.final_score,
                score_breakdown=v.score_breakdown,
                reason=v.reason,
                model=pass2_model,
                prompt_version=prompt_version,
                scorer_version=scorer_version,
                created_at=utc_now(),
            )
            db.add(clip)
            all_created_clips.append(clip)

    # Update scoring run token totals
    scoring_run.input_tokens = total_in_tokens
    scoring_run.output_tokens = total_out_tokens
    scoring_run.cost_inr = total_cost_inr
    db.flush()

    if progress_cb:
        progress_cb(100)

    logger.info(
        "scoring_pipeline_complete",
        video_id=str(video_id),
        scored_count=len(scored_moments_data),
        selected_count=len(selected_moments),
        total_clips_with_variants=len(all_created_clips),
        input_tokens=total_in_tokens,
        output_tokens=total_out_tokens,
        cost_inr=float(total_cost_inr),
    )

    return {
        "scoring_run_id": str(scoring_run_id),
        "scored_count": len(scored_moments_data),
        "selected_count": len(selected_moments),
        "total_clips_created": len(all_created_clips),
        "input_tokens": total_in_tokens,
        "output_tokens": total_out_tokens,
        "cost_inr": float(total_cost_inr),
    }
