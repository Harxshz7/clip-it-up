"""0005 phase3 video analysis, face tracking, and clip reframing

Revision ID: 0005_phase3_reframing
Revises: 0004_phase2_5_creator_review
Create Date: 2026-10-09 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0005_phase3_reframing'
down_revision: str | None = '0004_phase2_5_creator_review'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create video_analysis table
    op.create_table(
        'video_analysis',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('video_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version', sa.String(length=32), server_default='v1', nullable=False),
        sa.Column('fps_sampled', sa.Float(), server_default='6.0', nullable=False),
        sa.Column('scenes', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('status', sa.String(length=32), server_default='ready', nullable=False),  # queued | running | ready | failed
        sa.Column('frames_key', sa.String(length=1024), nullable=True),  # S3 key for raw npz detections
        sa.Column('summary', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('video_id', 'version', name='uq_video_analysis_video_version'),
    )
    op.create_index('ix_video_analysis_video_id', 'video_analysis', ['video_id'], unique=False)
    op.create_index('ix_video_analysis_status', 'video_analysis', ['status'], unique=False)

    # 2. Create face_tracks table
    op.create_table(
        'face_tracks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('analysis_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('track_id', sa.Integer(), nullable=False),
        sa.Column('start_ms', sa.BigInteger(), nullable=False),
        sa.Column('end_ms', sa.BigInteger(), nullable=False),
        sa.Column('avg_conf', sa.Float(), nullable=False),
        sa.Column('speaker_label', sa.String(length=64), nullable=True),
        sa.Column('summary', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['analysis_id'], ['video_analysis.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('analysis_id', 'track_id', name='uq_face_track_analysis_track_id'),
    )
    op.create_index('ix_face_tracks_analysis_id', 'face_tracks', ['analysis_id'], unique=False)
    op.create_index('ix_face_tracks_speaker_label', 'face_tracks', ['speaker_label'], unique=False)

    # 3. Create clip_reframes table
    op.create_table(
        'clip_reframes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clip_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('analysis_version', sa.String(length=32), server_default='v1', nullable=False),
        sa.Column('mode', sa.String(length=32), nullable=False),  # speaker_track | balanced | center | fit_blur
        sa.Column('crop_path', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('flags', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('source', sa.String(length=32), server_default='auto', nullable=False),  # auto | manual
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['clip_id'], ['clips.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('clip_id', 'analysis_version', 'source', name='uq_clip_reframe_clip_version_source'),
    )
    op.create_index('ix_clip_reframes_clip_id', 'clip_reframes', ['clip_id'], unique=False)
    op.create_index('ix_clip_reframes_mode', 'clip_reframes', ['mode'], unique=False)

    # 4. Create clip_reframe_edits table
    op.create_table(
        'clip_reframe_edits',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clip_reframe_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('keyframes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('mode', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['clip_reframe_id'], ['clip_reframes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_clip_reframe_edits_reframe_id', 'clip_reframe_edits', ['clip_reframe_id'], unique=False)
    op.create_index('ix_clip_reframe_edits_user_id', 'clip_reframe_edits', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_table('clip_reframe_edits')
    op.drop_table('clip_reframes')
    op.drop_table('face_tracks')
    op.drop_table('video_analysis')
