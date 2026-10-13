from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: str = "info"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/clip_it_up"
    DATABASE_SYNC_URL: str = "postgresql://postgres:postgres@localhost:5432/clip_it_up"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Storage (S3 / MinIO / Cloudflare R2)
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_PUBLIC_ENDPOINT_URL: str | None = "http://localhost:9000"
    S3_ACCESS_KEY_ID: str = "minioadmin"
    S3_SECRET_ACCESS_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "clip-it-up-videos"
    S3_REGION: str = "us-east-1"
    S3_USE_SSL: bool = False

    # Auth (Clerk)
    CLERK_SECRET_KEY: str | None = None
    CLERK_PUBLISHABLE_KEY: str | None = None
    CLERK_JWKS_URL: str | None = "https://api.clerk.com/v1/jwks"
    CLERK_ISSUER: str | None = None

    # Dev Auth Bypass
    DEV_AUTH_BYPASS: bool = True
    DEV_USER_ID: str = "00000000-0000-0000-0000-000000000001"
    DEV_USER_EMAIL: str = "dev@clipitup.local"
    DEV_CLERK_USER_ID: str = "user_dev_bypass"

    # API Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    MAX_UPLOAD_SIZE_BYTES: int = 5 * 1024 * 1024 * 1024  # 5 GB
    MULTIPART_THRESHOLD_BYTES: int = 100 * 1024 * 1024  # 100 MB
    MULTIPART_PART_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB per part
    PRESIGNED_URL_EXPIRY_SECONDS: int = 3600

    ALLOWED_CONTENT_TYPES: list[str] = Field(
        default_factory=lambda: [
            "video/mp4",
            "video/quicktime",
            "video/x-matroska",
            "video/webm",
        ]
    )

    # Pipeline & Processing Limits
    MAX_DURATION_MIN: int = 120
    PIPELINE_STAGE_DURATION_SECONDS: float = 2.0
    INJECT_RANDOM_FAILURE: bool = False

    # Transcription Backend & Models
    TRANSCRIBE_BACKEND: Literal["whisperx", "deepgram", "mock"] = "mock"
    HF_TOKEN: str | None = None
    WHISPER_MODEL: str = "large-v3"
    WHISPER_COMPUTE_TYPE: str = "float16"
    WHISPER_BATCH_SIZE: int = 16
    DIARIZATION_ENABLED: bool = True
    MIN_SPEAKERS: int | None = 1
    MAX_SPEAKERS: int | None = 10
    DEEPGRAM_API_KEY: str | None = None

    # LLM & Scoring (Anthropic Claude API)
    ANTHROPIC_API_KEY: str | None = None
    LLM_PASS1_MODEL: str = "claude-3-haiku-20240307"
    LLM_PASS2_MODEL: str = "claude-3-5-sonnet-20241022"
    LLM_SCORER_BACKEND: Literal["anthropic", "mock"] = "mock"
    PROMPT_VERSION: str = "v1"
    SCORER_VERSION: str = "v1"
    MAX_CANDIDATES_PER_HOUR: int = 60
    LLM_CONCURRENCY: int = 5
    USD_TO_INR_RATE: float = 85.0

    # Sentry
    SENTRY_DSN: str | None = None
    SENTRY_RELEASE: str = "clip-it-up@0.6.0"

    # Feature Flags & Launch Controls
    INVITE_ONLY: bool = False
    PROVIDER_STRIPE_ENABLED: bool = False
    GST_ENABLED: bool = False
    CAPTCHA_ENABLED: bool = False
    TOPUPS_ENABLED: bool = True
    SHOW_WHY_CHOSEN: bool = True
    MAINTENANCE_MODE: bool = False

    # Payment Gateways (Razorpay & Stripe)
    RAZORPAY_KEY_ID: str | None = "rzp_test_mock_key"
    RAZORPAY_KEY_SECRET: str | None = "rzp_test_mock_secret"
    RAZORPAY_WEBHOOK_SECRET: str | None = "rzp_test_webhook_secret"
    STRIPE_PUBLISHABLE_KEY: str | None = None
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None

    # Communications & Support
    RESEND_API_KEY: str | None = None
    SUPPORT_EMAIL: str = "support@clipitup.local"
    BILLING_EMAIL: str = "billing@clipitup.local"
    ADMIN_API_KEY: str = "dev_admin_secret_key"
    APP_BASE_URL: str = "http://localhost:3000"
    API_BASE_URL: str = "http://localhost:8000"

    # Inactivity & Supervisor
    JOB_STUCK_TIMEOUT_SECONDS: int = 600  # 10 minutes
    JOB_MAX_ATTEMPTS: int = 3
    RETENTION_SWEEP_DAYS: int = 7

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @field_validator("DEV_AUTH_BYPASS")
    @classmethod
    def validate_dev_bypass(cls, v: bool, info) -> bool:
        # Note: in pydantic-settings, validation runs per field
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


def load_scoring_weights(custom_weights_path: str | None = None) -> dict:
    """Load scoring weights and thresholds from YAML configuration file."""
    import os

    import yaml

    if custom_weights_path and os.path.exists(custom_weights_path):
        with open(custom_weights_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    default_path = os.path.join(os.path.dirname(__file__), "config", "scoring_weights.yaml")
    if os.path.exists(default_path):
        with open(default_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    # Fallback dictionary if file not found
    return {
        "version": "v1",
        "weights": {
            "hook": 0.30,
            "emotion": 0.15,
            "coherence": 0.20,
            "payoff": 0.20,
            "novelty": 0.10,
            "audio_energy": 0.10,
            "laughter": 0.05,
            "pause_penalty": 0.15,
            "flag_penalty": 0.30,
        },
        "hook_start_window_s": 3.0,
        "hook_energy_boost": 0.15,
        "thresholds": {
            "min_usable_score": 0.65,
            "selection_iou_threshold": 0.30,
            "diversity_window_minutes": 5.0,
            "max_clips_per_window": 2,
            "diversity_score_override": 0.85,
            "max_selected_clips": 10,
            "candidate_iou_cluster_threshold": 0.50,
        },
    }


def load_plans_config(custom_path: str | None = None) -> dict:
    """Load plan definitions from YAML configuration file."""
    import os
    import yaml

    search_paths = [
        custom_path,
        os.path.join(os.getcwd(), "config", "plans.yaml"),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "config", "plans.yaml")),
    ]
    for p in search_paths:
        if p and os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return yaml.safe_load(f)

    # Hardcoded fallback dictionary to guarantee reliable defaults
    return {
        "plans": {
            "free": {
                "key": "free",
                "name": "Free Tier",
                "price_inr_monthly": 0,
                "price_usd_monthly": 0,
                "monthly_source_minutes": 30,
                "max_exports_per_month": 10,
                "watermark": True,
                "max_video_length_min": 15,
                "max_concurrent_jobs": 1,
                "retention_days": 7,
                "priority": "normal",
                "is_active": True,
                "is_public": True,
                "features": {"watermark": True, "max_resolution": "1080p"},
            },
            "creator": {
                "key": "creator",
                "name": "Creator Plan",
                "price_inr_monthly": 1499,
                "price_usd_monthly": 19,
                "monthly_source_minutes": 300,
                "max_exports_per_month": 100,
                "watermark": False,
                "max_video_length_min": 60,
                "max_concurrent_jobs": 2,
                "retention_days": 30,
                "priority": "high",
                "is_active": True,
                "is_public": True,
                "features": {"watermark": False, "max_resolution": "1080p"},
            },
            "pro": {
                "key": "pro",
                "name": "Pro Studio",
                "price_inr_monthly": 3999,
                "price_usd_monthly": 49,
                "monthly_source_minutes": 1200,
                "max_exports_per_month": 500,
                "watermark": False,
                "max_video_length_min": 120,
                "max_concurrent_jobs": 5,
                "retention_days": 90,
                "priority": "highest",
                "is_active": True,
                "is_public": True,
                "features": {"watermark": False, "max_resolution": "4k"},
            },
        },
        "top_up_packs": {},
    }


def load_billing_config(custom_path: str | None = None) -> dict:
    """Load billing and GST config from YAML file."""
    import os
    import yaml

    search_paths = [
        custom_path,
        os.path.join(os.getcwd(), "config", "billing.yaml"),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "config", "billing.yaml")),
    ]
    for p in search_paths:
        if p and os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return yaml.safe_load(f)

    return {
        "seller": {
            "legal_name": "clip-it-up Technologies Private Limited",
            "gstin": "27AAAAA0000A1Z5",
            "state_code": "27",
            "state_name": "Maharashtra",
            "invoice_prefix": "CIU",
            "sac_code": "998314",
        },
        "taxes": {"gst_enabled": False, "default_tax_rate": 0.18, "prices_include_tax": False},
        "gateways": {"razorpay": {"enabled": True}, "stripe": {"enabled": False}},
        "billing_policy": {"overage_policy": "block", "grace_period_days": 3},
        "abuse_caps": {"max_free_signups_per_ip_per_day": 3, "disposable_email_domains": []},
    }

