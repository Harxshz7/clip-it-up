import os
import secrets
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from clip_shared.config import get_settings
from clip_shared.db.base import utc_now
from clip_shared.db.models import (
    Clip,
    ClipMoment,
    ClipReviewExport,
    ReviewRating,
    ReviewSession,
    ReviewSurvey,
    Video,
)
from clip_shared.db.session import get_db
from clip_shared.schemas.auth import AuthenticatedUser
from clip_shared.schemas.review import (
    GateReportResponse,
    ReviewClipPublicResponse,
    ReviewRatingResponse,
    ReviewRatingUpsertRequest,
    ReviewSessionCreatedResponse,
    ReviewSessionCreateRequest,
    ReviewSessionOwnerResponse,
    ReviewSessionPublicResponse,
    ReviewSurveyResponse,
    ReviewSurveyUpsertRequest,
)
from clip_shared.storage.s3 import get_s3_client

router = APIRouter(tags=["reviews"])
settings = get_settings()
logger = structlog.get_logger()

# In-memory token bucket rate limiter for public review endpoints (IP-based, 60 requests per minute)
_RATE_LIMIT_BUCKET: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW_S = 60.0
_RATE_LIMIT_MAX_REQUESTS = 120


def enforce_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    timestamps = _RATE_LIMIT_BUCKET[client_ip]
    # Prune old timestamps
    _RATE_LIMIT_BUCKET[client_ip] = [ts for ts in timestamps if now - ts < _RATE_LIMIT_WINDOW_S]
    if len(_RATE_LIMIT_BUCKET[client_ip]) >= _RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": {"code": "RATE_LIMIT_EXCEEDED", "message": "Too many requests. Please slow down."}},
        )
    _RATE_LIMIT_BUCKET[client_ip].append(now)


async def _get_valid_session_by_token(token: str, db: AsyncSession) -> ReviewSession:
    """Validate review session token with constant-time comparison and expiry check."""
    if not token or len(token) < 20:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "SESSION_NOT_FOUND", "message": "Invalid or missing review token."}},
        )

    stmt = select(ReviewSession).where(ReviewSession.token == token)
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session or not secrets.compare_digest(session.token, token):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "SESSION_NOT_FOUND", "message": "Review session not found."}},
        )

    # Expiry enforcement
    now_utc = utc_now()
    if session.expires_at < now_utc or session.status == "closed":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "SESSION_EXPIRED", "message": "This review session has expired or is closed."}},
        )

    return session


# ---------------------------------------------------------------------------
# OWNER ENDPOINTS (Authenticated)
# ---------------------------------------------------------------------------

@router.post("/videos/{video_id}/review-sessions", response_model=ReviewSessionCreatedResponse)
async def create_review_session(
    video_id: uuid.UUID,
    payload: ReviewSessionCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new private review session link for a video (authenticated video owner).
    Generates unguessable token and triggers crude export of top N clips.
    """
    # 1. Verify video ownership
    v_stmt = select(Video).where(Video.id == video_id, Video.user_id == user.id)
    v_res = await db.execute(v_stmt)
    video = v_res.scalar_one_or_none()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "VIDEO_NOT_FOUND", "message": "Video not found or access denied."}},
        )

    # 2. Generate secure token & expiry
    token = secrets.token_urlsafe(32)
    expires_at = utc_now() + timedelta(days=payload.expires_in_days)

    session = ReviewSession(
        id=uuid.uuid4(),
        video_id=video_id,
        created_by=user.id,
        token=token,
        creator_name=payload.creator_name,
        creator_email=payload.creator_email,
        status="open",
        expires_at=expires_at,
        created_at=utc_now(),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    # 3. Trigger crude export in background
    try:
        from worker.tasks.review import generate_review_exports
        generate_review_exports.delay(str(video_id), payload.top_n)
    except Exception as e:
        logger.warn("celery_dispatch_failed_trying_sync_or_ignoring", err=str(e))

    web_base_url = getattr(settings, "WEB_BASE_URL", "http://localhost:3000").rstrip("/")
    shareable_url = f"{web_base_url}/review/{token}"

    return ReviewSessionCreatedResponse(
        id=session.id,
        video_id=session.video_id,
        token=session.token,
        shareable_url=shareable_url,
        creator_name=session.creator_name,
        creator_email=session.creator_email,
        status=session.status,
        expires_at=session.expires_at,
        created_at=session.created_at,
        message="Review session created successfully.",
    )


@router.get("/review-sessions", response_model=list[ReviewSessionOwnerResponse])
async def list_review_sessions(
    video_id: uuid.UUID = Query(..., description="Video ID to filter review sessions"),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all review sessions created for a video with their rating counts and survey status."""
    v_stmt = select(Video).where(Video.id == video_id, Video.user_id == user.id)
    v_res = await db.execute(v_stmt)
    if not v_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "VIDEO_NOT_FOUND", "message": "Video not found."}},
        )

    s_stmt = (
        select(ReviewSession)
        .where(ReviewSession.video_id == video_id, ReviewSession.created_by == user.id)
        .order_by(desc(ReviewSession.created_at))
    )
    s_res = await db.execute(s_stmt)
    sessions = s_res.scalars().all()

    web_base_url = getattr(settings, "WEB_BASE_URL", "http://localhost:3000").rstrip("/")
    results = []

    # Count total clips for this video
    c_count_stmt = select(Clip).where(Clip.video_id == video_id)
    c_res = await db.execute(c_count_stmt)
    total_clips = len(c_res.scalars().all())

    for s in sessions:
        # Load ratings and survey
        r_stmt = select(ReviewRating).where(ReviewRating.session_id == s.id)
        r_res = await db.execute(r_stmt)
        ratings = r_res.scalars().all()

        surv_stmt = select(ReviewSurvey).where(ReviewSurvey.session_id == s.id)
        surv_res = await db.execute(surv_stmt)
        survey = surv_res.scalar_one_or_none()

        shareable_url = f"{web_base_url}/review/{s.token}"

        results.append(
            ReviewSessionOwnerResponse(
                id=s.id,
                video_id=s.video_id,
                token=s.token,
                creator_name=s.creator_name,
                creator_email=s.creator_email,
                status=s.status,
                shareable_url=shareable_url,
                expires_at=s.expires_at,
                created_at=s.created_at,
                submitted_at=s.submitted_at,
                ratings=[ReviewRatingResponse.model_validate(r) for r in ratings],
                survey=ReviewSurveyResponse.model_validate(survey) if survey else None,
                total_clips=total_clips,
                rated_clips_count=len(ratings),
            )
        )

    return results


@router.get("/review-sessions/{session_id}", response_model=ReviewSessionOwnerResponse)
async def get_review_session_detail(
    session_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full details of a specific review session for the owner."""
    s_stmt = select(ReviewSession).where(ReviewSession.id == session_id, ReviewSession.created_by == user.id)
    s_res = await db.execute(s_stmt)
    s = s_res.scalar_one_or_none()
    if not s:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "SESSION_NOT_FOUND", "message": "Review session not found."}},
        )

    r_stmt = select(ReviewRating).where(ReviewRating.session_id == s.id)
    r_res = await db.execute(r_stmt)
    ratings = r_res.scalars().all()

    surv_stmt = select(ReviewSurvey).where(ReviewSurvey.session_id == s.id)
    surv_res = await db.execute(surv_stmt)
    survey = surv_res.scalar_one_or_none()

    c_count_stmt = select(Clip).where(Clip.video_id == s.video_id)
    c_res = await db.execute(c_count_stmt)
    total_clips = len(c_res.scalars().all())

    web_base_url = getattr(settings, "WEB_BASE_URL", "http://localhost:3000").rstrip("/")
    shareable_url = f"{web_base_url}/review/{s.token}"

    return ReviewSessionOwnerResponse(
        id=s.id,
        video_id=s.video_id,
        token=s.token,
        creator_name=s.creator_name,
        creator_email=s.creator_email,
        status=s.status,
        shareable_url=shareable_url,
        expires_at=s.expires_at,
        created_at=s.created_at,
        submitted_at=s.submitted_at,
        ratings=[ReviewRatingResponse.model_validate(r) for r in ratings],
        survey=ReviewSurveyResponse.model_validate(survey) if survey else None,
        total_clips=total_clips,
        rated_clips_count=len(ratings),
    )


@router.delete("/review-sessions/{session_id}")
async def delete_review_session(
    session_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete review session, its ratings, survey, and clean up exports."""
    s_stmt = select(ReviewSession).where(ReviewSession.id == session_id, ReviewSession.created_by == user.id)
    s_res = await db.execute(s_stmt)
    s = s_res.scalar_one_or_none()
    if not s:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "SESSION_NOT_FOUND", "message": "Review session not found."}},
        )

    await db.delete(s)
    await db.commit()

    return {"deleted": True, "session_id": str(session_id)}


# ---------------------------------------------------------------------------
# PUBLIC CREATOR ENDPOINTS (Token-Gated, No Auth, Rate-Limited)
# ---------------------------------------------------------------------------

@router.get("/review/{token}", response_model=ReviewSessionPublicResponse)
async def get_public_review_session(
    token: str,
    request: Request,
    show_reasons: bool = Query(False, description="Config flag to show AI selection reasons"),
    db: AsyncSession = Depends(get_db),
):
    """
    Public token-gated endpoint for creators to view clips and session details.
    Internal scores and reasons are hidden by default to prevent anchoring.
    """
    enforce_rate_limit(request)
    session = await _get_valid_session_by_token(token, db)

    # Fetch Video
    v_stmt = select(Video).where(Video.id == session.video_id)
    v_res = await db.execute(v_stmt)
    video = v_res.scalar_one()

    # Fetch top clips for this video
    # 1. Fetch moments ordered by rank / score
    m_stmt = (
        select(ClipMoment)
        .where(ClipMoment.video_id == session.video_id)
        .order_by(ClipMoment.rank.nullslast(), desc(ClipMoment.final_score))
        .limit(10)
    )
    m_res = await db.execute(m_stmt)
    moments = m_res.scalars().all()
    moment_ids = [m.id for m in moments]

    clips = []
    if moment_ids:
        c_stmt = (
            select(Clip)
            .where(Clip.moment_id.in_(moment_ids))
            .order_by(desc(Clip.final_score))
        )
        c_res = await db.execute(c_stmt)
        all_clips = c_res.scalars().all()

        # Pick auto or best variant per moment
        for m in moments:
            m_clips = [c for c in all_clips if c.moment_id == m.id]
            if m_clips:
                auto_c = next((c for c in m_clips if c.variant_length_s == "auto"), m_clips[0])
                clips.append((m, auto_c))
    else:
        # Fallback to direct clips
        c_stmt = (
            select(Clip)
            .where(Clip.video_id == session.video_id)
            .order_by(desc(Clip.final_score))
            .limit(8)
        )
        c_res = await db.execute(c_stmt)
        direct_clips = c_res.scalars().all()
        clips = [(None, c) for c in direct_clips]

    # Fetch existing ratings for this session
    r_stmt = select(ReviewRating).where(ReviewRating.session_id == session.id)
    r_res = await db.execute(r_stmt)
    ratings_map = {r.clip_id: r for r in r_res.scalars().all()}

    # Fetch exports
    clip_ids = [c.id for _, c in clips]
    exp_stmt = select(ClipReviewExport).where(ClipReviewExport.clip_id.in_(clip_ids))
    exp_res = await db.execute(exp_stmt)
    exports = exp_res.scalars().all()
    exports_map: dict[uuid.UUID, dict[str, str]] = defaultdict(dict)

    s3_client = get_s3_client()
    for exp in exports:
        try:
            presigned_url = s3_client.generate_presigned_get_url(exp.storage_key, expires_in_seconds=3600)
            exports_map[exp.clip_id][exp.kind] = presigned_url
        except Exception:
            pass

    # Build public clip responses
    public_clips: list[ReviewClipPublicResponse] = []
    for rank_idx, (moment, clip) in enumerate(clips, start=1):
        existing_rating = ratings_map.get(clip.id)

        # Fallback preview URLs if exports not yet generated
        video_urls = exports_map.get(clip.id, {})
        if not video_urls:
            # Fallback to proxy video URL or direct endpoint
            if video.proxy_key:
                try:
                    proxy_url = s3_client.generate_presigned_get_url(video.proxy_key, expires_in_seconds=3600)
                    video_urls["horizontal"] = proxy_url
                    video_urls["vertical_center"] = proxy_url
                except Exception:
                    pass

        public_clips.append(
            ReviewClipPublicResponse(
                clip_id=clip.id,
                moment_id=clip.moment_id,
                rank=moment.rank if moment and moment.rank else rank_idx,
                title=clip.title,
                hook_text=clip.hook_text,
                start_ms=clip.start_ms,
                end_ms=clip.end_ms,
                duration_seconds=round((clip.end_ms - clip.start_ms) / 1000.0, 1),
                variant_length_s=clip.variant_length_s,
                video_urls=video_urls,
                rating=ReviewRatingResponse.model_validate(existing_rating) if existing_rating else None,
                why_chosen=clip.reason if show_reasons else None,
            )
        )

    # Fetch survey
    surv_stmt = select(ReviewSurvey).where(ReviewSurvey.session_id == session.id)
    surv_res = await db.execute(surv_stmt)
    survey = surv_res.scalar_one_or_none()

    consent_notice = "Feedback and video snippets are used solely to evaluate AI clip selection quality."

    return ReviewSessionPublicResponse(
        id=session.id,
        video_id=session.video_id,
        token=session.token,
        creator_name=session.creator_name,
        status=session.status,
        expires_at=session.expires_at,
        created_at=session.created_at,
        submitted_at=session.submitted_at,
        video_title=video.original_filename,
        consent_notice=consent_notice,
        clips=public_clips,
        survey=ReviewSurveyResponse.model_validate(survey) if survey else None,
    )


@router.get("/review/{token}/clips/{clip_id}/video")
async def get_clip_review_video(
    token: str,
    clip_id: uuid.UUID,
    kind: str = Query("vertical_center", pattern="^(horizontal|vertical_center)$"),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Get presigned URL or redirect to clip preview video (vertical center or horizontal)."""
    if request:
        enforce_rate_limit(request)
    session = await _get_valid_session_by_token(token, db)

    # Verify clip belongs to session's video
    c_stmt = select(Clip).where(Clip.id == clip_id, Clip.video_id == session.video_id)
    c_res = await db.execute(c_stmt)
    clip = c_res.scalar_one_or_none()
    if not clip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "CLIP_NOT_FOUND", "message": "Clip not found."}},
        )

    s3_client = get_s3_client()

    # Look for export record
    exp_stmt = select(ClipReviewExport).where(ClipReviewExport.clip_id == clip_id, ClipReviewExport.kind == kind)
    exp_res = await db.execute(exp_stmt)
    export_rec = exp_res.scalar_one_or_none()

    if export_rec:
        url = s3_client.generate_presigned_get_url(export_rec.storage_key, expires_in_seconds=3600)
        return RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    # Fallback to video proxy
    v_stmt = select(Video).where(Video.id == session.video_id)
    v_res = await db.execute(v_stmt)
    video = v_res.scalar_one()

    target_key = video.proxy_key or video.storage_key
    url = s3_client.generate_presigned_get_url(target_key, expires_in_seconds=3600)
    return RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.put("/review/{token}/ratings/{clip_id}", response_model=ReviewRatingResponse)
async def upsert_clip_rating(
    token: str,
    clip_id: uuid.UUID,
    payload: ReviewRatingUpsertRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Upsert rating for a clip in the review session."""
    enforce_rate_limit(request)
    session = await _get_valid_session_by_token(token, db)

    # Verify clip belongs to session's video
    c_stmt = select(Clip).where(Clip.id == clip_id, Clip.video_id == session.video_id)
    c_res = await db.execute(c_stmt)
    clip = c_res.scalar_one_or_none()
    if not clip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "CLIP_NOT_FOUND", "message": "Clip not found for this review session."}},
        )

    r_stmt = select(ReviewRating).where(
        ReviewRating.session_id == session.id,
        ReviewRating.clip_id == clip_id,
    )
    r_res = await db.execute(r_stmt)
    rating = r_res.scalar_one_or_none()

    if not rating:
        rating = ReviewRating(
            id=uuid.uuid4(),
            session_id=session.id,
            clip_id=clip_id,
            verdict=payload.verdict,
            reason_tag=payload.reason_tag,
            comment=payload.comment,
            watch_ms=payload.watch_ms,
            created_at=utc_now(),
        )
        db.add(rating)
    else:
        rating.verdict = payload.verdict
        rating.reason_tag = payload.reason_tag
        rating.comment = payload.comment
        if payload.watch_ms > 0:
            rating.watch_ms = payload.watch_ms
        rating.created_at = utc_now()

    await db.commit()
    await db.refresh(rating)

    return ReviewRatingResponse.model_validate(rating)


@router.put("/review/{token}/survey", response_model=ReviewSurveyResponse)
async def upsert_review_survey(
    token: str,
    payload: ReviewSurveyUpsertRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Upsert exit survey response for the review session."""
    enforce_rate_limit(request)
    session = await _get_valid_session_by_token(token, db)

    surv_stmt = select(ReviewSurvey).where(ReviewSurvey.session_id == session.id)
    surv_res = await db.execute(surv_stmt)
    survey = surv_res.scalar_one_or_none()

    if not survey:
        survey = ReviewSurvey(
            id=uuid.uuid4(),
            session_id=session.id,
            missing_text=payload.missing_text,
            current_workflow_text=payload.current_workflow_text,
            current_cost_text=payload.current_cost_text,
            price_open_inr=payload.price_open_inr,
            accepts_1500=payload.accepts_1500,
            accepts_4000=payload.accepts_4000,
            would_upload_next=payload.would_upload_next,
            upload_timeframe=payload.upload_timeframe,
            email_optin=payload.email_optin or False,
            created_at=utc_now(),
        )
        db.add(survey)
    else:
        survey.missing_text = payload.missing_text
        survey.current_workflow_text = payload.current_workflow_text
        survey.current_cost_text = payload.current_cost_text
        survey.price_open_inr = payload.price_open_inr
        survey.accepts_1500 = payload.accepts_1500
        survey.accepts_4000 = payload.accepts_4000
        survey.would_upload_next = payload.would_upload_next
        survey.upload_timeframe = payload.upload_timeframe
        survey.email_optin = payload.email_optin or False
        survey.created_at = utc_now()

    await db.commit()
    await db.refresh(survey)

    return ReviewSurveyResponse.model_validate(survey)


@router.post("/review/{token}/submit")
async def submit_review_session(
    token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Mark review session as submitted."""
    enforce_rate_limit(request)
    session = await _get_valid_session_by_token(token, db)

    session.status = "submitted"
    session.submitted_at = utc_now()
    await db.commit()

    return {
        "status": "submitted",
        "session_id": str(session.id),
        "submitted_at": session.submitted_at.isoformat(),
        "message": "Thank you! Your review has been recorded.",
    }


# ---------------------------------------------------------------------------
# GATE REPORT ENDPOINT
# ---------------------------------------------------------------------------

@router.get("/reviews/gate", response_model=GateReportResponse)
async def get_gate_report(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate and return Gate Decision Report across all submitted review sessions."""
    from eval.gate import generate_gate_report
    report = await generate_gate_report(db=db)
    return report
