import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from clip_shared.db.base import Base, utc_now

JSON_TYPE = JSON().with_variant(PG_JSONB, "postgresql")
UUID = Uuid


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clerk_user_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    survey_response: Mapped[dict[str, Any] | None] = mapped_column(JSON_TYPE, nullable=True)
    deletion_scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    projects: Mapped[list["Project"]] = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    videos: Mapped[list["Video"]] = relationship("Video", back_populates="user", cascade="all, delete-orphan")
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    usage_records: Mapped[list["Usage"]] = relationship("Usage", back_populates="user", cascade="all, delete-orphan")
    review_sessions: Mapped[list["ReviewSession"]] = relationship("ReviewSession", back_populates="creator", cascade="all, delete-orphan")
    reframe_edits: Mapped[list["ClipReframeEdit"]] = relationship("ClipReframeEdit", back_populates="user", cascade="all, delete-orphan")
    exports: Mapped[list["Export"]] = relationship("Export", back_populates="user", cascade="all, delete-orphan")
    plan: Mapped[Optional["UserPlan"]] = relationship("UserPlan", back_populates="user", uselist=False, cascade="all, delete-orphan")
    edits: Mapped[list["ClipEdit"]] = relationship("ClipEdit", back_populates="user", cascade="all, delete-orphan")
    editor_events: Mapped[list["EditorEvent"]] = relationship("EditorEvent", back_populates="user", cascade="all, delete-orphan")
    customers: Mapped[list["Customer"]] = relationship("Customer", back_populates="user", cascade="all, delete-orphan")
    subscriptions: Mapped[list["Subscription"]] = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="user", cascade="all, delete-orphan")
    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="user", cascade="all, delete-orphan")
    top_ups: Mapped[list["TopUp"]] = relationship("TopUp", back_populates="user", cascade="all, delete-orphan")
    quota_ledger_entries: Mapped[list["QuotaLedger"]] = relationship("QuotaLedger", back_populates="user", cascade="all, delete-orphan")
    terms_acceptances: Mapped[list["TermsAcceptance"]] = relationship("TermsAcceptance", back_populates="user", cascade="all, delete-orphan")
    brand_kits: Mapped[list["BrandKit"]] = relationship("BrandKit", back_populates="user", cascade="all, delete-orphan")
    brand_assets: Mapped[list["BrandAsset"]] = relationship("BrandAsset", back_populates="user", cascade="all, delete-orphan")
    variant_sets: Mapped[list["VariantSet"]] = relationship("VariantSet", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_users_created_at", "created_at"),
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="projects")
    videos: Mapped[list["Video"]] = relationship("Video", back_populates="project")

    __table_args__ = (
        Index("ix_projects_user_created_at", "user_id", "created_at"),
    )


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    has_audio: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    proxy_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    audio_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="uploading", nullable=False)  # uploading | uploaded | processing | ready | failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="videos")
    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="videos")
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="video", cascade="all, delete-orphan")
    transcript: Mapped[Optional["Transcript"]] = relationship("Transcript", back_populates="video", uselist=False, cascade="all, delete-orphan")
    usage_records: Mapped[list["Usage"]] = relationship("Usage", back_populates="video")
    clip_moments: Mapped[list["ClipMoment"]] = relationship("ClipMoment", back_populates="video", cascade="all, delete-orphan")
    clips: Mapped[list["Clip"]] = relationship("Clip", back_populates="video", cascade="all, delete-orphan")
    scoring_runs: Mapped[list["ScoringRun"]] = relationship("ScoringRun", back_populates="video", cascade="all, delete-orphan")
    audio_features_records: Mapped[list["AudioFeatures"]] = relationship("AudioFeatures", back_populates="video", cascade="all, delete-orphan")
    review_sessions: Mapped[list["ReviewSession"]] = relationship("ReviewSession", back_populates="video", cascade="all, delete-orphan")
    analysis_records: Mapped[list["VideoAnalysis"]] = relationship("VideoAnalysis", back_populates="video", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_videos_user_created_at", "user_id", "created_at"),
        Index("ix_videos_status", "status"),
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)  # queued | running | succeeded | failed | cancelled
    current_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    progress: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 1 (normal) to 4 (vip)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stage_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    partial_results: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="jobs")
    video: Mapped["Video"] = relationship("Video", back_populates="jobs")
    stages: Mapped[list["JobStage"]] = relationship("JobStage", back_populates="job", cascade="all, delete-orphan", order_by="JobStage.started_at")
    usage_records: Mapped[list["Usage"]] = relationship("Usage", back_populates="job")
    dead_letter_record: Mapped[Optional["DeadLetterJob"]] = relationship("DeadLetterJob", back_populates="job", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_jobs_user_created_at", "user_id", "created_at"),
        Index("ix_jobs_status", "status"),
    )


class JobStage(Base):
    __tablename__ = "job_stages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)  # ingest, proxy, transcribe, candidates, score, render
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)  # pending | running | succeeded | failed | cancelled
    progress: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cost_inr: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0000"), nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="stages")

    __table_args__ = (
        UniqueConstraint("job_id", "name", name="uq_job_stage_job_id_name"),
        Index("ix_job_stages_job_id_name", "job_id", "name"),
    )


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), unique=True, nullable=False)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)  # running | ready | failed
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    backend: Mapped[str | None] = mapped_column(String(32), nullable=True)
    word_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="transcript")
    words: Mapped[list["TranscriptWord"]] = relationship("TranscriptWord", back_populates="transcript", cascade="all, delete-orphan", order_by="TranscriptWord.idx")
    segments: Mapped[list["TranscriptSegment"]] = relationship("TranscriptSegment", back_populates="transcript", cascade="all, delete-orphan", order_by="TranscriptSegment.idx")
    speakers: Mapped[list["Speaker"]] = relationship("Speaker", back_populates="transcript", cascade="all, delete-orphan", order_by="Speaker.label")
    clip_moments: Mapped[list["ClipMoment"]] = relationship("ClipMoment", back_populates="transcript", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_transcripts_video_id", "video_id"),
        Index("ix_transcripts_status", "status"),
    )


class TranscriptWord(Base):
    __tablename__ = "transcript_words"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transcript_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=False)
    idx: Mapped[int] = mapped_column(BigInteger, nullable=False)
    word: Mapped[str] = mapped_column(String(255), nullable=False)
    start_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    end_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    speaker: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    transcript: Mapped["Transcript"] = relationship("Transcript", back_populates="words")

    __table_args__ = (
        Index("ix_transcript_words_t_idx", "transcript_id", "idx"),
        Index("ix_transcript_words_t_time", "transcript_id", "start_ms", "end_ms"),
    )


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transcript_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=False)
    idx: Mapped[int] = mapped_column(BigInteger, nullable=False)
    start_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    end_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    speaker: Mapped[str | None] = mapped_column(String(64), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    transcript: Mapped["Transcript"] = relationship("Transcript", back_populates="segments")

    __table_args__ = (
        Index("ix_transcript_segments_t_idx", "transcript_id", "idx"),
        Index("ix_transcript_segments_t_time", "transcript_id", "start_ms", "end_ms"),
    )


class Speaker(Base):
    __tablename__ = "speakers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transcript_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String(64), nullable=False)  # SPEAKER_00
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    transcript: Mapped["Transcript"] = relationship("Transcript", back_populates="speakers")

    __table_args__ = (
        UniqueConstraint("transcript_id", "label", name="uq_speaker_transcript_label"),
        Index("ix_speakers_transcript_label", "transcript_id", "label"),
    )


class ClipMoment(Base):
    """Core idea span candidate / scored moment."""
    __tablename__ = "clip_moments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    transcript_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=False, index=True)
    start_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    end_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="candidate", nullable=False)  # candidate | scored | selected | rejected
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="clip_moments")
    transcript: Mapped["Transcript"] = relationship("Transcript", back_populates="clip_moments")
    clips: Mapped[list["Clip"]] = relationship("Clip", back_populates="moment", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_clip_moments_video_status", "video_id", "status"),
        Index("ix_clip_moments_video_score", "video_id", "final_score"),
        Index("ix_clip_moments_video_rank", "video_id", "rank"),
    )


class ScoringRun(Base):
    """Reproducibility run tracking models, prompts, weights, tokens and INR cost."""
    __tablename__ = "scoring_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    scorer_version: Mapped[str] = mapped_column(String(64), nullable=False)
    weights: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    cost_inr: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0000"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="scoring_runs")
    clips: Mapped[list["Clip"]] = relationship("Clip", back_populates="scoring_run")

    __table_args__ = (
        Index("ix_scoring_runs_video_created", "video_id", "created_at"),
    )


class Clip(Base):
    """Actual clip variant (15s, 30s, 45s, 60s, auto) with fine trims, hook, and score breakdown."""
    __tablename__ = "clips"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    moment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clip_moments.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    scoring_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("scoring_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    variant_length_s: Mapped[str] = mapped_column(String(16), default="auto", nullable=False)  # 15 | 30 | 45 | 60 | auto
    start_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    end_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    hook_text: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)  # hook, emotion, coherence, payoff, novelty, audio_energy, laughter, pause_penalty
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    scorer_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    moment: Mapped["ClipMoment"] = relationship("ClipMoment", back_populates="clips")
    video: Mapped["Video"] = relationship("Video", back_populates="clips")
    scoring_run: Mapped[Optional["ScoringRun"]] = relationship("ScoringRun", back_populates="clips")
    feedback: Mapped[list["ClipFeedback"]] = relationship("ClipFeedback", back_populates="clip", cascade="all, delete-orphan")
    review_ratings: Mapped[list["ReviewRating"]] = relationship("ReviewRating", back_populates="clip", cascade="all, delete-orphan")
    review_exports: Mapped[list["ClipReviewExport"]] = relationship("ClipReviewExport", back_populates="clip", cascade="all, delete-orphan")
    reframe_records: Mapped[list["ClipReframe"]] = relationship("ClipReframe", back_populates="clip", cascade="all, delete-orphan")
    captions: Mapped[list["ClipCaption"]] = relationship("ClipCaption", back_populates="clip", cascade="all, delete-orphan")
    cleanups: Mapped[list["ClipCleanup"]] = relationship("ClipCleanup", back_populates="clip", cascade="all, delete-orphan")
    exports: Mapped[list["Export"]] = relationship("Export", back_populates="clip", cascade="all, delete-orphan")
    edits: Mapped[list["ClipEdit"]] = relationship("ClipEdit", back_populates="clip", cascade="all, delete-orphan")
    alternatives: Mapped[list["ClipAlternative"]] = relationship("ClipAlternative", back_populates="clip", cascade="all, delete-orphan")
    editor_events: Mapped[list["EditorEvent"]] = relationship("EditorEvent", back_populates="clip", cascade="all, delete-orphan")
    variant_sets: Mapped[list["VariantSet"]] = relationship("VariantSet", back_populates="clip", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_clips_video_score", "video_id", "final_score"),
        Index("ix_clips_moment_variant", "moment_id", "variant_length_s"),
        Index("ix_clips_created_at", "created_at"),
    )


class ClipFeedback(Base):
    """User rating / thumbs up/down feedback for active learning and prompt improvement."""
    __tablename__ = "clip_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clips.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(16), nullable=False)  # up | down
    reason_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)  # boring | no_context | bad_start | bad_end | off_topic | other
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    clip: Mapped["Clip"] = relationship("Clip", back_populates="feedback")
    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        UniqueConstraint("clip_id", "user_id", name="uq_clip_feedback_clip_user"),
    )


class AudioFeatures(Base):
    """Extracted per-second audio features metadata stored in S3 and summary in DB."""
    __tablename__ = "audio_features"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), default="v1", nullable=False)
    frames_key: Mapped[str] = mapped_column(String(1024), nullable=False)  # users/{uid}/videos/{vid}/features/audio_v{n}.npz
    summary: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="audio_features_records")

    __table_args__ = (
        UniqueConstraint("video_id", "version", name="uq_audio_features_video_version"),
        Index("ix_audio_features_video_version", "video_id", "version"),
    )


class EvalVideo(Base):
    """Eval benchmark video dataset tracking."""
    __tablename__ = "eval_videos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class EvalClipRating(Base):
    """Human rater ground-truth score (1-5) tied to time range or clip ID."""
    __tablename__ = "eval_clip_ratings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    start_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    end_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    clip_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    rater_id: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 to 5
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("video_slug", "start_ms", "end_ms", "rater_id", name="uq_eval_clip_rating_range_rater"),
        Index("ix_eval_ratings_slug_time", "video_slug", "start_ms", "end_ms"),
    )


class Usage(Base):
    __tablename__ = "usage"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="SET NULL"), nullable=True, index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True, index=True)
    metric: Mapped[str] = mapped_column(String(64), nullable=False)  # source_minutes, gpu_seconds, llm_tokens, etc.
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    cost_inr: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0000"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="usage_records")
    video: Mapped[Optional["Video"]] = relationship("Video", back_populates="usage_records")
    job: Mapped[Optional["Job"]] = relationship("Job", back_populates="usage_records")

    __table_args__ = (
        # Idempotency constraint: unique by job_id + metric so re-running stages is safe
        UniqueConstraint("job_id", "metric", name="uq_usage_job_id_metric"),
        Index("ix_usage_user_created_at", "user_id", "created_at"),
        Index("ix_usage_metric", "metric"),
    )


class ReviewSession(Base):
    """External creator review session accessible via private token without authentication."""
    __tablename__ = "review_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    creator_name: Mapped[str] = mapped_column(String(255), nullable=False)
    creator_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)  # open | submitted | closed
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="review_sessions")
    creator: Mapped["User"] = relationship("User", back_populates="review_sessions")
    ratings: Mapped[list["ReviewRating"]] = relationship("ReviewRating", back_populates="session", cascade="all, delete-orphan")
    survey: Mapped[Optional["ReviewSurvey"]] = relationship("ReviewSurvey", back_populates="session", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("token", name="uq_review_session_token"),
        Index("ix_review_sessions_video_status", "video_id", "status"),
        Index("ix_review_sessions_expires_at", "expires_at"),
    )


class ReviewRating(Base):
    """Per-clip rating submitted by creator in a review session."""
    __tablename__ = "review_ratings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("review_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    clip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clips.id", ondelete="CASCADE"), nullable=False, index=True)
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)  # post_as_is | post_with_edits | no
    reason_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)  # bad_start | bad_end | no_context | boring | off_topic | too_long | too_short | other
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    watch_ms: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    session: Mapped["ReviewSession"] = relationship("ReviewSession", back_populates="ratings")
    clip: Mapped["Clip"] = relationship("Clip", back_populates="review_ratings")

    __table_args__ = (
        UniqueConstraint("session_id", "clip_id", name="uq_review_rating_session_clip"),
    )


class ReviewSurvey(Base):
    """Exit survey submitted by creator after rating clips."""
    __tablename__ = "review_survey"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("review_sessions.id", ondelete="CASCADE"), unique=True, nullable=False)
    missing_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_workflow_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_cost_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_open_inr: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    accepts_1500: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    accepts_4000: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    would_upload_next: Mapped[str | None] = mapped_column(String(16), nullable=True)  # yes | maybe | no
    upload_timeframe: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email_optin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    session: Mapped["ReviewSession"] = relationship("ReviewSession", back_populates="survey")

    __table_args__ = (
        Index("ix_review_survey_session_id", "session_id", unique=True),
    )


class ClipReviewExport(Base):
    """Rendered crude video exports for creator preview and download."""
    __tablename__ = "clip_review_exports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clips.id", ondelete="CASCADE"), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # horizontal | vertical_center
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    clip: Mapped["Clip"] = relationship("Clip", back_populates="review_exports")

    __table_args__ = (
        UniqueConstraint("clip_id", "kind", name="uq_clip_review_export_clip_kind"),
    )


class VideoAnalysis(Base):
    """Video visual scene and face analysis summary stored per video version."""
    __tablename__ = "video_analysis"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="v1", nullable=False)
    fps_sampled: Mapped[float] = mapped_column(Float, default=6.0, nullable=False)
    scenes: Mapped[list[dict[str, Any]]] = mapped_column(JSON_TYPE, default=list, nullable=False)  # [{start_ms, end_ms, type, confidence}]
    status: Mapped[str] = mapped_column(String(32), default="ready", nullable=False)  # queued | running | ready | failed
    frames_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)  # S3 npz key
    summary: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="analysis_records")
    face_tracks: Mapped[list["FaceTrack"]] = relationship("FaceTrack", back_populates="analysis", cascade="all, delete-orphan", order_by="FaceTrack.track_id")

    __table_args__ = (
        UniqueConstraint("video_id", "version", name="uq_video_analysis_video_version"),
        Index("ix_video_analysis_video_id", "video_id"),
        Index("ix_video_analysis_status", "status"),
    )


class FaceTrack(Base):
    """Tracked face trajectory summary and speaker association."""
    __tablename__ = "face_tracks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("video_analysis.id", ondelete="CASCADE"), nullable=False)
    track_id: Mapped[int] = mapped_column(Integer, nullable=False)
    start_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    end_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    avg_conf: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    speaker_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    analysis: Mapped["VideoAnalysis"] = relationship("VideoAnalysis", back_populates="face_tracks")

    __table_args__ = (
        UniqueConstraint("analysis_id", "track_id", name="uq_face_track_analysis_track_id"),
        Index("ix_face_tracks_analysis_id", "analysis_id"),
        Index("ix_face_tracks_speaker_label", "speaker_label"),
    )


class ClipReframe(Base):
    """Auto-generated or active reframed 9:16 crop path for a clip."""
    __tablename__ = "clip_reframes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clips.id", ondelete="CASCADE"), nullable=False)
    analysis_version: Mapped[str] = mapped_column(String(32), default="v1", nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)  # speaker_track | balanced | center | fit_blur
    crop_path: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)  # keyframes [{t_ms, cx, cy, w, h}], segments, easing
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    flags: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)  # face_cut_risk, low_confidence, multi_person, fallback_reason
    source: Mapped[str] = mapped_column(String(32), default="auto", nullable=False)  # auto | manual
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    clip: Mapped["Clip"] = relationship("Clip", back_populates="reframe_records")
    edits: Mapped[list["ClipReframeEdit"]] = relationship("ClipReframeEdit", back_populates="reframe", cascade="all, delete-orphan", order_by="ClipReframeEdit.created_at.desc()")

    __table_args__ = (
        UniqueConstraint("clip_id", "analysis_version", "source", name="uq_clip_reframe_clip_version_source"),
        Index("ix_clip_reframes_clip_id", "clip_id"),
        Index("ix_clip_reframes_mode", "mode"),
    )


class ClipReframeEdit(Base):
    """Manual nudge/edit override layer on top of auto reframing."""
    __tablename__ = "clip_reframe_edits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clip_reframe_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clip_reframes.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    keyframes: Mapped[list[dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=False)
    mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    reframe: Mapped["ClipReframe"] = relationship("ClipReframe", back_populates="edits")
    user: Mapped["User"] = relationship("User", back_populates="reframe_edits")

    __table_args__ = (
        Index("ix_clip_reframe_edits_reframe_id", "clip_reframe_id"),
        Index("ix_clip_reframe_edits_user_id", "user_id"),
    )


class CaptionStyle(Base):
    """Subtitle presentation style pack specification (ASS + preview)."""
    __tablename__ = "caption_styles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="v1", nullable=False)
    spec: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("key", name="uq_caption_styles_key"),
    )


class ExportPreset(Base):
    """Platform-specific export configuration preset."""
    __tablename__ = "export_presets"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    width: Mapped[int] = mapped_column(Integer, default=1080, nullable=False)
    height: Mapped[int] = mapped_column(Integer, default=1920, nullable=False)
    fps: Mapped[float] = mapped_column(Float, default=30.0, nullable=False)
    max_duration_s: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    video_bitrate: Mapped[str] = mapped_column(String(32), default="8000k", nullable=False)
    crf: Mapped[int] = mapped_column(Integer, default=22, nullable=False)
    audio_bitrate: Mapped[str] = mapped_column(String(32), default="192k", nullable=False)
    loudness_lufs: Mapped[float] = mapped_column(Float, default=-14.0, nullable=False)
    safe_zone: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Plan(Base):
    """Subscription tiers and feature limits."""
    __tablename__ = "plans"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_inr_monthly: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    price_usd_monthly: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    monthly_source_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    monthly_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)  # Alias for backward compatibility
    max_exports_per_month: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    watermark: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    export_watermark: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # Alias for backward compatibility
    max_export_height: Mapped[int] = mapped_column(Integer, default=1920, nullable=False)
    max_video_length_min: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    max_concurrent_jobs: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    priority: Mapped[str] = mapped_column(String(32), default="normal", nullable=False)  # normal | high | highest | vip
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    razorpay_plan_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    stripe_price_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    features: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    user_plans: Mapped[list["UserPlan"]] = relationship("UserPlan", back_populates="plan")
    subscriptions: Mapped[list["Subscription"]] = relationship("Subscription", back_populates="plan")


class UserPlan(Base):
    """User assigned plan and active billing period."""
    __tablename__ = "user_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    plan_key: Mapped[str] = mapped_column(String(64), ForeignKey("plans.key", ondelete="CASCADE"), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)  # active | past_due | canceled | expired
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="plan")
    plan: Mapped["Plan"] = relationship("Plan", back_populates="user_plans")

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_plans_user_id"),
    )


class ClipCaption(Base):
    """Style-agnostic word captions stored in SOURCE time."""
    __tablename__ = "clip_captions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clips.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), default="v1", nullable=False)
    language: Mapped[str] = mapped_column(String(16), default="en", nullable=False)
    words: Mapped[list[dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=False)  # [{text, start_ms, end_ms, speaker, emphasis, deleted}]
    style_key: Mapped[str] = mapped_column(String(64), default="bold_pop", nullable=False, index=True)
    style_overrides: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="auto", nullable=False)  # auto | manual
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    clip: Mapped["Clip"] = relationship("Clip", back_populates="captions")

    __table_args__ = (
        UniqueConstraint("clip_id", "version", "source", name="uq_clip_captions_clip_version_source"),
    )


class ClipCleanup(Base):
    """Filler word and silence removal configuration and individual removal intervals."""
    __tablename__ = "clip_cleanups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clips.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), default="v1", nullable=False)
    options: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)  # remove_fillers, remove_silence, max_silence_ms, filler_list, crossfade_ms
    removals: Mapped[list[dict[str, Any]]] = mapped_column(JSON_TYPE, default=list, nullable=False)  # [{start_ms, end_ms, kind, text}]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    clip: Mapped["Clip"] = relationship("Clip", back_populates="cleanups")

    __table_args__ = (
        UniqueConstraint("clip_id", "version", name="uq_clip_cleanups_clip_version"),
    )


class Export(Base):
    """Final rendered clip export record."""
    __tablename__ = "exports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clips.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)  # queued | rendering | succeeded | failed | cancelled
    preset_key: Mapped[str] = mapped_column(String(64), nullable=False)
    params_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    render_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clip_variants.id", ondelete="SET NULL", use_alter=True, name="fk_exports_variant_id"),
        nullable=True,
        index=True,
    )
    external_post_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    performance_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON_TYPE, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    clip: Mapped["Clip"] = relationship("Clip", back_populates="exports")
    user: Mapped["User"] = relationship("User", back_populates="exports")
    variant: Mapped[Optional["ClipVariant"]] = relationship(
        "ClipVariant",
        foreign_keys=[variant_id],
        back_populates="export",
        post_update=True,
    )

    __table_args__ = (
        Index("ix_exports_created_at", "created_at"),
    )


class ClipEdit(Base):
    """Versioned edit document for a clip (single source of truth)."""
    __tablename__ = "clip_edits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clips.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    doc: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    parent_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_checkpoint: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    clip: Mapped["Clip"] = relationship("Clip", back_populates="edits")
    user: Mapped["User"] = relationship("User", back_populates="edits")

    __table_args__ = (
        Index("ix_clip_edits_clip_version", "clip_id", "version"),
        Index("ix_clip_edits_clip_created", "clip_id", "created_at"),
        UniqueConstraint("clip_id", "version", name="uq_clip_edits_clip_version"),
    )


class ClipAlternative(Base):
    """Alternative hook or range trims populated from scoring runs or regeneration."""
    __tablename__ = "clip_alternatives"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clips.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # hook | range
    start_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    end_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)  # scoring_run_id | regenerate
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    clip: Mapped["Clip"] = relationship("Clip", back_populates="alternatives")

    __table_args__ = (
        Index("ix_clip_alternatives_clip_kind", "clip_id", "kind"),
        Index("ix_clip_alternatives_created_at", "created_at"),
    )


class EditorEvent(Base):
    """Instrumentation event for editor performance and user workflow tracking."""
    __tablename__ = "editor_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    clip_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clips.id", ondelete="CASCADE"), nullable=True, index=True)
    session_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="editor_events")
    clip: Mapped[Optional["Clip"]] = relationship("Clip", back_populates="editor_events")

    __table_args__ = (
        Index("ix_editor_events_user_created", "user_id", "created_at"),
        Index("ix_editor_events_session", "session_id"),
        Index("ix_editor_events_type", "type"),
    )


# ---------------------------------------------------------------------------
# Phase 6 Models: Billing, Ledger, Invoices, Legal, Abuse & Operations
# ---------------------------------------------------------------------------

class Customer(Base):
    """Mapping between local user and payment gateway customer IDs."""
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)  # razorpay | stripe
    provider_customer_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="customers")
    subscriptions: Mapped[list["Subscription"]] = relationship("Subscription", back_populates="customer")

    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_customers_user_provider"),
        Index("ix_customers_provider_cust_id", "provider", "provider_customer_id"),
    )


class Subscription(Base):
    """Mirrored subscription record synced via webhooks."""
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)  # razorpay | stripe
    provider_subscription_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    plan_key: Mapped[str] = mapped_column(String(64), ForeignKey("plans.key", ondelete="RESTRICT"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)  # active | past_due | canceled | expired | halted | pending
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="subscriptions")
    customer: Mapped[Optional["Customer"]] = relationship("Customer", back_populates="subscriptions")
    plan: Mapped["Plan"] = relationship("Plan", back_populates="subscriptions")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="subscription")
    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="subscription")

    __table_args__ = (
        Index("ix_subscriptions_user_status", "user_id", "status"),
        Index("ix_subscriptions_provider_sub_id", "provider", "provider_subscription_id"),
    )


class Payment(Base):
    """Payment transaction log for audits, subscriptions, and top-ups."""
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True, index=True)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)  # razorpay | stripe
    provider_payment_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="succeeded", nullable=False, index=True)  # succeeded | failed | refunded | partially_refunded
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="payments")
    subscription: Mapped[Optional["Subscription"]] = relationship("Subscription", back_populates="payments")
    invoice: Mapped[Optional["Invoice"]] = relationship("Invoice", back_populates="payments", foreign_keys=[invoice_id])

    __table_args__ = (
        Index("ix_payments_user_created", "user_id", "created_at"),
    )


class Invoice(Base):
    """Sequential, gap-free tax invoice or receipt with GST breakdown and S3 PDF."""
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True, index=True)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)  # Populated when payment is created
    invoice_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    financial_year: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # e.g., 2026-27
    seq_number: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(32), default="tax_invoice", nullable=False)  # tax_invoice | receipt | credit_note
    original_invoice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True)

    # Customer & Tax details
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_address: Mapped[dict[str, Any] | None] = mapped_column(JSON_TYPE, nullable=True)
    customer_gstin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    customer_state_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    place_of_supply: Mapped[str] = mapped_column(String(32), default="intra_state", nullable=False)  # intra_state | inter_state | export

    # Financial Breakdowns
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cgst_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.0000"), nullable=False)
    cgst_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    sgst_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.0000"), nullable=False)
    sgst_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    igst_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.0000"), nullable=False)
    igst_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total_tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)

    status: Mapped[str] = mapped_column(String(32), default="paid", nullable=False)  # paid | void | refunded
    pdf_storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    lut_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="invoices")
    subscription: Mapped[Optional["Subscription"]] = relationship("Subscription", back_populates="invoices")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="invoice", foreign_keys=[Payment.invoice_id])
    credit_notes: Mapped[list["Invoice"]] = relationship("Invoice", remote_side=[original_invoice_id])

    __table_args__ = (
        UniqueConstraint("financial_year", "seq_number", "type", name="uq_invoice_fy_seq_type"),
        Index("ix_invoices_user_created", "user_id", "created_at"),
        Index("ix_invoices_status", "status"),
    )


class InvoiceSequence(Base):
    """Gap-free atomic sequence counter for financial year tax invoice generation."""
    __tablename__ = "invoice_sequences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    financial_year: Mapped[str] = mapped_column(String(16), nullable=False)
    seq_type: Mapped[str] = mapped_column(String(32), default="tax_invoice", nullable=False)
    last_val: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("prefix", "financial_year", "seq_type", name="uq_invoice_seq_prefix_fy_type"),
    )


class WebhookEvent(Base):
    """Idempotency log for payment webhooks to safely handle replays and out-of-order events."""
    __tablename__ = "webhook_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)  # razorpay | stripe
    event_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="received", nullable=False)  # received | processed | ignored | failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_webhook_events_provider_event_id"),
        Index("ix_webhook_events_created", "created_at"),
    )


class TopUp(Base):
    """One-time credit pack purchases adding source minutes with expiration."""
    __tablename__ = "top_ups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    pack_key: Mapped[str] = mapped_column(String(64), nullable=False)
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)  # active | exhausted | expired
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="top_ups")

    __table_args__ = (
        Index("ix_top_ups_user_status_exp", "user_id", "status", "expires_at"),
    )


class QuotaLedger(Base):
    """Append-only audit ledger of every minute reserved, reconciled, refunded, and topped up."""
    __tablename__ = "quota_ledger"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    delta_minutes: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # reasons: monthly_grant | job_reserve | job_reconcile | job_refund | top_up | admin_adjustment
    ref_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)  # job_id or payment_id
    meta: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="quota_ledger_entries")

    __table_args__ = (
        Index("ix_quota_ledger_user_created", "user_id", "created_at"),
    )


class InviteCode(Base):
    """Waitlist and soft-launch invite gating table."""
    __tablename__ = "invite_codes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    max_uses: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    uses_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    redemptions: Mapped[list["UserInvite"]] = relationship("UserInvite", back_populates="invite_code", cascade="all, delete-orphan")


class UserInvite(Base):
    """User invite redemption audit record."""
    __tablename__ = "user_invites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    invite_code_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("invite_codes.id", ondelete="CASCADE"), nullable=False, index=True)
    redeemed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    invite_code: Mapped["InviteCode"] = relationship("InviteCode", back_populates="redemptions")


class TermsAcceptance(Base):
    """Versioned legal document acceptance records for DPDP Act and compliance."""
    __tablename__ = "terms_acceptances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    doc_type: Mapped[str] = mapped_column(String(64), nullable=False)  # terms | privacy | aup | refund | dmca
    doc_version: Mapped[str] = mapped_column(String(32), nullable=False)
    ip_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="terms_acceptances")

    __table_args__ = (
        Index("ix_terms_acceptances_user_doc", "user_id", "doc_type", "doc_version"),
    )


class TakedownRequest(Base):
    """DMCA and copyright takedown notices queue with counter-notice flow and SLA timers."""
    __tablename__ = "takedown_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    claimant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    claimant_email: Mapped[str] = mapped_column(String(255), nullable=False)
    claimant_organization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    work_description: Mapped[str] = mapped_column(Text, nullable=False)
    infringing_url_or_id: Mapped[str] = mapped_column(String(1024), nullable=False)
    video_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="SET NULL"), nullable=True, index=True)
    good_faith_confirmed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    perjury_confirmed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    signature: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="submitted", nullable=False, index=True)
    # status: submitted | under_review | actioned_blocked | counter_notice_received | restored | rejected
    counter_notice_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON_TYPE, nullable=True)
    sla_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actioned_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    audit_trail: Mapped[list[dict[str, Any]]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_takedown_requests_created_status", "created_at", "status"),
    )


class DeletionAudit(Base):
    """Auditable log of video or account deletion operations."""
    __tablename__ = "deletion_audits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)  # video | account
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending_grace", nullable=False)  # pending_grace | completed | cancelled
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    grace_period_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    s3_objects_deleted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    db_rows_deleted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    audit_data: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_deletion_audits_entity", "entity_type", "entity_id"),
    )


class DeadLetterJob(Base):
    """Permanent graveyard for stuck/exhausted jobs to prevent silent hangs and enable debugging."""
    __tablename__ = "dead_letter_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    failed_stage: Mapped[str] = mapped_column(String(64), nullable=False)
    error_code: Mapped[str] = mapped_column(String(64), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="dead_letter_record")

    __table_args__ = (
        Index("ix_dead_letter_jobs_created", "created_at"),
        Index("ix_dead_letter_jobs_resolved", "resolved"),
    )


class AnalyticsEvent(Base):
    """Self-hosted telemetry and conversion event table (no PII in properties)."""
    __tablename__ = "analytics_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    event_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    properties: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    __table_args__ = (
        Index("ix_analytics_events_name_created", "event_name", "created_at"),
    )


class AppConfigFlag(Base):
    """Dynamic application feature flags and runtime configurations."""
    __tablename__ = "app_config_flags"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


# ---------------------------------------------------------------------------
# Phase 7a Models: Brand Kit and Auto-Variants
# ---------------------------------------------------------------------------

class BrandAsset(Base):
    """Uploaded user assets for brand kits: logos, fonts, intro/outro clips."""
    __tablename__ = "brand_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # logo | font | intro | outro
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="processing", nullable=False, index=True)  # processing | ready | failed
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="brand_assets")

    __table_args__ = (
        Index("ix_brand_assets_user_kind", "user_id", "kind"),
        Index("ix_brand_assets_created_at", "created_at"),
    )


class BrandKit(Base):
    """Reusable brand identity kit (logo, colors, typography, intro/outro, caption style)."""
    __tablename__ = "brand_kits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    colors: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)  # primary, secondary, text, highlight, background
    fonts: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)   # heading_asset_id, body_asset_id, font_family
    logo_asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("brand_assets.id", ondelete="SET NULL"), nullable=True)
    logo_position: Mapped[str] = mapped_column(String(32), default="top_right", nullable=False)  # top_left | top_right | bottom_left | bottom_right
    logo_opacity: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    logo_scale: Mapped[float] = mapped_column(Float, default=0.15, nullable=False)
    caption_style_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    caption_overrides: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    intro_asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("brand_assets.id", ondelete="SET NULL"), nullable=True)
    outro_asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("brand_assets.id", ondelete="SET NULL"), nullable=True)
    watermark_free_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="brand_kits")
    logo_asset: Mapped[Optional["BrandAsset"]] = relationship("BrandAsset", foreign_keys=[logo_asset_id])
    intro_asset: Mapped[Optional["BrandAsset"]] = relationship("BrandAsset", foreign_keys=[intro_asset_id])
    outro_asset: Mapped[Optional["BrandAsset"]] = relationship("BrandAsset", foreign_keys=[outro_asset_id])

    __table_args__ = (
        Index("ix_brand_kits_user_default", "user_id", "is_default"),
        Index("ix_brand_kits_created_at", "created_at"),
    )


class VariantSet(Base):
    """A generated set of auto-variants for a single clip moment."""
    __tablename__ = "variant_sets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clips.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="ready", nullable=False)  # pending | ready | failed
    dimensions: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list, nullable=False)  # ["hook", "style", "cta"]
    requested_count: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    clip: Mapped["Clip"] = relationship("Clip", back_populates="variant_sets")
    user: Mapped["User"] = relationship("User", back_populates="variant_sets")
    variants: Mapped[list["ClipVariant"]] = relationship("ClipVariant", back_populates="variant_set", cascade="all, delete-orphan", order_by="ClipVariant.created_at.asc()")

    __table_args__ = (
        Index("ix_variant_sets_clip_created", "clip_id", "created_at"),
    )


class ClipVariant(Base):
    """An individual variant of a clip moment with lightweight edit_doc snapshot."""
    __tablename__ = "clip_variants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    set_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("variant_sets.id", ondelete="CASCADE"), nullable=False, index=True)
    edit_doc: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    hook_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption_style_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cta_text: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cta_style: Mapped[str | None] = mapped_column(String(64), nullable=True)
    score_hint: Mapped[float | None] = mapped_column(Float, nullable=True)
    export_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exports.id", ondelete="SET NULL", use_alter=True, name="fk_clip_variants_export_id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    variant_set: Mapped["VariantSet"] = relationship("VariantSet", back_populates="variants")
    export: Mapped[Optional["Export"]] = relationship(
        "Export",
        foreign_keys="[Export.variant_id]",
        back_populates="variant",
        uselist=False,
        post_update=True,
    )

    __table_args__ = (
        Index("ix_clip_variants_created_at", "created_at"),
    )







