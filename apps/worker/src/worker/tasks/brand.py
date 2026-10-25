"""Celery background tasks for brand asset validation and preprocessing."""
import os
import shutil
import tempfile
import uuid

import structlog
from celery import shared_task
from PIL import Image

from clip_shared.db.models import BrandAsset
from clip_shared.db.session import get_sync_db
from clip_shared.media.brand_validator import (
    validate_font_asset,
    validate_logo_asset,
    validate_video_asset,
)
from clip_shared.media.ffmpeg import MediaValidationError
from clip_shared.storage.s3 import get_s3_client

logger = structlog.get_logger(__name__)


@shared_task(bind=True, name="worker.tasks.brand.validate_brand_asset")
def validate_brand_asset_task(self, asset_id: str) -> dict:
    """
    Validate, downscale, or transcode an uploaded brand asset.
    Updates the BrandAsset status to 'ready' or 'failed' and saves metadata.
    """
    logger.info("Starting brand asset validation", asset_id=asset_id)
    s3 = get_s3_client()
    temp_dir = tempfile.mkdtemp(prefix="brand_validate_")

    try:
        with get_sync_db() as db:
            asset = db.query(BrandAsset).filter(BrandAsset.id == uuid.UUID(asset_id)).first()
            if not asset:
                logger.error("Brand asset not found", asset_id=asset_id)
                return {"status": "not_found", "asset_id": asset_id}

            local_file = os.path.join(temp_dir, asset.filename)
            s3.download_file_stream(asset.storage_key, local_file)

            meta: dict = {}
            if asset.kind == "logo":
                meta = validate_logo_asset(local_file)
                asset.width = meta.get("width")
                asset.height = meta.get("height")

                # Generate downscaled thumbnail copy if large
                if meta.get("width", 0) > 512 or meta.get("height", 0) > 512:
                    try:
                        with Image.open(local_file) as img:
                            thumb = img.copy()
                            thumb.thumbnail((512, 512), Image.Resampling.LANCZOS)
                            thumb_path = os.path.join(temp_dir, "thumb_" + asset.filename)
                            thumb.save(thumb_path, format="PNG" if meta.get("has_alpha") else "JPEG")
                            thumb_key = asset.storage_key.rsplit(".", 1)[0] + "_thumb.png"
                            s3.upload_file(thumb_path, thumb_key, content_type="image/png")
                            meta["thumbnail_key"] = thumb_key
                    except Exception as te:
                        logger.warning("Failed to create logo thumbnail", error=str(te))

            elif asset.kind == "font":
                license_ack = bool(asset.metadata_json.get("license_acknowledged", True))
                meta = validate_font_asset(local_file, license_acknowledged=license_ack)

            elif asset.kind in ("intro", "outro"):
                meta = validate_video_asset(local_file, kind=asset.kind)
                asset.duration_ms = meta.get("duration_ms")
                asset.width = meta.get("width")
                asset.height = meta.get("height")

            else:
                raise MediaValidationError("INVALID_KIND", f"Unknown brand asset kind: {asset.kind}")

            # Merge metadata and mark ready
            updated_meta = dict(asset.metadata_json or {})
            updated_meta.update(meta)
            asset.metadata_json = updated_meta
            asset.status = "ready"
            db.commit()

            logger.info("Brand asset validated successfully", asset_id=asset_id, kind=asset.kind)
            return {"status": "ready", "asset_id": asset_id, "metadata": meta}

    except MediaValidationError as mve:
        logger.warning("Brand asset validation failed", asset_id=asset_id, error=str(mve), code=mve.code)
        with get_sync_db() as db:
            asset = db.query(BrandAsset).filter(BrandAsset.id == uuid.UUID(asset_id)).first()
            if asset:
                asset.status = "failed"
                meta_err = dict(asset.metadata_json or {})
                meta_err["error"] = str(mve)
                meta_err["error_code"] = mve.code
                asset.metadata_json = meta_err
                db.commit()
        return {"status": "failed", "asset_id": asset_id, "error": str(mve), "error_code": mve.code}

    except Exception as e:
        logger.error("Unexpected error during brand asset validation", asset_id=asset_id, error=str(e))
        with get_sync_db() as db:
            asset = db.query(BrandAsset).filter(BrandAsset.id == uuid.UUID(asset_id)).first()
            if asset:
                asset.status = "failed"
                meta_err = dict(asset.metadata_json or {})
                meta_err["error"] = str(e)
                meta_err["error_code"] = "INTERNAL_ERROR"
                asset.metadata_json = meta_err
                db.commit()
        return {"status": "failed", "asset_id": asset_id, "error": str(e), "error_code": "INTERNAL_ERROR"}

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
