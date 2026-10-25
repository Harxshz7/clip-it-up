import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from celery import shared_task
from sqlalchemy import desc, select

from clip_shared.billing.quota import QuotaService
from clip_shared.config import get_settings
from clip_shared.db.base import utc_now
from clip_shared.db.models import (
    BrandAsset,
    BrandKit,
    ClipVariant,
    DeadLetterJob,
    DeletionAudit,
    Job,
    JobStage,
    Plan,
    ReviewSession,
    User,
    UserPlan,
    VariantSet,
    Video,
)
from clip_shared.db.session import get_sync_db
from clip_shared.pubsub.redis import publish_job_event_sync
from clip_shared.storage.s3 import get_s3_client

logger = logging.getLogger(__name__)
settings = get_settings()

STAGE_QUEUES = {
    "ingest": "cpu",
    "proxy": "cpu",
    "transcribe": "gpu",
    "candidates": "cpu",
    "score": "cpu",
    "render": "cpu",
}


@shared_task(name="worker.tasks.supervisor.supervise_stuck_jobs")
def supervise_stuck_jobs() -> dict[str, Any]:
    """
    Celery Beat task detecting stalled or abandoned worker jobs.
    Re-enqueues idempotent stages up to max attempts, then transitions
    to dead-letter table with automatic quota refund.
    """
    timeout_s = settings.JOB_STUCK_TIMEOUT_SECONDS
    max_attempts = settings.JOB_MAX_ATTEMPTS
    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=timeout_s)

    requeued_count = 0
    dead_letter_count = 0

    with get_sync_db() as db:
        stuck_jobs = (
            db.query(Job)
            .filter(
                Job.status == "running",
                Job.stage_heartbeat != None,
                Job.stage_heartbeat < cutoff,
            )
            .all()
        )

        for job in stuck_jobs:
            current_stage = job.current_stage or "ingest"
            video = db.query(Video).filter(Video.id == job.video_id).first()

            if job.attempts < max_attempts:
                # Requeue stage idempotently
                job.attempts += 1
                job.stage_heartbeat = utc_now()
                db.flush()

                queue = STAGE_QUEUES.get(current_stage, "cpu")
                from worker.tasks.pipeline import run_stage
                run_stage.apply_async(args=[str(job.id), current_stage], queue=queue)

                logger.warning(
                    "Requeued stuck job: %s stage: %s (attempt %d/%d)",
                    job.id,
                    current_stage,
                    job.attempts,
                    max_attempts,
                )
                requeued_count += 1
            else:
                # Permanently failed: mark failed, record to dead-letter, auto-refund
                job.status = "failed"
                job.error = f"[INTERNAL] Stage '{current_stage}' timed out after {max_attempts} attempts."
                job.finished_at = utc_now()
                if video:
                    video.status = "failed"

                # Mark active stage failed
                stg = db.query(JobStage).filter(JobStage.job_id == job.id, JobStage.name == current_stage).first()
                if stg:
                    stg.status = "failed"
                    stg.finished_at = utc_now()

                # Dead letter record
                dl = DeadLetterJob(
                    id=uuid.uuid4(),
                    job_id=job.id,
                    user_id=job.user_id,
                    failed_stage=current_stage,
                    error_code="STUCK_JOB_TIMEOUT",
                    error_message=job.error,
                    attempts=job.attempts,
                    context={"video_id": str(job.video_id), "timeout_seconds": timeout_s},
                    resolved=False,
                    created_at=utc_now(),
                )
                db.add(dl)

                # Automatic refund of reserved quota
                est_min = (video.duration_seconds / 60.0) if (video and video.duration_seconds) else 10.0
                QuotaService.refund_minutes_sync(db, job.user_id, job.id, est_min)

                db.flush()
                all_stages = db.query(JobStage).filter(JobStage.job_id == job.id).all()
                from worker.tasks.pipeline import build_job_event_payload
                publish_job_event_sync(str(job.id), build_job_event_payload(job, all_stages))

                logger.error(
                    "Job %s permanently dead-lettered after %d attempts. Quota refunded.",
                    job.id,
                    max_attempts,
                )
                dead_letter_count += 1

        db.commit()

    return {
        "status": "success",
        "requeued": requeued_count,
        "dead_lettered": dead_letter_count,
    }


@shared_task(name="worker.tasks.supervisor.cleanup_retention_and_expired_data")
def cleanup_retention_and_expired_data() -> dict[str, Any]:
    """
    Celery Beat task enforcing plan data retention policies and executing
    scheduled account deletions after the 7-day grace period.
    """
    now = datetime.now(UTC)
    accounts_purged = 0
    expired_reviews_closed = 0
    videos_purged = 0

    s3 = get_s3_client()

    with get_sync_db() as db:
        # 1. Close expired creator review sessions
        expired_sessions = (
            db.query(ReviewSession)
            .filter(ReviewSession.status == "open", ReviewSession.expires_at < now)
            .all()
        )
        for sess in expired_sessions:
            sess.status = "closed"
            expired_reviews_closed += 1
        db.flush()

        # 2. Check users with expired 7-day deletion grace period
        due_deletions = (
            db.query(User)
            .filter(User.deletion_scheduled_at != None, User.deletion_scheduled_at <= now)
            .all()
        )
        for del_user in due_deletions:
            # Audit record
            audit = DeletionAudit(
                id=uuid.uuid4(),
                entity_type="account",
                entity_id=str(del_user.id),
                user_id=del_user.id,
                status="completed",
                requested_at=del_user.deletion_scheduled_at - timedelta(days=7),
                completed_at=utc_now(),
                audit_data={"email": del_user.email},
                created_at=utc_now(),
            )
            db.add(audit)

            # Explicitly purge user's brand assets from S3
            brand_assets = db.query(BrandAsset).filter(BrandAsset.user_id == del_user.id).all()
            for ba in brand_assets:
                if ba.storage_key:
                    s3.delete_object(ba.storage_key)

            # Purge all S3 keys for user
            prefix = f"users/{del_user.id}/"
            try:
                keys = s3.list_objects(prefix=prefix)
                for k in keys:
                    s3.delete_object(k)
                audit.s3_objects_deleted_count = len(keys)
            except Exception:
                pass

            # Cascade delete user row
            db.delete(del_user)
            accounts_purged += 1

        db.commit()

    return {
        "expired_reviews_closed": expired_reviews_closed,
        "accounts_purged": accounts_purged,
        "videos_purged": videos_purged,
    }
