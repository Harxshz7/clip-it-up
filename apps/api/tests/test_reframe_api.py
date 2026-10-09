import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from clip_shared.db.base import utc_now
from clip_shared.db.models import (
    Clip,
    ClipMoment,
    ClipReframe,
    FaceTrack,
    User,
    Video,
    VideoAnalysis,
)


@pytest.mark.asyncio
async def test_reframe_api_endpoints_and_ownership(
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

    # 2. Setup video analysis
    analysis_id = uuid.uuid4()
    analysis = VideoAnalysis(
        id=analysis_id,
        video_id=vid,
        version="v1",
        fps_sampled=6.0,
        scenes=[
            {"start_ms": 0, "end_ms": 60000, "type": "talking_head", "confidence": 0.95},
            {"start_ms": 60000, "end_ms": 120000, "type": "two_shot", "confidence": 0.92},
        ],
        status="ready",
        summary={"total_face_tracks": 1, "total_scenes": 2},
        created_at=utc_now(),
    )
    db_session.add(analysis)

    # 3. Setup FaceTrack
    ft = FaceTrack(
        id=uuid.uuid4(),
        analysis_id=analysis_id,
        track_id=0,
        start_ms=0,
        end_ms=60000,
        avg_conf=0.96,
        speaker_label="SPEAKER_00",
        summary={"mean_cx": 0.52, "mean_cy": 0.38, "mean_w": 0.18, "mean_h": 0.22},
        created_at=utc_now(),
    )
    db_session.add(ft)

    # 4. Setup Clip
    mid = uuid.uuid4()
    moment = ClipMoment(
        id=mid,
        video_id=vid,
        transcript_id=uuid.uuid4(),
        start_ms=5000,
        end_ms=35000,
        status="selected",
        final_score=0.92,
        created_at=utc_now(),
    )
    db_session.add(moment)

    cid = uuid.uuid4()
    clip = Clip(
        id=cid,
        moment_id=mid,
        video_id=vid,
        variant_length_s="30",
        start_ms=5000,
        end_ms=35000,
        hook_text="Exciting Hook",
        title="Sample Clip",
        final_score=0.92,
        score_breakdown={},
        reason="Good narrative",
        model="claude-3-5-sonnet",
        prompt_version="v1",
        scorer_version="v1",
        created_at=utc_now(),
    )
    db_session.add(clip)

    # 5. Setup auto ClipReframe
    reframe = ClipReframe(
        id=uuid.uuid4(),
        clip_id=cid,
        analysis_version="v1",
        mode="speaker_track",
        crop_path={
            "keyframes": [
                {"t_ms": 5000, "cx": 0.52, "cy": 0.45, "w": 0.3164, "h": 1.0},
                {"t_ms": 35000, "cx": 0.52, "cy": 0.45, "w": 0.3164, "h": 1.0},
            ],
            "segments": [{"start_ms": 5000, "end_ms": 35000, "mode": "speaker_track", "confidence": 0.95}],
            "target_aspect": "9:16",
        },
        confidence=0.95,
        flags={"face_cut_risk": False, "low_confidence": False, "multi_person": False},
        source="auto",
        created_at=utc_now(),
    )
    db_session.add(reframe)
    await db_session.commit()

    # 6. Test GET /videos/{video_id}/analysis (Authenticated as sample_user)
    headers = {"Authorization": f"Bearer {sample_user.id}"}
    res = await client.get(f"/videos/{vid}/analysis", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["video_id"] == str(vid)
    assert data["status"] == "ready"
    assert len(data["scenes"]) == 2
    assert len(data["face_tracks"]) == 1

    # 7. Test GET /clips/{clip_id}/reframe
    res = await client.get(f"/clips/{cid}/reframe", headers=headers)
    assert res.status_code == 200
    r_data = res.json()
    assert r_data["clip_id"] == str(cid)
    assert r_data["mode"] == "speaker_track"
    assert len(r_data["active_keyframes"]) == 2
    assert r_data["has_edits"] is False

    # 8. Test PUT /clips/{clip_id}/reframe (Manual nudge)
    nudge_payload = {
        "keyframes": [
            {"t_ms": 5000, "cx": 0.58, "cy": 0.46, "w": 0.3164, "h": 1.0},
            {"t_ms": 35000, "cx": 0.60, "cy": 0.46, "w": 0.3164, "h": 1.0},
        ],
        "mode": "speaker_track",
    }
    put_res = await client.put(f"/clips/{cid}/reframe", json=nudge_payload, headers=headers)
    assert put_res.status_code == 200
    put_data = put_res.json()
    assert put_data["has_edits"] is True
    assert put_data["active_keyframes"][0]["cx"] == 0.58

    # 9. Test DELETE /clips/{clip_id}/reframe/edits (Revert back to auto)
    del_res = await client.delete(f"/clips/{cid}/reframe/edits", headers=headers)
    assert del_res.status_code == 200
    del_data = del_res.json()
    assert del_data["has_edits"] is False
    assert del_data["active_keyframes"][0]["cx"] == 0.52

    # 10. Test Ownership Isolation (other_user gets 404)
    other_headers = {"Authorization": f"Bearer {other_user.id}"}
    unauth_get = await client.get(f"/clips/{cid}/reframe", headers=other_headers)
    assert unauth_get.status_code == 404

    unauth_put = await client.put(f"/clips/{cid}/reframe", json=nudge_payload, headers=other_headers)
    assert unauth_put.status_code == 404
