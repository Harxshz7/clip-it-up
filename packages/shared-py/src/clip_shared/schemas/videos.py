import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class UploadUrlRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=512)
    content_type: str = Field(..., min_length=1, max_length=128)
    size_bytes: int = Field(..., ge=0)
    project_id: Optional[uuid.UUID] = None


class MultipartPartInfo(BaseModel):
    part_number: int
    upload_url: str


class UploadUrlResponse(BaseModel):
    video_id: uuid.UUID
    storage_key: str
    upload_type: str  # direct_put | multipart
    upload_url: Optional[str] = None
    upload_id: Optional[str] = None
    part_urls: Optional[List[MultipartPartInfo]] = None
    part_size: Optional[int] = None
    total_parts: Optional[int] = None


class MultipartPartUrlRequest(BaseModel):
    video_id: uuid.UUID
    upload_id: str
    part_number: int = Field(..., ge=1, le=10000)


class MultipartPartUrlResponse(BaseModel):
    part_number: int
    upload_url: str


class CompletedPartInput(BaseModel):
    part_number: int = Field(..., alias="PartNumber", validation_alias="part_number")
    etag: str = Field(..., alias="ETag", validation_alias="etag")

    model_config = ConfigDict(populate_by_name=True)


class MultipartCompleteRequest(BaseModel):
    upload_id: str
    parts: List[CompletedPartInput]


class VideoResponse(BaseModel):
    id: uuid.UUID
    project_id: Optional[uuid.UUID] = None
    user_id: uuid.UUID
    original_filename: str
    storage_key: str
    size_bytes: int
    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    has_audio: bool = True
    proxy_key: Optional[str] = None
    audio_key: Optional[str] = None
    content_type: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
