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
