import random
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List

from celery import shared_task
from sqlalchemy.dialects.postgresql import insert as pg_insert

from clip_shared.config import get_settings
from clip_shared.db.session import get_sync_db
from clip_shared.db.models import Job, JobStage, Video, Usage
from clip_shared.db.base import utc_now
from clip_shared.pubsub.redis import publish_job_event_sync
from clip_shared.rates import StageRateConfig

settings = get_settings()

PIPELINE_STAGES = [
    "ingest",
    "proxy",
    "transcribe",
    "candidates",
    "score",
    "render",
]


def build_job_event_payload(job: Job, stages: List[JobStage]) -> Dict[str, Any]:
    """Helper to construct serializable event payload for SSE / Redis."""
    stages_data = [
        {
            "id": str(s.id),
            "job_id": str(s.job_id),
            "name": s.name,
            "status": s.status,
            "progress": s.progress,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "finished_at": s.finished_at.isoformat() if s.finished_at else None,
            "duration_ms": s.duration_ms,
            "cost_inr": float(s.cost_inr),
            "meta": s.meta or {},
        }
        for s in stages
    ]
    return {
        "job_id": str(job.id),
        "video_id": str(job.video_id),
        "user_id": str(job.user_id),
        "status": job.status,
        "current_stage": job.current_stage,
        "progress": job.progress,
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "stages": stages_data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@shared_task(name="worker.tasks.pipeline.start_pipeline", bind=True)
def start_pipeline(self, job_id_str: str):
    """Entrypoint to trigger pipeline stage execution."""
    return run_stage.delay(job_id_str, "ingest")


@shared_task(name="worker.tasks.pipeline.run_stage", bind=True, max_retries=0)
def run_stage(self, job_id_str: str, stage_name: str):
    """
    Execute a single pipeline stage idempotently, update DB, simulate progress,
    publish SSE events, calculate INR costs, write usage records, and chain to next stage.
    """
    job_id = uuid.UUID(job_id_str)
    total_stages = len(PIPELINE_STAGES)
    stage_index = PIPELINE_STAGES.index(stage_name) if stage_name in PIPELINE_STAGES else 0

    with get_sync_db() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return {"error": "Job not found"}

        # If job has been cancelled, abort execution
        if job.status == "cancelled":
            return {"status": "cancelled"}

        video = db.query(Video).filter(Video.id == job.video_id).first()

        # If first stage, initialize job
        if stage_index == 0 and job.status != "running":
            job.status = "running"
            job.started_at = utc_now()
            if video:
                video.status = "processing"

        job.current_stage = stage_name
        db.flush()

        # Find or create stage
        stage = db.query(JobStage).filter(JobStage.job_id == job_id, JobStage.name == stage_name).first()
        if not stage:
            stage = JobStage(
                id=uuid.uuid4(),
                job_id=job_id,
                name=stage_name,
                status="running",
                progress=0,
                started_at=utc_now(),
                meta={"attempts": 1},
            )
            db.add(stage)
        else:
            stage.status = "running"
            stage.progress = 0
            stage.started_at = utc_now()
            stage.finished_at = None
            meta = dict(stage.meta or {})
            meta["attempts"] = meta.get("attempts", 0) + 1
            stage.meta = meta

        db.flush()

        # Fetch all stages for event broadcasting
        all_stages = db.query(JobStage).filter(JobStage.job_id == job_id).order_by(JobStage.created_at).all() if hasattr(JobStage, 'created_at') else db.query(JobStage).filter(JobStage.job_id == job_id).all()
        publish_job_event_sync(str(job_id), build_job_event_payload(job, all_stages))

    # Simulate stage progress in small increments
    total_duration = settings.PIPELINE_STAGE_DURATION_SECONDS
    steps = 5
    step_sleep = max(total_duration / steps, 0.05)
    start_time = time.time()

    for step_num in range(1, steps + 1):
        time.sleep(step_sleep)
        step_pct = int((step_num / steps) * 100)

        # Calculate overall job progress
        overall_pct = int(((stage_index * 100) + step_pct) / total_stages)

        with get_sync_db() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job or job.status == "cancelled":
                return {"status": "cancelled"}

            stage = db.query(JobStage).filter(JobStage.job_id == job_id, JobStage.name == stage_name).first()
            if stage:
                stage.progress = step_pct
            job.progress = overall_pct
            db.flush()

            all_stages = db.query(JobStage).filter(JobStage.job_id == job_id).all()
            publish_job_event_sync(str(job_id), build_job_event_payload(job, all_stages))

    elapsed_ms = int((time.time() - start_time) * 1000)

    # Check for random failure injection
    if settings.INJECT_RANDOM_FAILURE and random.random() < 0.15:
        with get_sync_db() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            stage = db.query(JobStage).filter(JobStage.job_id == job_id, JobStage.name == stage_name).first()
            video = db.query(Video).filter(Video.id == job.video_id).first() if job else None

            err_msg = f"Simulated failure in stage '{stage_name}'"
            if stage:
                stage.status = "failed"
                stage.finished_at = utc_now()
                stage.duration_ms = elapsed_ms
            if job:
                job.status = "failed"
                job.error = err_msg
                job.finished_at = utc_now()
            if video:
                video.status = "failed"
            db.flush()

            all_stages = db.query(JobStage).filter(JobStage.job_id == job_id).all()
            publish_job_event_sync(str(job_id), build_job_event_payload(job, all_stages))
            return {"status": "failed", "stage": stage_name, "error": err_msg}

    # Finalize successful stage
    with get_sync_db() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job or job.status == "cancelled":
            return {"status": "cancelled"}

        stage = db.query(JobStage).filter(JobStage.job_id == job_id, JobStage.name == stage_name).first()
        video = db.query(Video).filter(Video.id == job.video_id).first()

        video_duration = video.duration_seconds if (video and video.duration_seconds) else 600.0
        stage_cost = StageRateConfig.calculate_stage_cost(stage_name, video_duration)
        metric_name = StageRateConfig.get_stage_metric(stage_name)
        metric_quantity = StageRateConfig.calculate_metric_quantity(stage_name, video_duration)

        if stage:
            stage.status = "succeeded"
            stage.progress = 100
            stage.finished_at = utc_now()
            stage.duration_ms = elapsed_ms
            stage.cost_inr = stage_cost
            meta = dict(stage.meta or {})
            meta["processed_duration_seconds"] = video_duration
            meta["simulated"] = True
            stage.meta = meta

        # Upsert usage record idempotently for (job_id, metric)
        usage_stmt = pg_insert(Usage).values(
            id=uuid.uuid4(),
            user_id=job.user_id,
            video_id=job.video_id,
            job_id=job.id,
            metric=metric_name,
            quantity=metric_quantity,
            cost_inr=stage_cost,
            created_at=utc_now(),
        ).on_conflict_do_update(
            constraint="uq_usage_job_id_metric",
            set_={
                "quantity": metric_quantity,
                "cost_inr": stage_cost,
            },
        )
        db.execute(usage_stmt)
        db.flush()

        is_last_stage = stage_index == total_stages - 1

        if is_last_stage:
            job.status = "succeeded"
            job.progress = 100
            job.finished_at = utc_now()
            job.current_stage = None
            if video:
                video.status = "ready"
                if not video.duration_seconds:
                    video.duration_seconds = video_duration

        db.flush()
        all_stages = db.query(JobStage).filter(JobStage.job_id == job_id).all()
        publish_job_event_sync(str(job_id), build_job_event_payload(job, all_stages))

    # Trigger next stage if applicable
    if not is_last_stage:
        next_stage_name = PIPELINE_STAGES[stage_index + 1]
        run_stage.delay(job_id_str, next_stage_name)

    return {"status": "succeeded", "stage": stage_name, "duration_ms": elapsed_ms, "cost_inr": float(stage_cost)}
