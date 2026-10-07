import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from clip_shared.db.base import utc_now
from clip_shared.db.models import (
    User,
    Video,
    Transcript,
    ClipMoment,
    Clip,
    ClipFeedback,
    ScoringRun,
    EvalVideo,
    EvalClipRating,
)


@pytest.mark.asyncio
async def test_clips_api_and_ownership_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_user: User,
    other_user: User,
):
    # 1. Setup sample video owned by sample_user
    vid = uuid.uuid4()
    video = Video(
        id=vid,
        user_id=sample_user.id,
        original_filename="startup_talk.mp4",
        storage_key=f"users/{sample_user.id}/videos/{vid}/source/startup_talk.mp4",
        size_bytes=50000000,
        content_type="video/mp4",
        status="ready",
        created_at=utc_now(),
    )
    db_session.add(video)

    # Transcript
    tid = uuid.uuid4()
    transcript = Transcript(
        id=tid,
        video_id=vid,
        language="en",
        status="ready",
        word_count=500,
        created_at=utc_now(),
    )
    db_session.add(transcript)

    # Scoring run
    s_run = ScoringRun(
        id=uuid.uuid4(),
        video_id=vid,
        prompt_version="v1",
        scorer_version="v1",
        weights={"hook": 0.3},
        model="claude-3-5-sonnet-20241022",
        input_tokens=1200,
        output_tokens=400,
        cost_inr=1.50,
        created_at=utc_now(),
    )
    db_session.add(s_run)

    # Moment & Clip
    mid = uuid.uuid4()
    moment = ClipMoment(
        id=mid,
        video_id=vid,
        transcript_id=tid,
        start_ms=10000,
        end_ms=40000,
        rank=1,
        final_score=0.91,
        status="selected",
        created_at=utc_now(),
    )
    db_session.add(moment)

    cid = uuid.uuid4()
    clip = Clip(
        id=cid,
        moment_id=mid,
        video_id=vid,
        scoring_run_id=s_run.id,
        variant_length_s="auto",
        start_ms=10000,
        end_ms=40000,
        hook_text="Why do 90% of startups fail?",
        title="The Fatal Startup Flaw",
        final_score=0.91,
        score_breakdown={"hook": 0.95, "emotion": 0.85, "coherence": 1.0, "payoff": 0.9},
        reason="Captivating hook with clear actionable advice.",
        model="claude-3-5-sonnet-20241022",
        prompt_version="v1",
        scorer_version="v1",
        created_at=utc_now(),
    )
    db_session.add(clip)
    await db_session.commit()

    # 2. GET /videos/{vid}/clips
    res = await client.get(f"/videos/{vid}/clips")
    assert res.status_code == 200
    data = res.json()
    assert data["total_moments"] == 1
    assert data["total_clips"] == 1
    assert data["moments"][0]["rank"] == 1
    assert data["moments"][0]["clips"][0]["title"] == "The Fatal Startup Flaw"

    # 3. GET /clips/{cid}
    c_res = await client.get(f"/clips/{cid}")
    assert c_res.status_code == 200
    assert c_res.json()["hook_text"] == "Why do 90% of startups fail?"

    # 4. Feedback Upsert and Delete
    fb_res = await client.post(
        f"/clips/{cid}/feedback",
        json={"value": "up", "reason_tag": None},
    )
    assert fb_res.status_code == 200
    assert fb_res.json()["value"] == "up"

    # Check updated GET includes feedback
    c_res2 = await client.get(f"/clips/{cid}")
    assert c_res2.json()["feedback"]["value"] == "up"

    # Delete feedback
    del_res = await client.delete(f"/clips/{cid}/feedback")
    assert del_res.status_code == 200

    # 5. POST /videos/{vid}/rescore
    rescore_res = await client.post(
        f"/videos/{vid}/rescore",
        json={"prompt_version": "v1", "weights": {"hook": 0.35}},
    )
    assert rescore_res.status_code == 200
    assert rescore_res.json()["status"] == "rescore_enqueued"

    # 6. GET /videos/{vid}/scoring-runs
    sr_res = await client.get(f"/videos/{vid}/scoring-runs")
    assert sr_res.status_code == 200
    assert len(sr_res.json()) >= 1

    # 7. Ownership Isolation check: other user video returns 404
    other_vid = uuid.uuid4()
    other_video = Video(
        id=other_vid,
        user_id=other_user.id,
        original_filename="secret_other.mp4",
        storage_key=f"users/{other_user.id}/videos/{other_vid}/source/secret.mp4",
        size_bytes=1000,
        content_type="video/mp4",
        status="ready",
        created_at=utc_now(),
    )
    db_session.add(other_video)
    await db_session.commit()

    iso_res = await client.get(f"/videos/{other_vid}/clips")
    assert iso_res.status_code == 404


@pytest.mark.asyncio
async def test_eval_api_endpoints(
    client: AsyncClient,
    db_session: AsyncSession,
):
    # Setup eval video
    ev = EvalVideo(
        id=uuid.uuid4(),
        slug="podcast_test_eval",
        title="Test Evaluation Podcast",
        duration_seconds=1800.0,
        meta={"speakers": ["Host"]},
        created_at=utc_now(),
    )
    db_session.add(ev)
    await db_session.commit()

    # GET /eval/videos
    v_res = await client.get("/eval/videos")
    assert v_res.status_code == 200
    assert any(v["slug"] == "podcast_test_eval" for v in v_res.json())

    # POST /eval/rate
    rate_res = await client.post(
        "/eval/rate",
        json={
            "video_slug": "podcast_test_eval",
            "start_ms": 10000,
            "end_ms": 40000,
            "rater_id": "rater_1",
            "score": 5,
            "comment": "Strong hook and resolution.",
        },
    )
    assert rate_res.status_code == 200
    assert rate_res.json()["score"] == 5

    # GET /eval/ratings/export
    exp_res = await client.get("/eval/ratings/export")
    assert exp_res.status_code == 200
    assert "podcast_test_eval" in exp_res.text
