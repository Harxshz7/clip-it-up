import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class CaptionStyleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name: str
    version: str
    spec: dict[str, Any]
    is_builtin: bool
    created_at: datetime


class ExportPresetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    name: str
    width: int
    height: int
    fps: float
    max_duration_s: int
    video_bitrate: str
    crf: int
    audio_bitrate: str
    loudness_lufs: float
    safe_zone: dict[str, Any]
    notes: str | None = None


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    name: str
    monthly_minutes: int
    export_watermark: bool
    max_export_height: int
    max_exports_per_month: int
    features: dict[str, Any]


class UserPlanMeResponse(BaseModel):
    plan: PlanResponse
    period_start: datetime
    monthly_source_minutes_used: float
    monthly_exports_used: int
    monthly_source_minutes_limit: int
    monthly_exports_limit: int
    watermark_required: bool


class ClipCaptionsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    clip_id: uuid.UUID
    version: str
    language: str
    words: list[dict[str, Any]]
    style_key: str
    style_overrides: dict[str, Any]
    source: str
    created_at: datetime


class ClipCaptionsUpdateRequest(BaseModel):
    words: list[dict[str, Any]]
    style_key: str | None = None
    style_overrides: dict[str, Any] | None = None


class ClipCaptionsRegenerateRequest(BaseModel):
    style_key: str | None = "bold_pop"
    language: str | None = "en"


class ClipCleanupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    clip_id: uuid.UUID
    version: str
    options: dict[str, Any]
    removals: list[dict[str, Any]]
    created_at: datetime


class ClipCleanupUpdateRequest(BaseModel):
    options: dict[str, Any] | None = None
    removals: list[dict[str, Any]] | None = None


class ClipCleanupAnalyzeResponse(BaseModel):
    clip_start_ms: int
    clip_end_ms: int
    original_duration_ms: int
    clean_duration_ms: int
    saved_ms: int
    saved_seconds: float
    cut_count: int
    filler_count: int
    silence_count: int
    savings_ratio: float
    options: dict[str, Any]
    removals: list[dict[str, Any]]
    keep_segments: list[dict[str, Any]]


class CreateExportRequest(BaseModel):
    preset_key: str | None = None
    presets: list[str] | None = None
    style_key: str | None = None
    force: bool = False


class ExportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    clip_id: uuid.UUID
    user_id: uuid.UUID
    status: str
    preset_key: str
    params_snapshot: dict[str, Any]
    storage_key: str | None = None
    duration_ms: int | None = None
    size_bytes: int | None = None
    render_ms: int | None = None
    error: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
    download_url: str | None = None


class DownloadUrlResponse(BaseModel):
    export_id: uuid.UUID
    download_url: str
    expires_in_seconds: int
