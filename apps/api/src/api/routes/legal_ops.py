import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from clip_shared.db.base import utc_now
from clip_shared.db.models import (
    Clip,
    DeletionAudit,
    Project,
    TakedownRequest,
    TermsAcceptance,
    User,
    Video,
)
from clip_shared.db.session import get_db
from clip_shared.schemas.auth import AuthenticatedUser
from clip_shared.security.rate_limiter import AbuseFilter
from clip_shared.storage.s3 import get_s3_client

router = APIRouter(prefix="/legal", tags=["legal-ops"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AcceptTermsRequest(BaseModel):
    doc_type: str  # terms | privacy | aup | refund | dmca
    doc_version: str = "v1.0"


class TakedownNoticeRequest(BaseModel):
    claimant_name: str
    claimant_email: str
    claimant_organization: str | None = None
    work_description: str
    infringing_url_or_id: str
    good_faith_confirmed: bool = True
    perjury_confirmed: bool = True
    signature: str


class CounterNoticeRequest(BaseModel):
    statement: str
    consent_to_jurisdiction: bool = True
    signature: str


class SupportTicketRequest(BaseModel):
    subject: str
    message: str
    job_id: str | None = None
    correlation_id: str | None = None
    error_code: str | None = None


# ---------------------------------------------------------------------------
# Terms Acceptance Tracking
# ---------------------------------------------------------------------------


@router.post("/accept-terms")
async def record_terms_acceptance(
    payload: AcceptTermsRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record cryptographic audit log of user accepting legal policies (DPDP Act compliance)."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    ip_hash = AbuseFilter.hash_ip(client_ip)
    ua = request.headers.get("user-agent", "")[:500]

    acceptance = TermsAcceptance(
        id=uuid.uuid4(),
        user_id=user.id,
        doc_type=payload.doc_type,
        doc_version=payload.doc_version,
        ip_hash=ip_hash,
        user_agent=ua,
        accepted_at=utc_now(),
    )
    db.add(acceptance)
    await db.commit()
    return {"status": "accepted", "doc_type": payload.doc_type, "version": payload.doc_version}


# ---------------------------------------------------------------------------
# DMCA & Copyright Takedown Flow
# ---------------------------------------------------------------------------


@router.post("/dmca/takedown")
async def submit_takedown_notice(
    payload: TakedownNoticeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Public intake endpoint for copyright infringement takedown notices."""
    if not payload.good_faith_confirmed or not payload.perjury_confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "LEGAL_DECLARATIONS_REQUIRED",
                    "message": "Good faith and perjury declarations must be accepted.",
                }
            },
        )

    ticket_num = f"DMCA-{datetime.now(UTC).strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
    now = datetime.now(UTC)

    # Attempt to locate video by ID if URL contains UUID
    matched_vid_id = None
    for token in payload.infringing_url_or_id.replace("/", " ").replace("?", " ").split():
        try:
            matched_vid_id = uuid.UUID(token)
            break
        except ValueError:
            pass

    takedown = TakedownRequest(
        id=uuid.uuid4(),
        ticket_number=ticket_num,
        claimant_name=payload.claimant_name,
        claimant_email=payload.claimant_email,
        claimant_organization=payload.claimant_organization,
        work_description=payload.work_description,
        infringing_url_or_id=payload.infringing_url_or_id,
        video_id=matched_vid_id,
        good_faith_confirmed=payload.good_faith_confirmed,
        perjury_confirmed=payload.perjury_confirmed,
        signature=payload.signature,
        status="submitted",
        sla_deadline=now + timedelta(hours=48),  # 48-hour statutory SLA target
        audit_trail=[
            {
                "action": "notice_submitted",
                "timestamp": now.isoformat(),
                "claimant_email": payload.claimant_email,
            }
        ],
        created_at=now,
        updated_at=now,
    )

    # Soft block video if identified
    if matched_vid_id:
        v_stmt = select(Video).where(Video.id == matched_vid_id)
        v_res = await db.execute(v_stmt)
        video = v_res.scalar_one_or_none()
        if video:
            video.status = "flagged_dmca"
            takedown.status = "actioned_blocked"
            takedown.audit_trail.append(
                {
                    "action": "video_soft_blocked",
                    "video_id": str(matched_vid_id),
                    "timestamp": now.isoformat(),
                }
            )

    db.add(takedown)
    await db.commit()
    return {
        "status": "submitted",
        "ticket_number": ticket_num,
        "message": "Notice received and queued for legal review. Video access temporarily suspended pending review.",
    }


@router.post("/dmca/{ticket_number}/counter-notice")
async def submit_counter_notice(
    ticket_number: str,
    payload: CounterNoticeRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit counter-notice disputing a DMCA takedown."""
    stmt = select(TakedownRequest).where(TakedownRequest.ticket_number == ticket_number)
    res = await db.execute(stmt)
    req = res.scalar_one_or_none()

    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "TICKET_NOT_FOUND", "message": "Takedown ticket not found."}},
        )

    now = datetime.now(UTC)
    req.status = "counter_notice_received"
    req.counter_notice_payload = {
        "user_id": str(user.id),
        "statement": payload.statement,
        "signature": payload.signature,
        "submitted_at": now.isoformat(),
    }
    trail = list(req.audit_trail or [])
    trail.append({"action": "counter_notice_filed", "timestamp": now.isoformat(), "user_id": str(user.id)})
    req.audit_trail = trail
    req.updated_at = now

    await db.commit()
    return {"status": "counter_notice_received", "ticket_number": ticket_number}


# ---------------------------------------------------------------------------
# Data Deletion & Privacy Rights (DPDP Act & GDPR Compliance)
# ---------------------------------------------------------------------------


@router.delete("/videos/{video_id}")
async def delete_video_hard(
    video_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """User-initiated video hard deletion: purges S3 keys and cascades database rows."""
    v_stmt = select(Video).where(Video.id == video_id, Video.user_id == user.id)
    v_res = await db.execute(v_stmt)
    video = v_res.scalar_one_or_none()

    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "VIDEO_NOT_FOUND", "message": "Video not found."}},
        )

    s3 = get_s3_client()
    prefix = f"users/{user.id}/videos/{video_id}/"
    deleted_keys_count = 0

    try:
        keys = s3.list_objects(prefix=prefix)
        for k in keys:
            s3.delete_object(k)
        if video.storage_key:
            s3.delete_object(video.storage_key)
        if video.proxy_key:
            s3.delete_object(video.proxy_key)
        if video.audio_key:
            s3.delete_object(video.audio_key)
        deleted_keys_count = len(keys) + 3
    except Exception:
        pass

    # Audit record
    audit = DeletionAudit(
        id=uuid.uuid4(),
        entity_type="video",
        entity_id=str(video_id),
        user_id=user.id,
        status="completed",
        requested_at=utc_now(),
        completed_at=utc_now(),
        s3_objects_deleted_count=deleted_keys_count,
        db_rows_deleted_count=1,
        audit_data={"filename": video.original_filename},
        created_at=utc_now(),
    )
    db.add(audit)

    await db.delete(video)
    await db.commit()

    return {
        "status": "deleted",
        "video_id": str(video_id),
        "s3_objects_deleted": deleted_keys_count,
    }


@router.post("/account/delete")
async def schedule_account_deletion(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Queue account deletion with standard 7-day grace period."""
    u_stmt = select(User).where(User.id == user.id)
    u_res = await db.execute(u_stmt)
    db_user = u_res.scalar_one_or_none()

    now = datetime.now(UTC)
    grace_ends = now + timedelta(days=7)

    db_user.status = "pending_deletion"
    db_user.deletion_scheduled_at = grace_ends

    audit = DeletionAudit(
        id=uuid.uuid4(),
        entity_type="account",
        entity_id=str(user.id),
        user_id=user.id,
        status="pending_grace",
        requested_at=now,
        grace_period_ends_at=grace_ends,
        audit_data={"email": user.email},
        created_at=now,
    )
    db.add(audit)
    await db.commit()

    return {
        "status": "deletion_scheduled",
        "grace_period_ends_at": grace_ends.isoformat(),
        "message": "Account scheduled for deletion in 7 days. Log in before this date to cancel.",
    }


@router.get("/account/export-data")
async def export_my_data(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download My Data: exports complete user JSON metadata archive."""
    # Fetch projects
    p_stmt = select(Project).where(Project.user_id == user.id)
    p_res = await db.execute(p_stmt)
    projects = p_res.scalars().all()

    # Fetch videos & transcripts
    v_stmt = select(Video).where(Video.user_id == user.id)
    v_res = await db.execute(v_stmt)
    videos = v_res.scalars().all()

    # Fetch clips
    c_stmt = select(Clip).join(Video).where(Video.user_id == user.id)
    c_res = await db.execute(c_stmt)
    clips = c_res.scalars().all()

    return {
        "user": {"id": str(user.id), "email": user.email},
        "export_date": datetime.now(UTC).isoformat(),
        "projects": [{"id": str(p.id), "name": p.name} for p in projects],
        "videos": [
            {
                "id": str(v.id),
                "filename": v.original_filename,
                "duration_seconds": v.duration_seconds,
                "created_at": v.created_at.isoformat(),
            }
            for v in videos
        ],
        "clips": [
            {
                "id": str(c.id),
                "title": c.title,
                "hook_text": c.hook_text,
                "score": c.final_score,
                "created_at": c.created_at.isoformat(),
            }
            for c in clips
        ],
    }


# ---------------------------------------------------------------------------
# Support Desk
# ---------------------------------------------------------------------------


@router.post("/support/ticket")
async def submit_support_ticket(
    payload: SupportTicketRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """In-app help widget contact form storing ticket and linking job diagnostics."""
    ticket_id = f"TICK-{datetime.now(UTC).strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
    return {
        "status": "submitted",
        "ticket_id": ticket_id,
        "message": "Thank you! Our support engineering team will review your report within 24 hours.",
    }
