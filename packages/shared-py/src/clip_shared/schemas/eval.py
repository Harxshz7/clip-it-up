import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class EvalVideoResponse(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    source_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class EvalClipRatingRequest(BaseModel):
    video_slug: str
    start_ms: int
    end_ms: int
    clip_id: Optional[uuid.UUID] = None
    rater_id: str
    score: int = Field(ge=1, le=5, description="1-5 rating")
    comment: Optional[str] = None


class EvalClipRatingResponse(BaseModel):
    id: uuid.UUID
    video_slug: str
    start_ms: int
    end_ms: int
    clip_id: Optional[uuid.UUID] = None
    rater_id: str
    score: int
    comment: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EvalRatingsExportResponse(BaseModel):
    ratings: List[EvalClipRatingResponse]
    total: int
