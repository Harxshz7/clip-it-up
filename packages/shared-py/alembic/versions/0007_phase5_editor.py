"""0007 phase5 editor state, alternatives, and instrumentation events

Revision ID: 0007_phase5_editor
Revises: 0006_phase4_export_render
Create Date: 2026-10-11 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0007_phase5_editor'
down_revision: str | None = '0006_phase4_export_render'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. clip_edits table
    op.create_table(
        'clip_edits',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clip_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('doc', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('parent_version', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=True),
        sa.Column('is_checkpoint', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.ForeignKeyConstraint(['clip_id'], ['clips.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('clip_id', 'version', name='uq_clip_edits_clip_version'),
    )
    op.create_index('ix_clip_edits_clip_version', 'clip_edits', ['clip_id', 'version'], unique=False)
    op.create_index('ix_clip_edits_clip_created', 'clip_edits', ['clip_id', 'created_at'], unique=False)

    # 2. clip_alternatives table
    op.create_table(
        'clip_alternatives',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clip_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('kind', sa.String(length=32), nullable=False),
        sa.Column('start_ms', sa.BigInteger(), nullable=False),
        sa.Column('end_ms', sa.BigInteger(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['clip_id'], ['clips.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_clip_alternatives_clip_kind', 'clip_alternatives', ['clip_id', 'kind'], unique=False)
    op.create_index('ix_clip_alternatives_created_at', 'clip_alternatives', ['created_at'], unique=False)

    # 3. editor_events table
    op.create_table(
        'editor_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clip_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('session_id', sa.String(length=128), nullable=False),
        sa.Column('type', sa.String(length=64), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['clip_id'], ['clips.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_editor_events_user_created', 'editor_events', ['user_id', 'created_at'], unique=False)
    op.create_index('ix_editor_events_session', 'editor_events', ['session_id'], unique=False)
    op.create_index('ix_editor_events_type', 'editor_events', ['type'], unique=False)


def downgrade() -> None:
    op.drop_table('editor_events')
    op.drop_table('clip_alternatives')
    op.drop_table('clip_edits')
