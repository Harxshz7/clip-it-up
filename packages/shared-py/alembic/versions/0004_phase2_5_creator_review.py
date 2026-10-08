"""0004 phase2_5 creator review sessions, ratings, survey, and exports

Revision ID: 0004_phase2_5_creator_review
Revises: 0003_phase2_clips
Create Date: 2026-10-08 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0004_phase2_5_creator_review'
down_revision: str | None = '0003_phase2_clips'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create review_sessions table
    op.create_table(
        'review_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('video_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('token', sa.String(length=128), nullable=False),
        sa.Column('creator_name', sa.String(length=255), nullable=False),
        sa.Column('creator_email', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=32), server_default='open', nullable=False),  # open | submitted | closed
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token', name='uq_review_session_token'),
    )
    op.create_index('ix_review_sessions_token', 'review_sessions', ['token'], unique=True)
    op.create_index('ix_review_sessions_video_id', 'review_sessions', ['video_id'], unique=False)
    op.create_index('ix_review_sessions_status', 'review_sessions', ['status'], unique=False)
    op.create_index('ix_review_sessions_expires_at', 'review_sessions', ['expires_at'], unique=False)

    # 2. Create review_ratings table
    op.create_table(
        'review_ratings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clip_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('verdict', sa.String(length=32), nullable=False),  # post_as_is | post_with_edits | no
        sa.Column('reason_tag', sa.String(length=64), nullable=True),  # bad_start | bad_end | no_context | boring | off_topic | too_long | too_short | other
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('watch_ms', sa.BigInteger(), server_default=sa.text('0'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['review_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['clip_id'], ['clips.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id', 'clip_id', name='uq_review_rating_session_clip'),
    )
    op.create_index('ix_review_ratings_session_id', 'review_ratings', ['session_id'], unique=False)
    op.create_index('ix_review_ratings_clip_id', 'review_ratings', ['clip_id'], unique=False)

    # 3. Create review_survey table
    op.create_table(
        'review_survey',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('missing_text', sa.Text(), nullable=True),
        sa.Column('current_workflow_text', sa.Text(), nullable=True),
        sa.Column('current_cost_text', sa.Text(), nullable=True),
        sa.Column('price_open_inr', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('accepts_1500', sa.Boolean(), nullable=True),
        sa.Column('accepts_4000', sa.Boolean(), nullable=True),
        sa.Column('would_upload_next', sa.String(length=16), nullable=True),  # yes | maybe | no
        sa.Column('upload_timeframe', sa.String(length=64), nullable=True),
        sa.Column('email_optin', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['review_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id', name='uq_review_survey_session'),
    )
    op.create_index('ix_review_survey_session_id', 'review_survey', ['session_id'], unique=True)

    # 4. Create clip_review_exports table
    op.create_table(
        'clip_review_exports',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clip_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('storage_key', sa.String(length=1024), nullable=False),
        sa.Column('kind', sa.String(length=32), nullable=False),  # horizontal | vertical_center
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['clip_id'], ['clips.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('clip_id', 'kind', name='uq_clip_review_export_clip_kind'),
    )
    op.create_index('ix_clip_review_exports_clip_kind', 'clip_review_exports', ['clip_id', 'kind'], unique=True)


def downgrade() -> None:
    op.drop_table('clip_review_exports')
    op.drop_table('review_survey')
    op.drop_table('review_ratings')
    op.drop_table('review_sessions')
