"""0006 phase4 captions, cleanups, export presets, plans, and final exports

Revision ID: 0006_phase4_export_render
Revises: 0005_phase3_reframing
Create Date: 2026-10-10 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0006_phase4_export_render'
down_revision: str | None = '0005_phase3_reframing'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. caption_styles table
    op.create_table(
        'caption_styles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('version', sa.String(length=32), server_default='v1', nullable=False),
        sa.Column('spec', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_builtin', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key', name='uq_caption_styles_key'),
    )
    op.create_index('ix_caption_styles_key', 'caption_styles', ['key'], unique=True)

    # 2. export_presets table
    op.create_table(
        'export_presets',
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('width', sa.Integer(), server_default='1080', nullable=False),
        sa.Column('height', sa.Integer(), server_default='1920', nullable=False),
        sa.Column('fps', sa.Float(), server_default='30.0', nullable=False),
        sa.Column('max_duration_s', sa.Integer(), server_default='60', nullable=False),
        sa.Column('video_bitrate', sa.String(length=32), server_default='8000k', nullable=False),
        sa.Column('crf', sa.Integer(), server_default='22', nullable=False),
        sa.Column('audio_bitrate', sa.String(length=32), server_default='192k', nullable=False),
        sa.Column('loudness_lufs', sa.Float(), server_default='-14.0', nullable=False),
        sa.Column('safe_zone', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('key'),
    )

    # 3. plans table
    op.create_table(
        'plans',
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('monthly_minutes', sa.Integer(), server_default='30', nullable=False),
        sa.Column('export_watermark', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('max_export_height', sa.Integer(), server_default='1920', nullable=False),
        sa.Column('max_exports_per_month', sa.Integer(), server_default='10', nullable=False),
        sa.Column('features', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('key'),
    )

    # 4. user_plans table
    op.create_table(
        'user_plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plan_key', sa.String(length=64), nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['plan_key'], ['plans.key'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_user_plans_user_id'),
    )
    op.create_index('ix_user_plans_user_id', 'user_plans', ['user_id'], unique=True)

    # 5. clip_captions table
    op.create_table(
        'clip_captions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clip_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version', sa.String(length=32), server_default='v1', nullable=False),
        sa.Column('language', sa.String(length=16), server_default='en', nullable=False),
        sa.Column('words', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('style_key', sa.String(length=64), server_default='bold_pop', nullable=False),
        sa.Column('style_overrides', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('source', sa.String(length=32), server_default='auto', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['clip_id'], ['clips.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('clip_id', 'version', 'source', name='uq_clip_captions_clip_version_source'),
    )
    op.create_index('ix_clip_captions_clip_id', 'clip_captions', ['clip_id'], unique=False)
    op.create_index('ix_clip_captions_style_key', 'clip_captions', ['style_key'], unique=False)

    # 6. clip_cleanups table
    op.create_table(
        'clip_cleanups',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clip_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version', sa.String(length=32), server_default='v1', nullable=False),
        sa.Column('options', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('removals', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['clip_id'], ['clips.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('clip_id', 'version', name='uq_clip_cleanups_clip_version'),
    )
    op.create_index('ix_clip_cleanups_clip_id', 'clip_cleanups', ['clip_id'], unique=False)

    # 7. exports table
    op.create_table(
        'exports',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clip_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='queued', nullable=False),
        sa.Column('preset_key', sa.String(length=64), nullable=False),
        sa.Column('params_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('storage_key', sa.String(length=1024), nullable=True),
        sa.Column('duration_ms', sa.BigInteger(), nullable=True),
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('render_ms', sa.BigInteger(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['clip_id'], ['clips.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_exports_clip_id', 'exports', ['clip_id'], unique=False)
    op.create_index('ix_exports_user_id', 'exports', ['user_id'], unique=False)
    op.create_index('ix_exports_status', 'exports', ['status'], unique=False)
    op.create_index('ix_exports_created_at', 'exports', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('exports')
    op.drop_table('clip_cleanups')
    op.drop_table('clip_captions')
    op.drop_table('user_plans')
    op.drop_table('plans')
    op.drop_table('export_presets')
    op.drop_table('caption_styles')
