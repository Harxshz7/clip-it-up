import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EvalVideoResponse(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    source_url: str | None = None
    duration_seconds: float | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class EvalClipRatingRequest(BaseModel):
    video_slug: str
    start_ms: int
    end_ms: int
    clip_id: uuid.UUID | None = None
    rater_id: str
    score: int = Field(ge=1, le=5, description="1-5 rating")
    comment: str | None = None


class EvalClipRatingResponse(BaseModel):
    id: uuid.UUID
    video_slug: str
    start_ms: int
    end_ms: int
    clip_id: uuid.UUID | None = None
    rater_id: str
    score: int
    comment: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EvalRatingsExportResponse(BaseModel):
    ratings: list[EvalClipRatingResponse]
    total: int
