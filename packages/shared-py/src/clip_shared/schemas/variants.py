"""Pydantic schemas for Auto-Variants generation, batch export, and metrics logging."""
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class VariantGenerateRequest(BaseModel):
    count: int = Field(default=4, ge=1, le=10)
    dimensions: list[Literal["hook", "style", "cta"]] = Field(
        default_factory=lambda: ["hook", "style", "cta"]
    )
    cta_goal: str | None = Field(
        default="follow",
        description="follow | link_in_bio | subscribe | engagement | comment",
    )
    include_baseline: bool = Field(
        default=True,
        description="Always include the original clip edit as variant A baseline",
    )


class ClipVariantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    set_id: uuid.UUID
    label: str
    hook_text: str | None = None
    caption_style_key: str | None = None
    cta_text: str | None = None
    cta_style: str | None = None
    score_hint: float | None = None
    export_id: uuid.UUID | None = None
    edit_doc: dict[str, Any]
    created_at: datetime


class VariantSetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    clip_id: uuid.UUID
    user_id: uuid.UUID
    status: str
    dimensions: list[str]
    requested_count: int
    created_at: datetime
    variants: list[ClipVariantResponse] = Field(default_factory=list)


class VariantBatchExportRequest(BaseModel):
    variant_ids: list[uuid.UUID] = Field(min_length=1)
    preset_key: str = "tiktok"


class VariantBatchExportResponse(BaseModel):
    set_id: uuid.UUID
    export_ids: list[uuid.UUID]
    count: int
    message: str


class ExportMetricsUpdateRequest(BaseModel):
    platform: str | None = Field(default=None, description="tiktok | reels | shorts | linkedin")
    url: str | None = Field(default=None, description="External published post URL")
    views: int | None = Field(default=None, ge=0)
    likes: int | None = Field(default=None, ge=0)
    avg_watch_pct: float | None = Field(default=None, ge=0.0, le=100.0)
