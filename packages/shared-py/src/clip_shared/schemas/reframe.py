import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


ReframeMode = Literal[
    "speaker_track",
    "balanced",
    "center",
    "fit_blur",
    "split_stack",
    "content_fit",
    "content_zoom",
    "stack",
    "pip",
]

SceneType = Literal[
    "talking_head",
    "two_shot",
    "group",
    "screen_content",
    "whiteboard",
    "hybrid_pip",
    "b_roll_other",
    "wide_multi",
    "screen_share_or_slides",
    "other",
]


class LayoutRegion(BaseModel):
    src_x: float = Field(default=0.0, ge=0.0, le=1.0)
    src_y: float = Field(default=0.0, ge=0.0, le=1.0)
    src_w: float = Field(default=1.0, gt=0.0, le=1.0)
    src_h: float = Field(default=1.0, gt=0.0, le=1.0)
    dst_x: float = Field(default=0.0, ge=0.0, le=1.0)
    dst_y: float = Field(default=0.0, ge=0.0, le=1.0)
    dst_w: float = Field(default=1.0, gt=0.0, le=1.0)
    dst_h: float = Field(default=1.0, gt=0.0, le=1.0)
    shape: Literal["rect", "circle", "rounded_rect"] = "rect"
    corner_radius: float = 0.0
    border_width: int = 0
    border_color: str = "#ffffff"
    track_id: int | None = None
    label: str | None = None


class ReframeLayout(BaseModel):
    type: Literal["content_fit", "content_zoom", "split_stack", "stack", "pip", "crop"]
    regions: list[LayoutRegion] = Field(default_factory=list)
    background: Literal["blur", "color", "brand"] = "blur"
    background_color: str = "#0b0f17"
    safe_zones: dict[str, Any] = Field(default_factory=dict)


class ReframeKeyframe(BaseModel):
    t_ms: int = Field(ge=0, description="Timestamp in milliseconds")
    cx: float = Field(ge=0.0, le=1.0, description="Normalized crop center X (0 to 1)")
    cy: float = Field(ge=0.0, le=1.0, description="Normalized crop center Y (0 to 1)")
    w: float = Field(gt=0.0, le=1.0, description="Normalized crop width (0 to 1)")
    h: float = Field(gt=0.0, le=1.0, description="Normalized crop height (0 to 1)")

    @field_validator("cx", "cy", "w", "h")
    @classmethod
    def clamp_bounds(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))


class ReframeSegment(BaseModel):
    start_ms: int
    end_ms: int
    mode: ReframeMode
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    target_track_id: int | None = None
    fallback_reason: str | None = None
    layout: ReframeLayout | dict[str, Any] | None = None


class ReframeFlags(BaseModel):
    face_cut_risk: bool = False
    low_confidence: bool = False
    multi_person: bool = False
    unreadable_text: bool = False
    multi_speaker_conflict: bool = False
    low_roi_confidence: bool = False
    reaction_cutaway: bool = False
    ping_pong_prevented: bool = False
    fallback_reason: str | None = None
    suggested_fix: str | None = None


class ReframeCropPath(BaseModel):
    keyframes: list[ReframeKeyframe] = Field(default_factory=list)
    segments: list[ReframeSegment] = Field(default_factory=list)
    layout: ReframeLayout | dict[str, Any] | None = None
    easing: str = "ease_in_out"
    source_width: int | None = None
    source_height: int | None = None
    target_aspect: str = "9:16"


class ReframeResponse(BaseModel):
    id: uuid.UUID
    clip_id: uuid.UUID
    analysis_version: str
    mode: ReframeMode
    crop_path: ReframeCropPath
    layout: ReframeLayout | dict[str, Any] | None = None
    confidence: float
    flags: ReframeFlags
    source: Literal["auto", "manual"]
    has_edits: bool = False
    created_at: datetime
    active_keyframes: list[ReframeKeyframe] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ReframeUpdateRequest(BaseModel):
    keyframes: list[ReframeKeyframe] = Field(min_length=1, max_length=1000)
    mode: ReframeMode | None = None
    layout: ReframeLayout | dict[str, Any] | None = None


class ReframeRegenerateRequest(BaseModel):
    mode_override: ReframeMode | None = None
    analysis_version: str | None = None


class SceneItem(BaseModel):
    start_ms: int
    end_ms: int
    type: SceneType
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    num_faces: int = 0
    sub_shots: list[dict[str, Any]] = Field(default_factory=list)
    features: dict[str, Any] = Field(default_factory=dict)


class FaceTrackResponse(BaseModel):
    id: uuid.UUID
    track_id: int
    start_ms: int
    end_ms: int
    avg_conf: float
    speaker_label: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class VideoAnalysisResponse(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    version: str
    fps_sampled: float
    scenes: list[SceneItem]
    status: Literal["queued", "running", "ready", "failed"]
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    face_tracks: list[FaceTrackResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
