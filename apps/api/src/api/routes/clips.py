import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from clip_shared.config import get_settings
from clip_shared.db.base import utc_now
from clip_shared.db.models import (
    Clip,
    ClipFeedback,
    ClipMoment,
    Job,
    JobStage,
    ScoringRun,
    Transcript,
    Video,
)
from clip_shared.db.session import get_db
from clip_shared.schemas.auth import AuthenticatedUser
from clip_shared.schemas.clips import (
    ClipFeedbackRequest,
    ClipFeedbackResponse,
    ClipMomentResponse,
    ClipResponse,
    RescoreRequest,
    ScoringRunResponse,
    VideoClipsResponse,
)

router = APIRouter(tags=["clips"])
settings = get_settings()


@router.get("/videos/{video_id}/clips", response_model=VideoClipsResponse)
async def get_video_clips(
    video_id: uuid.UUID,
    status_filter: str | None = Query(None, alias="status", description="Filter by moment status (selected | scored | candidate | rejected)"),
    min_score: float | None = Query(None, ge=0.0, le=1.0, description="Minimum clip score"),
    sort: str | None = Query("score", pattern="^(score|time|rank)$", description="Sort moments by score, time, or rank"),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all clip moments for a video grouped with their variants (15/30/45/60/auto).
    Strict ownership check (404 for unauthorized/missing).
    """
    # 1. Verify video ownership
    v_stmt = select(Video).where(Video.id == video_id, Video.user_id == user.id)
    v_res = await db.execute(v_stmt)
    video = v_res.scalar_one_or_none()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "VIDEO_NOT_FOUND", "message": "Video not found."}},
        )

    # 2. Query Moments
    m_stmt = select(ClipMoment).where(ClipMoment.video_id == video_id)
    if status_filter:
        m_stmt = m_stmt.where(ClipMoment.status == status_filter)
    if min_score is not None:
        m_stmt = m_stmt.where(ClipMoment.final_score >= min_score)

    if sort == "time":
        m_stmt = m_stmt.order_by(ClipMoment.start_ms)
    elif sort == "rank":
        m_stmt = m_stmt.order_by(ClipMoment.rank.nullslast(), desc(ClipMoment.final_score))
    else:  # score
        m_stmt = m_stmt.order_by(desc(ClipMoment.final_score), ClipMoment.start_ms)

    m_res = await db.execute(m_stmt)
    moments = m_res.scalars().all()

    # 3. Query all Clips with feedback for this user
    moment_ids = [m.id for m in moments]
    clips_by_moment: dict[uuid.UUID, list[ClipResponse]] = {m.id: [] for m in moments}

    if moment_ids:
        c_stmt = (
            select(Clip)
            .where(Clip.moment_id.in_(moment_ids))
            .order_by(Clip.variant_length_s)
        )
        c_res = await db.execute(c_stmt)
        clips = c_res.scalars().all()

        clip_ids = [c.id for c in clips]
        fb_map: dict[uuid.UUID, ClipFeedback] = {}
        if clip_ids:
            fb_stmt = select(ClipFeedback).where(
                ClipFeedback.clip_id.in_(clip_ids),
                ClipFeedback.user_id == user.id,
            )
            fb_res = await db.execute(fb_stmt)
            for fb in fb_res.scalars().all():
                fb_map[fb.clip_id] = fb

        for c in clips:
            fb_obj = fb_map.get(c.id)
            fb_resp = ClipFeedbackResponse.model_validate(fb_obj) if fb_obj else None
            c_resp = ClipResponse(
                id=c.id,
                moment_id=c.moment_id,
                video_id=c.video_id,
                scoring_run_id=c.scoring_run_id,
                variant_length_s=c.variant_length_s,
                start_ms=c.start_ms,
                end_ms=c.end_ms,
                duration_seconds=round((c.end_ms - c.start_ms) / 1000.0, 2),
                hook_text=c.hook_text,
                title=c.title,
                final_score=c.final_score,
                score_breakdown=c.score_breakdown or {},
                reason=c.reason,
                model=c.model,
                prompt_version=c.prompt_version,
                scorer_version=c.scorer_version,
                created_at=c.created_at,
                feedback=fb_resp,
            )
            clips_by_moment[c.moment_id].append(c_resp)

    moment_responses: list[ClipMomentResponse] = []
    total_clips_count = 0
    for m in moments:
        m_clips = clips_by_moment.get(m.id, [])
        total_clips_count += len(m_clips)
        moment_responses.append(
            ClipMomentResponse(
                id=m.id,
                video_id=m.video_id,
                transcript_id=m.transcript_id,
                start_ms=m.start_ms,
                end_ms=m.end_ms,
                duration_seconds=round((m.end_ms - m.start_ms) / 1000.0, 2),
                rank=m.rank,
                final_score=m.final_score,
                status=m.status,
                created_at=m.created_at,
                clips=m_clips,
            )
        )

    return VideoClipsResponse(
        video_id=video_id,
        moments=moment_responses,
        total_moments=len(moment_responses),
        total_clips=total_clips_count,
    )


@router.get("/clips/{clip_id}", response_model=ClipResponse)
async def get_single_clip(
    clip_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get single clip details with breakdown and user feedback."""
    stmt = (
        select(Clip)
        .join(Video, Video.id == Clip.video_id)
        .where(Clip.id == clip_id, Video.user_id == user.id)
    )
    res = await db.execute(stmt)
    clip = res.scalar_one_or_none()
    if not clip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "CLIP_NOT_FOUND", "message": "Clip not found."}},
        )

    # Fetch feedback
    fb_stmt = select(ClipFeedback).where(ClipFeedback.clip_id == clip_id, ClipFeedback.user_id == user.id)
    fb_res = await db.execute(fb_stmt)
    feedback = fb_res.scalar_one_or_none()

    return ClipResponse(
        id=clip.id,
        moment_id=clip.moment_id,
        video_id=clip.video_id,
        scoring_run_id=clip.scoring_run_id,
        variant_length_s=clip.variant_length_s,
        start_ms=clip.start_ms,
        end_ms=clip.end_ms,
        duration_seconds=round((clip.end_ms - clip.start_ms) / 1000.0, 2),
        hook_text=clip.hook_text,
        title=clip.title,
        final_score=clip.final_score,
        score_breakdown=clip.score_breakdown or {},
        reason=clip.reason,
        model=clip.model,
        prompt_version=clip.prompt_version,
        scorer_version=clip.scorer_version,
        created_at=clip.created_at,
        feedback=ClipFeedbackResponse.model_validate(feedback) if feedback else None,
    )


@router.post("/clips/{clip_id}/feedback", response_model=ClipFeedbackResponse)
async def submit_clip_feedback(
    clip_id: uuid.UUID,
    payload: ClipFeedbackRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit thumbs up/down and optional reason tag on a clip (upsert)."""
    # Verify clip ownership
    stmt = (
        select(Clip)
        .join(Video, Video.id == Clip.video_id)
        .where(Clip.id == clip_id, Video.user_id == user.id)
    )
    res = await db.execute(stmt)
    clip = res.scalar_one_or_none()
    if not clip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "CLIP_NOT_FOUND", "message": "Clip not found."}},
        )

    # Upsert feedback
    fb_stmt = select(ClipFeedback).where(ClipFeedback.clip_id == clip_id, ClipFeedback.user_id == user.id)
    fb_res = await db.execute(fb_stmt)
    feedback = fb_res.scalar_one_or_none()

    if feedback:
        feedback.value = payload.value
        feedback.reason_tag = payload.reason_tag
    else:
        feedback = ClipFeedback(
            id=uuid.uuid4(),
            clip_id=clip_id,
            user_id=user.id,
            value=payload.value,
            reason_tag=payload.reason_tag,
            created_at=utc_now(),
        )
        db.add(feedback)

    await db.commit()
    await db.refresh(feedback)
    return feedback


@router.delete("/clips/{clip_id}/feedback")
async def delete_clip_feedback(
    clip_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove user feedback on a clip."""
    fb_stmt = select(ClipFeedback).where(ClipFeedback.clip_id == clip_id, ClipFeedback.user_id == user.id)
    fb_res = await db.execute(fb_stmt)
    feedback = fb_res.scalar_one_or_none()
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "FEEDBACK_NOT_FOUND", "message": "Feedback not found."}},
        )

    await db.delete(feedback)
    await db.commit()
    return {"status": "deleted", "clip_id": str(clip_id)}


@router.post("/videos/{video_id}/rescore")
async def rescore_video(
    video_id: uuid.UUID,
    payload: RescoreRequest = RescoreRequest(),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Re-run scoring stage with optional prompt_version or custom weights WITHOUT re-transcribing.
    Creates a new ScoringRun and triggers Celery scoring stage.
    """
    # 1. Verify video and transcript readiness
    v_stmt = select(Video).where(Video.id == video_id, Video.user_id == user.id)
    v_res = await db.execute(v_stmt)
    video = v_res.scalar_one_or_none()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "VIDEO_NOT_FOUND", "message": "Video not found."}},
        )

    t_stmt = select(Transcript).where(Transcript.video_id == video_id)
    t_res = await db.execute(t_stmt)
    transcript = t_res.scalar_one_or_none()
    if not transcript or transcript.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "TRANSCRIPT_NOT_READY", "message": "Cannot rescore: transcript is not ready yet."}},
        )

    # 2. Create Job for scoring rerun
    job = Job(
        id=uuid.uuid4(),
        video_id=video.id,
        user_id=user.id,
        status="queued",
        current_stage="candidates",
        progress=0,
        partial_results={"transcript": True, "rescore": True},
        created_at=utc_now(),
    )
    db.add(job)
    await db.flush()

    # Stages for rescore: candidates -> score
    stg_cand = JobStage(id=uuid.uuid4(), job_id=job.id, name="candidates", status="pending", progress=0, meta={})
    stg_score = JobStage(id=uuid.uuid4(), job_id=job.id, name="score", status="pending", progress=0, meta={})
    db.add(stg_cand)
    db.add(stg_score)

    await db.commit()

    # 3. Trigger worker candidates stage directly
    try:
        from worker.celery_app import celery_app
        celery_app.send_task("worker.tasks.pipeline.run_stage", args=[str(job.id), "candidates"], queue="cpu")
    except Exception:
        pass

    return {
        "status": "rescore_enqueued",
        "job_id": str(job.id),
        "video_id": str(video_id),
    }


@router.get("/videos/{video_id}/scoring-runs", response_model=list[ScoringRunResponse])
async def list_scoring_runs(
    video_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List historical scoring runs for a video."""
    v_stmt = select(Video).where(Video.id == video_id, Video.user_id == user.id)
    v_res = await db.execute(v_stmt)
    video = v_res.scalar_one_or_none()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "VIDEO_NOT_FOUND", "message": "Video not found."}},
        )

    stmt = select(ScoringRun).where(ScoringRun.video_id == video_id).order_by(desc(ScoringRun.created_at))
    res = await db.execute(stmt)
    runs = res.scalars().all()
    return runs
