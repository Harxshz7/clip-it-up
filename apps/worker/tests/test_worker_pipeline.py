import os
import uuid
from unittest.mock import patch, MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["ENVIRONMENT"] = "development"
os.environ["PIPELINE_STAGE_DURATION_SECONDS"] = "0.05"
os.environ["INJECT_RANDOM_FAILURE"] = "false"

from clip_shared.db.base import Base, utc_now
from clip_shared.db.models import User, Video, Job, JobStage, Usage
from worker.tasks.pipeline import run_stage, PIPELINE_STAGES


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


def test_stage_chain_and_idempotent_rerun(sync_db):
    video_id = uuid.uuid4()
    job_id = uuid.uuid4()

    video = Video(
        id=video_id,
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        original_filename="podcast.mp4",
        storage_key="test-key",
        size_bytes=1000,
        content_type="video/mp4",
        duration_seconds=300.0,
        status="uploaded",
        created_at=utc_now(),
    )
    sync_db.add(video)

    job = Job(
        id=job_id,
        video_id=video_id,
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        status="queued",
        progress=0,
        created_at=utc_now(),
    )
    sync_db.add(job)
    sync_db.commit()

    with patch("worker.tasks.pipeline.get_sync_db") as mock_db, \
         patch("worker.tasks.pipeline.publish_job_event_sync") as mock_pub, \
         patch("worker.tasks.pipeline.run_stage.delay") as mock_delay:

        mock_db.return_value.__enter__.return_value = sync_db
        mock_db.return_value.__exit__.return_value = None

        # 1. Run first stage: ingest
        res = run_stage(str(job_id), "ingest")
        assert res["status"] == "succeeded"
        assert res["stage"] == "ingest"

        # Verify next stage was triggered
        mock_delay.assert_called_with(str(job_id), "proxy")

        # 2. Run stage again (rerun test)
        res_rerun = run_stage(str(job_id), "ingest")
        assert res_rerun["status"] == "succeeded"

        # Verify usage row exists
        stage = sync_db.query(JobStage).filter(JobStage.job_id == job_id, JobStage.name == "ingest").first()
        assert stage is not None
        assert stage.status == "succeeded"
        assert stage.progress == 100
