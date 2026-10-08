import os
import shutil
import tempfile
import uuid
from datetime import UTC, datetime

import structlog
from celery import shared_task
from sqlalchemy import desc, select

from clip_shared.config import get_settings
from clip_shared.db.base import utc_now
from clip_shared.db.models import Clip, ClipMoment, ClipReviewExport, Video
from clip_shared.db.session import get_sync_db
from clip_shared.media.ffmpeg import export_crude_clip
from clip_shared.pubsub.redis import publish_job_event_sync
from clip_shared.storage.s3 import get_s3_client

logger = structlog.get_logger()
settings = get_settings()


def run_crude_exports_for_video(video_id: uuid.UUID, top_n: int = 8) -> list[dict]:
    """
    Cut crude preview clips (horizontal + 9:16 center crop) for top N clips of a video,
    upload to S3, and save to clip_review_exports table.
    Idempotent: rerun updates records and overwrites S3 objects.
    """
    s3_client = get_s3_client()
    results = []

    with get_sync_db() as db:
        video = db.execute(select(Video).where(Video.id == video_id)).scalar_one_or_none()
        if not video:
            logger.error("export_crude_video_not_found", video_id=str(video_id))
            return []

        # Find top N clips (by moment rank or final_score)
        # 1. Fetch selected moments or highest scoring moments
        m_stmt = (
            select(ClipMoment)
            .where(ClipMoment.video_id == video_id)
            .order_by(ClipMoment.rank.nullslast(), desc(ClipMoment.final_score))
            .limit(top_n)
        )
        moments = db.execute(m_stmt).scalars().all()
        moment_ids = [m.id for m in moments]

        if not moment_ids:
            # Fallback directly to clips ordered by score
            c_stmt = (
                select(Clip)
                .where(Clip.video_id == video_id)
                .order_by(desc(Clip.final_score))
                .limit(top_n)
            )
            clips = db.execute(c_stmt).scalars().all()
        else:
            # Fetch auto or longest variant per moment
            clips = []
            for m_id in moment_ids:
                c_stmt = (
                    select(Clip)
                    .where(Clip.moment_id == m_id)
                    .order_by(desc(Clip.final_score))
                )
                m_clips = db.execute(c_stmt).scalars().all()
                if m_clips:
                    # Prefer auto variant if present, otherwise top score
                    auto_c = next((c for c in m_clips if c.variant_length_s == "auto"), m_clips[0])
                    clips.append(auto_c)

        if not clips:
            logger.warn("no_clips_found_for_crude_export", video_id=str(video_id))
            return []

        temp_dir = tempfile.mkdtemp(prefix=f"crude_export_{video_id}_")
        local_src_path = os.path.join(temp_dir, f"source_{video.id}.mp4")

        try:
            # Download source video from S3 (or use proxy_key if available/smaller)
            source_s3_key = video.storage_key
            logger.info("downloading_source_video_for_crude_export", key=source_s3_key)
            try:
                s3_client.download_file(source_s3_key, local_src_path)
            except Exception as e:
                # Try proxy key as fallback
                if video.proxy_key:
                    logger.warn("source_download_failed_trying_proxy", proxy_key=video.proxy_key, err=str(e))
                    s3_client.download_file(video.proxy_key, local_src_path)
                else:
                    raise

            total_exports = len(clips) * 2
            completed_exports = 0

            for clip in clips:
                kinds = ["horizontal", "vertical_center"]
                for kind in kinds:
                    out_filename = f"{clip.id}_{kind}.mp4"
                    local_out_path = os.path.join(temp_dir, out_filename)
                    storage_key = f"users/{video.user_id}/videos/{video.id}/reviews/clips/{out_filename}"

                    # Export using FFmpeg
                    try:
                        export_crude_clip(
                            input_video=local_src_path,
                            output_mp4=local_out_path,
                            start_ms=clip.start_ms,
                            end_ms=clip.end_ms,
                            kind=kind,
                            watermark_text="Preview",
                        )

                        # Upload to S3
                        s3_client.upload_file(local_out_path, storage_key, content_type="video/mp4")

                        # Upsert into clip_review_exports table
                        exp_stmt = select(ClipReviewExport).where(
                            ClipReviewExport.clip_id == clip.id,
                            ClipReviewExport.kind == kind,
                        )
                        export_rec = db.execute(exp_stmt).scalar_one_or_none()

                        if not export_rec:
                            export_rec = ClipReviewExport(
                                id=uuid.uuid4(),
                                clip_id=clip.id,
                                storage_key=storage_key,
                                kind=kind,
                                created_at=utc_now(),
                            )
                            db.add(export_rec)
                        else:
                            export_rec.storage_key = storage_key
                            export_rec.created_at = utc_now()

                        db.commit()

                        completed_exports += 1
                        results.append({
                            "clip_id": str(clip.id),
                            "kind": kind,
                            "storage_key": storage_key,
                        })

                    except Exception as clip_err:
                        logger.error(
                            "crude_clip_export_failed",
                            clip_id=str(clip.id),
                            kind=kind,
                            error=str(clip_err),
                        )

            # Publish SSE / redis event for exports readiness
            payload = {
                "event": "review_exports_ready",
                "video_id": str(video_id),
                "total_exports": len(results),
                "timestamp": datetime.now(UTC).isoformat(),
            }
            try:
                publish_job_event_sync(str(video_id), payload)
            except Exception:
                pass

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    return results


@shared_task(name="worker.tasks.review.generate_review_exports", bind=True)
def generate_review_exports(self, video_id_str: str, top_n: int = 8):
    """Celery task for lazy crude exports."""
    video_id = uuid.UUID(video_id_str)
    return run_crude_exports_for_video(video_id=video_id, top_n=top_n)
