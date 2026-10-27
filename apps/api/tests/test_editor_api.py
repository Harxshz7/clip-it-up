import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from clip_shared.db.base import utc_now
from clip_shared.db.models import (
    Clip,
    ClipMoment,
    Transcript,
    TranscriptWord,
    User,
    Video,
)


async def _create_test_clip(db_session: AsyncSession, user_id: uuid.UUID) -> tuple[Video, Clip]:
    vid = uuid.uuid4()
    video = Video(
        id=vid,
        user_id=user_id,
        original_filename="podcast_ep1.mp4",
        storage_key=f"users/{user_id}/videos/{vid}/source/podcast_ep1.mp4",
        size_bytes=10000000,
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
        word_count=100,
        created_at=utc_now(),
    )
    db_session.add(transcript)

    # Add a few words
    w1 = TranscriptWord(
        id=uuid.uuid4(),
        transcript_id=tid,
        idx=0,
        word="Hello",
        start_ms=1000,
        end_ms=1500,
        speaker="SPEAKER_00",
        confidence=0.99,
    )
    w2 = TranscriptWord(
        id=uuid.uuid4(),
        transcript_id=tid,
        idx=1,
        word="world",
        start_ms=1500,
        end_ms=2000,
        speaker="SPEAKER_00",
        confidence=0.99,
    )
    db_session.add_all([w1, w2])

    mid = uuid.uuid4()
    moment = ClipMoment(
        id=mid,
        video_id=vid,
        transcript_id=tid,
        start_ms=1000,
        end_ms=20000,
        rank=1,
        final_score=0.95,
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
        start_ms=1000,
        end_ms=20000,
        hook_text="Hello world clip hook line",
        title="Epic clip title",
        final_score=0.95,
        score_breakdown={"hook": 0.9, "retention": 0.95},
        reason="Captivating hook and great dialogue",
        model="claude-3-5-sonnet",
        prompt_version="v1",
        scorer_version="v1",
        created_at=utc_now(),
    )
    db_session.add(clip)

    await db_session.commit()
    await db_session.refresh(clip)
    await db_session.refresh(video)
    return video, clip


@pytest.mark.asyncio
async def test_editor_get_initial_edit_doc(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_user: User,
):
    video, clip = await _create_test_clip(db_session, sample_user.id)

    # 1. GET /clips/{id}/edit should auto-generate v1
    resp = await client.get(f"/clips/{clip.id}/edit")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["clip_id"] == str(clip.id)
    assert data["version"] == 1
    assert data["is_checkpoint"] is True
    doc = data["doc"]
    assert doc["range"]["start_ms"] == 1000
    assert doc["range"]["end_ms"] == 20000
    assert doc["hook"]["text"] == "Hello world clip hook line"
    assert len(doc["captions"]["words"]) == 2


@pytest.mark.asyncio
async def test_editor_put_autosave_collapse_and_conflict(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_user: User,
):
    video, clip = await _create_test_clip(db_session, sample_user.id)

    # Initialize v1
    init_res = await client.get(f"/clips/{clip.id}/edit")
    doc = init_res.json()["doc"]

    # 1. Create a checkpoint to start v2
    doc["range"]["end_ms"] = 18000
    save1 = await client.put(
        f"/clips/{clip.id}/edit",
        json={"doc": doc, "is_checkpoint": False, "label": "autosave_1"},
        headers={"If-Match": "1"},
    )
    assert save1.status_code == 200
    assert save1.json()["version"] == 2

    # 2. Rapid autosave within 30s should collapse into version 2
    doc["range"]["end_ms"] = 16000
    save2 = await client.put(
        f"/clips/{clip.id}/edit",
        json={"doc": doc, "is_checkpoint": False, "label": "autosave_2"},
        headers={"If-Match": "2"},
    )
    assert save2.status_code == 200
    # Collapsed: version remains 2
    assert save2.json()["version"] == 2
    assert save2.json()["doc"]["range"]["end_ms"] == 16000

    # 3. Explicit checkpoint creates version 3
    doc["range"]["end_ms"] = 15000
    chk_res = await client.post(
        f"/clips/{clip.id}/edit/checkpoint",
        json={"label": "trimmed to 15s"},
    )
    assert chk_res.status_code == 200
    assert chk_res.json()["version"] == 3
    assert chk_res.json()["is_checkpoint"] is True

    # 4. If-Match conflict: client sends outdated version (e.g. 1)
    conflict_res = await client.put(
        f"/clips/{clip.id}/edit",
        json={"doc": doc, "is_checkpoint": False},
        headers={"If-Match": "1"},
    )
    assert conflict_res.status_code == 409
    err = conflict_res.json()["error"]
    assert err["code"] == "VERSION_CONFLICT"
    assert err["server_version"] == 3
    assert "server_doc" in err


@pytest.mark.asyncio
async def test_editor_versions_restore_and_reset(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_user: User,
):
    video, clip = await _create_test_clip(db_session, sample_user.id)

    # Initial v1
    await client.get(f"/clips/{clip.id}/edit")

    # Checkpoint v2
    await client.post(f"/clips/{clip.id}/edit/checkpoint", json={"label": "manual checkpoint"})

    # Checkpoint v3
    await client.post(f"/clips/{clip.id}/edit/checkpoint", json={"label": "second checkpoint"})

    # List versions
    v_res = await client.get(f"/clips/{clip.id}/edit/versions")
    assert v_res.status_code == 200
    versions = v_res.json()
    assert len(versions) == 3
    assert [v["version"] for v in versions] == [3, 2, 1]

    # Restore v2
    rest_res = await client.post(f"/clips/{clip.id}/edit/restore", json={"version": 2})
    assert rest_res.status_code == 200
    restored = rest_res.json()
    assert restored["version"] == 4
    assert restored["parent_version"] == 2
    assert "Restored from v2" in restored["label"]

    # Reset to auto
    reset_res = await client.post(f"/clips/{clip.id}/edit/reset")
    assert reset_res.status_code == 200
    reset_data = reset_res.json()
    assert reset_data["version"] == 5
    assert reset_data["doc"]["range"]["end_ms"] == 20000
    assert reset_data["label"] == "Reset to auto"


@pytest.mark.asyncio
async def test_editor_alternatives_and_regenerate(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_user: User,
):
    video, clip = await _create_test_clip(db_session, sample_user.id)
    # Initialize auto doc and seeded alternatives
    await client.get(f"/clips/{clip.id}/edit")

    # List alternatives
    alt_res = await client.get(f"/clips/{clip.id}/alternatives")
    assert alt_res.status_code == 200
    alts = alt_res.json()
    assert len(alts) >= 1

    # Regenerate clip with length mode
    regen_res = await client.post(
        f"/clips/{clip.id}/regenerate",
        json={"mode": "length", "params": {"length_s": 15}},
    )
    assert regen_res.status_code == 200
    regen_data = regen_res.json()
    assert regen_data["mode"] == "length"
    assert regen_data["alternative"]["kind"] == "range"
    assert regen_data["alternative"]["end_ms"] == clip.start_ms + 15000


@pytest.mark.asyncio
async def test_editor_bulk_and_events_and_metrics(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_user: User,
):
    video, clip = await _create_test_clip(db_session, sample_user.id)

    # 1. Bulk dismiss
    bulk_res = await client.post(
        "/clips/bulk",
        json={"action": "dismiss", "clip_ids": [str(clip.id)]},
    )
    assert bulk_res.status_code == 200
    assert bulk_res.json()["count"] == 1

    # 2. Record events
    session_id = str(uuid.uuid4())
    now_iso = datetime.now(UTC).isoformat()
    events_payload = [
        {
            "session_id": session_id,
            "type": "clip_visible",
            "clip_id": str(clip.id),
            "payload": {"time": 1000},
            "created_at": now_iso,
        },
        {
            "session_id": session_id,
            "type": "delete_word",
            "clip_id": str(clip.id),
            "payload": {"word": "world"},
            "created_at": now_iso,
        },
        {
            "session_id": session_id,
            "type": "export_click",
            "clip_id": str(clip.id),
            "payload": {"preset": "tiktok"},
            "created_at": now_iso,
        },
    ]
    ev_res = await client.post("/editor/events", json={"events": events_payload})
    assert ev_res.status_code == 200
    assert ev_res.json()["count"] == 3

    # 3. Admin metrics
    metrics_res = await client.get("/admin/editor-metrics")
    assert metrics_res.status_code == 200
    metrics = metrics_res.json()
    assert metrics["total_sessions"] >= 1
    assert "delete_word" in metrics["edit_type_frequencies"]
    assert metrics["drop_off_points"]["completed_export"] >= 1


@pytest.mark.asyncio
async def test_editor_export_snapshot_records_version(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_user: User,
):
    video, clip = await _create_test_clip(db_session, sample_user.id)

    # Initialize v1
    edit_res = await client.get(f"/clips/{clip.id}/edit")
    doc = edit_res.json()["doc"]

    # Export clip
    exp_res = await client.post(
        f"/clips/{clip.id}/exports",
        json={"preset_key": "tiktok", "doc_snapshot": doc},
    )
    assert exp_res.status_code == 200
    exports = exp_res.json()
    assert len(exports) == 1
    assert exports[0]["params_snapshot"]["doc_version"] == 1
    assert exports[0]["params_snapshot"]["doc_snapshot"]["clip_id"] == str(clip.id)


@pytest.mark.asyncio
async def test_editor_ownership_isolation_and_validation(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_user: User,
    other_user: User,
):
    video, clip = await _create_test_clip(db_session, other_user.id)

    # sample_user tries to get other_user's clip -> 404
    get_res = await client.get(f"/clips/{clip.id}/edit")
    assert get_res.status_code == 404

    # Validation: invalid range (start_ms >= end_ms)
    invalid_doc = {
        "clip_id": str(clip.id),
        "base_clip_id": str(clip.id),
        "version": 1,
        "range": {"start_ms": 20000, "end_ms": 10000},  # Invalid!
        "removals": [],
        "captions": {"words": [], "style_key": "bold_pop", "style_overrides": {}, "enabled": True},
        "reframe": {"mode_overrides": {}, "keyframes": []},
        "hook": {"text": "test", "source": "auto", "start_ms": 0},
        "preset_key": "tiktok",
        "cleanup_options": {"remove_fillers": True, "remove_silence": True, "max_silence_ms": 1500},
    }
    save_res = await client.put(
        f"/clips/{clip.id}/edit",
        json={"doc": invalid_doc},
    )
    assert save_res.status_code == 422
