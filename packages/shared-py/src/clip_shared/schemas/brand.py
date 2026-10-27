"""Pydantic schemas for Brand Kits and Brand Assets."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BrandColors(BaseModel):
    primary: str = "#8B5CF6"
    secondary: str = "#6366F1"
    text: str = "#FFFFFF"
    highlight: str = "#FACC15"
    background: str = "#0F172A"


class BrandFonts(BaseModel):
    heading_asset_id: str | None = None
    body_asset_id: str | None = None
    font_family: str | None = None


class BrandAssetUploadUrlRequest(BaseModel):
    filename: str
    content_type: str
    size_bytes: int = Field(gt=0)
    kind: Literal["logo", "font", "intro", "outro"]


class BrandAssetUploadUrlResponse(BaseModel):
    asset_id: uuid.UUID
    upload_url: str
    storage_key: str
    expires_in_seconds: int = 3600


class BrandAssetCompleteRequest(BaseModel):
    asset_id: uuid.UUID | None = None
    license_acknowledged: bool = Field(
        default=False,
        description="Required true for custom font uploads acknowledging commercial license rights",
    )


class BrandAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    kind: str
    storage_key: str
    filename: str
    content_type: str
    size_bytes: int
    width: int | None = None
    height: int | None = None
    duration_ms: int | None = None
    status: str
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    download_url: str | None = None


class BrandKitCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    is_default: bool = False
    colors: dict[str, str] = Field(
        default_factory=lambda: {
            "primary": "#8B5CF6",
            "secondary": "#6366F1",
            "text": "#FFFFFF",
            "highlight": "#FACC15",
            "background": "#0F172A",
        }
    )
    fonts: dict[str, Any] = Field(default_factory=dict)
    logo_asset_id: uuid.UUID | None = None
    logo_position: Literal["top_left", "top_right", "bottom_left", "bottom_right"] = "top_right"
    logo_opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    logo_scale: float = Field(default=0.15, ge=0.05, le=0.35)
    caption_style_key: str | None = "bold_pop"
    caption_overrides: dict[str, Any] = Field(default_factory=dict)
    intro_asset_id: uuid.UUID | None = None
    outro_asset_id: uuid.UUID | None = None
    watermark_free_override: bool = False


class BrandKitUpdateRequest(BaseModel):
    name: str | None = None
    is_default: bool | None = None
    colors: dict[str, str] | None = None
    fonts: dict[str, Any] | None = None
    logo_asset_id: uuid.UUID | None = None
    logo_position: Literal["top_left", "top_right", "bottom_left", "bottom_right"] | None = None
    logo_opacity: float | None = Field(default=None, ge=0.0, le=1.0)
    logo_scale: float | None = Field(default=None, ge=0.05, le=0.35)
    caption_style_key: str | None = None
    caption_overrides: dict[str, Any] | None = None
    intro_asset_id: uuid.UUID | None = None
    outro_asset_id: uuid.UUID | None = None
    watermark_free_override: bool | None = None


class BrandKitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    is_default: bool
    colors: dict[str, Any]
    fonts: dict[str, Any]
    logo_asset_id: uuid.UUID | None = None
    logo_position: str
    logo_opacity: float
    logo_scale: float
    caption_style_key: str | None = None
    caption_overrides: dict[str, Any] = Field(default_factory=dict)
    intro_asset_id: uuid.UUID | None = None
    outro_asset_id: uuid.UUID | None = None
    watermark_free_override: bool
    created_at: datetime
    updated_at: datetime
    logo_asset: BrandAssetResponse | None = None
    intro_asset: BrandAssetResponse | None = None
    outro_asset: BrandAssetResponse | None = None
