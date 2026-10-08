import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

VerdictType = Literal["post_as_is", "post_with_edits", "no"]
ReasonTagType = Literal[
    "bad_start",
    "bad_end",
    "no_context",
    "boring",
    "off_topic",
    "too_long",
    "too_short",
    "other",
]
SessionStatusType = Literal["open", "submitted", "closed"]
UploadIntentType = Literal["yes", "maybe", "no"]
ExportKindType = Literal["horizontal", "vertical_center"]


class ReviewSessionCreateRequest(BaseModel):
    creator_name: str = Field(min_length=1, max_length=255)
    creator_email: str | None = Field(default=None, max_length=255)
    expires_in_days: int = Field(default=14, ge=1, le=90)
    top_n: int = Field(default=8, ge=1, le=50)


class ReviewRatingUpsertRequest(BaseModel):
    verdict: VerdictType
    reason_tag: ReasonTagType | None = None
    comment: str | None = Field(default=None, max_length=5000)
    watch_ms: int = Field(default=0, ge=0)


class ReviewRatingResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    clip_id: uuid.UUID
    verdict: VerdictType
    reason_tag: str | None = None
    comment: str | None = None
    watch_ms: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewSurveyUpsertRequest(BaseModel):
    missing_text: str | None = Field(default=None, max_length=5000)
    current_workflow_text: str | None = Field(default=None, max_length=5000)
    current_cost_text: str | None = Field(default=None, max_length=5000)
    price_open_inr: float | None = Field(default=None, ge=0.0)
    accepts_1500: bool | None = None
    accepts_4000: bool | None = None
    would_upload_next: UploadIntentType | None = None
    upload_timeframe: str | None = Field(default=None, max_length=128)
    email_optin: bool = False


class ReviewSurveyResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    missing_text: str | None = None
    current_workflow_text: str | None = None
    current_cost_text: str | None = None
    price_open_inr: float | None = None
    accepts_1500: bool | None = None
    accepts_4000: bool | None = None
    would_upload_next: UploadIntentType | None = None
    upload_timeframe: str | None = None
    email_optin: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewExportInfo(BaseModel):
    clip_id: uuid.UUID
    kind: ExportKindType
    url: str

    model_config = {"from_attributes": True}


class ReviewClipPublicResponse(BaseModel):
    clip_id: uuid.UUID
    moment_id: uuid.UUID
    rank: int | None = None
    title: str
    hook_text: str
    start_ms: int
    end_ms: int
    duration_seconds: float
    variant_length_s: str
    video_urls: dict[str, str] = Field(default_factory=dict)  # {"vertical_center": url, "horizontal": url}
    rating: ReviewRatingResponse | None = None
    why_chosen: str | None = None  # Hidden by default to prevent anchoring; shown only when requested

    model_config = {"from_attributes": True}


class ReviewSessionPublicResponse(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    token: str
    creator_name: str
    status: SessionStatusType
    expires_at: datetime
    created_at: datetime
    submitted_at: datetime | None = None
    video_title: str
    consent_notice: str
    clips: list[ReviewClipPublicResponse] = Field(default_factory=list)
    survey: ReviewSurveyResponse | None = None


class ReviewSessionOwnerResponse(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    token: str
    creator_name: str
    creator_email: str | None = None
    status: SessionStatusType
    shareable_url: str
    expires_at: datetime
    created_at: datetime
    submitted_at: datetime | None = None
    ratings: list[ReviewRatingResponse] = Field(default_factory=list)
    survey: ReviewSurveyResponse | None = None
    total_clips: int = 0
    rated_clips_count: int = 0

    model_config = {"from_attributes": True}


class ReviewSessionCreatedResponse(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    token: str
    shareable_url: str
    creator_name: str
    creator_email: str | None = None
    status: SessionStatusType
    expires_at: datetime
    created_at: datetime
    message: str = "Review session created successfully."


class GateReportResponse(BaseModel):
    report_id: str
    timestamp: str
    generated_at: str
    overall_verdict: Literal["GO", "FIX SELECTION FIRST", "RETHINK"]
    checks: list[dict[str, Any]]
    metrics: dict[str, Any]
    creator_summaries: list[dict[str, Any]]
    recommendations: list[str]
    markdown_path: str | None = None
    json_path: str | None = None
