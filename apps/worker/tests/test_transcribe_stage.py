import os
import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["ENVIRONMENT"] = "development"
os.environ["PIPELINE_STAGE_DURATION_SECONDS"] = "0.01"
os.environ["TRANSCRIBE_BACKEND"] = "mock"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DATABASE_SYNC_URL"] = "sqlite:///:memory:"

from clip_shared.db.base import Base, utc_now
from clip_shared.db.models import (
    Job,
    Speaker,
    Transcript,
    TranscriptSegment,
    TranscriptWord,
    User,
    Video,
)
from worker.tasks.pipeline import run_stage


@pytest.fixture
def sync_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    user = User(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        clerk_user_id="user_dev_bypass",
        email="dev@clipitup.local",
    )
    session.add(user)
    session.commit()

    yield session
    session.close()


def test_transcribe_stage_and_idempotent_rerun(sync_db):
    video_id = uuid.uuid4()
    job_id = uuid.uuid4()

    video = Video(
        id=video_id,
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        original_filename="test_podcast.mp4",
        storage_key=f"users/00000000-0000-0000-0000-000000000001/videos/{video_id}/source/test_podcast.mp4",
        size_bytes=50000,
        content_type="video/mp4",
        duration_seconds=180.0,
        status="processing",
        created_at=utc_now(),
    )
    sync_db.add(video)

    job = Job(
        id=job_id,
        video_id=video_id,
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        status="running",
        current_stage="transcribe",
        progress=33,
        created_at=utc_now(),
    )
    sync_db.add(job)
    sync_db.commit()

    with patch("worker.tasks.pipeline.get_sync_db") as mock_db, \
         patch("worker.tasks.pipeline.publish_job_event_sync") as mock_pub, \
         patch("worker.tasks.pipeline.get_s3_client") as mock_s3, \
         patch("worker.tasks.pipeline.run_stage.apply_async"), \
         patch("worker.tasks.pipeline.run_stage.delay"):

        mock_db.return_value.__enter__.return_value = sync_db
        mock_db.return_value.__exit__.return_value = None

        mock_s3_inst = MagicMock()
        mock_s3.return_value = mock_s3_inst

        # 1. Run transcribe stage
        res = run_stage(str(job_id), "transcribe")
        assert res["status"] == "succeeded"
        assert res["stage"] == "transcribe"

        # Check Transcript in DB
        transcript = sync_db.query(Transcript).filter(Transcript.video_id == video_id).first()
        assert transcript is not None
        assert transcript.status == "ready"
        assert transcript.backend == "mock"
        assert transcript.word_count > 0

        # Check Words & Segments
        words = sync_db.query(TranscriptWord).filter(TranscriptWord.transcript_id == transcript.id).all()
        assert len(words) == transcript.word_count
        assert words[0].start_ms >= 0

        segments = sync_db.query(TranscriptSegment).filter(TranscriptSegment.transcript_id == transcript.id).all()
        assert len(segments) > 0
        assert segments[0].text is not None

        speakers = sync_db.query(Speaker).filter(Speaker.transcript_id == transcript.id).all()
        assert len(speakers) >= 2

        # Check job partial results
        sync_db.refresh(job)
        assert job.partial_results.get("transcript") is True

        # Check SSE events published
        assert mock_pub.called
        event_names = [call[0][1].get("event") for call in mock_pub.call_args_list if isinstance(call[0][1], dict)]
        assert "transcript_ready" in event_names

        # Check raw JSON uploaded to S3
        assert mock_s3_inst.upload_json.called

        # 2. Idempotent rerun of transcribe stage
        res_rerun = run_stage(str(job_id), "transcribe")
        assert res_rerun["status"] == "succeeded"

        # Count transcripts: must still be exactly 1
        transcripts_count = sync_db.query(Transcript).filter(Transcript.video_id == video_id).count()
        assert transcripts_count == 1
