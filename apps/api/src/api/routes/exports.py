"""API routes for caption styles, export presets, clip captions, cleanups, exports, and plans."""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from clip_shared.config import get_settings
from clip_shared.db.base import utc_now
from clip_shared.db.models import (
    CaptionStyle,
    Clip,
    ClipCaption,
    ClipCleanup,
    ClipReframe,
    Export,
    ExportPreset,
    Plan,
    Transcript,
    TranscriptWord,
    Usage,
    User,
    UserPlan,
    Video,
)
from clip_shared.db.session import get_db
from clip_shared.media.captions import build_clip_captions_data
from clip_shared.media.cleanup import plan_clip_cleanup
from clip_shared.media.edl import EditDecisionList
from clip_shared.media.plan_limits import (
    PlanLimitExceededError,
    compute_params_snapshot_hash,
    enforce_export_plan_limits,
    get_user_plan_and_usage,
)
from clip_shared.pubsub.redis import subscribe_export_events_async
from clip_shared.schemas.auth import AuthenticatedUser
from clip_shared.schemas.exports import (
    CaptionStyleResponse,
    ClipCaptionsRegenerateRequest,
    ClipCaptionsResponse,
    ClipCaptionsUpdateRequest,
    ClipCleanupAnalyzeResponse,
    ClipCleanupResponse,
    ClipCleanupUpdateRequest,
    CreateExportRequest,
    DownloadUrlResponse,
    ExportPresetResponse,
    ExportResponse,
    PlanResponse,
    UserPlanMeResponse,
)
from clip_shared.storage.s3 import get_s3_client

router = APIRouter(tags=["exports"])
settings = get_settings()


# ---------------------------------------------------------------------------
# 1. Caption Styles & Export Presets & Plans
# ---------------------------------------------------------------------------

@router.get("/caption-styles", response_model=list[CaptionStyleResponse])
async def list_caption_styles(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all available subtitle presentation style packs."""
    stmt = select(CaptionStyle).order_by(CaptionStyle.name)
    res = await db.execute(stmt)
    styles = res.scalars().all()
    return styles


@router.get("/export-presets", response_model=list[ExportPresetResponse])
async def list_export_presets(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all platform-compliant export presets (TikTok, Reels, Shorts, Generic Vertical)."""
    stmt = select(ExportPreset).order_by(ExportPreset.name)
    res = await db.execute(stmt)
    presets = res.scalars().all()
    return presets


@router.get("/plans/me", response_model=UserPlanMeResponse)
async def get_my_plan(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user plan, feature limits, and monthly quota consumption."""
    # Find user plan
    stmt = select(UserPlan).where(UserPlan.user_id == user.id)
    res = await db.execute(stmt)
    u_plan = res.scalar_one_or_none()

    plan_key = u_plan.plan_key if u_plan else "free"
    period_start = u_plan.period_start if u_plan else datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0)

    p_stmt = select(Plan).where(Plan.key == plan_key)
    p_res = await db.execute(p_stmt)
    plan = p_res.scalar_one_or_none()
    if not plan:
        # Fallback default plan
        plan = Plan(
            key="free",
            name="Free Tier",
            monthly_minutes=30,
            export_watermark=True,
            max_export_height=1920,
            max_exports_per_month=10,
            features={"watermark": True, "max_resolution": "1080p"},
        )

    # Monthly source minutes used
    src_stmt = select(func.coalesce(func.sum(Usage.quantity), 0)).where(
        Usage.user_id == user.id,
        Usage.metric == "source_minutes",
        Usage.created_at >= period_start,
    )
    src_res = await db.execute(src_stmt)
    source_min_used = float(src_res.scalar() or 0.0)

    # Monthly exports used
    exp_stmt = select(func.count(Export.id)).where(
        Export.user_id == user.id,
        Export.status.in_(["queued", "rendering", "succeeded"]),
        Export.created_at >= period_start,
    )
    exp_res = await db.execute(exp_stmt)
    exports_used = int(exp_res.scalar() or 0)

    return UserPlanMeResponse(
        plan=PlanResponse.model_validate(plan),
        period_start=period_start,
        monthly_source_minutes_used=source_min_used,
        monthly_exports_used=exports_used,
        monthly_source_minutes_limit=plan.monthly_minutes,
        monthly_exports_limit=plan.max_exports_per_month,
        watermark_required=plan.export_watermark,
    )


# ---------------------------------------------------------------------------
# 2. Clip Captions
# ---------------------------------------------------------------------------

async def _get_clip_and_verify_ownership(clip_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> tuple[Clip, Video]:
    """Helper to verify clip and video ownership."""
    stmt = select(Clip, Video).join(Video, Clip.video_id == Video.id).where(Clip.id == clip_id, Video.user_id == user_id)
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "CLIP_NOT_FOUND", "message": "Clip not found."}},
        )
    return row[0], row[1]


@router.get("/clips/{clip_id}/captions", response_model=ClipCaptionsResponse)
async def get_clip_captions(
    clip_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get captions for a clip.
    If no captions record exists yet, automatically generates initial captions
    from the transcript words in SOURCE time and default style 'bold_pop'.
    """
    clip, video = await _get_clip_and_verify_ownership(clip_id, user.id, db)

    # Check existing caption record
    stmt = select(ClipCaption).where(ClipCaption.clip_id == clip.id).order_by(desc(ClipCaption.created_at))
    res = await db.execute(stmt)
    caption_rec = res.scalar_one_or_none()

    if caption_rec:
        return caption_rec

    # Generate initial captions from transcript
    t_stmt = select(Transcript).where(Transcript.video_id == video.id)
    t_res = await db.execute(t_stmt)
    transcript = t_res.scalar_one_or_none()

    raw_words = []
    if transcript:
        w_stmt = select(TranscriptWord).where(
            TranscriptWord.transcript_id == transcript.id,
            TranscriptWord.end_ms >= clip.start_ms,
            TranscriptWord.start_ms <= clip.end_ms,
        ).order_by(TranscriptWord.idx)
        w_res = await db.execute(w_stmt)
        for w in w_res.scalars().all():
            raw_words.append({
                "text": w.word,
                "start_ms": w.start_ms,
                "end_ms": w.end_ms,
                "speaker": w.speaker,
                "emphasis": False,
                "deleted": False,
            })

    words_data = build_clip_captions_data(
        words=raw_words,
        clip_start_ms=clip.start_ms,
        clip_end_ms=clip.end_ms,
        style_key="bold_pop",
        language=transcript.language if transcript else "en",
    )

    caption_rec = ClipCaption(
        id=uuid.uuid4(),
        clip_id=clip.id,
        version="v1",
        language=transcript.language if transcript else "en",
        words=words_data,
        style_key="bold_pop",
        style_overrides={},
        source="auto",
    )
    db.add(caption_rec)
    await db.commit()
    await db.refresh(caption_rec)
    return caption_rec


@router.put("/clips/{clip_id}/captions", response_model=ClipCaptionsResponse)
async def update_clip_captions(
    clip_id: uuid.UUID,
    payload: ClipCaptionsUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update captions for a clip (words text/timings, emphasis toggles, style_key, overrides).
    Validates monotonic ordering and boundaries.
    """
    clip, video = await _get_clip_and_verify_ownership(clip_id, user.id, db)

    # Validate words ordering & structure
    prev_end = 0
    for w in payload.words:
        if "text" not in w or "start_ms" not in w or "end_ms" not in w:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "INVALID_CAPTION_WORD", "message": "Caption words must contain text, start_ms, and end_ms."}},
            )
        start_ms = int(w["start_ms"])
        end_ms = int(w["end_ms"])
        if end_ms < start_ms:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "INVALID_WORD_TIMING", "message": f"Word end_ms ({end_ms}) cannot precede start_ms ({start_ms})."}},
            )

    stmt = select(ClipCaption).where(ClipCaption.clip_id == clip.id).order_by(desc(ClipCaption.created_at))
    res = await db.execute(stmt)
    caption_rec = res.scalar_one_or_none()

    if caption_rec:
        caption_rec.words = payload.words
        if payload.style_key is not None:
            caption_rec.style_key = payload.style_key
        if payload.style_overrides is not None:
            caption_rec.style_overrides = payload.style_overrides
        caption_rec.source = "manual"
    else:
        caption_rec = ClipCaption(
            id=uuid.uuid4(),
            clip_id=clip.id,
            version="v1",
            language="en",
            words=payload.words,
            style_key=payload.style_key or "bold_pop",
            style_overrides=payload.style_overrides or {},
            source="manual",
        )
        db.add(caption_rec)

    await db.commit()
    await db.refresh(caption_rec)
    return caption_rec


@router.post("/clips/{clip_id}/captions/regenerate", response_model=ClipCaptionsResponse)
async def regenerate_clip_captions(
    clip_id: uuid.UUID,
    payload: ClipCaptionsRegenerateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Re-chunk and re-highlight keyword emphasis from the base transcript for a clip.
    """
    clip, video = await _get_clip_and_verify_ownership(clip_id, user.id, db)

    t_stmt = select(Transcript).where(Transcript.video_id == video.id)
    t_res = await db.execute(t_stmt)
    transcript = t_res.scalar_one_or_none()

    raw_words = []
    if transcript:
        w_stmt = select(TranscriptWord).where(
            TranscriptWord.transcript_id == transcript.id,
            TranscriptWord.end_ms >= clip.start_ms,
            TranscriptWord.start_ms <= clip.end_ms,
        ).order_by(TranscriptWord.idx)
        w_res = await db.execute(w_stmt)
        for w in w_res.scalars().all():
            raw_words.append({
                "text": w.word,
                "start_ms": w.start_ms,
                "end_ms": w.end_ms,
                "speaker": w.speaker,
                "emphasis": False,
                "deleted": False,
            })

    style_key = payload.style_key or "bold_pop"
    words_data = build_clip_captions_data(
        words=raw_words,
        clip_start_ms=clip.start_ms,
        clip_end_ms=clip.end_ms,
        style_key=style_key,
        language=payload.language or (transcript.language if transcript else "en"),
    )

    stmt = select(ClipCaption).where(ClipCaption.clip_id == clip.id).order_by(desc(ClipCaption.created_at))
    res = await db.execute(stmt)
    caption_rec = res.scalar_one_or_none()

    if caption_rec:
        caption_rec.words = words_data
        caption_rec.style_key = style_key
        caption_rec.source = "auto"
    else:
        caption_rec = ClipCaption(
            id=uuid.uuid4(),
            clip_id=clip.id,
            version="v1",
            language=transcript.language if transcript else "en",
            words=words_data,
            style_key=style_key,
            style_overrides={},
            source="auto",
        )
        db.add(caption_rec)

    await db.commit()
    await db.refresh(caption_rec)
    return caption_rec


# ---------------------------------------------------------------------------
# 3. Filler & Silence Cleanup
# ---------------------------------------------------------------------------

@router.get("/clips/{clip_id}/cleanup", response_model=ClipCleanupResponse)
async def get_clip_cleanup(
    clip_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get active cleanup configuration and individual removal intervals for a clip."""
    clip, video = await _get_clip_and_verify_ownership(clip_id, user.id, db)

    stmt = select(ClipCleanup).where(ClipCleanup.clip_id == clip.id)
    res = await db.execute(stmt)
    cleanup_rec = res.scalar_one_or_none()

    if cleanup_rec:
        return cleanup_rec

    # Initialize default cleanup record
    cleanup_rec = ClipCleanup(
        id=uuid.uuid4(),
        clip_id=clip.id,
        version="v1",
        options={
            "remove_fillers": True,
            "remove_silence": True,
            "max_silence_ms": 700,
            "target_silence_ms": 250,
            "crossfade_ms": 40,
            "snap_cuts": True,
        },
        removals=[],
    )
    db.add(cleanup_rec)
    await db.commit()
    await db.refresh(cleanup_rec)
    return cleanup_rec


@router.put("/clips/{clip_id}/cleanup", response_model=ClipCleanupResponse)
async def update_clip_cleanup(
    clip_id: uuid.UUID,
    payload: ClipCleanupUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update cleanup options and individual removal intervals for a clip."""
    clip, video = await _get_clip_and_verify_ownership(clip_id, user.id, db)

    stmt = select(ClipCleanup).where(ClipCleanup.clip_id == clip.id)
    res = await db.execute(stmt)
    cleanup_rec = res.scalar_one_or_none()

    if not cleanup_rec:
        cleanup_rec = ClipCleanup(
            id=uuid.uuid4(),
            clip_id=clip.id,
            version="v1",
            options=payload.options or {
                "remove_fillers": True,
                "remove_silence": True,
                "max_silence_ms": 700,
                "target_silence_ms": 250,
                "crossfade_ms": 40,
                "snap_cuts": True,
            },
            removals=payload.removals or [],
        )
        db.add(cleanup_rec)
    else:
        if payload.options is not None:
            cleanup_rec.options = {**cleanup_rec.options, **payload.options}
        if payload.removals is not None:
            cleanup_rec.removals = payload.removals

    await db.commit()
    await db.refresh(cleanup_rec)
    return cleanup_rec


@router.post("/clips/{clip_id}/cleanup/analyze", response_model=ClipCleanupAnalyzeResponse)
async def analyze_clip_cleanup(
    clip_id: uuid.UUID,
    options: dict[str, Any] | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Run filler and silence detection analysis for a clip.
    Returns proposed removals, duration savings, and resulting EDL keep segments.
    Does not persist changes to the database.
    """
    clip, video = await _get_clip_and_verify_ownership(clip_id, user.id, db)

    # Fetch transcript words
    t_stmt = select(Transcript).where(Transcript.video_id == video.id)
    t_res = await db.execute(t_stmt)
    transcript = t_res.scalar_one_or_none()

    words_list = []
    if transcript:
        w_stmt = select(TranscriptWord).where(
            TranscriptWord.transcript_id == transcript.id,
            TranscriptWord.end_ms >= clip.start_ms,
            TranscriptWord.start_ms <= clip.end_ms,
        ).order_by(TranscriptWord.idx)
        w_res = await db.execute(w_stmt)
        for w in w_res.scalars().all():
            words_list.append({
                "text": w.word,
                "start_ms": w.start_ms,
                "end_ms": w.end_ms,
                "speaker": w.speaker,
            })

    cleanup_res = plan_clip_cleanup(
        clip_start_ms=clip.start_ms,
        clip_end_ms=clip.end_ms,
        words=words_list,
        options=options,
        max_removal_ratio=0.25,
    )

    return ClipCleanupAnalyzeResponse(
        clip_start_ms=cleanup_res.clip_start_ms,
        clip_end_ms=cleanup_res.clip_end_ms,
        original_duration_ms=cleanup_res.original_duration_ms,
        clean_duration_ms=cleanup_res.clean_duration_ms,
        saved_ms=cleanup_res.saved_ms,
        saved_seconds=round(cleanup_res.saved_ms / 1000.0, 2),
        cut_count=cleanup_res.cut_count,
        filler_count=cleanup_res.filler_count,
        silence_count=cleanup_res.silence_count,
        savings_ratio=cleanup_res.savings_ratio,
        options=cleanup_res.options,
        removals=[r.__dict__ for r in cleanup_res.removals],
        keep_segments=[s.__dict__ for s in cleanup_res.edl.keep_segments],
    )


# ---------------------------------------------------------------------------
# 4. Exports
# ---------------------------------------------------------------------------

@router.post("/clips/{clip_id}/exports", response_model=list[ExportResponse])
async def create_clip_export(
    clip_id: uuid.UUID,
    payload: CreateExportRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create export job(s) for a clip.
    Supports single `preset_key` or list of `presets`.
    Server-side enforces plan limits and watermark.
    Supports idempotency caching by params_snapshot hash.
    Dispatches Celery background worker render task.
    """
    clip, video = await _get_clip_and_verify_ownership(clip_id, user.id, db)

    # 1. Enforce Plan Limits
    # Get user plan
    up_stmt = select(UserPlan).where(UserPlan.user_id == user.id)
    up_res = await db.execute(up_stmt)
    user_plan = up_res.scalar_one_or_none()
    plan_key = user_plan.plan_key if user_plan else "free"
    period_start = user_plan.period_start if user_plan else datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0)

    p_stmt = select(Plan).where(Plan.key == plan_key)
    p_res = await db.execute(p_stmt)
    plan = p_res.scalar_one_or_none()
    if not plan:
        plan = Plan(
            key="free",
            name="Free Tier",
            monthly_minutes=30,
            export_watermark=True,
            max_export_height=1920,
            max_exports_per_month=10,
            features={"watermark": True},
        )

    # Check monthly exports limit
    cnt_stmt = select(func.count(Export.id)).where(
        Export.user_id == user.id,
        Export.status.in_(["queued", "rendering", "succeeded"]),
        Export.created_at >= period_start,
    )
    cnt_res = await db.execute(cnt_stmt)
    exports_count = int(cnt_res.scalar() or 0)

    presets_to_export = payload.presets if payload.presets else [payload.preset_key or "tiktok"]

    if exports_count + len(presets_to_export) > plan.max_exports_per_month:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": {
                    "code": "PLAN_LIMIT_EXCEEDED",
                    "message": f"Monthly export limit ({plan.max_exports_per_month}) reached for plan '{plan.name}'. Please upgrade to export more clips.",
                    "limit_type": "max_exports_per_month",
                    "limit_value": plan.max_exports_per_month,
                    "current_value": exports_count,
                    "reset_date": period_start.strftime("%Y-%m-%d"),
                }
            },
        )

    # Resolve active captions version & style
    c_stmt = select(ClipCaption).where(ClipCaption.clip_id == clip.id).order_by(desc(ClipCaption.created_at))
    c_res = await db.execute(c_stmt)
    captions_rec = c_res.scalar_one_or_none()
    caption_version = captions_rec.version if captions_rec else "v1"
    style_key = payload.style_key or (captions_rec.style_key if captions_rec else "bold_pop")

    # Resolve cleanup version
    cl_stmt = select(ClipCleanup).where(ClipCleanup.clip_id == clip.id)
    cl_res = await db.execute(cl_stmt)
    cleanup_rec = cl_res.scalar_one_or_none()
    cleanup_version = cleanup_rec.version if cleanup_rec else "v1"

    # Resolve reframe id
    rf_stmt = select(ClipReframe).where(ClipReframe.clip_id == clip.id).order_by(desc(ClipReframe.created_at))
    rf_res = await db.execute(rf_stmt)
    reframe_rec = rf_res.scalar_one_or_none()
    reframe_id = str(reframe_rec.id) if reframe_rec else "default"

    created_exports: list[Export] = []

    for p_key in presets_to_export:
        params_snapshot = {
            "clip_id": str(clip.id),
            "preset": p_key,
            "style_key": style_key,
            "caption_version": caption_version,
            "cleanup_version": cleanup_version,
            "reframe_id": reframe_id,
            "watermark": bool(plan.export_watermark),
        }
        params_hash = compute_params_snapshot_hash(params_snapshot)
        params_snapshot["hash"] = params_hash

        # Idempotency check: if existing export matches and not force, return existing
        if not payload.force:
            exist_stmt = select(Export).where(
                Export.clip_id == clip.id,
                Export.preset_key == p_key,
                Export.status.in_(["queued", "rendering", "succeeded"]),
            ).order_by(desc(Export.created_at))
            exist_res = await db.execute(exist_stmt)
            existing = exist_res.scalar_one_or_none()
            if existing and existing.params_snapshot.get("hash") == params_hash:
                created_exports.append(existing)
                continue

        # Create new export record
        export_id = uuid.uuid4()
        export_rec = Export(
            id=export_id,
            clip_id=clip.id,
            user_id=user.id,
            status="queued",
            preset_key=p_key,
            params_snapshot=params_snapshot,
        )
        db.add(export_rec)
        await db.commit()
        await db.refresh(export_rec)

        # Dispatch Celery render task
        from worker.tasks.render import render_export_task
        render_export_task.delay(str(export_id))

        created_exports.append(export_rec)

    # Generate download URLs where ready
    s3 = get_s3_client()
    responses: list[ExportResponse] = []
    for exp in created_exports:
        resp = ExportResponse.model_validate(exp)
        if exp.storage_key and exp.status == "succeeded":
            try:
                resp.download_url = s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": settings.S3_BUCKET_NAME, "Key": exp.storage_key},
                    ExpiresIn=settings.PRESIGNED_URL_EXPIRY_SECONDS,
                )
            except Exception:
                pass
        responses.append(resp)

    return responses


@router.get("/exports/{export_id}", response_model=ExportResponse)
async def get_export(
    export_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get export status and details by export ID."""
    stmt = select(Export).where(Export.id == export_id, Export.user_id == user.id)
    res = await db.execute(stmt)
    export_rec = res.scalar_one_or_none()
    if not export_rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "EXPORT_NOT_FOUND", "message": "Export not found."}},
        )

    resp = ExportResponse.model_validate(export_rec)
    if export_rec.storage_key and export_rec.status == "succeeded":
        s3 = get_s3_client()
        try:
            resp.download_url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.S3_BUCKET_NAME, "Key": export_rec.storage_key},
                ExpiresIn=settings.PRESIGNED_URL_EXPIRY_SECONDS,
            )
        except Exception:
            pass

    return resp


@router.get("/clips/{clip_id}/exports", response_model=list[ExportResponse])
async def list_clip_exports(
    clip_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all exports created for a clip."""
    clip, video = await _get_clip_and_verify_ownership(clip_id, user.id, db)

    stmt = select(Export).where(Export.clip_id == clip.id, Export.user_id == user.id).order_by(desc(Export.created_at))
    res = await db.execute(stmt)
    exports = res.scalars().all()

    s3 = get_s3_client()
    responses: list[ExportResponse] = []
    for exp in exports:
        resp = ExportResponse.model_validate(exp)
        if exp.storage_key and exp.status == "succeeded":
            try:
                resp.download_url = s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": settings.S3_BUCKET_NAME, "Key": exp.storage_key},
                    ExpiresIn=settings.PRESIGNED_URL_EXPIRY_SECONDS,
                )
            except Exception:
                pass
        responses.append(resp)

    return responses


@router.get("/exports/{export_id}/download-url", response_model=DownloadUrlResponse)
async def get_export_download_url(
    export_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a presigned S3 download URL for a completed export."""
    stmt = select(Export).where(Export.id == export_id, Export.user_id == user.id)
    res = await db.execute(stmt)
    export_rec = res.scalar_one_or_none()

    if not export_rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "EXPORT_NOT_FOUND", "message": "Export not found."}},
        )

    if export_rec.status != "succeeded" or not export_rec.storage_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "EXPORT_NOT_READY", "message": f"Export status is '{export_rec.status}' and not ready for download."}},
        )

    s3 = get_s3_client()
    download_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_NAME, "Key": export_rec.storage_key},
        ExpiresIn=settings.PRESIGNED_URL_EXPIRY_SECONDS,
    )

    return DownloadUrlResponse(
        export_id=export_rec.id,
        download_url=download_url,
        expires_in_seconds=settings.PRESIGNED_URL_EXPIRY_SECONDS,
    )


@router.get("/exports/{export_id}/events")
async def stream_export_events(
    export_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Server-Sent Events (SSE) stream for real-time export progress updates."""
    stmt = select(Export).where(Export.id == export_id, Export.user_id == user.id)
    res = await db.execute(stmt)
    export_rec = res.scalar_one_or_none()
    if not export_rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "EXPORT_NOT_FOUND", "message": "Export not found."}},
        )

    async def event_generator():
        # Yield initial state
        initial_payload = {
            "type": "export_state",
            "export_id": str(export_id),
            "status": export_rec.status,
            "progress": 100.0 if export_rec.status == "succeeded" else (5.0 if export_rec.status == "rendering" else 0.0),
        }
        yield f"data: {json.dumps(initial_payload)}\n\n"

        if export_rec.status in ("succeeded", "failed", "cancelled"):
            return

        async for event in subscribe_export_events_async(str(export_id)):
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") in ("export_ready", "export_failed"):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
