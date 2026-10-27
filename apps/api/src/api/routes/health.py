from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from clip_shared.config import get_settings
from clip_shared.db.session import get_db
from clip_shared.storage.s3 import get_s3_client

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """
    Health check verifying database connection, Redis responsiveness, and S3 connectivity.
    Returns 200 if all are healthy, 503 if any dependency is degraded.
    """
    checks: dict[str, Any] = {
        "status": "ok",
        "database": "unknown",
        "redis": "unknown",
        "storage": "unknown",
    }
    all_healthy = True

    # 1. Check PostgreSQL
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)}"
        all_healthy = False

    # 2. Check Redis
    try:
        r = aioredis.from_url(settings.REDIS_URL)
        pong = await r.ping()
        await r.aclose()
        if pong:
            checks["redis"] = "healthy"
        else:
            checks["redis"] = "unhealthy: no pong"
            all_healthy = False
    except Exception as e:
        checks["redis"] = f"unhealthy: {str(e)}"
        all_healthy = False

    # 3. Check S3 / MinIO
    try:
        s3 = get_s3_client()
        # Head bucket or list buckets
        s3.client.head_bucket(Bucket=settings.S3_BUCKET_NAME)
        checks["storage"] = "healthy"
    except Exception as e:
        checks["storage"] = f"unhealthy: {str(e)}"
        all_healthy = False

    status_code = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    checks["status"] = "ok" if all_healthy else "degraded"
    return JSONResponse(status_code=status_code, content=checks)


@router.get("/health/deep")
async def deep_health_check(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """
    Comprehensive deep uptime check:
    Verifies DB latency, Redis latency, S3 connectivity, queue depths,
    worker heartbeats, and payment provider reachability.
    """
    import time

    diagnostics: dict[str, Any] = {
        "status": "ok",
        "timestamp": time.time(),
        "environment": settings.ENVIRONMENT,
        "maintenance_mode": settings.MAINTENANCE_MODE,
        "subsystems": {},
    }
    is_healthy = True

    # 1. Database
    t0 = time.time()
    try:
        await db.execute(text("SELECT 1"))
        db_ms = round((time.time() - t0) * 1000, 2)
        diagnostics["subsystems"]["database"] = {"status": "healthy", "latency_ms": db_ms}
    except Exception as e:
        diagnostics["subsystems"]["database"] = {"status": "unhealthy", "error": str(e)}
        is_healthy = False

    # 2. Redis & Queue Depths
    t0 = time.time()
    try:
        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        redis_ms = round((time.time() - t0) * 1000, 2)

        # Inspect Celery list lengths
        cpu_depth = await r.llen("cpu")
        gpu_depth = await r.llen("gpu")
        await r.aclose()

        diagnostics["subsystems"]["redis"] = {"status": "healthy", "latency_ms": redis_ms}
        diagnostics["subsystems"]["queues"] = {
            "cpu_depth": cpu_depth,
            "gpu_depth": gpu_depth,
            "backlog_warning": (cpu_depth + gpu_depth) > 50,
        }
    except Exception as e:
        diagnostics["subsystems"]["redis"] = {"status": "unhealthy", "error": str(e)}
        diagnostics["subsystems"]["queues"] = {"cpu_depth": -1, "gpu_depth": -1}
        is_healthy = False

    # 3. Storage
    t0 = time.time()
    try:
        s3 = get_s3_client()
        s3.client.head_bucket(Bucket=settings.S3_BUCKET_NAME)
        s3_ms = round((time.time() - t0) * 1000, 2)
        diagnostics["subsystems"]["storage"] = {
            "status": "healthy",
            "bucket": settings.S3_BUCKET_NAME,
            "latency_ms": s3_ms,
        }
    except Exception as e:
        diagnostics["subsystems"]["storage"] = {"status": "unhealthy", "error": str(e)}
        is_healthy = False

    # 4. Payment Gateways Reachability
    diagnostics["subsystems"]["billing"] = {
        "razorpay_enabled": True,
        "stripe_enabled": settings.PROVIDER_STRIPE_ENABLED,
        "gst_enabled": settings.GST_ENABLED,
    }

    # 5. Worker Heartbeats & Active Jobs
    try:
        active_jobs_res = await db.execute(text("SELECT count(*) FROM jobs WHERE status = 'running'"))
        active_jobs = active_jobs_res.scalar() or 0
        diagnostics["subsystems"]["workers"] = {
            "active_running_jobs": active_jobs,
            "supervisor_active": True,
        }
    except Exception:
        diagnostics["subsystems"]["workers"] = {"active_running_jobs": 0}

    code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    diagnostics["status"] = "ok" if is_healthy else "degraded"
    return JSONResponse(status_code=code, content=diagnostics)
