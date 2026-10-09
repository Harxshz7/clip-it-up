"""Celery tasks for video visual analysis and clip reframing."""
from datetime import UTC, datetime
import uuid
from celery import shared_task
import structlog
from clip_shared.db.session import get_sync_db
from clip_shared.pubsub.redis import publish_job_event_sync
from clip_shared.storage.s3 import get_s3_client
from worker.analysis.service import run_video_analysis
from worker.reframe.service import generate_clip_reframe

logger = structlog.get_logger()


@shared_task(name="worker.tasks.analysis.analyze_video_task", bind=True)
def analyze_video_task(self, video_id_str: str, version: str = "v1"):
    """Celery task executing video visual scene and face analysis."""
    video_id = uuid.UUID(video_id_str)
    s3 = get_s3_client()

    def on_progress(pct: int, msg: str):
        payload = {
            "event": "video_analysis_progress",
            "video_id": str(video_id),
            "progress": pct,
            "message": msg,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        try:
            publish_job_event_sync(str(video_id), payload)
        except Exception:
            pass

    with get_sync_db() as db:
        analysis = run_video_analysis(
            video_id=video_id,
            s3_client=s3,
            db_session=db,
            version=version,
            on_progress=on_progress,
        )

        # Notify completion
        payload = {
            "event": "video_analysis_ready",
            "video_id": str(video_id),
            "analysis_id": str(analysis.id),
            "version": version,
            "status": "ready",
            "timestamp": datetime.now(UTC).isoformat(),
        }
        try:
            publish_job_event_sync(str(video_id), payload)
        except Exception:
            pass

        return {
            "analysis_id": str(analysis.id),
            "video_id": str(video_id),
            "status": analysis.status,
            "scenes_count": len(analysis.scenes),
        }


@shared_task(name="worker.tasks.analysis.reframe_clip_task", bind=True)
def reframe_clip_task(self, clip_id_str: str, mode_override: str | None = None, force: bool = False):
    """Celery task generating 9:16 reframe for a single clip."""
    clip_id = uuid.UUID(clip_id_str)
    s3 = get_s3_client()

    with get_sync_db() as db:
        reframe = generate_clip_reframe(
            clip_id=clip_id,
            s3_client=s3,
            db_session=db,
            mode_override=mode_override,
            force_regenerate=force,
        )
        return {
            "reframe_id": str(reframe.id),
            "clip_id": str(clip_id),
            "mode": reframe.mode,
            "confidence": reframe.confidence,
        }
