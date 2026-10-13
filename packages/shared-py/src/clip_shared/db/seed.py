import uuid
from datetime import UTC, datetime, timedelta

from clip_shared.config import get_settings, load_plans_config
from clip_shared.db.models import (
    AppConfigFlag,
    CaptionStyle,
    Clip,
    ClipCaption,
    ClipEdit,
    ClipMoment,
    ClipReframe,
    ExportPreset,
    InviteCode,
    Plan,
    Project,
    ScoringRun,
    Transcript,
    TranscriptSegment,
    TranscriptWord,
    User,
    UserPlan,
    Video,
)
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
                is_admin=True,
                status="active",
            )
            db.add(user)
            db.flush()
            print(f"Created dev admin user: {user.email} ({user.id})")
        else:
            user.is_admin = True
            db.flush()

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

        # 3. Plans from config/plans.yaml
        plans_cfg = load_plans_config()
        configured_plans = plans_cfg.get("plans", {})
        for pkey, pdata in configured_plans.items():
            plan = db.query(Plan).filter(Plan.key == pkey).first()
            if not plan:
                plan = Plan(
                    key=pkey,
                    name=pdata.get("name", pkey.capitalize()),
                    description=pdata.get("description"),
                    price_inr_monthly=pdata.get("price_inr_monthly", 0),
                    price_usd_monthly=pdata.get("price_usd_monthly", 0),
                    monthly_source_minutes=pdata.get("monthly_source_minutes", 30),
                    monthly_minutes=pdata.get("monthly_source_minutes", 30),
                    max_exports_per_month=pdata.get("max_exports_per_month", 10),
                    watermark=pdata.get("watermark", True),
                    export_watermark=pdata.get("watermark", True),
                    max_export_height=pdata.get("max_export_height", 1920),
                    max_video_length_min=pdata.get("max_video_length_min", 15),
                    max_concurrent_jobs=pdata.get("max_concurrent_jobs", 1),
                    retention_days=pdata.get("retention_days", 7),
                    priority=pdata.get("priority", "normal"),
                    is_active=pdata.get("is_active", True),
                    is_public=pdata.get("is_public", True),
                    razorpay_plan_id=pdata.get("razorpay_plan_id"),
                    stripe_price_id=pdata.get("stripe_price_id"),
                    features=pdata.get("features", {}),
                )
                db.add(plan)
                db.flush()
                print(f"Seeded plan: {plan.name} ({plan.key})")
            else:
                # Update existing plan with new config fields
                plan.name = pdata.get("name", plan.name)
                plan.description = pdata.get("description", plan.description)
                plan.price_inr_monthly = pdata.get("price_inr_monthly", plan.price_inr_monthly)
                plan.price_usd_monthly = pdata.get("price_usd_monthly", plan.price_usd_monthly)
                plan.monthly_source_minutes = pdata.get("monthly_source_minutes", plan.monthly_source_minutes)
                plan.monthly_minutes = plan.monthly_source_minutes
                plan.max_exports_per_month = pdata.get("max_exports_per_month", plan.max_exports_per_month)
                plan.watermark = pdata.get("watermark", plan.watermark)
                plan.export_watermark = plan.watermark
                plan.max_video_length_min = pdata.get("max_video_length_min", plan.max_video_length_min)
                plan.max_concurrent_jobs = pdata.get("max_concurrent_jobs", plan.max_concurrent_jobs)
                plan.retention_days = pdata.get("retention_days", plan.retention_days)
                plan.priority = pdata.get("priority", plan.priority)
                plan.is_active = pdata.get("is_active", plan.is_active)
                plan.is_public = pdata.get("is_public", plan.is_public)
                plan.razorpay_plan_id = pdata.get("razorpay_plan_id", plan.razorpay_plan_id)
                plan.stripe_price_id = pdata.get("stripe_price_id", plan.stripe_price_id)
                plan.features = pdata.get("features", plan.features)
                db.flush()

        # 4. User Plan
        user_plan = db.query(UserPlan).filter(UserPlan.user_id == user.id).first()
        if not user_plan:
            now = datetime.now(UTC)
            user_plan = UserPlan(
                id=uuid.uuid4(),
                user_id=user.id,
                plan_key="free",
                period_start=now,
                period_end=now + timedelta(days=30),
                status="active",
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

        # 7. App Config Flags
        default_flags = {
            "INVITE_ONLY": {"enabled": False, "description": "Gate signup behind invite codes for soft launch"},
            "PROVIDER_STRIPE_ENABLED": {"enabled": False, "description": "Enable Stripe USD subscriptions alongside Razorpay"},
            "GST_ENABLED": {"enabled": False, "description": "Issue tax invoices with GSTIN and CGST/SGST/IGST breakdown"},
            "CAPTCHA_ENABLED": {"enabled": False, "description": "Enable Cloudflare Turnstile on public signup and review forms"},
            "TOPUPS_ENABLED": {"enabled": True, "description": "Allow purchasing one-off top-up minute packs"},
            "SHOW_WHY_CHOSEN": {"enabled": True, "description": "Show AI reasoning tags on clips in frontend"},
            "MAINTENANCE_MODE": {"enabled": False, "description": "Show read-only maintenance notice across web UI"},
        }
        for fkey, fval in default_flags.items():
            flag = db.query(AppConfigFlag).filter(AppConfigFlag.key == fkey).first()
            if not flag:
                flag = AppConfigFlag(
                    key=fkey,
                    value=fval,
                    description=fval.get("description"),
                )
                db.add(flag)
                db.flush()
                print(f"Seeded flag: {fkey}")

        # 8. Soft Launch Invite Codes
        default_invites = [
            {"code": "CREATORLAUNCH", "max_uses": 100, "notes": "Soft launch initial cohort VIP code"},
            {"code": "EARLYACCESS2026", "max_uses": 50, "notes": "Early access creator community invite"},
        ]
        for inv in default_invites:
            code_rec = db.query(InviteCode).filter(InviteCode.code == inv["code"]).first()
            if not code_rec:
                code_rec = InviteCode(
                    id=uuid.uuid4(),
                    code=inv["code"],
                    max_uses=inv["max_uses"],
                    notes=inv["notes"],
                    created_by=user.id,
                )
                db.add(code_rec)
                db.flush()
                print(f"Seeded invite code: {inv['code']}")

        # 9. Seed Demo Sample Video & Clips (Instant no-upload tryout)
        demo_vid_id = uuid.UUID("00000000-0000-0000-0000-000000000099")
        demo_video = db.query(Video).filter(Video.id == demo_vid_id).first()
        if not demo_video:
            demo_video = Video(
                id=demo_vid_id,
                project_id=project.id,
                user_id=user.id,
                original_filename="sample_founders_talk.mp4",
                storage_key="sample/sample_founders_talk.mp4",
                proxy_key="sample/sample_founders_talk_proxy.mp4",
                audio_key="sample/sample_founders_talk_audio.wav",
                size_bytes=45_000_000,
                content_type="video/mp4",
                duration_seconds=360.0,
                width=1920,
                height=1080,
                fps=30.0,
                has_audio=True,
                status="ready",
            )
            db.add(demo_video)
            db.flush()

            # Transcript
            demo_transcript = Transcript(
                id=uuid.uuid4(),
                video_id=demo_vid_id,
                language="en",
                status="ready",
                model="large-v3",
                backend="whisperx",
                word_count=520,
            )
            db.add(demo_transcript)
            db.flush()

            # Add sample words
            sample_words = [
                ("The", 0, 200), ("biggest", 210, 500), ("mistake", 510, 850),
                ("founders", 860, 1200), ("make", 1210, 1500), ("is", 1510, 1650),
                ("building", 1660, 2100), ("features", 2110, 2500), ("nobody", 2510, 2900),
                ("asked", 2910, 3200), ("for.", 3210, 3600), ("Talk", 3700, 4000),
                ("to", 4010, 4100), ("ten", 4110, 4400), ("customers", 4410, 4900),
                ("before", 4910, 5300), ("writing", 5310, 5700), ("a", 5710, 5800),
                ("single", 5810, 6200), ("line", 6210, 6500), ("of", 6510, 6650),
                ("code.", 6660, 7100),
            ]
            for idx, (w, s, e) in enumerate(sample_words):
                db.add(TranscriptWord(
                    id=uuid.uuid4(),
                    transcript_id=demo_transcript.id,
                    idx=idx,
                    word=w,
                    start_ms=s,
                    end_ms=e,
                    speaker="SPEAKER_00",
                    confidence=0.98,
                ))

            # Add Scoring Run
            scoring_run = ScoringRun(
                id=uuid.uuid4(),
                video_id=demo_vid_id,
                prompt_version="v1",
                scorer_version="v1",
                weights={"hook": 0.35, "retention": 0.35, "novelty": 0.30},
                model="claude-3-5-sonnet",
                input_tokens=1200,
                output_tokens=350,
                cost_inr=0.25,
            )
            db.add(scoring_run)
            db.flush()

            # Add 3 Sample Moments & Clips
            clips_meta = [
                (
                    "The #1 Mistake First-Time Founders Make",
                    "Talk to 10 customers before writing code",
                    0, 28000, 0.94,
                    "High emotional punchline, immediate actionable advice for founders.",
                ),
                (
                    "Why Retention Beats Acquisition Every Single Time",
                    "A leaky bucket will kill your SaaS faster than competitors",
                    45000, 72000, 0.89,
                    "Clear hook contrast between vanity signups and paying retention.",
                ),
                (
                    "The 1,000 True Fans Playbook for Modern Creators",
                    "You don't need millions of followers to make a great living",
                    90000, 118000, 0.86,
                    "Strong contrarian take on audience size vs monetization depth.",
                ),
            ]
            for title, hook, start_ms, end_ms, score, reason in clips_meta:
                moment = ClipMoment(
                    id=uuid.uuid4(),
                    video_id=demo_vid_id,
                    transcript_id=demo_transcript.id,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    rank=1,
                    final_score=score,
                    status="selected",
                )
                db.add(moment)
                db.flush()

                clip = Clip(
                    id=uuid.uuid4(),
                    moment_id=moment.id,
                    video_id=demo_vid_id,
                    scoring_run_id=scoring_run.id,
                    variant_length_s="30",
                    start_ms=start_ms,
                    end_ms=end_ms,
                    hook_text=hook,
                    title=title,
                    final_score=score,
                    score_breakdown={"hook": 0.95, "retention": 0.90, "novelty": 0.85},
                    reason=reason,
                    model="claude-3-5-sonnet",
                )
                db.add(clip)
                db.flush()

                # Add Reframe
                db.add(ClipReframe(
                    id=uuid.uuid4(),
                    clip_id=clip.id,
                    analysis_version="v1",
                    mode="speaker_track",
                    crop_path={"keyframes": [{"t_ms": 0, "cx": 0.5, "cy": 0.5, "w": 0.5625, "h": 1.0}]},
                    confidence=0.96,
                    flags={},
                    source="auto",
                ))

                # Add Caption
                db.add(ClipCaption(
                    id=uuid.uuid4(),
                    clip_id=clip.id,
                    version="v1",
                    language="en",
                    words=[{"text": w, "start_ms": s, "end_ms": e, "deleted": False} for w, s, e in sample_words],
                    style_key="bold_pop",
                    style_overrides={},
                    source="auto",
                ))

                # Add Edit Doc
                db.add(ClipEdit(
                    id=uuid.uuid4(),
                    clip_id=clip.id,
                    user_id=user.id,
                    version=1,
                    doc={
                        "version": 1,
                        "clip_id": str(clip.id),
                        "video_id": str(demo_vid_id),
                        "source_range": {"start_ms": start_ms, "end_ms": end_ms},
                        "removals": [],
                        "captions": {
                            "style_key": "bold_pop",
                            "words": [{"text": w, "start_ms": s, "end_ms": e, "deleted": False} for w, s, e in sample_words],
                        },
                        "reframe": {
                            "mode": "speaker_track",
                            "keyframes": [{"t_ms": 0, "cx": 0.5, "cy": 0.5, "w": 0.5625, "h": 1.0}],
                        },
                    },
                    label="Initial Scored Clip",
                    is_checkpoint=True,
                ))

            print(f"Seeded demo sample video: {demo_video.id} with 3 scored clips")

        db.commit()



if __name__ == "__main__":
    seed_database()
