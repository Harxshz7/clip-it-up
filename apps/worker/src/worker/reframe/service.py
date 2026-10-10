"""Lazy reframe generation service linking VideoAnalysis, FaceTracks, and ClipReframe persistence."""
import uuid
from typing import Any

import structlog
from sqlalchemy import select

from clip_shared.db.base import utc_now
from clip_shared.db.models import Clip, ClipReframe, FaceTrack, Video, VideoAnalysis
from clip_shared.schemas.reframe import SceneItem
from worker.analysis.service import run_video_analysis
from worker.reframe.planner import plan_clip_reframe

logger = structlog.get_logger()


def generate_clip_reframe(
    clip_id: uuid.UUID,
    s3_client: Any,
    db_session: Any,
    analysis_version: str = "v1",
    mode_override: str | None = None,
    force_regenerate: bool = False,
) -> ClipReframe:
    """
    Lazy computation of 9:16 reframe crop path for a clip.
    If video analysis is not yet available, runs video analysis first.
    """
    # 1. Fetch clip and video
    clip = db_session.get(Clip, clip_id)
    if not clip:
        raise ValueError(f"Clip {clip_id} not found")

    video = db_session.get(Video, clip.video_id)
    if not video:
        raise ValueError(f"Video {clip.video_id} not found")

    # 2. Check existing auto reframe if not forced
    stmt = select(ClipReframe).where(
        ClipReframe.clip_id == clip_id,
        ClipReframe.analysis_version == analysis_version,
        ClipReframe.source == "auto",
    )
    existing_reframe = db_session.execute(stmt).scalars().first()
    if existing_reframe and not force_regenerate and not mode_override:
        return existing_reframe

    # 3. Ensure VideoAnalysis is computed and ready
    analysis_stmt = select(VideoAnalysis).where(
        VideoAnalysis.video_id == clip.video_id,
        VideoAnalysis.version == analysis_version,
    )
    analysis = db_session.execute(analysis_stmt).scalars().first()

    if not analysis or analysis.status != "ready":
        logger.info("Video analysis missing or not ready, triggering analysis now", video_id=str(clip.video_id))
        analysis = run_video_analysis(
            video_id=clip.video_id,
            s3_client=s3_client,
            db_session=db_session,
            version=analysis_version,
        )

    # 4. Fetch face tracks
    ft_stmt = select(FaceTrack).where(FaceTrack.analysis_id == analysis.id)
    face_tracks = db_session.execute(ft_stmt).scalars().all()

    # Parse scene items
    scenes = [SceneItem(**s) if isinstance(s, dict) else s for s in analysis.scenes]

    src_w = video.width or 1280
    src_h = video.height or 720

    # 5. Plan reframe
    plan = plan_clip_reframe(
        clip_start_ms=clip.start_ms,
        clip_end_ms=clip.end_ms,
        scenes=scenes,
        tracks=face_tracks,
        src_w=src_w,
        src_h=src_h,
        mode_override=mode_override,
    )

    crop_path_dict = plan.crop_path.model_dump()
    flags_dict = plan.flags.model_dump()

    # 6. Upsert ClipReframe record
    if existing_reframe:
        existing_reframe.mode = plan.mode
        existing_reframe.crop_path = crop_path_dict
        existing_reframe.confidence = plan.confidence
        existing_reframe.flags = flags_dict
        reframe_record = existing_reframe
    else:
        reframe_record = ClipReframe(
            id=uuid.uuid4(),
            clip_id=clip_id,
            analysis_version=analysis_version,
            mode=plan.mode,
            crop_path=crop_path_dict,
            confidence=plan.confidence,
            flags=flags_dict,
            source="auto",
            created_at=utc_now(),
        )
        db_session.add(reframe_record)

    db_session.commit()
    logger.info("Generated reframe for clip", clip_id=str(clip_id), mode=plan.mode, conf=plan.confidence)
    return reframe_record
