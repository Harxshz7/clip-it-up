import math
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from clip_shared.config import get_settings
from clip_shared.db.session import get_db
from clip_shared.db.models import Video, Job, JobStage, Project
from clip_shared.db.base import utc_now
from clip_shared.schemas.auth import AuthenticatedUser
from clip_shared.schemas.videos import (
    UploadUrlRequest,
    UploadUrlResponse,
    MultipartPartInfo,
    MultipartPartUrlRequest,
    MultipartPartUrlResponse,
    MultipartCompleteRequest,
    VideoResponse,
)
from clip_shared.schemas.jobs import CompleteUploadResponse, JobResponse
from clip_shared.storage.s3 import get_s3_client, get_storage_key, sanitize_filename
from api.dependencies import get_current_user

router = APIRouter(prefix="/videos", tags=["videos"])
settings = get_settings()


@router.post("/upload-url", response_model=UploadUrlResponse)
async def create_upload_url(
    payload: UploadUrlRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Validate video upload request, create Video entry (status=uploading),
    and return presigned PUT URL or multipart upload parameters.
    """
    # 1. Content type validation
    if payload.content_type.lower() not in [c.lower() for c in settings.ALLOWED_CONTENT_TYPES]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_CONTENT_TYPE",
                    "message": f"Unsupported content type '{payload.content_type}'. Allowed types: {', '.join(settings.ALLOWED_CONTENT_TYPES)}",
                }
            },
        )

    # 2. Size validation
    if payload.size_bytes <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_FILE_SIZE", "message": "File size must be greater than 0 bytes."}},
        )

    if payload.size_bytes > settings.MAX_UPLOAD_SIZE_BYTES:
        max_gb = settings.MAX_UPLOAD_SIZE_BYTES / (1024 * 1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "FILE_TOO_LARGE",
                    "message": f"File size exceeds maximum allowed limit of {max_gb:.1f} GB.",
                }
            },
        )

    # 3. Verify project if specified
    project_id = payload.project_id
    if project_id:
        proj_stmt = select(Project).where(Project.id == project_id, Project.user_id == user.id)
        proj_res = await db.execute(proj_stmt)
        if not proj_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "PROJECT_NOT_FOUND", "message": "Project not found."}},
            )

    video_id = uuid.uuid4()
    storage_key = get_storage_key(user.id, video_id, payload.filename)

    # Create Video record
    video = Video(
        id=video_id,
        project_id=project_id,
        user_id=user.id,
        original_filename=sanitize_filename(payload.filename),
        storage_key=storage_key,
        size_bytes=payload.size_bytes,
        content_type=payload.content_type,
        status="uploading",
        created_at=utc_now(),
    )
    db.add(video)
    await db.commit()
    await db.refresh(video)

    s3 = get_s3_client()

    # Determine single PUT vs Multipart
    if payload.size_bytes <= settings.MULTIPART_THRESHOLD_BYTES:
        presigned_url = s3.generate_presigned_put_url(
            storage_key=storage_key,
            content_type=payload.content_type,
        )
        return UploadUrlResponse(
            video_id=video_id,
            storage_key=storage_key,
            upload_type="direct_put",
            upload_url=presigned_url,
        )
    else:
        # Multipart Upload initialization
        upload_id = s3.create_multipart_upload(
            storage_key=storage_key,
            content_type=payload.content_type,
        )
        part_size = settings.MULTIPART_PART_SIZE_BYTES
        total_parts = math.ceil(payload.size_bytes / part_size)

        part_urls: List[MultipartPartInfo] = []
        for part_num in range(1, total_parts + 1):
            p_url = s3.generate_presigned_part_url(
                storage_key=storage_key,
                upload_id=upload_id,
                part_number=part_num,
            )
            part_urls.append(MultipartPartInfo(part_number=part_num, upload_url=p_url))

        return UploadUrlResponse(
            video_id=video_id,
            storage_key=storage_key,
            upload_type="multipart",
            upload_id=upload_id,
            part_urls=part_urls,
            part_size=part_size,
            total_parts=total_parts,
        )


@router.post("/multipart/part-url", response_model=MultipartPartUrlResponse)
async def get_multipart_part_url(
    payload: MultipartPartUrlRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a presigned PUT URL for a retry of a specific multipart part."""
    stmt = select(Video).where(Video.id == payload.video_id, Video.user_id == user.id)
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "VIDEO_NOT_FOUND", "message": "Video not found."}},
        )

    s3 = get_s3_client()
    url = s3.generate_presigned_part_url(
        storage_key=video.storage_key,
        upload_id=payload.upload_id,
        part_number=payload.part_number,
    )
    return MultipartPartUrlResponse(part_number=payload.part_number, upload_url=url)


@router.post("/multipart/complete/{video_id}")
async def complete_multipart(
    video_id: uuid.UUID,
    payload: MultipartCompleteRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Complete an S3 multipart upload."""
    stmt = select(Video).where(Video.id == video_id, Video.user_id == user.id)
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "VIDEO_NOT_FOUND", "message": "Video not found."}},
        )

    s3 = get_s3_client()
    parts_list = [{"PartNumber": p.part_number, "ETag": p.etag} for p in payload.parts]
    try:
        s3.complete_multipart_upload(
            storage_key=video.storage_key,
            upload_id=payload.upload_id,
            parts=parts_list,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "MULTIPART_COMPLETE_FAILED", "message": f"Failed to complete multipart upload: {str(e)}"}},
        )

    return {"status": "multipart_completed", "video_id": str(video_id)}


@router.post("/{video_id}/complete", response_model=CompleteUploadResponse)
async def complete_video_upload(
    video_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Verify video uploaded to S3 (via HEAD request), update status to 'uploaded',
    create a Job and initial JobStages, and enqueue worker pipeline.
    """
    stmt = select(Video).where(Video.id == video_id, Video.user_id == user.id)
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "VIDEO_NOT_FOUND", "message": "Video not found."}},
        )

    s3 = get_s3_client()
    exists = s3.check_object_exists(video.storage_key)
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "S3_OBJECT_MISSING",
                    "message": "Uploaded object was not found in storage. Please re-upload.",
                }
            },
        )

    # Update video
    video.status = "uploaded"

    # Create Job
    job = Job(
        id=uuid.uuid4(),
        video_id=video.id,
        user_id=user.id,
        status="queued",
        current_stage="ingest",
        progress=0,
        created_at=utc_now(),
    )
    db.add(job)
    await db.flush()

    # Create initial stages
    stages_order = ["ingest", "proxy", "transcribe", "candidates", "score", "render"]
    created_stages: List[JobStage] = []
    for stage_name in stages_order:
        stg = JobStage(
            id=uuid.uuid4(),
            job_id=job.id,
            name=stage_name,
            status="pending",
            progress=0,
            meta={},
        )
        db.add(stg)
        created_stages.append(stg)

    await db.commit()
    await db.refresh(video)
    await db.refresh(job)

    # Enqueue Celery pipeline task
    try:
        from worker.celery_app import celery_app
        celery_app.send_task("worker.tasks.pipeline.start_pipeline", args=[str(job.id)])
    except Exception as e:
        # Log warning if celery broker is offline during unit testing
        pass

    job_dict = {
        "id": job.id,
        "video_id": job.video_id,
        "user_id": job.user_id,
        "status": job.status,
        "current_stage": job.current_stage,
        "progress": job.progress,
        "error": job.error,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "stages": created_stages,
    }

    return CompleteUploadResponse(video_id=video.id, job=JobResponse.model_validate(job_dict))


@router.get("", response_model=List[VideoResponse])
async def list_videos(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all videos belonging to authenticated user."""
    stmt = select(Video).where(Video.user_id == user.id).order_by(desc(Video.created_at))
    result = await db.execute(stmt)
    videos = result.scalars().all()
    return videos


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get single video details. Return 404 for missing or unauthorized resources."""
    stmt = select(Video).where(Video.id == video_id, Video.user_id == user.id)
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "VIDEO_NOT_FOUND", "message": "Video not found."}},
        )
    return video
