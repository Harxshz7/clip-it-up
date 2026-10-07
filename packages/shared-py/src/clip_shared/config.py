from functools import lru_cache
from typing import List, Literal, Optional
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
    S3_PUBLIC_ENDPOINT_URL: Optional[str] = "http://localhost:9000"
    S3_ACCESS_KEY_ID: str = "minioadmin"
    S3_SECRET_ACCESS_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "clip-it-up-videos"
    S3_REGION: str = "us-east-1"
    S3_USE_SSL: bool = False

    # Auth (Clerk)
    CLERK_SECRET_KEY: Optional[str] = None
    CLERK_PUBLISHABLE_KEY: Optional[str] = None
    CLERK_JWKS_URL: Optional[str] = "https://api.clerk.com/v1/jwks"
    CLERK_ISSUER: Optional[str] = None

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

    ALLOWED_CONTENT_TYPES: List[str] = Field(
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
    HF_TOKEN: Optional[str] = None
    WHISPER_MODEL: str = "large-v3"
    WHISPER_COMPUTE_TYPE: str = "float16"
    WHISPER_BATCH_SIZE: int = 16
    DIARIZATION_ENABLED: bool = True
    MIN_SPEAKERS: Optional[int] = 1
    MAX_SPEAKERS: Optional[int] = 10
    DEEPGRAM_API_KEY: Optional[str] = None

    # LLM & Scoring (Anthropic Claude API)
    ANTHROPIC_API_KEY: Optional[str] = None
    LLM_PASS1_MODEL: str = "claude-3-haiku-20240307"
    LLM_PASS2_MODEL: str = "claude-3-5-sonnet-20241022"
    LLM_SCORER_BACKEND: Literal["anthropic", "mock"] = "mock"
    PROMPT_VERSION: str = "v1"
    SCORER_VERSION: str = "v1"
    MAX_CANDIDATES_PER_HOUR: int = 60
    LLM_CONCURRENCY: int = 5
    USD_TO_INR_RATE: float = 85.0

    # Sentry
    SENTRY_DSN: Optional[str] = None

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @field_validator("DEV_AUTH_BYPASS")
    @classmethod
    def validate_dev_bypass(cls, v: bool, info) -> bool:
        # Note: in pydantic-settings, validation runs per field
        return v


@lru_cache()
def get_settings() -> Settings:
    return Settings()


def load_scoring_weights(custom_weights_path: Optional[str] = None) -> dict:
    """Load scoring weights and thresholds from YAML configuration file."""
    import os
    import yaml

    if custom_weights_path and os.path.exists(custom_weights_path):
        with open(custom_weights_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    default_path = os.path.join(os.path.dirname(__file__), "config", "scoring_weights.yaml")
    if os.path.exists(default_path):
        with open(default_path, "r", encoding="utf-8") as f:
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
