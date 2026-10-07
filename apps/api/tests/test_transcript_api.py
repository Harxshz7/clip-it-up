import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from clip_shared.db.base import utc_now
from clip_shared.db.models import Speaker, Transcript, TranscriptSegment, TranscriptWord, Video


@pytest.mark.asyncio
async def test_transcript_api_complete_lifecycle(client: AsyncClient, sample_user, other_user, db_session: AsyncSession):
    # 1. Setup video and transcript for sample_user
    video_id = uuid.uuid4()
    video = Video(
        id=video_id,
        user_id=sample_user.id,
        original_filename="interview.mp4",
        storage_key=f"users/{sample_user.id}/videos/{video_id}/source/interview.mp4",
        proxy_key=f"users/{sample_user.id}/videos/{video_id}/proxy/proxy_720p.mp4",
        size_bytes=10240,
        duration_seconds=120.0,
        content_type="video/mp4",
        status="ready",
        created_at=utc_now(),
    )
    db_session.add(video)

    transcript_id = uuid.uuid4()
    transcript = Transcript(
        id=transcript_id,
        video_id=video_id,
        language="en",
        status="ready",
        model="large-v3",
        backend="whisperx",
        word_count=4,
        created_at=utc_now(),
    )
    db_session.add(transcript)

    # Speakers
    spk1_id = uuid.uuid4()
    spk1 = Speaker(id=spk1_id, transcript_id=transcript_id, label="SPEAKER_00", display_name="Host")
    spk2_id = uuid.uuid4()
    spk2 = Speaker(id=spk2_id, transcript_id=transcript_id, label="SPEAKER_01", display_name="Guest")
    db_session.add_all([spk1, spk2])

    # Words
    w1 = TranscriptWord(id=uuid.uuid4(), transcript_id=transcript_id, idx=0, word="Hello", start_ms=0, end_ms=400, speaker="SPEAKER_00")
    w2 = TranscriptWord(id=uuid.uuid4(), transcript_id=transcript_id, idx=1, word="world.", start_ms=450, end_ms=800, speaker="SPEAKER_00")
    w3 = TranscriptWord(id=uuid.uuid4(), transcript_id=transcript_id, idx=2, word="Hi", start_ms=1200, end_ms=1500, speaker="SPEAKER_01")
    w4 = TranscriptWord(id=uuid.uuid4(), transcript_id=transcript_id, idx=3, word="there.", start_ms=1550, end_ms=1900, speaker="SPEAKER_01")
    db_session.add_all([w1, w2, w3, w4])

    # Segments
    seg1 = TranscriptSegment(id=uuid.uuid4(), transcript_id=transcript_id, idx=0, start_ms=0, end_ms=800, speaker="SPEAKER_00", text="Hello world.")
    seg2 = TranscriptSegment(id=uuid.uuid4(), transcript_id=transcript_id, idx=1, start_ms=1200, end_ms=1900, speaker="SPEAKER_01", text="Hi there.")
    db_session.add_all([seg1, seg2])

    await db_session.commit()

    # 2. Test GET /videos/{id}/transcript
    resp = await client.get(f"/videos/{video_id}/transcript")
    assert resp.status_code == 200
    data = resp.json()
    assert data["transcript"]["id"] == str(transcript_id)
    assert len(data["speakers"]) == 2
    assert len(data["segments"]) == 2
    assert data["segments"][0]["text"] == "Hello world."

    # Test time range filtering: from_ms=1000
    resp_filtered = await client.get(f"/videos/{video_id}/transcript?from_ms=1000")
    assert resp_filtered.status_code == 200
    data_filt = resp_filtered.json()
    assert len(data_filt["segments"]) == 1
    assert data_filt["segments"][0]["text"] == "Hi there."

    # 3. Test GET /videos/{id}/transcript/words
    resp_words = await client.get(f"/videos/{video_id}/transcript/words?from_ms=0&to_ms=1000")
    assert resp_words.status_code == 200
    w_data = resp_words.json()
    assert w_data["total"] == 2
    assert w_data["words"][0]["word"] == "Hello"

    # 4. Test PATCH /videos/{id}/speakers/{speaker_id}
    resp_rename = await client.patch(
        f"/videos/{video_id}/speakers/{spk1_id}",
        json={"display_name": "Alexander"},
    )
    assert resp_rename.status_code == 200
    assert resp_rename.json()["display_name"] == "Alexander"

    # 5. Test GET /videos/{id}/proxy-url
    resp_proxy = await client.get(f"/videos/{video_id}/proxy-url")
    assert resp_proxy.status_code == 200
    assert "proxy_url" in resp_proxy.json()

    # 6. Test GET /videos/{id}/transcript/export?format=txt|srt|vtt|json
    for fmt in ["txt", "srt", "vtt", "json"]:
        resp_exp = await client.get(f"/videos/{video_id}/transcript/export?format={fmt}")
        assert resp_exp.status_code == 200
        assert len(resp_exp.text) > 0

    # 7. Ownership Isolation: other_user cannot access sample_user's transcript
    other_video_id = uuid.uuid4()
    other_video = Video(
        id=other_video_id,
        user_id=other_user.id,
        original_filename="private.mp4",
        storage_key="secret-key",
        size_bytes=100,
        content_type="video/mp4",
        status="ready",
        created_at=utc_now(),
    )
    db_session.add(other_video)
    await db_session.commit()

    resp_other = await client.get(f"/videos/{other_video_id}/transcript")
    assert resp_other.status_code == 404
    assert resp_other.json()["error"]["code"] == "VIDEO_NOT_FOUND"
