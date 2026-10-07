import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ClipScoreBreakdown(BaseModel):
    hook: float = Field(ge=0.0, le=1.0)
    emotion: float = Field(ge=0.0, le=1.0)
    coherence: float = Field(ge=0.0, le=1.0)
    payoff: float = Field(ge=0.0, le=1.0)
    novelty: float = Field(ge=0.0, le=1.0)
    audio_energy: float = Field(ge=0.0, le=1.0)
    laughter: float = Field(ge=0.0, le=1.0)
    pause_penalty: float = Field(ge=0.0, le=1.0)
    flag_penalty: float = Field(ge=0.0, le=1.0)
    flags: dict[str, bool] = Field(default_factory=dict)


class ClipFeedbackResponse(BaseModel):
    id: uuid.UUID
    clip_id: uuid.UUID
    user_id: uuid.UUID
    value: Literal["up", "down"]
    reason_tag: Literal["boring", "no_context", "bad_start", "bad_end", "off_topic", "other"] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClipFeedbackRequest(BaseModel):
    value: Literal["up", "down"]
    reason_tag: Literal["boring", "no_context", "bad_start", "bad_end", "off_topic", "other"] | None = None


class ClipResponse(BaseModel):
    id: uuid.UUID
    moment_id: uuid.UUID
    video_id: uuid.UUID
    scoring_run_id: uuid.UUID | None = None
    variant_length_s: str
    start_ms: int
    end_ms: int
    duration_seconds: float
    hook_text: str
    title: str
    final_score: float
    score_breakdown: dict[str, Any]
    reason: str
    model: str
    prompt_version: str
    scorer_version: str
    created_at: datetime
    feedback: ClipFeedbackResponse | None = None

    model_config = {"from_attributes": True}


class ClipMomentResponse(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    transcript_id: uuid.UUID
    start_ms: int
    end_ms: int
    duration_seconds: float
    rank: int | None = None
    final_score: float | None = None
    status: Literal["candidate", "scored", "selected", "rejected"]
    created_at: datetime
    clips: list[ClipResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class VideoClipsResponse(BaseModel):
    video_id: uuid.UUID
    moments: list[ClipMomentResponse]
    total_moments: int
    total_clips: int


class RescoreRequest(BaseModel):
    prompt_version: str | None = None
    weights: dict[str, float] | None = None


class ScoringRunResponse(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    prompt_version: str
    scorer_version: str
    weights: dict[str, Any]
    model: str
    input_tokens: int
    output_tokens: int
    cost_inr: float
    created_at: datetime

    model_config = {"from_attributes": True}
