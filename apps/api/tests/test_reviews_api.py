import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from clip_shared.db.base import utc_now
from clip_shared.db.models import (
    Clip,
    ClipMoment,
    ReviewRating,
    ReviewSession,
    ReviewSurvey,
    Transcript,
    User,
    Video,
)


@pytest.mark.asyncio
async def test_create_review_session_and_ownership(
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
        original_filename="podcast_ep12.mp4",
        storage_key=f"users/{sample_user.id}/videos/{vid}/source/podcast_ep12.mp4",
        size_bytes=40000000,
        content_type="video/mp4",
        status="ready",
        created_at=utc_now(),
    )
    db_session.add(video)
    await db_session.commit()

    # 2. Owner creates review session
    res = await client.post(
        f"/videos/{vid}/review-sessions",
        json={
            "creator_name": "Aarav Creator",
            "creator_email": "aarav@test.local",
            "expires_in_days": 14,
            "top_n": 8,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert len(data["token"]) >= 32
    assert "review/" in data["shareable_url"]
    assert data["creator_name"] == "Aarav Creator"
    assert data["status"] == "open"

    # 3. Owner lists sessions
    list_res = await client.get(f"/review-sessions?video_id={vid}")
    assert list_res.status_code == 200
    sessions = list_res.json()
    assert len(sessions) == 1
    assert sessions[0]["creator_name"] == "Aarav Creator"
    assert sessions[0]["status"] == "open"

    # 4. Ownership isolation: non-existent video returns 404
    fake_vid = uuid.uuid4()
    bad_res = await client.post(
        f"/videos/{fake_vid}/review-sessions",
        json={"creator_name": "Ghost"},
    )
    assert bad_res.status_code == 404


@pytest.mark.asyncio
async def test_public_review_token_and_score_hiding(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_user: User,
):
    vid = uuid.uuid4()
    video = Video(
        id=vid,
        user_id=sample_user.id,
        original_filename="interview.mp4",
        storage_key=f"users/{sample_user.id}/videos/{vid}/source/interview.mp4",
        size_bytes=30000000,
        content_type="video/mp4",
        status="ready",
        created_at=utc_now(),
    )
    db_session.add(video)

    tid = uuid.uuid4()
    transcript = Transcript(
        id=tid,
        video_id=vid,
        language="en",
        status="ready",
        word_count=200,
        created_at=utc_now(),
    )
    db_session.add(transcript)

    mid = uuid.uuid4()
    moment = ClipMoment(
        id=mid,
        video_id=vid,
        transcript_id=tid,
        start_ms=5000,
        end_ms=35000,
        rank=1,
        final_score=0.94,
        status="selected",
        created_at=utc_now(),
    )
    db_session.add(moment)

    cid = uuid.uuid4()
    clip = Clip(
        id=cid,
        moment_id=mid,
        video_id=vid,
        variant_length_s="auto",
        start_ms=5000,
        end_ms=35000,
        hook_text="This is why you shouldn't give up",
        title="Never Give Up",
        final_score=0.94,
        score_breakdown={"hook": 0.95, "emotion": 0.9},
        reason="Extremely punchy opening with relatable struggle.",
        model="claude-3-5-sonnet",
        prompt_version="v1",
        scorer_version="v1",
        created_at=utc_now(),
    )
    db_session.add(clip)

    token = "secret_creator_token_12345678901234567890"
    session = ReviewSession(
        id=uuid.uuid4(),
        video_id=vid,
        created_by=sample_user.id,
        token=token,
        creator_name="Priya Patel",
        status="open",
        expires_at=utc_now() + timedelta(days=7),
        created_at=utc_now(),
    )
    db_session.add(session)
    await db_session.commit()

    # 1. Access with valid public token
    res = await client.get(f"/review/{token}")
    assert res.status_code == 200
    pub_data = res.json()
    assert pub_data["creator_name"] == "Priya Patel"
    assert pub_data["video_title"] == "interview.mp4"
    assert "Feedback and video" in pub_data["consent_notice"]
    assert len(pub_data["clips"]) == 1

    pub_clip = pub_data["clips"][0]
    assert pub_clip["title"] == "Never Give Up"
    assert pub_clip["hook_text"] == "This is why you shouldn't give up"
    # Internal scores, breakdowns, and model names must NOT be exposed to creators
    assert "final_score" not in pub_clip
    assert "score_breakdown" not in pub_clip
    assert "model" not in pub_clip
    assert pub_clip["why_chosen"] is None

    # 2. Access with show_reasons=true flag
    res_why = await client.get(f"/review/{token}?show_reasons=true")
    assert res_why.status_code == 200
    assert res_why.json()["clips"][0]["why_chosen"] == "Extremely punchy opening with relatable struggle."

    # 3. Invalid token returns 404
    bad_token_res = await client.get("/review/invalid_token_xyz_9999999999999999")
    assert bad_token_res.status_code == 404

    # 4. Expired token returns 404
    expired_session = ReviewSession(
        id=uuid.uuid4(),
        video_id=vid,
        created_by=sample_user.id,
        token="expired_token_12345678901234567890",
        creator_name="Late Creator",
        status="open",
        expires_at=utc_now() - timedelta(days=1),
        created_at=utc_now() - timedelta(days=15),
    )
    db_session.add(expired_session)
    await db_session.commit()

    exp_res = await client.get("/review/expired_token_12345678901234567890")
    assert exp_res.status_code == 404


@pytest.mark.asyncio
async def test_rating_upsert_survey_and_submit_flow(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_user: User,
):
    vid = uuid.uuid4()
    video = Video(
        id=vid,
        user_id=sample_user.id,
        original_filename="tech_review.mp4",
        storage_key=f"users/{sample_user.id}/videos/{vid}/source/tech_review.mp4",
        size_bytes=20000000,
        content_type="video/mp4",
        status="ready",
        created_at=utc_now(),
    )
    db_session.add(video)

    mid = uuid.uuid4()
    moment = ClipMoment(
        id=mid,
        video_id=vid,
        transcript_id=uuid.uuid4(),
        start_ms=0,
        end_ms=25000,
        rank=1,
        final_score=0.88,
        status="selected",
        created_at=utc_now(),
    )
    db_session.add(moment)

    cid = uuid.uuid4()
    clip = Clip(
        id=cid,
        moment_id=mid,
        video_id=vid,
        variant_length_s="auto",
        start_ms=0,
        end_ms=25000,
        hook_text="The iPhone 16 secret feature",
        title="iPhone 16 Secret",
        final_score=0.88,
        score_breakdown={},
        reason="Good reveal.",
        model="claude",
        prompt_version="v1",
        scorer_version="v1",
        created_at=utc_now(),
    )
    db_session.add(clip)

    token = "workflow_token_12345678901234567890"
    session = ReviewSession(
        id=uuid.uuid4(),
        video_id=vid,
        created_by=sample_user.id,
        token=token,
        creator_name="Rohan Vlogs",
        status="open",
        expires_at=utc_now() + timedelta(days=14),
        created_at=utc_now(),
    )
    db_session.add(session)
    await db_session.commit()

    # 1. Submit rating for clip
    r_res = await client.put(
        f"/review/{token}/ratings/{cid}",
        json={
            "verdict": "post_with_edits",
            "reason_tag": "bad_start",
            "comment": "Trim first 1 second.",
            "watch_ms": 22000,
        },
    )
    assert r_res.status_code == 200
    r_data = r_res.json()
    assert r_data["verdict"] == "post_with_edits"
    assert r_data["reason_tag"] == "bad_start"
    assert r_data["comment"] == "Trim first 1 second."

    # 2. Update rating (idempotent upsert)
    r_res2 = await client.put(
        f"/review/{token}/ratings/{cid}",
        json={
            "verdict": "post_as_is",
            "comment": "Changed my mind, good as is.",
        },
    )
    assert r_res2.status_code == 200
    assert r_res2.json()["verdict"] == "post_as_is"

    # 3. Submit survey
    s_res = await client.put(
        f"/review/{token}/survey",
        json={
            "missing_text": "Animated captions",
            "current_workflow_text": "Premiere Pro",
            "current_cost_text": "₹5,000/mo",
            "price_open_inr": 2000,
            "accepts_1500": True,
            "accepts_4000": False,
            "would_upload_next": "yes",
            "upload_timeframe": "In 3 days",
            "email_optin": True,
        },
    )
    assert s_res.status_code == 200
    s_data = s_res.json()
    assert s_data["missing_text"] == "Animated captions"
    assert s_data["accepts_1500"] is True

    # 4. Finalize submit
    sub_res = await client.post(f"/review/{token}/submit")
    assert sub_res.status_code == 200
    assert sub_res.json()["status"] == "submitted"


@pytest.mark.asyncio
async def test_delete_review_session(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_user: User,
):
    vid = uuid.uuid4()
    video = Video(
        id=vid,
        user_id=sample_user.id,
        original_filename="delete_test.mp4",
        storage_key=f"users/{sample_user.id}/videos/{vid}/source/delete_test.mp4",
        size_bytes=1000,
        content_type="video/mp4",
        status="ready",
        created_at=utc_now(),
    )
    db_session.add(video)

    sid = uuid.uuid4()
    session = ReviewSession(
        id=sid,
        video_id=vid,
        created_by=sample_user.id,
        token="to_delete_token_12345678901234567890",
        creator_name="To Delete",
        status="open",
        expires_at=utc_now() + timedelta(days=1),
        created_at=utc_now(),
    )
    db_session.add(session)
    await db_session.commit()

    del_res = await client.delete(f"/review-sessions/{sid}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # Check that public endpoint now 404s
    get_res = await client.get("/review/to_delete_token_12345678901234567890")
    assert get_res.status_code == 404
