import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from clip_shared.config import get_settings
from clip_shared.db.base import utc_now
from clip_shared.db.models import (
    Clip,
    ClipReframe,
    ClipReframeEdit,
    FaceTrack,
    Video,
    VideoAnalysis,
)
from clip_shared.db.session import get_db, get_sync_db
from clip_shared.schemas.auth import AuthenticatedUser
from clip_shared.schemas.reframe import (
    FaceTrackResponse,
    ReframeCropPath,
    ReframeFlags,
    ReframeKeyframe,
    ReframeRegenerateRequest,
    ReframeResponse,
    ReframeUpdateRequest,
    SceneItem,
    VideoAnalysisResponse,
)
from clip_shared.storage.s3 import get_s3_client
from worker.analysis.service import run_video_analysis
from worker.reframe.service import generate_clip_reframe

router = APIRouter(tags=["reframe"])
settings = get_settings()


@router.post("/videos/{video_id}/analysis", response_model=VideoAnalysisResponse)
async def trigger_video_analysis(
    video_id: uuid.UUID,
    version: str = Query("v1", description="Analysis version tag"),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger or re-run video scene and face tracking analysis.
    Idempotent: returns existing analysis if already ready.
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

    # 2. Check if already computed
    a_stmt = select(VideoAnalysis).where(
        VideoAnalysis.video_id == video_id,
        VideoAnalysis.version == version,
    )
    a_res = await db.execute(a_stmt)
    analysis = a_res.scalar_one_or_none()

    if not analysis or analysis.status != "ready":
        # Run synchronous / background analysis
        s3 = get_s3_client()
        with get_sync_db() as sync_db:
            analysis = run_video_analysis(
                video_id=video_id,
                s3_client=s3,
                db_session=sync_db,
                version=version,
            )

    # Fetch face tracks
    ft_stmt = select(FaceTrack).where(FaceTrack.analysis_id == analysis.id).order_by(FaceTrack.track_id)
    ft_res = await db.execute(ft_stmt)
    face_tracks = ft_res.scalars().all()

    scenes_list = [SceneItem(**s) if isinstance(s, dict) else s for s in analysis.scenes]

    return VideoAnalysisResponse(
        id=analysis.id,
        video_id=analysis.video_id,
        version=analysis.version,
        fps_sampled=analysis.fps_sampled,
        scenes=scenes_list,
        status=analysis.status,
        summary=analysis.summary or {},
        created_at=analysis.created_at,
        face_tracks=[
            FaceTrackResponse(
                id=ft.id,
                track_id=ft.track_id,
                start_ms=ft.start_ms,
                end_ms=ft.end_ms,
                avg_conf=ft.avg_conf,
                speaker_label=ft.speaker_label,
                summary=ft.summary or {},
            )
            for ft in face_tracks
        ],
    )


@router.get("/videos/{video_id}/analysis", response_model=VideoAnalysisResponse)
async def get_video_analysis(
    video_id: uuid.UUID,
    version: str = Query("v1", description="Analysis version tag"),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get video visual scene and face analysis summary.
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

    # 2. Query analysis record
    a_stmt = select(VideoAnalysis).where(
        VideoAnalysis.video_id == video_id,
        VideoAnalysis.version == version,
    )
    a_res = await db.execute(a_stmt)
    analysis = a_res.scalar_one_or_none()

    if not analysis:
        # Lazy compute analysis on demand
        s3 = get_s3_client()
        with get_sync_db() as sync_db:
            analysis = run_video_analysis(
                video_id=video_id,
                s3_client=s3,
                db_session=sync_db,
                version=version,
            )

    ft_stmt = select(FaceTrack).where(FaceTrack.analysis_id == analysis.id).order_by(FaceTrack.track_id)
    ft_res = await db.execute(ft_stmt)
    face_tracks = ft_res.scalars().all()

    scenes_list = [SceneItem(**s) if isinstance(s, dict) else s for s in analysis.scenes]

    return VideoAnalysisResponse(
        id=analysis.id,
        video_id=analysis.video_id,
        version=analysis.version,
        fps_sampled=analysis.fps_sampled,
        scenes=scenes_list,
        status=analysis.status,
        summary=analysis.summary or {},
        created_at=analysis.created_at,
        face_tracks=[
            FaceTrackResponse(
                id=ft.id,
                track_id=ft.track_id,
                start_ms=ft.start_ms,
                end_ms=ft.end_ms,
                avg_conf=ft.avg_conf,
                speaker_label=ft.speaker_label,
                summary=ft.summary or {},
            )
            for ft in face_tracks
        ],
    )


@router.get("/clips/{clip_id}/reframe", response_model=ReframeResponse)
async def get_clip_reframe(
    clip_id: uuid.UUID,
    analysis_version: str = Query("v1", description="Analysis version tag"),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get 9:16 reframe crop path for a clip (auto + active manual edit).
    Lazy-computes reframe if not already generated.
    """
    # 1. Verify clip and video ownership
    c_stmt = select(Clip).join(Video, Clip.video_id == Video.id).where(Clip.id == clip_id, Video.user_id == user.id)
    c_res = await db.execute(c_stmt)
    clip = c_res.scalar_one_or_none()
    if not clip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "CLIP_NOT_FOUND", "message": "Clip not found."}},
        )

    # 2. Query Auto Reframe
    r_stmt = select(ClipReframe).where(
        ClipReframe.clip_id == clip_id,
        ClipReframe.analysis_version == analysis_version,
        ClipReframe.source == "auto",
    )
    r_res = await db.execute(r_stmt)
    reframe = r_res.scalar_one_or_none()

    if not reframe:
        # Lazy generate reframe
        s3 = get_s3_client()
        with get_sync_db() as sync_db:
            reframe = generate_clip_reframe(
                clip_id=clip_id,
                s3_client=s3,
                db_session=sync_db,
                analysis_version=analysis_version,
            )

    # 3. Check for manual edits
    edit_stmt = (
        select(ClipReframeEdit)
        .where(ClipReframeEdit.clip_reframe_id == reframe.id)
        .order_by(desc(ClipReframeEdit.created_at))
    )
    edit_res = await db.execute(edit_stmt)
    latest_edit = edit_res.scalars().first()

    crop_path_dict = reframe.crop_path if isinstance(reframe.crop_path, dict) else {}
    auto_keyframes = [
        ReframeKeyframe(**k) if isinstance(k, dict) else k
        for k in crop_path_dict.get("keyframes", [])
    ]

    active_keyframes = auto_keyframes
    active_mode = reframe.mode
    has_edits = False

    if latest_edit:
        has_edits = True
        active_keyframes = [
            ReframeKeyframe(**k) if isinstance(k, dict) else k
            for k in latest_edit.keyframes
        ]
        if latest_edit.mode:
            active_mode = latest_edit.mode

    flags_dict = reframe.flags if isinstance(reframe.flags, dict) else {}

    return ReframeResponse(
        id=reframe.id,
        clip_id=reframe.clip_id,
        analysis_version=reframe.analysis_version,
        mode=active_mode,
        crop_path=ReframeCropPath(**crop_path_dict) if crop_path_dict else ReframeCropPath(keyframes=active_keyframes),
        confidence=reframe.confidence,
        flags=ReframeFlags(**flags_dict) if flags_dict else ReframeFlags(),
        source=reframe.source,
        has_edits=has_edits,
        created_at=reframe.created_at,
        active_keyframes=active_keyframes,
    )


@router.post("/clips/{clip_id}/reframe/regenerate", response_model=ReframeResponse)
async def regenerate_clip_reframe(
    clip_id: uuid.UUID,
    payload: ReframeRegenerateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Force recompute auto 9:16 reframe for a clip with optional mode override.
    """
    # 1. Verify ownership
    c_stmt = select(Clip).join(Video, Clip.video_id == Video.id).where(Clip.id == clip_id, Video.user_id == user.id)
    c_res = await db.execute(c_stmt)
    clip = c_res.scalar_one_or_none()
    if not clip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "CLIP_NOT_FOUND", "message": "Clip not found."}},
        )

    analysis_version = payload.analysis_version or "v1"

    s3 = get_s3_client()
    with get_sync_db() as sync_db:
        reframe = generate_clip_reframe(
            clip_id=clip_id,
            s3_client=s3,
            db_session=sync_db,
            analysis_version=analysis_version,
            mode_override=payload.mode_override,
            force_regenerate=True,
        )

    crop_path_dict = reframe.crop_path if isinstance(reframe.crop_path, dict) else {}
    keyframes = [
        ReframeKeyframe(**k) if isinstance(k, dict) else k
        for k in crop_path_dict.get("keyframes", [])
    ]
    flags_dict = reframe.flags if isinstance(reframe.flags, dict) else {}

    return ReframeResponse(
        id=reframe.id,
        clip_id=reframe.clip_id,
        analysis_version=reframe.analysis_version,
        mode=reframe.mode,
        crop_path=ReframeCropPath(**crop_path_dict),
        confidence=reframe.confidence,
        flags=ReframeFlags(**flags_dict),
        source=reframe.source,
        has_edits=False,
        created_at=reframe.created_at,
        active_keyframes=keyframes,
    )


@router.put("/clips/{clip_id}/reframe", response_model=ReframeResponse)
async def update_clip_reframe(
    clip_id: uuid.UUID,
    payload: ReframeUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Manual nudge/edit keyframes for clip reframe.
    Validates keyframe coordinate bounds and preserves auto reframe.
    """
    # 1. Verify ownership
    c_stmt = select(Clip).join(Video, Clip.video_id == Video.id).where(Clip.id == clip_id, Video.user_id == user.id)
    c_res = await db.execute(c_stmt)
    clip = c_res.scalar_one_or_none()
    if not clip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "CLIP_NOT_FOUND", "message": "Clip not found."}},
        )

    # 2. Query Auto Reframe
    r_stmt = select(ClipReframe).where(ClipReframe.clip_id == clip_id, ClipReframe.source == "auto")
    r_res = await db.execute(r_stmt)
    reframe = r_res.scalar_one_or_none()
    if not reframe:
        s3 = get_s3_client()
        with get_sync_db() as sync_db:
            reframe = generate_clip_reframe(clip_id=clip_id, s3_client=s3, db_session=sync_db)

    # 3. Validate keyframes
    keyframes_json = [k.model_dump() for k in payload.keyframes]
    for k in payload.keyframes:
        if not (0.0 <= k.cx <= 1.0 and 0.0 <= k.cy <= 1.0 and 0.0 < k.w <= 1.0 and 0.0 < k.h <= 1.0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_KEYFRAME_BOUNDS", "message": "Keyframe coordinates must be between 0.0 and 1.0."}},
            )

    # 4. Insert new edit
    edit = ClipReframeEdit(
        id=uuid.uuid4(),
        clip_reframe_id=reframe.id,
        user_id=user.id,
        keyframes=keyframes_json,
        mode=payload.mode or reframe.mode,
        created_at=utc_now(),
    )
    db.add(edit)
    await db.commit()

    crop_path_dict = reframe.crop_path if isinstance(reframe.crop_path, dict) else {}
    flags_dict = reframe.flags if isinstance(reframe.flags, dict) else {}

    return ReframeResponse(
        id=reframe.id,
        clip_id=reframe.clip_id,
        analysis_version=reframe.analysis_version,
        mode=edit.mode or reframe.mode,
        crop_path=ReframeCropPath(**crop_path_dict),
        confidence=reframe.confidence,
        flags=ReframeFlags(**flags_dict),
        source=reframe.source,
        has_edits=True,
        created_at=reframe.created_at,
        active_keyframes=payload.keyframes,
    )


@router.delete("/clips/{clip_id}/reframe/edits", response_model=ReframeResponse)
async def revert_clip_reframe_edits(
    clip_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Revert manual edits back to auto reframe.
    """
    # 1. Verify ownership
    c_stmt = select(Clip).join(Video, Clip.video_id == Video.id).where(Clip.id == clip_id, Video.user_id == user.id)
    c_res = await db.execute(c_stmt)
    clip = c_res.scalar_one_or_none()
    if not clip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "CLIP_NOT_FOUND", "message": "Clip not found."}},
        )

    # 2. Query Auto Reframe
    r_stmt = select(ClipReframe).where(ClipReframe.clip_id == clip_id, ClipReframe.source == "auto")
    r_res = await db.execute(r_stmt)
    reframe = r_res.scalar_one_or_none()
    if not reframe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "REFRAME_NOT_FOUND", "message": "Reframe record not found."}},
        )

    # 3. Delete manual edits
    del_stmt = delete(ClipReframeEdit).where(ClipReframeEdit.clip_reframe_id == reframe.id)
    await db.execute(del_stmt)
    await db.commit()

    crop_path_dict = reframe.crop_path if isinstance(reframe.crop_path, dict) else {}
    auto_keyframes = [
        ReframeKeyframe(**k) if isinstance(k, dict) else k
        for k in crop_path_dict.get("keyframes", [])
    ]
    flags_dict = reframe.flags if isinstance(reframe.flags, dict) else {}

    return ReframeResponse(
        id=reframe.id,
        clip_id=reframe.clip_id,
        analysis_version=reframe.analysis_version,
        mode=reframe.mode,
        crop_path=ReframeCropPath(**crop_path_dict),
        confidence=reframe.confidence,
        flags=ReframeFlags(**flags_dict),
        source=reframe.source,
        has_edits=False,
        created_at=reframe.created_at,
        active_keyframes=auto_keyframes,
    )
