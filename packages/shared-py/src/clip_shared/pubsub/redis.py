import json
from collections.abc import AsyncGenerator
from typing import Any

import redis
import redis.asyncio as aioredis

from clip_shared.config import get_settings

settings = get_settings()

# Sync Redis client for Celery
_sync_redis: redis.Redis | None = None


def get_sync_redis() -> redis.Redis:
    global _sync_redis
    if _sync_redis is None:
        _sync_redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _sync_redis


def publish_job_event_sync(job_id: str, event_data: dict[str, Any]) -> None:
    """Publish job update event to Redis channel `job:{id}` from Celery worker."""
    client = get_sync_redis()
    channel = f"job:{job_id}"
    payload = json.dumps(event_data, default=str)
    client.publish(channel, payload)


# Async Redis client for FastAPI SSE
_async_redis_pool: aioredis.ConnectionPool | None = None


def get_async_redis_client() -> aioredis.Redis:
    global _async_redis_pool
    if _async_redis_pool is None:
        _async_redis_pool = aioredis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=50,
        )
    return aioredis.Redis(connection_pool=_async_redis_pool)


async def subscribe_job_events_async(job_id: str) -> AsyncGenerator[dict[str, Any], None]:
    """Async generator subscribing to Redis channel `job:{id}` for SSE streaming."""
    client = get_async_redis_client()
    pubsub = client.pubsub()
    channel = f"job:{job_id}"
    await pubsub.subscribe(channel)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    yield data
                except (json.JSONDecodeError, TypeError):
                    continue
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
