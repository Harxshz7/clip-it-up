import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from clip_shared.db.base import utc_now
from clip_shared.db.models import (
    CaptionStyle,
    Clip,
    ClipMoment,
    ExportPreset,
    Plan,
    Transcript,
    TranscriptWord,
    User,
    UserPlan,
    Video,
)


@pytest.mark.asyncio
async def test_caption_styles_and_presets_and_plan_me(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_user: User,
):
    """Verify list caption styles, export presets, and current user plan info."""
    # Seed a style and preset in test DB
    style = CaptionStyle(
        id=uuid.uuid4(),
        key="bold_pop_test",
        name="Bold Pop Test",
        version="v1",
        spec={"font_family": "Montserrat", "font_size_pt": 68},
        is_builtin=True,
    )
    db_session.add(style)

    preset = ExportPreset(
        key="tiktok_test",
        name="TikTok Test",
        width=1080,
        height=1920,
        fps=30.0,
        max_duration_s=600,
        video_bitrate="8500k",
        crf=21,
        audio_bitrate="192k",
        loudness_lufs=-14.0,
        safe_zone={"top": 140, "bottom": 320, "left": 60, "right": 120},
    )
    db_session.add(preset)

    plan = Plan(
        key="free_test",
        name="Free Test Plan",
        monthly_minutes=30,
        export_watermark=True,
        max_export_height=1920,
        max_exports_per_month=10,
        features={"watermark": True},
    )
    db_session.add(plan)

    uplan = UserPlan(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        plan_key="free_test",
        period_start=utc_now(),
    )
    db_session.add(uplan)
    await db_session.commit()

    # 1. GET /caption-styles
    resp = await client.get("/caption-styles")
    assert resp.status_code == 200
    styles_data = resp.json()
    assert any(s["key"] == "bold_pop_test" for s in styles_data)

    # 2. GET /export-presets
    resp_p = await client.get("/export-presets")
    assert resp_p.status_code == 200
    presets_data = resp_p.json()
    assert any(p["key"] == "tiktok_test" for p in presets_data)

    # 3. GET /plans/me
    resp_m = await client.get("/plans/me")
    assert resp_m.status_code == 200
    plan_me = resp_m.json()
    assert plan_me["plan"]["key"] == "free_test"
    assert plan_me["watermark_required"] is True
    assert plan_me["monthly_exports_limit"] == 10


@pytest.mark.asyncio
async def test_clip_captions_and_cleanups_lifecycle(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_user: User,
    other_user: User,
):
    """Verify clip captions creation, update, regeneration, and cleanup analyze/update."""
    vid = uuid.uuid4()
    video = Video(
        id=vid,
        user_id=sample_user.id,
        original_filename="podcast.mp4",
        storage_key=f"users/{sample_user.id}/videos/{vid}/source/podcast.mp4",
        size_bytes=40000000,
        width=1280,
        height=720,
        fps=30.0,
        duration_seconds=120.0,
        content_type="video/mp4",
        status="ready",
        created_at=utc_now(),
    )
    db_session.add(video)

    transcript = Transcript(
        id=uuid.uuid4(),
        video_id=vid,
        language="en",
        status="ready",
        word_count=5,
        created_at=utc_now(),
    )
    db_session.add(transcript)

    words = [
        TranscriptWord(id=uuid.uuid4(), transcript_id=transcript.id, idx=0, word="Hey", start_ms=1000, end_ms=1400),
        TranscriptWord(id=uuid.uuid4(), transcript_id=transcript.id, idx=1, word="um", start_ms=1500, end_ms=1800),
        TranscriptWord(id=uuid.uuid4(), transcript_id=transcript.id, idx=2, word="everyone", start_ms=1900, end_ms=2500),
        TranscriptWord(id=uuid.uuid4(), transcript_id=transcript.id, idx=3, word="welcome", start_ms=2600, end_ms=3000),
    ]
    for w in words:
        db_session.add(w)

    moment = ClipMoment(
        id=uuid.uuid4(),
        video_id=vid,
        transcript_id=transcript.id,
        start_ms=1000,
        end_ms=4000,
        status="selected",
        final_score=0.92,
    )
    db_session.add(moment)

    clip = Clip(
        id=uuid.uuid4(),
        moment_id=moment.id,
        video_id=vid,
        variant_length_s="auto",
        start_ms=1000,
        end_ms=4000,
        hook_text="Hey everyone welcome",
        title="Epic intro",
        final_score=0.92,
        score_breakdown={},
        reason="Good hook",
        model="claude-3-5-sonnet",
        prompt_version="v1",
        scorer_version="v1",
    )
    db_session.add(clip)
    await db_session.commit()

    # 1. GET /clips/{id}/captions (auto generation)
    resp_c = await client.get(f"/clips/{clip.id}/captions")
    assert resp_c.status_code == 200
    caps = resp_c.json()
    assert caps["clip_id"] == str(clip.id)
    assert len(caps["words"]) >= 4

    # 2. PUT /clips/{id}/captions (update words / style)
    up_payload = {
        "words": [
            {"text": "Hey", "start_ms": 1000, "end_ms": 1400, "emphasis": True, "deleted": False},
            {"text": "everyone", "start_ms": 1900, "end_ms": 2500, "emphasis": False, "deleted": False},
        ],
        "style_key": "clean_minimal",
    }
    resp_up = await client.put(f"/clips/{clip.id}/captions", json=up_payload)
    assert resp_up.status_code == 200
    assert resp_up.json()["style_key"] == "clean_minimal"
    assert len(resp_up.json()["words"]) == 2

    # 3. POST /clips/{id}/captions/regenerate
    resp_regen = await client.post(f"/clips/{clip.id}/captions/regenerate", json={"style_key": "bold_pop"})
    assert resp_regen.status_code == 200
    assert resp_regen.json()["style_key"] == "bold_pop"

    # 4. POST /clips/{id}/cleanup/analyze
    resp_an = await client.post(f"/clips/{clip.id}/cleanup/analyze", json={"remove_fillers": True, "remove_silence": True})
    assert resp_an.status_code == 200
    an_data = resp_an.json()
    assert an_data["original_duration_ms"] == 3000
    assert "removals" in an_data

    # 5. GET /clips/{id}/cleanup
    resp_cl = await client.get(f"/clips/{clip.id}/cleanup")
    assert resp_cl.status_code == 200

    # 6. PUT /clips/{id}/cleanup
    resp_cl_up = await client.put(
        f"/clips/{clip.id}/cleanup",
        json={
            "options": {"remove_fillers": True, "max_silence_ms": 600},
            "removals": [{"start_ms": 1500, "end_ms": 1800, "kind": "filler", "text": "um"}],
        },
    )
    assert resp_cl_up.status_code == 200
    assert len(resp_cl_up.json()["removals"]) == 1


@pytest.mark.asyncio
async def test_exports_creation_and_plan_limit_and_idempotency(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_user: User,
):
    """Verify export creation, Celery dispatch, idempotency caching, and plan limit enforcement."""
    vid = uuid.uuid4()
    video = Video(
        id=vid,
        user_id=sample_user.id,
        original_filename="clip.mp4",
        storage_key=f"users/{sample_user.id}/videos/{vid}/source/clip.mp4",
        size_bytes=20000000,
        width=1280,
        height=720,
        fps=30.0,
        duration_seconds=60.0,
        content_type="video/mp4",
        status="ready",
        created_at=utc_now(),
    )
    db_session.add(video)

    moment = ClipMoment(
        id=uuid.uuid4(),
        video_id=vid,
        transcript_id=uuid.uuid4(),
        start_ms=0,
        end_ms=20000,
        status="selected",
        final_score=0.95,
    )
    db_session.add(moment)

    clip = Clip(
        id=uuid.uuid4(),
        moment_id=moment.id,
        video_id=vid,
        variant_length_s="auto",
        start_ms=0,
        end_ms=20000,
        hook_text="Amazing intro",
        title="Clip Title",
        final_score=0.95,
        score_breakdown={},
        reason="Good",
        model="claude-3-5-sonnet",
        prompt_version="v1",
        scorer_version="v1",
    )
    db_session.add(clip)

    plan = Plan(
        key="test_plan_limit",
        name="Test Plan",
        monthly_minutes=30,
        export_watermark=False,
        max_export_height=1920,
        max_exports_per_month=2,  # Limit is 2
        features={},
    )
    db_session.add(plan)

    uplan = UserPlan(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        plan_key="test_plan_limit",
        period_start=utc_now(),
    )
    db_session.add(uplan)
    await db_session.commit()

    with patch("worker.tasks.render.render_export_task.delay") as mock_delay:
        mock_delay.return_value = None

        # 1. Create first export -> success
        resp1 = await client.post(f"/clips/{clip.id}/exports", json={"preset_key": "tiktok"})
        assert resp1.status_code == 200
        exp1_list = resp1.json()
        assert len(exp1_list) == 1
        exp1 = exp1_list[0]
        assert exp1["status"] == "queued"
        assert mock_delay.called

        # 2. Idempotency test: Same parameters while existing is queued creates or returns
        resp_idemp = await client.post(f"/clips/{clip.id}/exports", json={"preset_key": "tiktok"})
        assert resp_idemp.status_code == 200

        # 3. Create second export -> success
        resp2 = await client.post(f"/clips/{clip.id}/exports", json={"preset_key": "reels", "force": True})
        assert resp2.status_code == 200

        # 4. Third export -> should exceed plan limit of 2 (402 Payment Required)
        resp3 = await client.post(f"/clips/{clip.id}/exports", json={"preset_key": "shorts", "force": True})
        assert resp3.status_code == 402
        err = resp3.json()
        assert err["error"]["code"] == "PLAN_LIMIT_EXCEEDED"
        assert err["error"]["limit_value"] == 2
