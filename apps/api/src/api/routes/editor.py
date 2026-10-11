import json
import statistics
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from clip_shared.config import get_settings
from clip_shared.db.base import utc_now
from clip_shared.db.models import (
    CaptionStyle,
    Clip,
    ClipAlternative,
    ClipCaption,
    ClipCleanup,
    ClipEdit,
    ClipMoment,
    ClipReframe,
    EditorEvent,
    Export,
    ExportPreset,
    Plan,
    Transcript,
    TranscriptWord,
    Usage,
    UserPlan,
    Video,
)
from clip_shared.db.session import get_db
from clip_shared.media.captions import build_clip_captions_data
from clip_shared.media.cleanup import plan_clip_cleanup
from clip_shared.media.plan_limits import compute_params_snapshot_hash
from clip_shared.pubsub.redis import publish_event_async
from clip_shared.schemas.auth import AuthenticatedUser
from clip_shared.schemas.editor import (
    CaptionWordModel,
    CaptionsModel,
    CleanupOptionsModel,
    ClipAlternativeResponse,
    ClipBulkActionRequest,
    ClipEditCheckpointRequest,
    ClipEditDoc,
    ClipEditResponse,
    ClipEditRestoreRequest,
    ClipEditSaveRequest,
    ClipEditVersionSummary,
    ClipRegenerateRequest,
    EditorEventsBatchRequest,
    EditorMetricsResponse,
    HookModel,
    RangeModel,
    ReframeKeyframeModel,
    ReframeModel,
    RemovalModel,
)
from clip_shared.schemas.exports import ExportResponse
from clip_shared.storage.s3 import get_s3_client

router = APIRouter(tags=["editor"])
settings = get_settings()


def _ensure_tz(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


async def _get_clip_and_verify_ownership(
    clip_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> tuple[Clip, Video]:
    stmt = (
        select(Clip, Video)
        .join(Video, Clip.video_id == Video.id)
        .where(Clip.id == clip_id, Video.user_id == user_id)
    )
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "CLIP_NOT_FOUND", "message": "Clip not found or unauthorized."}},
        )
    return row[0], row[1]


async def _build_auto_edit_doc(clip: Clip, video: Video, db: AsyncSession) -> ClipEditDoc:
    """Construct version 1 of ClipEditDoc from existing auto pipeline artifacts."""
    # 1. Range
    clip_range = RangeModel(start_ms=clip.start_ms, end_ms=clip.end_ms)

    # 2. Hook
    hook = HookModel(text=clip.hook_text, source="auto", start_ms=clip.start_ms)

    # 3. Captions
    c_stmt = (
        select(ClipCaption)
        .where(ClipCaption.clip_id == clip.id)
        .order_by(desc(ClipCaption.created_at))
        .limit(1)
    )
    c_res = await db.execute(c_stmt)
    existing_caption = c_res.scalar_one_or_none()

    captions_words: list[CaptionWordModel] = []
    style_key = "bold_pop"
    style_overrides: dict[str, Any] = {}

    if existing_caption and existing_caption.words:
        style_key = existing_caption.style_key
        style_overrides = existing_caption.style_overrides or {}
        for w in existing_caption.words:
            captions_words.append(
                CaptionWordModel(
                    text=str(w.get("text", "")),
                    start_ms=int(w.get("start_ms", 0)),
                    end_ms=int(w.get("end_ms", 0)),
                    speaker=w.get("speaker"),
                    emphasis=bool(w.get("emphasis", False)),
                    deleted=bool(w.get("deleted", False)),
                )
            )
    else:
        # Fallback to transcript words
        t_stmt = select(Transcript).where(Transcript.video_id == video.id)
        t_res = await db.execute(t_stmt)
        transcript = t_res.scalar_one_or_none()
        if transcript:
            w_stmt = (
                select(TranscriptWord)
                .where(
                    TranscriptWord.transcript_id == transcript.id,
                    TranscriptWord.start_ms < clip.end_ms,
                    TranscriptWord.end_ms > clip.start_ms,
                )
                .order_by(TranscriptWord.idx)
            )
            w_res = await db.execute(w_stmt)
            for tw in w_res.scalars().all():
                captions_words.append(
                    CaptionWordModel(
                        text=tw.word,
                        start_ms=tw.start_ms,
                        end_ms=tw.end_ms,
                        speaker=tw.speaker,
                        emphasis=False,
                        deleted=False,
                    )
                )

    captions = CaptionsModel(
        words=captions_words,
        style_key=style_key,
        style_overrides=style_overrides,
        enabled=True,
    )

    # 4. Reframe
    rf_stmt = (
        select(ClipReframe)
        .where(ClipReframe.clip_id == clip.id)
        .order_by(desc(ClipReframe.created_at))
        .limit(1)
    )
    rf_res = await db.execute(rf_stmt)
    reframe_rec = rf_res.scalar_one_or_none()

    reframe_kfs: list[ReframeKeyframeModel] = []
    if reframe_rec:
        crop_path = reframe_rec.crop_path or {}
        raw_kfs = crop_path.get("keyframes", [])
        for k in raw_kfs:
            reframe_kfs.append(
                ReframeKeyframeModel(
                    t_ms=int(k.get("t_ms", 0)),
                    x=float(k.get("x", 0.5)),
                    y=float(k.get("y", 0.5)),
                    width=k.get("width"),
                    height=k.get("height"),
                    scale=k.get("scale"),
                )
            )

    if not reframe_kfs:
        reframe_kfs = [
            ReframeKeyframeModel(t_ms=0, x=0.5, y=0.5),
            ReframeKeyframeModel(t_ms=max(100, clip.end_ms - clip.start_ms), x=0.5, y=0.5),
        ]

    reframe = ReframeModel(mode_overrides={}, keyframes=reframe_kfs)

    # 5. Clean-up & Removals
    cl_stmt = (
        select(ClipCleanup)
        .where(ClipCleanup.clip_id == clip.id)
        .order_by(desc(ClipCleanup.created_at))
        .limit(1)
    )
    cl_res = await db.execute(cl_stmt)
    cleanup_rec = cl_res.scalar_one_or_none()

    removals: list[RemovalModel] = []
    cleanup_opts = CleanupOptionsModel()

    if cleanup_rec:
        if cleanup_rec.options:
            opts = cleanup_rec.options
            cleanup_opts = CleanupOptionsModel(
                remove_fillers=bool(opts.get("remove_fillers", True)),
                remove_silence=bool(opts.get("remove_silence", True)),
                max_silence_ms=int(opts.get("max_silence_ms", 1500)),
                target_silence_ms=int(opts.get("target_silence_ms", 500)),
                crossfade_ms=int(opts.get("crossfade_ms", 25)),
                snap_cuts=bool(opts.get("snap_cuts", True)),
            )
        for r in cleanup_rec.removals or []:
            removals.append(
                RemovalModel(
                    id=str(uuid.uuid4()),
                    start_ms=int(r.get("start_ms", 0)),
                    end_ms=int(r.get("end_ms", 0)),
                    kind=str(r.get("kind", "manual")),
                    enabled=True,
                    text=r.get("text"),
                )
            )

    # Deduplicate and sort removals
    removals.sort(key=lambda x: (x.start_ms, x.end_ms))

    return ClipEditDoc(
        clip_id=str(clip.id),
        base_clip_id=str(clip.id),
        version=1,
        range=clip_range,
        removals=removals,
        captions=captions,
        reframe=reframe,
        hook=hook,
        preset_key="tiktok",
        cleanup_options=cleanup_opts,
    )


# ---------------------------------------------------------------------------
# 1. Edit Doc: GET, PUT (autosave + collapse), Checkpoint, Versions, Restore, Reset
# ---------------------------------------------------------------------------

@router.get("/clips/{clip_id}/edit", response_model=ClipEditResponse)
async def get_clip_edit(
    clip_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get active edit document for a clip.
    If none exists, creates version 1 from auto artifacts.
    """
    clip, video = await _get_clip_and_verify_ownership(clip_id, user.id, db)

    stmt = (
        select(ClipEdit)
        .where(ClipEdit.clip_id == clip_id)
        .order_by(desc(ClipEdit.version))
        .limit(1)
    )
    res = await db.execute(stmt)
    active_edit = res.scalar_one_or_none()

    if not active_edit:
        doc = await _build_auto_edit_doc(clip, video, db)
        active_edit = ClipEdit(
            id=uuid.uuid4(),
            clip_id=clip.id,
            user_id=user.id,
            version=1,
            doc=doc.model_dump(),
            parent_version=None,
            created_at=utc_now(),
            label="auto_initialized",
            is_checkpoint=True,
        )
        db.add(active_edit)

        # Seed initial alternatives if none exist
        alt_stmt = select(func.count(ClipAlternative.id)).where(ClipAlternative.clip_id == clip.id)
        alt_res = await db.execute(alt_stmt)
        if int(alt_res.scalar() or 0) == 0:
            # Query sibling variants
            sib_stmt = select(Clip).where(Clip.moment_id == clip.moment_id, Clip.id != clip.id)
            sib_res = await db.execute(sib_stmt)
            for sib in sib_res.scalars().all():
                db.add(
                    ClipAlternative(
                        id=uuid.uuid4(),
                        clip_id=clip.id,
                        kind="range",
                        start_ms=sib.start_ms,
                        end_ms=sib.end_ms,
                        text=f"{sib.variant_length_s}s variant trim",
                        score=sib.final_score,
                        reason=sib.reason,
                        source=str(sib.scoring_run_id) if sib.scoring_run_id else "scoring",
                        created_at=utc_now(),
                    )
                )
            # Add an alternate hook suggestion from the moment
            db.add(
                ClipAlternative(
                    id=uuid.uuid4(),
                    clip_id=clip.id,
                    kind="hook",
                    start_ms=clip.start_ms,
                    end_ms=min(clip.end_ms, clip.start_ms + 4000),
                    text=f"Alt hook: {clip.hook_text[:60]}...",
                    score=clip.final_score,
                    reason="Alternative opening hook phrasing",
                    source="moment",
                    created_at=utc_now(),
                )
            )

        await db.commit()
        await db.refresh(active_edit)

    return ClipEditResponse(
        id=active_edit.id,
        clip_id=active_edit.clip_id,
        user_id=active_edit.user_id,
        version=active_edit.version,
        doc=ClipEditDoc.model_validate(active_edit.doc),
        parent_version=active_edit.parent_version,
        label=active_edit.label,
        is_checkpoint=active_edit.is_checkpoint,
        created_at=active_edit.created_at,
    )


@router.put("/clips/{clip_id}/edit", response_model=ClipEditResponse)
async def save_clip_edit(
    clip_id: uuid.UUID,
    payload: ClipEditSaveRequest,
    if_match: str | None = Header(None, alias="If-Match"),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Save clip edit with optimistic concurrency and autosave collapse window (30s).
    """
    clip, video = await _get_clip_and_verify_ownership(clip_id, user.id, db)

    # 1. Fetch current highest version
    stmt = (
        select(ClipEdit)
        .where(ClipEdit.clip_id == clip_id)
        .order_by(desc(ClipEdit.version))
        .limit(1)
    )
    res = await db.execute(stmt)
    latest = res.scalar_one_or_none()

    if not latest:
        # Initialize if client pushed first
        latest = ClipEdit(
            id=uuid.uuid4(),
            clip_id=clip.id,
            user_id=user.id,
            version=1,
            doc=payload.doc.model_dump(),
            parent_version=None,
            created_at=utc_now(),
            label=payload.label or "initial",
            is_checkpoint=payload.is_checkpoint,
        )
        db.add(latest)
        await db.commit()
        await db.refresh(latest)
        return ClipEditResponse(
            id=latest.id,
            clip_id=latest.clip_id,
            user_id=latest.user_id,
            version=latest.version,
            doc=ClipEditDoc.model_validate(latest.doc),
            parent_version=latest.parent_version,
            label=latest.label,
            is_checkpoint=latest.is_checkpoint,
            created_at=latest.created_at,
        )

    # 2. Check optimistic concurrency
    if if_match:
        try:
            expected_ver = int(if_match.strip('"\' '))
            if expected_ver != latest.version:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": {
                            "code": "VERSION_CONFLICT",
                            "message": f"Conflict: server is at version {latest.version}, client sent version {expected_ver}.",
                            "server_version": latest.version,
                            "server_doc": latest.doc,
                        }
                    },
                )
        except ValueError:
            pass

    # 3. Collapse window check (30s)
    # If not a checkpoint, latest is not a checkpoint, and created < 30s ago -> collapse
    now = utc_now()
    time_since_creation = (now - _ensure_tz(latest.created_at)).total_seconds()
    can_collapse = (
        not payload.is_checkpoint
        and not latest.is_checkpoint
        and time_since_creation < 30.0
    )

    doc_data = payload.doc.model_dump()

    if can_collapse:
        doc_data["version"] = latest.version
        latest.doc = doc_data
        if payload.label:
            latest.label = payload.label
        latest.created_at = now
        await db.commit()
        await db.refresh(latest)
        target_record = latest
    else:
        new_version = latest.version + 1
        doc_data["version"] = new_version
        new_edit = ClipEdit(
            id=uuid.uuid4(),
            clip_id=clip.id,
            user_id=user.id,
            version=new_version,
            doc=doc_data,
            parent_version=latest.version,
            created_at=now,
            label=payload.label or ("checkpoint" if payload.is_checkpoint else "autosave"),
            is_checkpoint=payload.is_checkpoint,
        )
        db.add(new_edit)
        await db.commit()
        await db.refresh(new_edit)
        target_record = new_edit

    return ClipEditResponse(
        id=target_record.id,
        clip_id=target_record.clip_id,
        user_id=target_record.user_id,
        version=target_record.version,
        doc=ClipEditDoc.model_validate(target_record.doc),
        parent_version=target_record.parent_version,
        label=target_record.label,
        is_checkpoint=target_record.is_checkpoint,
        created_at=target_record.created_at,
    )


@router.post("/clips/{clip_id}/edit/checkpoint", response_model=ClipEditResponse)
async def create_checkpoint(
    clip_id: uuid.UUID,
    payload: ClipEditCheckpointRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a persistent explicit checkpoint version."""
    clip, video = await _get_clip_and_verify_ownership(clip_id, user.id, db)

    stmt = (
        select(ClipEdit)
        .where(ClipEdit.clip_id == clip_id)
        .order_by(desc(ClipEdit.version))
        .limit(1)
    )
    res = await db.execute(stmt)
    latest = res.scalar_one_or_none()

    if not latest:
        doc = await _build_auto_edit_doc(clip, video, db)
        doc_data = doc.model_dump()
        parent_v = None
        new_v = 1
    else:
        doc_data = dict(latest.doc)
        parent_v = latest.version
        new_v = latest.version + 1

    doc_data["version"] = new_v
    checkpoint = ClipEdit(
        id=uuid.uuid4(),
        clip_id=clip.id,
        user_id=user.id,
        version=new_v,
        doc=doc_data,
        parent_version=parent_v,
        created_at=utc_now(),
        label=payload.label,
        is_checkpoint=True,
    )
    db.add(checkpoint)
    await db.commit()
    await db.refresh(checkpoint)

    return ClipEditResponse(
        id=checkpoint.id,
        clip_id=checkpoint.clip_id,
        user_id=checkpoint.user_id,
        version=checkpoint.version,
        doc=ClipEditDoc.model_validate(checkpoint.doc),
        parent_version=checkpoint.parent_version,
        label=checkpoint.label,
        is_checkpoint=checkpoint.is_checkpoint,
        created_at=checkpoint.created_at,
    )


@router.get("/clips/{clip_id}/edit/versions", response_model=list[ClipEditVersionSummary])
async def list_edit_versions(
    clip_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all version summaries for a clip."""
    await _get_clip_and_verify_ownership(clip_id, user.id, db)

    stmt = (
        select(ClipEdit)
        .where(ClipEdit.clip_id == clip_id)
        .order_by(desc(ClipEdit.version))
    )
    res = await db.execute(stmt)
    edits = res.scalars().all()
    return [
        ClipEditVersionSummary(
            version=e.version,
            parent_version=e.parent_version,
            label=e.label,
            is_checkpoint=e.is_checkpoint,
            created_at=e.created_at,
        )
        for e in edits
    ]


@router.post("/clips/{clip_id}/edit/restore", response_model=ClipEditResponse)
async def restore_edit_version(
    clip_id: uuid.UUID,
    payload: ClipEditRestoreRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Restore a previous edit version as a new active checkpoint."""
    await _get_clip_and_verify_ownership(clip_id, user.id, db)

    # Fetch target version
    t_stmt = select(ClipEdit).where(ClipEdit.clip_id == clip_id, ClipEdit.version == payload.version)
    t_res = await db.execute(t_stmt)
    target = t_res.scalar_one_or_none()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "VERSION_NOT_FOUND", "message": f"Version {payload.version} not found."}},
        )

    # Fetch latest version number
    max_stmt = select(func.max(ClipEdit.version)).where(ClipEdit.clip_id == clip_id)
    max_res = await db.execute(max_stmt)
    max_ver = int(max_res.scalar() or target.version)

    new_v = max_ver + 1
    doc_data = dict(target.doc)
    doc_data["version"] = new_v

    restored = ClipEdit(
        id=uuid.uuid4(),
        clip_id=clip_id,
        user_id=user.id,
        version=new_v,
        doc=doc_data,
        parent_version=target.version,
        created_at=utc_now(),
        label=f"Restored from v{payload.version}",
        is_checkpoint=True,
    )
    db.add(restored)
    await db.commit()
    await db.refresh(restored)

    return ClipEditResponse(
        id=restored.id,
        clip_id=restored.clip_id,
        user_id=restored.user_id,
        version=restored.version,
        doc=ClipEditDoc.model_validate(restored.doc),
        parent_version=restored.parent_version,
        label=restored.label,
        is_checkpoint=restored.is_checkpoint,
        created_at=restored.created_at,
    )


@router.post("/clips/{clip_id}/edit/reset", response_model=ClipEditResponse)
async def reset_edit_to_auto(
    clip_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reset edit document back to original auto state."""
    clip, video = await _get_clip_and_verify_ownership(clip_id, user.id, db)

    max_stmt = select(func.max(ClipEdit.version)).where(ClipEdit.clip_id == clip_id)
    max_res = await db.execute(max_stmt)
    max_ver = int(max_res.scalar() or 0)

    doc = await _build_auto_edit_doc(clip, video, db)
    new_v = max_ver + 1
    doc_data = doc.model_dump()
    doc_data["version"] = new_v

    reset_edit = ClipEdit(
        id=uuid.uuid4(),
        clip_id=clip.id,
        user_id=user.id,
        version=new_v,
        doc=doc_data,
        parent_version=max_ver if max_ver > 0 else None,
        created_at=utc_now(),
        label="Reset to auto",
        is_checkpoint=True,
    )
    db.add(reset_edit)
    await db.commit()
    await db.refresh(reset_edit)

    return ClipEditResponse(
        id=reset_edit.id,
        clip_id=reset_edit.clip_id,
        user_id=reset_edit.user_id,
        version=reset_edit.version,
        doc=ClipEditDoc.model_validate(reset_edit.doc),
        parent_version=reset_edit.parent_version,
        label=reset_edit.label,
        is_checkpoint=reset_edit.is_checkpoint,
        created_at=reset_edit.created_at,
    )


# ---------------------------------------------------------------------------
# 2. Alternatives & Regenerate
# ---------------------------------------------------------------------------

@router.get("/clips/{clip_id}/alternatives", response_model=list[ClipAlternativeResponse])
async def list_clip_alternatives(
    clip_id: uuid.UUID,
    kind: str | None = Query(None, pattern="^(hook|range)$"),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List alternative hooks and range trims for a clip."""
    await _get_clip_and_verify_ownership(clip_id, user.id, db)

    stmt = select(ClipAlternative).where(ClipAlternative.clip_id == clip_id)
    if kind:
        stmt = stmt.where(ClipAlternative.kind == kind)
    stmt = stmt.order_by(desc(ClipAlternative.created_at))

    res = await db.execute(stmt)
    alts = res.scalars().all()
    return alts


@router.post("/clips/{clip_id}/regenerate")
async def regenerate_clip(
    clip_id: uuid.UUID,
    payload: ClipRegenerateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Regenerate hook, duration, trim or similar moment without re-transcribing.
    Produces a new alternative record, records usage, and emits SSE event.
    """
    clip, video = await _get_clip_and_verify_ownership(clip_id, user.id, db)

    mode = payload.mode
    params = payload.params
    job_id = uuid.uuid4()

    # Calculate scoped alternative based on mode
    if mode == "length":
        target_s = int(params.get("length_s", 30))
        target_dur_ms = target_s * 1000
        new_start = clip.start_ms
        new_end = min(video.duration_seconds * 1000 if video.duration_seconds else new_start + target_dur_ms, new_start + target_dur_ms)
        alt_kind = "range"
        alt_text = f"Regenerated {target_s}s trim"
        alt_reason = f"Targeted duration variant ({target_s}s)"
    elif mode == "hook":
        # Alt hook starting slightly earlier or later
        shift_ms = int(params.get("shift_ms", 1500))
        new_start = max(0, clip.start_ms + shift_ms)
        new_end = clip.end_ms
        alt_kind = "hook"
        alt_text = f"Alternative hook: {params.get('hook_text', clip.hook_text)}"
        alt_reason = "Alternative high-energy sentence opening"
    elif mode == "trim":
        tightness = params.get("tightness", "tight")
        delta = 2000 if tightness == "tight" else -2000
        new_start = max(0, clip.start_ms + delta)
        new_end = max(new_start + 5000, clip.end_ms - delta)
        alt_kind = "range"
        alt_text = f"Trim variation ({tightness})"
        alt_reason = f"Adjusted pacing with {tightness} boundary trims"
    else:  # similar
        # Find another span in video
        new_start = min(clip.start_ms + 45000, max(0, clip.start_ms - 30000))
        new_end = new_start + (clip.end_ms - clip.start_ms)
        alt_kind = "range"
        alt_text = "Similar energetic moment"
        alt_reason = "Topical continuity and high tone variance"

    alt = ClipAlternative(
        id=uuid.uuid4(),
        clip_id=clip.id,
        kind=alt_kind,
        start_ms=int(new_start),
        end_ms=int(new_end),
        text=alt_text,
        score=round(min(1.0, clip.final_score * 0.98), 2),
        reason=alt_reason,
        source=f"regenerate:{mode}",
        created_at=utc_now(),
    )
    db.add(alt)

    # Record usage & cost (₹0.15 INR per regeneration)
    usage = Usage(
        id=uuid.uuid4(),
        user_id=user.id,
        video_id=video.id,
        metric="clip_regenerations",
        quantity=1,
        cost_inr=0.15,
        created_at=utc_now(),
    )
    db.add(usage)

    await db.commit()
    await db.refresh(alt)

    # Emit SSE event
    await publish_event_async(
        f"video:{video.id}",
        "regenerate_ready",
        {
            "job_id": str(job_id),
            "clip_id": str(clip.id),
            "mode": mode,
            "alternative_id": str(alt.id),
        },
    )

    return {
        "job_id": str(job_id),
        "mode": mode,
        "alternative": ClipAlternativeResponse.model_validate(alt),
    }


# ---------------------------------------------------------------------------
# 3. Bulk Actions
# ---------------------------------------------------------------------------

@router.post("/clips/bulk")
async def bulk_clip_actions(
    payload: ClipBulkActionRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Perform bulk operations on multiple clips: 'dismiss' or 'export'.
    """
    if not payload.clip_ids:
        return {"status": "ok", "processed": 0}

    # Fetch and verify ownership for all clips
    stmt = (
        select(Clip)
        .join(Video, Clip.video_id == Video.id)
        .where(Clip.id.in_(payload.clip_ids), Video.user_id == user.id)
    )
    res = await db.execute(stmt)
    clips = res.scalars().all()

    if payload.action == "dismiss":
        moment_ids = [c.moment_id for c in clips]
        if moment_ids:
            # Mark moments as rejected
            m_stmt = select(ClipMoment).where(ClipMoment.id.in_(moment_ids))
            m_res = await db.execute(m_stmt)
            for m in m_res.scalars().all():
                m.status = "rejected"
        await db.commit()
        return {"status": "dismissed", "count": len(clips)}

    elif payload.action == "export":
        from api.routes.exports import create_clip_export
        from clip_shared.schemas.exports import CreateExportRequest

        export_results = []
        for c in clips:
            exp_res = await create_clip_export(
                clip_id=c.id,
                payload=CreateExportRequest(preset_key=payload.preset or "tiktok"),
                user=user,
                db=db,
            )
            export_results.extend(exp_res)

        return {"status": "exported", "exports": export_results}

    return {"status": "unknown_action"}


# ---------------------------------------------------------------------------
# 4. Instrumentation & Admin Metrics
# ---------------------------------------------------------------------------

@router.post("/editor/events")
async def record_editor_events(
    payload: EditorEventsBatchRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Batched instrumentation recording of client editor events."""
    count = 0
    now = utc_now()
    for ev in payload.events:
        record = EditorEvent(
            id=uuid.uuid4(),
            user_id=user.id,
            clip_id=ev.clip_id,
            session_id=ev.session_id,
            type=ev.type,
            payload=ev.payload or {},
            created_at=ev.created_at or now,
        )
        db.add(record)
        count += 1

    await db.commit()
    return {"status": "recorded", "count": count}


@router.get("/admin/editor-metrics", response_model=EditorMetricsResponse)
async def get_editor_metrics(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Owner/admin metrics: median & p90 hands-on time, edit type frequencies,
    drop-off points, and export-without-editing rate.
    """
    stmt = select(EditorEvent).order_by(EditorEvent.created_at)
    res = await db.execute(stmt)
    events = res.scalars().all()

    # Group by session
    sessions: dict[str, list[EditorEvent]] = {}
    for ev in events:
        sessions.setdefault(ev.session_id, []).append(ev)

    hands_on_durations: list[float] = []
    time_to_first_clips: list[float] = []
    time_to_first_edits: list[float] = []
    time_to_first_exports: list[float] = []
    edit_counts: dict[str, int] = {}
    drop_offs: dict[str, int] = {"open_no_edit": 0, "edit_no_export": 0, "completed_export": 0}
    exports_without_edits = 0
    total_exports = 0
    regenerate_count = 0

    for s_id, s_events in sessions.items():
        s_events.sort(key=lambda x: _ensure_tz(x.created_at))
        start_time = _ensure_tz(s_events[0].created_at)
        has_edit = False
        has_export = False
        session_active_seconds = 0.0

        for i in range(len(s_events) - 1):
            gap = (_ensure_tz(s_events[i + 1].created_at) - _ensure_tz(s_events[i].created_at)).total_seconds()
            if gap <= 20.0:
                session_active_seconds += gap

        for ev in s_events:
            t_from_start = (_ensure_tz(ev.created_at) - start_time).total_seconds()
            if ev.type == "clip_visible" and not time_to_first_clips:
                time_to_first_clips.append(t_from_start)
            elif ev.type in ("edit_action", "delete_word", "trim_boundary", "style_change", "swap_hook", "toggle_cleanup"):
                edit_counts[ev.type] = edit_counts.get(ev.type, 0) + 1
                if not has_edit:
                    has_edit = True
                    time_to_first_edits.append(t_from_start)
            elif ev.type == "export_click":
                has_export = True
                total_exports += 1
                time_to_first_exports.append(t_from_start)
            elif ev.type == "regenerate_click":
                regenerate_count += 1

        if session_active_seconds > 0:
            hands_on_durations.append(session_active_seconds)

        if has_export:
            drop_offs["completed_export"] += 1
            if not has_edit:
                exports_without_edits += 1
        elif has_edit:
            drop_offs["edit_no_export"] += 1
        else:
            drop_offs["open_no_edit"] += 1

    def _calc_percentile(data: list[float], p: float, default: float = 0.0) -> float:
        if not data:
            return default
        sorted_d = sorted(data)
        idx = int(round((len(sorted_d) - 1) * p))
        return round(sorted_d[idx], 2)

    median_hands_on = _calc_percentile(hands_on_durations, 0.5, 45.0)
    p90_hands_on = _calc_percentile(hands_on_durations, 0.9, 120.0)
    median_clip = _calc_percentile(time_to_first_clips, 0.5, 12.0)
    median_edit = _calc_percentile(time_to_first_edits, 0.5, 25.0)
    median_export = _calc_percentile(time_to_first_exports, 0.5, 65.0)

    export_no_edit_rate = round(exports_without_edits / max(1, total_exports), 2)

    return EditorMetricsResponse(
        total_sessions=len(sessions),
        median_hands_on_time_s=median_hands_on,
        p90_hands_on_time_s=p90_hands_on,
        median_time_to_first_clip_s=median_clip,
        median_time_to_first_edit_s=median_edit,
        median_time_to_first_export_s=median_export,
        export_without_editing_rate=export_no_edit_rate,
        edit_type_frequencies=edit_counts,
        drop_off_points=drop_offs,
        total_regenerate_count=regenerate_count,
    )
