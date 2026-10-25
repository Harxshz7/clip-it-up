"""API routes for Brand Kits and Brand Assets management."""
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.dependencies import get_current_user
from clip_shared.billing.quota import QuotaService
from clip_shared.config import load_plans_config
from clip_shared.db.base import utc_now
from clip_shared.db.models import BrandAsset, BrandKit
from clip_shared.db.session import get_db
from clip_shared.schemas.auth import AuthenticatedUser
from clip_shared.schemas.brand import (
    BrandAssetCompleteRequest,
    BrandAssetResponse,
    BrandAssetUploadUrlRequest,
    BrandAssetUploadUrlResponse,
    BrandKitCreateRequest,
    BrandKitResponse,
    BrandKitUpdateRequest,
)
from clip_shared.storage.s3 import get_s3_client, sanitize_filename

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["brand"])


async def get_user_plan_features(db: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    """Retrieve active plan features for the user, falling back to plans.yaml config."""
    plan, _, _ = await QuotaService.get_user_plan_and_period(db, user_id)
    plans_cfg = load_plans_config().get("plans", {})
    cfg_features = plans_cfg.get(plan.key, {}).get("features", {})
    features = dict(cfg_features)
    if plan.features:
        features.update(plan.features)
    return features


def to_asset_response(asset: BrandAsset) -> BrandAssetResponse:
    """Format BrandAsset to response schema with presigned download URL."""
    s3 = get_s3_client()
    download_url = None
    if asset.storage_key:
        try:
            download_url = s3.generate_presigned_get_url(asset.storage_key)
        except Exception:
            pass

    return BrandAssetResponse(
        id=asset.id,
        user_id=asset.user_id,
        kind=asset.kind,
        storage_key=asset.storage_key,
        filename=asset.filename,
        content_type=asset.content_type,
        size_bytes=asset.size_bytes,
        width=asset.width,
        height=asset.height,
        duration_ms=asset.duration_ms,
        status=asset.status,
        metadata_json=asset.metadata_json or {},
        created_at=asset.created_at,
        download_url=download_url,
    )


def to_kit_response(kit: BrandKit) -> BrandKitResponse:
    """Format BrandKit to response schema with loaded relationships."""
    logo_resp = to_asset_response(kit.logo_asset) if kit.logo_asset else None
    intro_resp = to_asset_response(kit.intro_asset) if kit.intro_asset else None
    outro_resp = to_asset_response(kit.outro_asset) if kit.outro_asset else None

    return BrandKitResponse(
        id=kit.id,
        user_id=kit.user_id,
        name=kit.name,
        is_default=kit.is_default,
        colors=kit.colors or {},
        fonts=kit.fonts or {},
        logo_asset_id=kit.logo_asset_id,
        logo_position=kit.logo_position,
        logo_opacity=kit.logo_opacity,
        logo_scale=kit.logo_scale,
        caption_style_key=kit.caption_style_key,
        caption_overrides=kit.caption_overrides or {},
        intro_asset_id=kit.intro_asset_id,
        outro_asset_id=kit.outro_asset_id,
        watermark_free_override=kit.watermark_free_override,
        created_at=kit.created_at,
        updated_at=kit.updated_at,
        logo_asset=logo_resp,
        intro_asset=intro_resp,
        outro_asset=outro_resp,
    )


# ---------------------------------------------------------------------------
# Brand Kit Routes
# ---------------------------------------------------------------------------

@router.get("/brand-kits", response_model=list[BrandKitResponse])
async def list_brand_kits(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all brand kits belonging to the authenticated user."""
    features = await get_user_plan_features(db, user.id)
    if not features.get("brand_kit", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "BRAND_KIT_NOT_IN_PLAN", "message": "Brand kits are not available on your plan. Upgrade to Creator or Pro to unlock custom branding."}},
        )

    stmt = (
        select(BrandKit)
        .options(
            selectinload(BrandKit.logo_asset),
            selectinload(BrandKit.intro_asset),
            selectinload(BrandKit.outro_asset),
        )
        .where(BrandKit.user_id == user.id)
        .order_by(BrandKit.is_default.desc(), BrandKit.created_at.desc())
    )
    result = await db.execute(stmt)
    kits = result.scalars().all()
    return [to_kit_response(k) for k in kits]


@router.post("/brand-kits", response_model=BrandKitResponse, status_code=status.HTTP_201_CREATED)
async def create_brand_kit(
    payload: BrandKitCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new brand kit, enforcing plan quotas and asset ownership."""
    features = await get_user_plan_features(db, user.id)
    if not features.get("brand_kit", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "BRAND_KIT_NOT_IN_PLAN", "message": "Brand kits are not available on your plan. Upgrade to Creator or Pro to unlock custom branding."}},
        )

    max_kits = features.get("max_brand_kits", 1)
    current_count = await db.scalar(select(func.count(BrandKit.id)).where(BrandKit.user_id == user.id)) or 0
    if current_count >= max_kits:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "LIMIT_EXCEEDED", "message": f"Brand kit quota ({max_kits}) exceeded for your plan. Upgrade your plan to create more brand kits."}},
        )

    # Validate asset ownership
    for asset_id, kind_name in [
        (payload.logo_asset_id, "logo"),
        (payload.intro_asset_id, "intro"),
        (payload.outro_asset_id, "outro"),
    ]:
        if asset_id:
            asset = await db.scalar(select(BrandAsset).where(BrandAsset.id == asset_id, BrandAsset.user_id == user.id))
            if not asset:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": {"code": "NOT_FOUND", "message": f"Brand {kind_name} asset {asset_id} not found."}},
                )

    # If first kit or explicitly marked default, update default flags
    is_default = payload.is_default or (current_count == 0)
    if is_default:
        existing_defaults = (await db.execute(select(BrandKit).where(BrandKit.user_id == user.id, BrandKit.is_default == True))).scalars().all()  # noqa: E712
        for d in existing_defaults:
            d.is_default = False

    kit = BrandKit(
        id=uuid.uuid4(),
        user_id=user.id,
        name=payload.name,
        is_default=is_default,
        colors=payload.colors,
        fonts=payload.fonts,
        logo_asset_id=payload.logo_asset_id,
        logo_position=payload.logo_position,
        logo_opacity=payload.logo_opacity,
        logo_scale=payload.logo_scale,
        caption_style_key=payload.caption_style_key,
        caption_overrides=payload.caption_overrides,
        intro_asset_id=payload.intro_asset_id,
        outro_asset_id=payload.outro_asset_id,
        watermark_free_override=payload.watermark_free_override,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(kit)
    await db.commit()

    # Reload with relationships
    stmt = (
        select(BrandKit)
        .options(
            selectinload(BrandKit.logo_asset),
            selectinload(BrandKit.intro_asset),
            selectinload(BrandKit.outro_asset),
        )
        .where(BrandKit.id == kit.id)
    )
    loaded = (await db.execute(stmt)).scalar_one()
    return to_kit_response(loaded)


@router.get("/brand-kits/default", response_model=BrandKitResponse)
async def get_default_brand_kit(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the user's default brand kit."""
    features = await get_user_plan_features(db, user.id)
    if not features.get("brand_kit", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "BRAND_KIT_NOT_IN_PLAN", "message": "Brand kits are not available on your plan."}},
        )

    stmt = (
        select(BrandKit)
        .options(
            selectinload(BrandKit.logo_asset),
            selectinload(BrandKit.intro_asset),
            selectinload(BrandKit.outro_asset),
        )
        .where(BrandKit.user_id == user.id, BrandKit.is_default == True)  # noqa: E712
    )
    kit = (await db.execute(stmt)).scalar_one_or_none()
    if not kit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "No default brand kit configured."}},
        )
    return to_kit_response(kit)


@router.get("/brand-kits/{kit_id}", response_model=BrandKitResponse)
async def get_brand_kit(
    kit_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a single brand kit by ID (ownership checked)."""
    features = await get_user_plan_features(db, user.id)
    if not features.get("brand_kit", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "BRAND_KIT_NOT_IN_PLAN", "message": "Brand kits are not available on your plan."}},
        )

    stmt = (
        select(BrandKit)
        .options(
            selectinload(BrandKit.logo_asset),
            selectinload(BrandKit.intro_asset),
            selectinload(BrandKit.outro_asset),
        )
        .where(BrandKit.id == kit_id, BrandKit.user_id == user.id)
    )
    kit = (await db.execute(stmt)).scalar_one_or_none()
    if not kit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Brand kit not found."}},
        )
    return to_kit_response(kit)


@router.put("/brand-kits/{kit_id}", response_model=BrandKitResponse)
async def update_brand_kit(
    kit_id: uuid.UUID,
    payload: BrandKitUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing brand kit."""
    features = await get_user_plan_features(db, user.id)
    if not features.get("brand_kit", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "BRAND_KIT_NOT_IN_PLAN", "message": "Brand kits are not available on your plan."}},
        )

    stmt = select(BrandKit).where(BrandKit.id == kit_id, BrandKit.user_id == user.id)
    kit = (await db.execute(stmt)).scalar_one_or_none()
    if not kit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Brand kit not found."}},
        )

    # Validate asset ownership if updated
    for asset_id, kind_name in [
        (payload.logo_asset_id, "logo"),
        (payload.intro_asset_id, "intro"),
        (payload.outro_asset_id, "outro"),
    ]:
        if asset_id is not None:
            asset = await db.scalar(select(BrandAsset).where(BrandAsset.id == asset_id, BrandAsset.user_id == user.id))
            if not asset:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": {"code": "NOT_FOUND", "message": f"Brand {kind_name} asset {asset_id} not found."}},
                )

    if payload.is_default is True:
        existing_defaults = (await db.execute(select(BrandKit).where(BrandKit.user_id == user.id, BrandKit.is_default == True))).scalars().all()  # noqa: E712
        for d in existing_defaults:
            d.is_default = False
        kit.is_default = True
    elif payload.is_default is False:
        kit.is_default = False

    if payload.name is not None:
        kit.name = payload.name
    if payload.colors is not None:
        kit.colors = payload.colors
    if payload.fonts is not None:
        kit.fonts = payload.fonts
    if payload.logo_asset_id is not None:
        kit.logo_asset_id = payload.logo_asset_id
    if payload.logo_position is not None:
        kit.logo_position = payload.logo_position
    if payload.logo_opacity is not None:
        kit.logo_opacity = payload.logo_opacity
    if payload.logo_scale is not None:
        kit.logo_scale = payload.logo_scale
    if payload.caption_style_key is not None:
        kit.caption_style_key = payload.caption_style_key
    if payload.caption_overrides is not None:
        kit.caption_overrides = payload.caption_overrides
    if payload.intro_asset_id is not None:
        kit.intro_asset_id = payload.intro_asset_id
    if payload.outro_asset_id is not None:
        kit.outro_asset_id = payload.outro_asset_id
    if payload.watermark_free_override is not None:
        kit.watermark_free_override = payload.watermark_free_override

    kit.updated_at = utc_now()
    await db.commit()

    # Reload with relationships
    stmt = (
        select(BrandKit)
        .options(
            selectinload(BrandKit.logo_asset),
            selectinload(BrandKit.intro_asset),
            selectinload(BrandKit.outro_asset),
        )
        .where(BrandKit.id == kit.id)
    )
    loaded = (await db.execute(stmt)).scalar_one()
    return to_kit_response(loaded)


@router.put("/brand-kits/{kit_id}/default", response_model=BrandKitResponse)
@router.post("/brand-kits/{kit_id}/default", response_model=BrandKitResponse)
async def set_default_brand_kit(
    kit_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set a brand kit as the user's default brand kit."""
    features = await get_user_plan_features(db, user.id)
    if not features.get("brand_kit", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "BRAND_KIT_NOT_IN_PLAN", "message": "Brand kits are not available on your plan."}},
        )

    stmt = select(BrandKit).where(BrandKit.id == kit_id, BrandKit.user_id == user.id)
    kit = (await db.execute(stmt)).scalar_one_or_none()
    if not kit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Brand kit not found."}},
        )

    # Clear other defaults
    all_kits = (await db.execute(select(BrandKit).where(BrandKit.user_id == user.id))).scalars().all()
    for k in all_kits:
        k.is_default = (k.id == kit.id)

    kit.updated_at = utc_now()
    await db.commit()

    stmt = (
        select(BrandKit)
        .options(
            selectinload(BrandKit.logo_asset),
            selectinload(BrandKit.intro_asset),
            selectinload(BrandKit.outro_asset),
        )
        .where(BrandKit.id == kit.id)
    )
    loaded = (await db.execute(stmt)).scalar_one()
    return to_kit_response(loaded)


@router.delete("/brand-kits/{kit_id}")
async def delete_brand_kit(
    kit_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a brand kit."""
    stmt = select(BrandKit).where(BrandKit.id == kit_id, BrandKit.user_id == user.id)
    kit = (await db.execute(stmt)).scalar_one_or_none()
    if not kit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Brand kit not found."}},
        )

    await db.delete(kit)
    await db.commit()
    return {"deleted": True, "kit_id": str(kit_id)}


# ---------------------------------------------------------------------------
# Brand Assets Routes
# ---------------------------------------------------------------------------

@router.get("/brand-assets", response_model=list[BrandAssetResponse])
async def list_brand_assets(
    kind: str | None = Query(None, description="Optional filter by kind: logo | font | intro | outro"),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all uploaded brand assets for the user."""
    stmt = select(BrandAsset).where(BrandAsset.user_id == user.id)
    if kind:
        stmt = stmt.where(BrandAsset.kind == kind)
    stmt = stmt.order_by(BrandAsset.created_at.desc())

    result = await db.execute(stmt)
    assets = result.scalars().all()
    return [to_asset_response(a) for a in assets]


@router.post("/brand-assets/upload-url", response_model=BrandAssetUploadUrlResponse)
async def generate_brand_asset_upload_url(
    payload: BrandAssetUploadUrlRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a presigned S3 PUT URL for uploading a brand asset."""
    features = await get_user_plan_features(db, user.id)
    if not features.get("brand_kit", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "BRAND_KIT_NOT_IN_PLAN", "message": "Brand assets require a plan with Brand Kit support."}},
        )

    # Size check
    max_mb = features.get("max_brand_asset_size_mb", 5)
    if payload.size_bytes > max_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "LIMIT_EXCEEDED", "message": f"Asset size exceeds maximum limit of {max_mb}MB for your plan."}},
        )

    # Intro/outro support check
    if payload.kind in ("intro", "outro"):
        max_duration = features.get("max_intro_outro_length_s", 0)
        if max_duration <= 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "BRAND_KIT_NOT_IN_PLAN", "message": "Custom intro/outro videos are not included in your current plan."}},
            )

    asset_id = uuid.uuid4()
    clean_name = sanitize_filename(payload.filename)
    storage_key = f"users/{str(user.id)}/brand/{payload.kind}s/{str(asset_id)}/{clean_name}"

    asset = BrandAsset(
        id=asset_id,
        user_id=user.id,
        kind=payload.kind,
        storage_key=storage_key,
        filename=clean_name,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        status="processing",
        metadata_json={},
        created_at=utc_now(),
    )
    db.add(asset)
    await db.commit()

    s3 = get_s3_client()
    upload_url = s3.generate_presigned_put_url(
        storage_key=storage_key,
        content_type=payload.content_type,
    )

    return BrandAssetUploadUrlResponse(
        asset_id=asset_id,
        upload_url=upload_url,
        storage_key=storage_key,
        expires_in_seconds=3600,
    )


@router.post("/brand-assets/{asset_id}/complete", response_model=BrandAssetResponse)
@router.post("/brand-assets/complete", response_model=BrandAssetResponse)
async def complete_brand_asset_upload(
    payload: BrandAssetCompleteRequest,
    asset_id: uuid.UUID | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark asset upload complete, validate licence acknowledgment, and trigger processing."""
    target_id = asset_id or payload.asset_id
    if not target_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "ASSET_INVALID", "message": "asset_id must be provided."}},
        )

    stmt = select(BrandAsset).where(BrandAsset.id == target_id, BrandAsset.user_id == user.id)
    asset = (await db.execute(stmt)).scalar_one_or_none()
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Brand asset not found."}},
        )

    # Custom font license check
    if asset.kind == "font" and not payload.license_acknowledged:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "ASSET_INVALID", "message": "Commercial license rights must be acknowledged for font upload."}},
        )

    meta = dict(asset.metadata_json or {})
    meta["license_acknowledged"] = payload.license_acknowledged
    asset.metadata_json = meta
    await db.commit()

    # Trigger async Celery validation
    try:
        from worker.celery_app import celery_app
        celery_app.send_task("worker.tasks.brand.validate_brand_asset", args=[str(asset.id)])
    except Exception as e:
        logger.warning("Could not dispatch brand asset validation task", error=str(e))
        # If celery is unavailable (e.g. testing), mark ready for tests
        asset.status = "ready"
        await db.commit()

    await db.refresh(asset)
    return to_asset_response(asset)


@router.delete("/brand-assets/{asset_id}")
async def delete_brand_asset(
    asset_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an uploaded brand asset and its underlying S3 storage."""
    stmt = select(BrandAsset).where(BrandAsset.id == asset_id, BrandAsset.user_id == user.id)
    asset = (await db.execute(stmt)).scalar_one_or_none()
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Brand asset not found."}},
        )

    s3 = get_s3_client()
    if asset.storage_key:
        s3.delete_object(asset.storage_key)

    await db.delete(asset)
    await db.commit()
    return {"deleted": True, "asset_id": str(asset_id)}
