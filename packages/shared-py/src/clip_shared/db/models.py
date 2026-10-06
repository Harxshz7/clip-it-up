import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    String,
    BigInteger,
    Integer,
    Float,
    Numeric,
    DateTime,
    Boolean,
    ForeignKey,
    Index,
    UniqueConstraint,
    Text,
    JSON,
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
    projects: Mapped[List["Project"]] = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    videos: Mapped[List["Video"]] = relationship("Video", back_populates="user", cascade="all, delete-orphan")
    jobs: Mapped[List["Job"]] = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    usage_records: Mapped[List["Usage"]] = relationship("Usage", back_populates="user", cascade="all, delete-orphan")

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
    videos: Mapped[List["Video"]] = relationship("Video", back_populates="project")

    __table_args__ = (
        Index("ix_projects_user_created_at", "user_id", "created_at"),
    )


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    has_audio: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    proxy_key: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    audio_key: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="uploading", nullable=False)  # uploading | uploaded | processing | ready | failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="videos")
    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="videos")
    jobs: Mapped[List["Job"]] = relationship("Job", back_populates="video", cascade="all, delete-orphan")
    transcript: Mapped[Optional["Transcript"]] = relationship("Transcript", back_populates="video", uselist=False, cascade="all, delete-orphan")
    usage_records: Mapped[List["Usage"]] = relationship("Usage", back_populates="video")

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
    current_stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    progress: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    partial_results: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="jobs")
    video: Mapped["Video"] = relationship("Video", back_populates="jobs")
    stages: Mapped[List["JobStage"]] = relationship("JobStage", back_populates="job", cascade="all, delete-orphan", order_by="JobStage.started_at")
    usage_records: Mapped[List["Usage"]] = relationship("Usage", back_populates="job")

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
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    cost_inr: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0000"), nullable=False)
    meta: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)

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
    language: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)  # running | ready | failed
    model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    backend: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    word_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="transcript")
    words: Mapped[List["TranscriptWord"]] = relationship("TranscriptWord", back_populates="transcript", cascade="all, delete-orphan", order_by="TranscriptWord.idx")
    segments: Mapped[List["TranscriptSegment"]] = relationship("TranscriptSegment", back_populates="transcript", cascade="all, delete-orphan", order_by="TranscriptSegment.idx")
    speakers: Mapped[List["Speaker"]] = relationship("Speaker", back_populates="transcript", cascade="all, delete-orphan", order_by="Speaker.label")

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
    speaker: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

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
    speaker: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
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
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    transcript: Mapped["Transcript"] = relationship("Transcript", back_populates="speakers")

    __table_args__ = (
        UniqueConstraint("transcript_id", "label", name="uq_speaker_transcript_label"),
        Index("ix_speakers_transcript_label", "transcript_id", "label"),
    )


class Usage(Base):
    __tablename__ = "usage"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="SET NULL"), nullable=True, index=True)
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True, index=True)
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

