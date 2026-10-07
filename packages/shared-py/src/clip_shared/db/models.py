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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    projects: Mapped[list["Project"]] = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    videos: Mapped[list["Video"]] = relationship("Video", back_populates="user", cascade="all, delete-orphan")
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    usage_records: Mapped[list["Usage"]] = relationship("Usage", back_populates="user", cascade="all, delete-orphan")

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


