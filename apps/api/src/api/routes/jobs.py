import asyncio
import json
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from clip_shared.config import get_settings
from clip_shared.db.session import get_db, AsyncSessionLocal
from clip_shared.db.models import Job, JobStage
from clip_shared.db.base import utc_now
from clip_shared.schemas.auth import AuthenticatedUser
from clip_shared.schemas.jobs import JobResponse
from clip_shared.pubsub.redis import subscribe_job_events_async, publish_job_event_sync
from api.dependencies import get_current_user

router = APIRouter(prefix="/jobs", tags=["jobs"])
settings = get_settings()


async def get_job_snapshot_data(job_id: uuid.UUID, user_id: uuid.UUID) -> Optional[dict]:
    """Fetch complete job and stages data snapshot."""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Job)
            .options(selectinload(Job.stages))
            .where(Job.id == job_id, Job.user_id == user_id)
        )
        result = await session.execute(stmt)
        job = result.scalar_one_or_none()
        if not job:
            return None

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
            for s in sorted(job.stages, key=lambda x: str(x.id))
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
            "timestamp": utc_now().isoformat(),
        }


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get single job with stage execution details. Returns 404 if not found or unauthorized."""
    stmt = (
        select(Job)
        .options(selectinload(Job.stages))
        .where(Job.id == job_id, Job.user_id == user.id)
    )
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "JOB_NOT_FOUND", "message": "Job not found."}},
        )
    return job


@router.get("/{job_id}/events")
async def stream_job_events(
    job_id: uuid.UUID,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
):
    """
    Server-Sent Events (SSE) endpoint:
    1. Verifies ownership.
    2. Sends full job state snapshot first (also handles Last-Event-ID reconnect).
    3. Streams real-time updates from Redis pub/sub.
    4. Sends 15s heartbeats.
    5. Closes cleanly on terminal state (succeeded, failed, cancelled).
    """
    initial_snapshot = await get_job_snapshot_data(job_id, user.id)
    if not initial_snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "JOB_NOT_FOUND", "message": "Job not found."}},
        )

    async def event_generator():
        event_counter = 0
        
        # 1. Send initial snapshot immediately
        event_counter += 1
        yield f"id: {event_counter}\nevent: snapshot\ndata: {json.dumps(initial_snapshot)}\n\n"

        # If already in terminal state, finish stream
        if initial_snapshot["status"] in ("succeeded", "failed", "cancelled"):
            return

        # 2. Subscribe to Redis pubsub and multiplex with 15s heartbeat
        pubsub_gen = subscribe_job_events_async(str(job_id))
        
        try:
            pubsub_task = asyncio.create_task(pubsub_gen.__anext__())
            
            while True:
                # Wait for pub/sub message or 15s heartbeat timeout
                done, pending = await asyncio.wait(
                    [pubsub_task],
                    timeout=15.0,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if await request.is_disconnected():
                    break

                if done:
                    try:
                        event_data = pubsub_task.result()
                        event_counter += 1
                        yield f"id: {event_counter}\nevent: update\ndata: {json.dumps(event_data)}\n\n"

                        if event_data.get("status") in ("succeeded", "failed", "cancelled"):
                            break

                        # Schedule next message fetch
                        pubsub_task = asyncio.create_task(pubsub_gen.__anext__())
                    except StopAsyncIteration:
                        break
                else:
                    # Heartbeat fired
                    yield f": heartbeat {utc_now().isoformat()}\n\n"

        except asyncio.CancelledError:
            pass
        finally:
            if not pubsub_task.done():
                pubsub_task.cancel()
            await pubsub_gen.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running or queued job."""
    stmt = (
        select(Job)
        .options(selectinload(Job.stages))
        .where(Job.id == job_id, Job.user_id == user.id)
    )
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "JOB_NOT_FOUND", "message": "Job not found."}},
        )

    if job.status in ("succeeded", "failed", "cancelled"):
        return job

    job.status = "cancelled"
    job.finished_at = utc_now()

    # Cancel any running/pending stage
    for stage in job.stages:
        if stage.status in ("pending", "running"):
            stage.status = "cancelled"
            stage.finished_at = utc_now()

    await db.commit()
    await db.refresh(job)

    # Broadcast cancelled event to Redis
    event_payload = await get_job_snapshot_data(job.id, user.id)
    if event_payload:
        publish_job_event_sync(str(job.id), event_payload)

    return job
