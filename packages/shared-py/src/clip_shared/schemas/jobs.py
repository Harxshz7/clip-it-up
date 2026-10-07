import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class JobStageResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    name: str
    status: str
    progress: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    cost_inr: Decimal
    meta: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class JobResponse(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    user_id: uuid.UUID
    status: str
    current_stage: str | None = None
    progress: int
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    stages: list[JobStageResponse] | None = None

    model_config = ConfigDict(from_attributes=True)


class CompleteUploadResponse(BaseModel):
    video_id: uuid.UUID
    job: JobResponse
