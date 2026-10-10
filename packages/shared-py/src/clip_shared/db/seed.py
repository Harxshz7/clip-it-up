import uuid
from datetime import datetime, timezone

from clip_shared.config import get_settings
from clip_shared.db.models import CaptionStyle, ExportPreset, Plan, Project, User, UserPlan
from clip_shared.db.session import get_sync_db

settings = get_settings()

DEFAULT_CAPTION_STYLES = [
    {
        "key": "bold_pop",
        "name": "Bold Pop",
        "version": "v1",
        "is_builtin": True,
        "spec": {
            "font_family": "Montserrat",
            "font_weight": "900",
            "font_size_pt": 68,
            "uppercase": True,
            "primary_color": "&H00FFFFFF",      # ASS format: &HAABBGGRR (White)
            "highlight_color": "&H0000E6FF",    # Yellow in BGR (&H0000E6FF)
            "outline_color": "&H00000000",      # Black
            "outline_width": 5.5,
            "shadow_color": "&H80000000",
            "shadow_offset": 2.0,
            "alignment": 2,                     # Bottom Center
            "margin_v": 280,
            "margin_h": 60,
            "max_chars_per_line": 24,
            "max_lines": 2,
            "words_per_chunk": 3,
            "min_duration_ms": 250,
            "animation": "pop",                 # pop scale-in on active word
            "highlight_style": "word_scale_color",
            "safe_zone_anchor": "bottom",
        },
    },
    {
        "key": "clean_minimal",
        "name": "Clean Minimal",
        "version": "v1",
        "is_builtin": True,
        "spec": {
            "font_family": "Inter",
            "font_weight": "600",
            "font_size_pt": 52,
            "uppercase": False,
            "primary_color": "&H00FFFFFF",
            "highlight_color": "&H00F8BD38",    # Cyan / Sky accent in BGR
            "outline_color": "&H00111111",
            "outline_width": 2.0,
            "shadow_color": "&H90000000",
            "shadow_offset": 3.0,
            "alignment": 2,
            "margin_v": 280,
            "margin_h": 60,
            "max_chars_per_line": 34,
            "max_lines": 2,
            "words_per_chunk": 5,
            "min_duration_ms": 250,
            "animation": "none",
            "highlight_style": "color_bold",
            "safe_zone_anchor": "bottom",
        },
    },
    {
        "key": "karaoke",
        "name": "Karaoke Dynamic",
        "version": "v1",
        "is_builtin": True,
        "spec": {
            "font_family": "Poppins",
            "font_weight": "800",
            "font_size_pt": 62,
            "uppercase": True,
            "primary_color": "&H00CCCCCC",      # Dimmed white / light gray for inactive
            "highlight_color": "&H0000CCFF",    # Amber/Yellow for active
            "outline_color": "&H00000000",
            "outline_width": 4.5,
            "shadow_color": "&H80000000",
            "shadow_offset": 2.0,
            "alignment": 2,
            "margin_v": 280,
            "margin_h": 60,
            "max_chars_per_line": 28,
            "max_lines": 2,
            "words_per_chunk": 4,
            "min_duration_ms": 250,
            "animation": "karaoke",             # \k tags timing
            "highlight_style": "karaoke_sweep",
            "safe_zone_anchor": "bottom",
        },
    },
]

DEFAULT_PRESETS = [
    {
        "key": "tiktok",
        "name": "TikTok (9:16 Full HD)",
        "width": 1080,
        "height": 1920,
        "fps": 30.0,
        "max_duration_s": 600,
        "video_bitrate": "8500k",
        "crf": 21,
        "audio_bitrate": "192k",
        "loudness_lufs": -14.0,
        "safe_zone": {"top": 140, "bottom": 320, "left": 60, "right": 120},
        "notes": "Optimal for TikTok feed algorithms, safe zone clears right-side action buttons and bottom captions.",
    },
    {
        "key": "reels",
        "name": "Instagram Reels (9:16)",
        "width": 1080,
        "height": 1920,
        "fps": 30.0,
        "max_duration_s": 90,
        "video_bitrate": "8000k",
        "crf": 22,
        "audio_bitrate": "192k",
        "loudness_lufs": -14.0,
        "safe_zone": {"top": 120, "bottom": 300, "left": 60, "right": 80},
        "notes": "Instagram Reels 9:16 vertical standard, 90s duration cap recommendation.",
    },
    {
        "key": "shorts",
        "name": "YouTube Shorts (9:16)",
        "width": 1080,
        "height": 1920,
        "fps": 30.0,
        "max_duration_s": 60,
        "video_bitrate": "8000k",
        "crf": 22,
        "audio_bitrate": "192k",
        "loudness_lufs": -14.0,
        "safe_zone": {"top": 120, "bottom": 280, "left": 60, "right": 60},
        "notes": "YouTube Shorts 60s hard limit, centered title safe zone.",
    },
    {
        "key": "generic_vertical",
        "name": "Generic Vertical 9:16",
        "width": 1080,
        "height": 1920,
        "fps": 30.0,
        "max_duration_s": 300,
        "video_bitrate": "7500k",
        "crf": 22,
        "audio_bitrate": "192k",
        "loudness_lufs": -14.0,
        "safe_zone": {"top": 100, "bottom": 250, "left": 50, "right": 50},
        "notes": "Standard high quality 1080x1920 MP4 with balanced safe zone margins.",
    },
]

DEFAULT_PLANS = [
    {
        "key": "free",
        "name": "Free Tier",
        "monthly_minutes": 30,
        "export_watermark": True,
        "max_export_height": 1920,
        "max_exports_per_month": 10,
        "features": {
            "watermark": True,
            "max_resolution": "1080p",
            "indic_subtitles": True,
            "cleanup_fillers": True,
        },
    },
    {
        "key": "creator",
        "name": "Creator Plan",
        "monthly_minutes": 300,
        "export_watermark": False,
        "max_export_height": 1920,
        "max_exports_per_month": 100,
        "features": {
            "watermark": False,
            "max_resolution": "1080p",
            "priority_rendering": True,
            "indic_subtitles": True,
            "cleanup_fillers": True,
        },
    },
    {
        "key": "pro",
        "name": "Pro Studio",
        "monthly_minutes": 1200,
        "export_watermark": False,
        "max_export_height": 1920,
        "max_exports_per_month": 500,
        "features": {
            "watermark": False,
            "max_resolution": "4k",
            "priority_rendering": True,
            "custom_fonts": True,
            "batch_export": True,
            "indic_subtitles": True,
        },
    },
]


def seed_database():
    with get_sync_db() as db:
        # 1. Dev User
        dev_user_id = uuid.UUID(settings.DEV_USER_ID)
        user = db.query(User).filter(User.id == dev_user_id).first()
        if not user:
            user = User(
                id=dev_user_id,
                clerk_user_id=settings.DEV_CLERK_USER_ID,
                email=settings.DEV_USER_EMAIL,
            )
            db.add(user)
            db.flush()
            print(f"Created dev user: {user.email} ({user.id})")

        # 2. Default Project
        project = db.query(Project).filter(Project.user_id == user.id, Project.name == "Default Project").first()
        if not project:
            project = Project(
                id=uuid.uuid4(),
                user_id=user.id,
                name="Default Project",
            )
            db.add(project)
            db.flush()
            print(f"Created default project: {project.name} ({project.id})")

        # 3. Plans
        for plan_data in DEFAULT_PLANS:
            plan = db.query(Plan).filter(Plan.key == plan_data["key"]).first()
            if not plan:
                plan = Plan(
                    key=plan_data["key"],
                    name=plan_data["name"],
                    monthly_minutes=plan_data["monthly_minutes"],
                    export_watermark=plan_data["export_watermark"],
                    max_export_height=plan_data["max_export_height"],
                    max_exports_per_month=plan_data["max_exports_per_month"],
                    features=plan_data["features"],
                )
                db.add(plan)
                db.flush()
                print(f"Seeded plan: {plan.name} ({plan.key})")

        # 4. User Plan
        user_plan = db.query(UserPlan).filter(UserPlan.user_id == user.id).first()
        if not user_plan:
            user_plan = UserPlan(
                id=uuid.uuid4(),
                user_id=user.id,
                plan_key="free",
                period_start=datetime.now(timezone.utc),
            )
            db.add(user_plan)
            db.flush()
            print(f"Assigned default 'free' plan to dev user: {user.id}")

        # 5. Caption Styles
        for style_data in DEFAULT_CAPTION_STYLES:
            style = db.query(CaptionStyle).filter(CaptionStyle.key == style_data["key"]).first()
            if not style:
                style = CaptionStyle(
                    id=uuid.uuid4(),
                    key=style_data["key"],
                    name=style_data["name"],
                    version=style_data["version"],
                    is_builtin=style_data["is_builtin"],
                    spec=style_data["spec"],
                )
                db.add(style)
                db.flush()
                print(f"Seeded caption style: {style.name} ({style.key})")

        # 6. Export Presets
        for preset_data in DEFAULT_PRESETS:
            preset = db.query(ExportPreset).filter(ExportPreset.key == preset_data["key"]).first()
            if not preset:
                preset = ExportPreset(
                    key=preset_data["key"],
                    name=preset_data["name"],
                    width=preset_data["width"],
                    height=preset_data["height"],
                    fps=preset_data["fps"],
                    max_duration_s=preset_data["max_duration_s"],
                    video_bitrate=preset_data["video_bitrate"],
                    crf=preset_data["crf"],
                    audio_bitrate=preset_data["audio_bitrate"],
                    loudness_lufs=preset_data["loudness_lufs"],
                    safe_zone=preset_data["safe_zone"],
                    notes=preset_data.get("notes"),
                )
                db.add(preset)
                db.flush()
                print(f"Seeded export preset: {preset.name} ({preset.key})")

        db.commit()


if __name__ == "__main__":
    seed_database()
