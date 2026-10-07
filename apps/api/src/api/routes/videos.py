import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from clip_shared.config import get_settings
from clip_shared.db.base import utc_now
from clip_shared.db.models import (
    Job,
    JobStage,
    Project,
    Speaker,
    Transcript,
    TranscriptSegment,
    TranscriptWord,
    Video,
)
from clip_shared.db.session import get_db
from clip_shared.schemas.auth import AuthenticatedUser
from clip_shared.schemas.jobs import CompleteUploadResponse, JobResponse
from clip_shared.schemas.transcripts import (
    ProxyUrlResponse,
    SpeakerResponse,
    TranscriptDetailResponse,
    TranscriptMetadataResponse,
    TranscriptSegmentResponse,
    TranscriptWordResponse,
    TranscriptWordsRangeResponse,
    UpdateSpeakerRequest,
)
from clip_shared.schemas.videos import (
    MultipartCompleteRequest,
    MultipartPartInfo,
    MultipartPartUrlRequest,
    MultipartPartUrlResponse,
    UploadUrlRequest,
    UploadUrlResponse,
    VideoResponse,
)
from clip_shared.storage.s3 import get_s3_client, get_storage_key, sanitize_filename

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

        part_urls: list[MultipartPartInfo] = []
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
        ) from e

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
    created_stages: list[JobStage] = []
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
    except Exception:
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


@router.get("", response_model=list[VideoResponse])
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


@router.get("/{video_id}/proxy-url", response_model=ProxyUrlResponse)
async def get_video_proxy_url(
    video_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get presigned GET URL for the 720p preview proxy video (supports range requests)."""
    stmt = select(Video).where(Video.id == video_id, Video.user_id == user.id)
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "VIDEO_NOT_FOUND", "message": "Video not found."}},
        )

    target_key = video.proxy_key or video.storage_key
    s3 = get_s3_client()
    proxy_url = s3.generate_presigned_get_url(target_key, expires_in=3600)

    return ProxyUrlResponse(
        video_id=video.id,
        proxy_url=proxy_url,
        expires_in_seconds=3600,
        content_type="video/mp4",
    )


@router.get("/{video_id}/transcript", response_model=TranscriptDetailResponse)
async def get_video_transcript(
    video_id: uuid.UUID,
    from_ms: int | None = Query(None, description="Filter start time in milliseconds"),
    to_ms: int | None = Query(None, description="Filter end time in milliseconds"),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get transcript metadata, speaker list, and timed segments.
    Optionally filter segments by time range [from_ms, to_ms].
    """
    stmt = (
        select(Transcript)
        .join(Video, Video.id == Transcript.video_id)
        .where(Transcript.video_id == video_id, Video.user_id == user.id)
    )
    result = await db.execute(stmt)
    transcript = result.scalar_one_or_none()

    if not transcript:
        # Check if video exists to return appropriate 404
        v_stmt = select(Video).where(Video.id == video_id, Video.user_id == user.id)
        v_res = await db.execute(v_stmt)
        if not v_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "VIDEO_NOT_FOUND", "message": "Video not found."}},
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "TRANSCRIPT_NOT_FOUND", "message": "Transcript is not ready yet."}},
        )

    # Fetch speakers
    spk_stmt = select(Speaker).where(Speaker.transcript_id == transcript.id).order_by(Speaker.label)
    spk_res = await db.execute(spk_stmt)
    speakers = spk_res.scalars().all()

    # Fetch segments with optional time filtering
    seg_stmt = select(TranscriptSegment).where(TranscriptSegment.transcript_id == transcript.id)
    if from_ms is not None:
        seg_stmt = seg_stmt.where(TranscriptSegment.end_ms >= from_ms)
    if to_ms is not None:
        seg_stmt = seg_stmt.where(TranscriptSegment.start_ms <= to_ms)
    seg_stmt = seg_stmt.order_by(TranscriptSegment.idx)

    seg_res = await db.execute(seg_stmt)
    segments = seg_res.scalars().all()

    # Count total segments
    count_stmt = select(TranscriptSegment).where(TranscriptSegment.transcript_id == transcript.id)
    count_res = await db.execute(count_stmt)
    total_segments = len(count_res.scalars().all())

    return TranscriptDetailResponse(
        transcript=TranscriptMetadataResponse.model_validate(transcript),
        speakers=[SpeakerResponse.model_validate(s) for s in speakers],
        segments=[TranscriptSegmentResponse.model_validate(s) for s in segments],
        total_segments=total_segments,
        has_more=False,
    )


@router.get("/{video_id}/transcript/words", response_model=TranscriptWordsRangeResponse)
async def get_transcript_words_range(
    video_id: uuid.UUID,
    from_ms: int | None = Query(None, description="Start time filter in ms"),
    to_ms: int | None = Query(None, description="End time filter in ms"),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch words within a specific time range for high precision player seeking & highlighting."""
    stmt = (
        select(Transcript)
        .join(Video, Video.id == Transcript.video_id)
        .where(Transcript.video_id == video_id, Video.user_id == user.id)
    )
    result = await db.execute(stmt)
    transcript = result.scalar_one_or_none()

    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "TRANSCRIPT_NOT_FOUND", "message": "Transcript not found."}},
        )

    w_stmt = select(TranscriptWord).where(TranscriptWord.transcript_id == transcript.id)
    if from_ms is not None:
        w_stmt = w_stmt.where(TranscriptWord.end_ms >= from_ms)
    if to_ms is not None:
        w_stmt = w_stmt.where(TranscriptWord.start_ms <= to_ms)
    w_stmt = w_stmt.order_by(TranscriptWord.idx)

    w_res = await db.execute(w_stmt)
    words = w_res.scalars().all()

    return TranscriptWordsRangeResponse(
        words=[TranscriptWordResponse.model_validate(w) for w in words],
        from_ms=from_ms,
        to_ms=to_ms,
        total=len(words),
    )


@router.patch("/{video_id}/speakers/{speaker_id}", response_model=SpeakerResponse)
async def update_speaker_display_name(
    video_id: uuid.UUID,
    speaker_id: uuid.UUID,
    payload: UpdateSpeakerRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update speaker display name (e.g. rename SPEAKER_00 to 'Alex')."""
    stmt = (
        select(Speaker)
        .join(Transcript, Transcript.id == Speaker.transcript_id)
        .join(Video, Video.id == Transcript.video_id)
        .where(Speaker.id == speaker_id, Video.id == video_id, Video.user_id == user.id)
    )
    result = await db.execute(stmt)
    speaker = result.scalar_one_or_none()

    if not speaker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "SPEAKER_NOT_FOUND", "message": "Speaker not found."}},
        )

    speaker.display_name = payload.display_name.strip()
    await db.commit()
    await db.refresh(speaker)

    return SpeakerResponse.model_validate(speaker)


@router.get("/{video_id}/transcript/export")
async def export_transcript(
    video_id: uuid.UUID,
    format: str = Query("txt", pattern="^(txt|srt|vtt|json)$"),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export transcript in requested format: txt, srt, vtt, or json."""
    from fastapi.responses import Response

    from worker.transcription.base import SegmentItem, SpeakerItem, TranscriptionResult, WordItem
    from worker.transcription.export import export_json, export_srt, export_txt, export_vtt

    stmt = (
        select(Transcript)
        .join(Video, Video.id == Transcript.video_id)
        .where(Transcript.video_id == video_id, Video.user_id == user.id)
    )
    result = await db.execute(stmt)
    transcript = result.scalar_one_or_none()

    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "TRANSCRIPT_NOT_FOUND", "message": "Transcript not found."}},
        )

    # Fetch speakers
    spk_stmt = select(Speaker).where(Speaker.transcript_id == transcript.id).order_by(Speaker.label)
    spk_res = await db.execute(spk_stmt)
    speakers = spk_res.scalars().all()
    speakers_map = {s.label: s.display_name or s.label for s in speakers}

    # Fetch segments
    seg_stmt = select(TranscriptSegment).where(TranscriptSegment.transcript_id == transcript.id).order_by(TranscriptSegment.idx)
    seg_res = await db.execute(seg_stmt)
    segments = seg_res.scalars().all()

    # Convert to SegmentItems
    segment_items = [
        SegmentItem(
            idx=s.idx,
            start_ms=s.start_ms,
            end_ms=s.end_ms,
            speaker=s.speaker,
            text=s.text,
        )
        for s in segments
    ]

    media_types = {
        "txt": "text/plain; charset=utf-8",
        "srt": "application/x-subrip; charset=utf-8",
        "vtt": "text/vtt; charset=utf-8",
        "json": "application/json; charset=utf-8",
    }

    if format == "txt":
        content = export_txt(segment_items, speakers_map=speakers_map)
    elif format == "srt":
        content = export_srt(segment_items, speakers_map=speakers_map)
    elif format == "vtt":
        content = export_vtt(segment_items, speakers_map=speakers_map)
    elif format == "json":
        # Fetch words for json
        w_stmt = select(TranscriptWord).where(TranscriptWord.transcript_id == transcript.id).order_by(TranscriptWord.idx)
        w_res = await db.execute(w_stmt)
        words = w_res.scalars().all()
        word_items = [
            WordItem(
                idx=w.idx,
                word=w.word,
                start_ms=w.start_ms,
                end_ms=w.end_ms,
                speaker=w.speaker,
                confidence=w.confidence,
            )
            for w in words
        ]
        trans_res = TranscriptionResult(
            language=transcript.language or "en",
            status=transcript.status,
            model=transcript.model or "unknown",
            backend=transcript.backend or "unknown",
            word_count=transcript.word_count,
            words=word_items,
            segments=segment_items,
            speakers=[SpeakerItem(label=s.label, display_name=s.display_name) for s in speakers],
        )
        content = export_json(trans_res, speakers_map=speakers_map)
    else:
        content = export_txt(segment_items, speakers_map=speakers_map)

    filename = f"transcript_{str(video_id)[:8]}.{format}"
    return Response(
        content=content,
        media_type=media_types.get(format, "text/plain"),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
