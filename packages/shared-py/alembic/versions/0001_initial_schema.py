"""0001 initial schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clerk_user_id', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('clerk_user_id')
    )
    op.create_index('ix_users_clerk_user_id', 'users', ['clerk_user_id'], unique=True)
    op.create_index('ix_users_email', 'users', ['email'], unique=False)
    op.create_index('ix_users_created_at', 'users', ['created_at'], unique=False)

    # 2. projects
    op.create_table(
        'projects',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_projects_user_id', 'projects', ['user_id'], unique=False)
    op.create_index('ix_projects_user_created_at', 'projects', ['user_id', 'created_at'], unique=False)

    # 3. videos
    op.create_table(
        'videos',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('original_filename', sa.String(length=512), nullable=False),
        sa.Column('storage_key', sa.String(length=1024), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('content_type', sa.String(length=128), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_videos_project_id', 'videos', ['project_id'], unique=False)
    op.create_index('ix_videos_user_id', 'videos', ['user_id'], unique=False)
    op.create_index('ix_videos_user_created_at', 'videos', ['user_id', 'created_at'], unique=False)
    op.create_index('ix_videos_status', 'videos', ['status'], unique=False)

    # 4. jobs
    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('video_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('current_stage', sa.String(length=64), nullable=True),
        sa.Column('progress', sa.BigInteger(), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_jobs_video_id', 'jobs', ['video_id'], unique=False)
    op.create_index('ix_jobs_user_id', 'jobs', ['user_id'], unique=False)
    op.create_index('ix_jobs_user_created_at', 'jobs', ['user_id', 'created_at'], unique=False)
    op.create_index('ix_jobs_status', 'jobs', ['status'], unique=False)

    # 5. job_stages
    op.create_table(
        'job_stages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('progress', sa.BigInteger(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.BigInteger(), nullable=True),
        sa.Column('cost_inr', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id', 'name', name='uq_job_stage_job_id_name')
    )
    op.create_index('ix_job_stages_job_id', 'job_stages', ['job_id'], unique=False)
    op.create_index('ix_job_stages_job_id_name', 'job_stages', ['job_id', 'name'], unique=False)

    # 6. usage
    op.create_table(
        'usage',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('video_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('metric', sa.String(length=64), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column('cost_inr', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id', 'metric', name='uq_usage_job_id_metric')
    )
    op.create_index('ix_usage_job_id', 'usage', ['job_id'], unique=False)
    op.create_index('ix_usage_user_id', 'usage', ['user_id'], unique=False)
    op.create_index('ix_usage_video_id', 'usage', ['video_id'], unique=False)
    op.create_index('ix_usage_user_created_at', 'usage', ['user_id', 'created_at'], unique=False)
    op.create_index('ix_usage_metric', 'usage', ['metric'], unique=False)


def downgrade() -> None:
    op.drop_table('usage')
    op.drop_table('job_stages')
    op.drop_table('jobs')
    op.drop_table('videos')
    op.drop_table('projects')
    op.drop_table('users')
