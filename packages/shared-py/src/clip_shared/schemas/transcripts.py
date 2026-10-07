import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SpeakerResponse(BaseModel):
    id: uuid.UUID
    transcript_id: uuid.UUID
    label: str
    display_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UpdateSpeakerRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=255)


class TranscriptWordResponse(BaseModel):
    id: uuid.UUID
    transcript_id: uuid.UUID
    idx: int
    word: str
    start_ms: int
    end_ms: int
    speaker: str | None = None
    confidence: float | None = None

    model_config = ConfigDict(from_attributes=True)


class TranscriptSegmentResponse(BaseModel):
    id: uuid.UUID
    transcript_id: uuid.UUID
    idx: int
    start_ms: int
    end_ms: int
    speaker: str | None = None
    text: str
    words: list[TranscriptWordResponse] | None = None

    model_config = ConfigDict(from_attributes=True)


class TranscriptMetadataResponse(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    language: str | None = None
    status: str
    model: str | None = None
    backend: str | None = None
    word_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TranscriptDetailResponse(BaseModel):
    transcript: TranscriptMetadataResponse
    speakers: list[SpeakerResponse]
    segments: list[TranscriptSegmentResponse]
    total_segments: int
    has_more: bool = False


class TranscriptWordsRangeResponse(BaseModel):
    words: list[TranscriptWordResponse]
    from_ms: int | None = None
    to_ms: int | None = None
    total: int


class ProxyUrlResponse(BaseModel):
    video_id: uuid.UUID
    proxy_url: str
    expires_in_seconds: int
    content_type: str = "video/mp4"
