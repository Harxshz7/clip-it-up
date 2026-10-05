import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class JobStageResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    name: str
    status: str
    progress: int
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    cost_inr: Decimal
    meta: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class JobResponse(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    user_id: uuid.UUID
    status: str
    current_stage: Optional[str] = None
    progress: int
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    stages: Optional[List[JobStageResponse]] = None

    model_config = ConfigDict(from_attributes=True)


class CompleteUploadResponse(BaseModel):
    video_id: uuid.UUID
    job: JobResponse
