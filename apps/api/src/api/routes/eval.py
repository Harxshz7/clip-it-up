import csv
import io
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import Response
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from clip_shared.config import get_settings
from clip_shared.db.session import get_db
from clip_shared.db.base import utc_now
from clip_shared.db.models import EvalVideo, EvalClipRating, Clip
from clip_shared.schemas.auth import AuthenticatedUser
from clip_shared.schemas.eval import (
    EvalVideoResponse,
    EvalClipRatingRequest,
    EvalClipRatingResponse,
    EvalRatingsExportResponse,
)
from api.dependencies import get_current_user

router = APIRouter(prefix="/eval", tags=["eval"])
settings = get_settings()


@router.get("/videos", response_model=List[EvalVideoResponse])
async def list_eval_videos(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List benchmark dataset videos."""
    stmt = select(EvalVideo).order_by(EvalVideo.slug)
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/rate", response_model=EvalClipRatingResponse)
async def submit_eval_rating(
    payload: EvalClipRatingRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit blind 1-5 human rater score for a clip or time range."""
    # Check for existing rating by this rater for this time window
    stmt = select(EvalClipRating).where(
        EvalClipRating.video_slug == payload.video_slug,
        EvalClipRating.start_ms == payload.start_ms,
        EvalClipRating.end_ms == payload.end_ms,
        EvalClipRating.rater_id == payload.rater_id,
    )
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    if existing:
        existing.score = payload.score
        existing.comment = payload.comment
        existing.clip_id = payload.clip_id
        await db.commit()
        await db.refresh(existing)
        return existing

    rating = EvalClipRating(
        id=uuid.uuid4(),
        video_slug=payload.video_slug,
        start_ms=payload.start_ms,
        end_ms=payload.end_ms,
        clip_id=payload.clip_id,
        rater_id=payload.rater_id,
        score=payload.score,
        comment=payload.comment,
        created_at=utc_now(),
    )
    db.add(rating)
    await db.commit()
    await db.refresh(rating)
    return rating


@router.get("/ratings", response_model=List[EvalClipRatingResponse])
async def list_eval_ratings(
    video_slug: Optional[str] = Query(None),
    rater_id: Optional[str] = Query(None),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all human ratings with optional filters."""
    stmt = select(EvalClipRating)
    if video_slug:
        stmt = stmt.where(EvalClipRating.video_slug == video_slug)
    if rater_id:
        stmt = stmt.where(EvalClipRating.rater_id == rater_id)
    stmt = stmt.order_by(desc(EvalClipRating.created_at))

    res = await db.execute(stmt)
    return res.scalars().all()


@router.get("/ratings/export")
async def export_eval_ratings_csv(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export all eval ground-truth ratings as CSV."""
    stmt = select(EvalClipRating).order_by(EvalClipRating.video_slug, EvalClipRating.start_ms)
    res = await db.execute(stmt)
    ratings = res.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "video_slug", "start_ms", "end_ms", "clip_id", "rater_id", "score", "comment", "created_at"])
    for r in ratings:
        writer.writerow([
            str(r.id),
            r.video_slug,
            r.start_ms,
            r.end_ms,
            str(r.clip_id) if r.clip_id else "",
            r.rater_id,
            r.score,
            r.comment or "",
            r.created_at.isoformat() if r.created_at else "",
        ])

    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="eval_ratings.csv"'},
    )
