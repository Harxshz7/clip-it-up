import uuid
from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, ConfigDict, Field


class SpeakerResponse(BaseModel):
    id: uuid.UUID
    transcript_id: uuid.UUID
    label: str
    display_name: Optional[str] = None

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
    speaker: Optional[str] = None
    confidence: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class TranscriptSegmentResponse(BaseModel):
    id: uuid.UUID
    transcript_id: uuid.UUID
    idx: int
    start_ms: int
    end_ms: int
    speaker: Optional[str] = None
    text: str
    words: Optional[List[TranscriptWordResponse]] = None

    model_config = ConfigDict(from_attributes=True)


class TranscriptMetadataResponse(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    language: Optional[str] = None
    status: str
    model: Optional[str] = None
    backend: Optional[str] = None
    word_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TranscriptDetailResponse(BaseModel):
    transcript: TranscriptMetadataResponse
    speakers: List[SpeakerResponse]
    segments: List[TranscriptSegmentResponse]
    total_segments: int
    has_more: bool = False


class TranscriptWordsRangeResponse(BaseModel):
    words: List[TranscriptWordResponse]
    from_ms: Optional[int] = None
    to_ms: Optional[int] = None
    total: int


class ProxyUrlResponse(BaseModel):
    video_id: uuid.UUID
    proxy_url: str
    expires_in_seconds: int
    content_type: str = "video/mp4"
