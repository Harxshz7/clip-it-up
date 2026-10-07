import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from clip_shared.db.base import utc_now
from clip_shared.db.models import Job, Video


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    with patch("api.routes.health.get_s3_client") as mock_s3, \
         patch("redis.asyncio.from_url") as mock_redis:
        mock_redis_client = MagicMock()
        mock_redis_client.ping = MagicMock(return_value=asyncio_future(True))
        mock_redis_client.aclose = MagicMock(return_value=asyncio_future(None))
        mock_redis.return_value = mock_redis_client

        mock_s3_instance = MagicMock()
        mock_s3_instance.client.head_bucket.return_value = {}
        mock_s3.return_value = mock_s3_instance

        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


def asyncio_future(result):
    f = pytest.importorskip("asyncio").Future()
    f.set_result(result)
    return f


@pytest.mark.asyncio
async def test_upload_url_validation(client: AsyncClient, sample_user):
    # 1. Invalid content type
    resp = await client.post(
        "/videos/upload-url",
        json={"filename": "test.txt", "content_type": "text/plain", "size_bytes": 1024},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_CONTENT_TYPE"

    # 2. Invalid file size (0 bytes)
    resp = await client.post(
        "/videos/upload-url",
        json={"filename": "test.mp4", "content_type": "video/mp4", "size_bytes": 0},
    )
    assert resp.status_code == 400

    # 3. Valid direct PUT upload (<100MB)
    with patch("api.routes.videos.get_s3_client") as mock_s3:
        mock_s3_instance = MagicMock()
        mock_s3_instance.generate_presigned_put_url.return_value = "http://minio:9000/presigned-put-url"
        mock_s3.return_value = mock_s3_instance

        resp = await client.post(
            "/videos/upload-url",
            json={"filename": "my_podcast.mp4", "content_type": "video/mp4", "size_bytes": 50 * 1024 * 1024},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["upload_type"] == "direct_put"
        assert "upload_url" in data
        assert "users/00000000-0000-0000-0000-000000000001/videos/" in data["storage_key"]


@pytest.mark.asyncio
async def test_complete_flow_and_ownership_isolation(client: AsyncClient, sample_user, other_user, db_session):
    # Create video owned by sample_user
    video_id = uuid.uuid4()
    video = Video(
        id=video_id,
        user_id=sample_user.id,
        original_filename="sample.mp4",
        storage_key=f"users/{sample_user.id}/videos/{video_id}/source/sample.mp4",
        size_bytes=10000,
        content_type="video/mp4",
        status="uploading",
        created_at=utc_now(),
    )
    db_session.add(video)
    await db_session.commit()

    # Complete upload with mock S3 HEAD check
    with patch("api.routes.videos.get_s3_client") as mock_s3:
        mock_s3_instance = MagicMock()
        mock_s3_instance.check_object_exists.return_value = True
        mock_s3.return_value = mock_s3_instance

        resp = await client.post(f"/videos/{video_id}/complete")
        assert resp.status_code == 200
        data = resp.json()
        assert data["video_id"] == str(video_id)
        assert data["job"]["status"] == "queued"
        assert len(data["job"]["stages"]) == 6

    # Test ownership isolation: Querying another user's video returns 404
    other_video_id = uuid.uuid4()
    other_video = Video(
        id=other_video_id,
        user_id=other_user.id,
        original_filename="secret.mp4",
        storage_key="secret-key",
        size_bytes=500,
        content_type="video/mp4",
        status="ready",
        created_at=utc_now(),
    )
    db_session.add(other_video)
    await db_session.commit()

    resp = await client.get(f"/videos/{other_video_id}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "VIDEO_NOT_FOUND"


@pytest.mark.asyncio
async def test_job_events_initial_snapshot(client: AsyncClient, sample_user, db_session):
    video_id = uuid.uuid4()
    video = Video(
        id=video_id,
        user_id=sample_user.id,
        original_filename="demo.mp4",
        storage_key="test-key",
        size_bytes=1000,
        content_type="video/mp4",
        status="processing",
        created_at=utc_now(),
    )
    db_session.add(video)

    job_id = uuid.uuid4()
    job = Job(
        id=job_id,
        video_id=video_id,
        user_id=sample_user.id,
        status="succeeded",
        progress=100,
        created_at=utc_now(),
    )
    db_session.add(job)
    await db_session.commit()

    resp = await client.get(f"/jobs/{job_id}/events")
    assert resp.status_code == 200
    assert "event: snapshot" in resp.text
    assert str(job_id) in resp.text
