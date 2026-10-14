import uuid
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator


class RangeModel(BaseModel):
    start_ms: int = Field(ge=0, description="Start time in source milliseconds")
    end_ms: int = Field(gt=0, description="End time in source milliseconds")

    @model_validator(mode="after")
    def validate_range(self) -> "RangeModel":
        if self.start_ms >= self.end_ms:
            raise ValueError(f"start_ms ({self.start_ms}) must be strictly less than end_ms ({self.end_ms})")
        return self


class RemovalModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    kind: Literal["filler", "silence", "manual", "mixed"] = "manual"
    enabled: bool = True
    text: str | None = None

    @model_validator(mode="after")
    def validate_removal(self) -> "RemovalModel":
        if self.start_ms > self.end_ms:
            raise ValueError(f"Removal start_ms ({self.start_ms}) must be <= end_ms ({self.end_ms})")
        return self


class CaptionWordModel(BaseModel):
    text: str
    start_ms: int
    end_ms: int
    speaker: str | None = None
    emphasis: bool = False
    deleted: bool = False


class CaptionsModel(BaseModel):
    words: list[CaptionWordModel] = Field(default_factory=list)
    style_key: str = "bold_pop"
    style_overrides: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class ReframeKeyframeModel(BaseModel):
    t_ms: int
    x: float
    y: float
    width: float | None = None
    height: float | None = None
    scale: float | None = None


class ReframeModel(BaseModel):
    mode_overrides: dict[str, str] = Field(default_factory=dict)
    keyframes: list[ReframeKeyframeModel] = Field(default_factory=list)


class HookModel(BaseModel):
    text: str
    source: Literal["auto", "alt", "manual"] = "auto"
    start_ms: int = 0


class CleanupOptionsModel(BaseModel):
    remove_fillers: bool = True
    remove_silence: bool = True
    max_silence_ms: int = 1500
    target_silence_ms: int = 500
    crossfade_ms: int = 25
    snap_cuts: bool = True


class BrandConfigModel(BaseModel):
    kit_id: str | None = None
    apply_logo: bool = True
    apply_intro: bool = True
    apply_outro: bool = True
    apply_style: bool = True


class CTAModel(BaseModel):
    text: str = ""
    style: str | None = "overlay"  # overlay | end_card
    duration_s: float = 2.0


class ClipEditDoc(BaseModel):
    clip_id: str
    base_clip_id: str
    version: int = Field(ge=1)
    range: RangeModel
    removals: list[RemovalModel] = Field(default_factory=list)
    captions: CaptionsModel
    reframe: ReframeModel = Field(default_factory=ReframeModel)
    hook: HookModel
    preset_key: str = "tiktok"
    cleanup_options: CleanupOptionsModel = Field(default_factory=CleanupOptionsModel)
    brand: BrandConfigModel | None = Field(default_factory=BrandConfigModel)
    cta: CTAModel | None = None

    @model_validator(mode="after")
    def validate_doc(self) -> "ClipEditDoc":
        # Validate that enabled removals are ordered and non-overlapping
        enabled_removals = [r for r in self.removals if r.enabled]
        # Sort check
        for i in range(len(enabled_removals) - 1):
            curr = enabled_removals[i]
            nxt = enabled_removals[i + 1]
            if nxt.start_ms < curr.start_ms:
                raise ValueError("Removals must be ordered by start_ms")
            if curr.end_ms > nxt.start_ms:
                raise ValueError(
                    f"Overlapping removals detected: [{curr.start_ms}, {curr.end_ms}] and [{nxt.start_ms}, {nxt.end_ms}]"
                )
        return self


class ClipEditResponse(BaseModel):
    id: uuid.UUID
    clip_id: uuid.UUID
    user_id: uuid.UUID
    version: int
    doc: ClipEditDoc
    parent_version: int | None = None
    label: str | None = None
    is_checkpoint: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class ClipEditVersionSummary(BaseModel):
    version: int
    parent_version: int | None = None
    label: str | None = None
    is_checkpoint: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class ClipEditSaveRequest(BaseModel):
    doc: ClipEditDoc
    label: str | None = None
    is_checkpoint: bool = False


class ClipEditCheckpointRequest(BaseModel):
    label: str = Field(min_length=1, max_length=255)


class ClipEditRestoreRequest(BaseModel):
    version: int = Field(ge=1)


class ClipAlternativeResponse(BaseModel):
    id: uuid.UUID
    clip_id: uuid.UUID
    kind: Literal["hook", "range"]
    start_ms: int
    end_ms: int
    text: str
    score: float | None = None
    reason: str | None = None
    source: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClipRegenerateRequest(BaseModel):
    mode: Literal["length", "hook", "trim", "similar"]
    params: dict[str, Any] = Field(default_factory=dict)


class ClipBulkActionRequest(BaseModel):
    action: Literal["dismiss", "export"]
    clip_ids: list[uuid.UUID]
    preset: str | None = None


class EditorEventPayload(BaseModel):
    session_id: str
    type: str
    clip_id: uuid.UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class EditorEventsBatchRequest(BaseModel):
    events: list[EditorEventPayload]


class EditorMetricsResponse(BaseModel):
    total_sessions: int
    median_hands_on_time_s: float
    p90_hands_on_time_s: float
    median_time_to_first_clip_s: float
    median_time_to_first_edit_s: float
    median_time_to_first_export_s: float
    export_without_editing_rate: float
    edit_type_frequencies: dict[str, int]
    drop_off_points: dict[str, int]
    total_regenerate_count: int
