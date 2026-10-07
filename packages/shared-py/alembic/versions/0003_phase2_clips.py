"""0003 phase2 clips, moments, scoring_runs, feedback, audio_features, and eval tables

Revision ID: 0003_phase2_clips
Revises: 0002_phase1_transcripts
Create Date: 2026-10-07 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0003_phase2_clips'
down_revision: str | None = '0002_phase1_transcripts'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create clip_moments table
    op.create_table(
        'clip_moments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('video_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('transcript_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('start_ms', sa.BigInteger(), nullable=False),
        sa.Column('end_ms', sa.BigInteger(), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=True),
        sa.Column('final_score', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=32), server_default='candidate', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['transcript_id'], ['transcripts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_clip_moments_video_status', 'clip_moments', ['video_id', 'status'], unique=False)
    op.create_index('ix_clip_moments_video_score', 'clip_moments', ['video_id', 'final_score'], unique=False)
    op.create_index('ix_clip_moments_video_rank', 'clip_moments', ['video_id', 'rank'], unique=False)

    # 2. Create scoring_runs table
    op.create_table(
        'scoring_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('video_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('prompt_version', sa.String(length=64), nullable=False),
        sa.Column('scorer_version', sa.String(length=64), nullable=False),
        sa.Column('weights', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('model', sa.String(length=64), nullable=False),
        sa.Column('input_tokens', sa.BigInteger(), server_default=sa.text('0'), nullable=False),
        sa.Column('output_tokens', sa.BigInteger(), server_default=sa.text('0'), nullable=False),
        sa.Column('cost_inr', sa.Numeric(precision=12, scale=4), server_default=sa.text('0.0000'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scoring_runs_video_created', 'scoring_runs', ['video_id', 'created_at'], unique=False)

    # 3. Create clips table
    op.create_table(
        'clips',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('moment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('video_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scoring_run_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('variant_length_s', sa.String(length=16), server_default='auto', nullable=False),
        sa.Column('start_ms', sa.BigInteger(), nullable=False),
        sa.Column('end_ms', sa.BigInteger(), nullable=False),
        sa.Column('hook_text', sa.Text(), nullable=False),
        sa.Column('title', sa.String(length=512), nullable=False),
        sa.Column('final_score', sa.Float(), nullable=False),
        sa.Column('score_breakdown', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('model', sa.String(length=64), nullable=False),
        sa.Column('prompt_version', sa.String(length=64), nullable=False),
        sa.Column('scorer_version', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['moment_id'], ['clip_moments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['scoring_run_id'], ['scoring_runs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_clips_video_score', 'clips', ['video_id', 'final_score'], unique=False)
    op.create_index('ix_clips_moment_variant', 'clips', ['moment_id', 'variant_length_s'], unique=False)
    op.create_index('ix_clips_created_at', 'clips', ['created_at'], unique=False)

    # 4. Create clip_feedback table
    op.create_table(
        'clip_feedback',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clip_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('value', sa.String(length=16), nullable=False),
        sa.Column('reason_tag', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['clip_id'], ['clips.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('clip_id', 'user_id', name='uq_clip_feedback_clip_user')
    )
    op.create_index('ix_clip_feedback_clip_id', 'clip_feedback', ['clip_id'], unique=False)
    op.create_index('ix_clip_feedback_user_id', 'clip_feedback', ['user_id'], unique=False)

    # 5. Create audio_features table
    op.create_table(
        'audio_features',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('video_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version', sa.String(length=32), server_default='v1', nullable=False),
        sa.Column('frames_key', sa.String(length=1024), nullable=False),
        sa.Column('summary', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('video_id', 'version', name='uq_audio_features_video_version')
    )
    op.create_index('ix_audio_features_video_version', 'audio_features', ['video_id', 'version'], unique=False)

    # 6. Create eval_videos table
    op.create_table(
        'eval_videos',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('slug', sa.String(length=128), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('source_url', sa.String(length=1024), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_index('ix_eval_videos_slug', 'eval_videos', ['slug'], unique=True)

    # 7. Create eval_clip_ratings table
    op.create_table(
        'eval_clip_ratings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('video_slug', sa.String(length=128), nullable=False),
        sa.Column('start_ms', sa.BigInteger(), nullable=False),
        sa.Column('end_ms', sa.BigInteger(), nullable=False),
        sa.Column('clip_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('rater_id', sa.String(length=64), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('video_slug', 'start_ms', 'end_ms', 'rater_id', name='uq_eval_clip_rating_range_rater')
    )
    op.create_index('ix_eval_ratings_slug_time', 'eval_clip_ratings', ['video_slug', 'start_ms', 'end_ms'], unique=False)


def downgrade() -> None:
    op.drop_table('eval_clip_ratings')
    op.drop_table('eval_videos')
    op.drop_table('audio_features')
    op.drop_table('clip_feedback')
    op.drop_table('clips')
    op.drop_table('scoring_runs')
    op.drop_table('clip_moments')
