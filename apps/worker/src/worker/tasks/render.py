"""Celery background tasks for video rendering and export."""
import os
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import structlog
from celery import shared_task

from clip_shared.config import get_settings
from clip_shared.db.base import utc_now
from clip_shared.db.models import (
    CaptionStyle,
    Clip,
    ClipCaption,
    ClipCleanup,
    ClipReframe,
    Export,
    ExportPreset,
    Plan,
    Usage,
    User,
    UserPlan,
    Video,
)
from clip_shared.db.session import get_sync_db
from clip_shared.media.edl import EditDecisionList
from clip_shared.media.render import (
    RenderJobSnapshot,
    execute_export_render,
)
from clip_shared.pubsub.redis import publish_export_event_sync
from clip_shared.rates import StageRateConfig
from clip_shared.storage.s3 import get_s3_client

logger = structlog.get_logger()
settings = get_settings()


@shared_task(
    name="worker.tasks.render.render_export_task",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    acks_late=True,
    queue="cpu",
)
def render_export_task(self, export_id: str) -> dict[str, Any]:
    """
    Celery task that executes single-pass vertical video export render.
    Reads immutable source snapshot, executes FFmpeg filtergraph with libass,
    enforces plan watermark server-side, validates output, and uploads to S3.
    """
    export_uuid = uuid.UUID(export_id)
    t0 = time.perf_counter()

    with get_sync_db() as db:
        export_rec = db.query(Export).filter(Export.id == export_uuid).first()
        if not export_rec:
            logger.error("export_not_found", export_id=export_id)
            return {"error": f"Export {export_id} not found."}

        clip = db.query(Clip).filter(Clip.id == export_rec.clip_id).first()
        if not clip:
            export_rec.status = "failed"
            export_rec.error = "Associated clip not found."
            db.commit()
            publish_export_event_sync(export_id, {"type": "export_failed", "error": export_rec.error})
            return {"error": export_rec.error}

        video = db.query(Video).filter(Video.id == clip.video_id).first()
        user = db.query(User).filter(User.id == export_rec.user_id).first()

        # Resolve user plan and server-side watermark rule
        user_plan = db.query(UserPlan).filter(UserPlan.user_id == user.id).first()
        plan_key = user_plan.plan_key if user_plan else "free"
        plan = db.query(Plan).filter(Plan.key == plan_key).first()
        watermark_enabled = bool(plan.export_watermark if plan else True)

        # Resolve preset
        preset = db.query(ExportPreset).filter(ExportPreset.key == export_rec.preset_key).first()
        preset_config = {
            "width": preset.width if preset else 1080,
            "height": preset.height if preset else 1920,
            "fps": preset.fps if preset else 30.0,
            "crf": preset.crf if preset else 22,
            "video_bitrate": preset.video_bitrate if preset else "8000k",
            "audio_bitrate": preset.audio_bitrate if preset else "192k",
            "loudness_lufs": preset.loudness_lufs if preset else -14.0,
            "safe_zone": preset.safe_zone if preset else {"top": 120, "bottom": 280, "left": 60, "right": 60},
        }

        # Resolve cleanups and EDL
        cleanup_rec = db.query(ClipCleanup).filter(ClipCleanup.clip_id == clip.id).first()
        removals = cleanup_rec.removals if cleanup_rec else []
        edl = EditDecisionList.create(
            clip_start_ms=clip.start_ms,
            clip_end_ms=clip.end_ms,
            removals=removals,
        )

        # Resolve reframe crop path
        reframe_rec = db.query(ClipReframe).filter(ClipReframe.clip_id == clip.id).first()
        crop_path = reframe_rec.crop_path if reframe_rec else {"keyframes": [{"t_ms": 0, "cx": 0.5, "cy": 0.5, "w": 0.5625, "h": 1.0}]}

        # Resolve captions and style
        captions_rec = db.query(ClipCaption).filter(ClipCaption.clip_id == clip.id).first()
        style_key = captions_rec.style_key if captions_rec else "bold_pop"
        caption_style = db.query(CaptionStyle).filter(CaptionStyle.key == style_key).first()
        style_spec = caption_style.spec if caption_style else {
            "font_family": "Montserrat",
            "font_size_pt": 68,
            "uppercase": True,
            "primary_color": "&H00FFFFFF",
            "highlight_color": "&H0000E6FF",
            "outline_color": "&H00000000",
            "outline_width": 5.0,
            "alignment": 2,
            "margin_v": 280,
            "margin_h": 60,
            "animation": "pop",
        }

        # Apply any style overrides
        if captions_rec and captions_rec.style_overrides:
            style_spec = {**style_spec, **captions_rec.style_overrides}

        caption_words = captions_rec.words if captions_rec else []

        # Mark rendering status
        export_rec.status = "rendering"
        db.commit()

        publish_export_event_sync(export_id, {
            "type": "export_progress",
            "export_id": export_id,
            "status": "rendering",
            "progress": 5.0,
        })

    # Prepare temp workspace
    temp_dir = tempfile.mkdtemp(prefix=f"export_{export_id}_")
    local_source_video = os.path.join(temp_dir, "original_source.mp4")
    local_rendered_mp4 = os.path.join(temp_dir, f"rendered_{export_id}.mp4")
    fonts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "fonts"))

    try:
        # Download original source video
        s3 = get_s3_client()
        s3.download_file(
            Bucket=settings.S3_BUCKET_NAME,
            Key=video.storage_key,
            Filename=local_source_video,
        )

        snapshot = RenderJobSnapshot(
            clip_id=str(clip.id),
            user_id=str(user.id),
            export_id=export_id,
            preset_key=export_rec.preset_key,
            clip_start_ms=clip.start_ms,
            clip_end_ms=clip.end_ms,
            edl=edl,
            crop_path=crop_path,
            captions_words=caption_words,
            caption_style_spec=style_spec,
            preset_config=preset_config,
            watermark_enabled=watermark_enabled,
            watermark_text="Clip It Up",
            crossfade_ms=cleanup_rec.options.get("crossfade_ms", 40) if cleanup_rec else 40,
        )

        def on_progress(pct: float):
            # Scale progress between 10% and 90%
            eff_pct = round(10.0 + (pct * 0.8), 1)
            publish_export_event_sync(export_id, {
                "type": "export_progress",
                "export_id": export_id,
                "status": "rendering",
                "progress": eff_pct,
            })

        # Execute single-pass render
        render_metrics = execute_export_render(
            input_video=local_source_video,
            output_mp4=local_rendered_mp4,
            snapshot=snapshot,
            fonts_dir=fonts_dir if os.path.exists(fonts_dir) else None,
            progress_cb=on_progress,
        )

        # Upload output MP4 to S3
        dest_s3_key = f"users/{user.id}/exports/{export_id}.mp4"
        s3.upload_file(
            Filename=local_rendered_mp4,
            Bucket=settings.S3_BUCKET_NAME,
            Key=dest_s3_key,
            ExtraArgs={"ContentType": "video/mp4"},
        )

        total_wall_ms = int((time.perf_counter() - t0) * 1000)

        # Update DB record
        with get_sync_db() as db:
            export_rec = db.query(Export).filter(Export.id == export_uuid).first()
            export_rec.status = "succeeded"
            export_rec.storage_key = dest_s3_key
            export_rec.duration_ms = render_metrics["duration_ms"]
            export_rec.size_bytes = render_metrics["size_bytes"]
            export_rec.render_ms = render_metrics["render_ms"]
            export_rec.finished_at = datetime.now(timezone.utc)

            # Record usage
            exp_seconds = Decimal(str(render_metrics["duration_ms"] / 1000.0)).quantize(Decimal("0.01"))
            cpu_seconds = Decimal(str(render_metrics["render_ms"] / 1000.0)).quantize(Decimal("0.01"))
            cost = StageRateConfig.calculate_stage_cost("render", duration_seconds=float(exp_seconds))

            # Record export usage
            usage_exp = Usage(
                id=uuid.uuid4(),
                user_id=user.id,
                video_id=video.id,
                metric="export_seconds",
                quantity=exp_seconds,
                cost_inr=cost,
            )
            db.add(usage_exp)

            usage_cpu = Usage(
                id=uuid.uuid4(),
                user_id=user.id,
                video_id=video.id,
                metric="render_cpu_seconds",
                quantity=cpu_seconds,
                cost_inr=Decimal("0.0000"),
            )
            db.add(usage_cpu)
            db.commit()

        # Publish SSE export ready
        publish_export_event_sync(export_id, {
            "type": "export_ready",
            "export_id": export_id,
            "status": "succeeded",
            "progress": 100.0,
            "storage_key": dest_s3_key,
            "duration_ms": render_metrics["duration_ms"],
            "size_bytes": render_metrics["size_bytes"],
            "render_ms": render_metrics["render_ms"],
            "realtime_factor": render_metrics.get("realtime_factor"),
        })

        logger.info(
            "export_succeeded",
            export_id=export_id,
            duration_ms=render_metrics["duration_ms"],
            render_ms=render_metrics["render_ms"],
            rtf=render_metrics.get("realtime_factor"),
        )
        return render_metrics

    except Exception as e:
        logger.error("export_render_error", export_id=export_id, exc_info=True)
        with get_sync_db() as db:
            export_rec = db.query(Export).filter(Export.id == export_uuid).first()
            if export_rec:
                export_rec.status = "failed"
                export_rec.error = str(e)
                db.commit()

        publish_export_event_sync(export_id, {
            "type": "export_failed",
            "export_id": export_id,
            "status": "failed",
            "error": str(e),
        })
        raise e

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
