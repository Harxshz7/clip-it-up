"""0002 phase1 transcripts and video fields

Revision ID: 0002_phase1_transcripts
Revises: 0001_initial_schema
Create Date: 2026-10-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0002_phase1_transcripts'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update videos table
    op.add_column('videos', sa.Column('width', sa.Integer(), nullable=True))
    op.add_column('videos', sa.Column('height', sa.Integer(), nullable=True))
    op.add_column('videos', sa.Column('fps', sa.Float(), nullable=True))
    op.add_column('videos', sa.Column('has_audio', sa.Boolean(), server_default=sa.text('true'), nullable=False))
    op.add_column('videos', sa.Column('proxy_key', sa.String(length=1024), nullable=True))
    op.add_column('videos', sa.Column('audio_key', sa.String(length=1024), nullable=True))

    # 2. Update jobs table
    op.add_column('jobs', sa.Column('partial_results', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))

    # 3. Create transcripts table
    op.create_table(
        'transcripts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('video_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('language', sa.String(length=16), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('model', sa.String(length=64), nullable=True),
        sa.Column('backend', sa.String(length=32), nullable=True),
        sa.Column('word_count', sa.BigInteger(), server_default=sa.text('0'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('video_id')
    )
    op.create_index('ix_transcripts_video_id', 'transcripts', ['video_id'], unique=True)
    op.create_index('ix_transcripts_status', 'transcripts', ['status'], unique=False)

    # 4. Create transcript_words table
    op.create_table(
        'transcript_words',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('transcript_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('idx', sa.BigInteger(), nullable=False),
        sa.Column('word', sa.String(length=255), nullable=False),
        sa.Column('start_ms', sa.BigInteger(), nullable=False),
        sa.Column('end_ms', sa.BigInteger(), nullable=False),
        sa.Column('speaker', sa.String(length=64), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['transcript_id'], ['transcripts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_transcript_words_t_idx', 'transcript_words', ['transcript_id', 'idx'], unique=False)
    op.create_index('ix_transcript_words_t_time', 'transcript_words', ['transcript_id', 'start_ms', 'end_ms'], unique=False)

    # 5. Create transcript_segments table
    op.create_table(
        'transcript_segments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('transcript_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('idx', sa.BigInteger(), nullable=False),
        sa.Column('start_ms', sa.BigInteger(), nullable=False),
        sa.Column('end_ms', sa.BigInteger(), nullable=False),
        sa.Column('speaker', sa.String(length=64), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['transcript_id'], ['transcripts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_transcript_segments_t_idx', 'transcript_segments', ['transcript_id', 'idx'], unique=False)
    op.create_index('ix_transcript_segments_t_time', 'transcript_segments', ['transcript_id', 'start_ms', 'end_ms'], unique=False)

    # 6. Create speakers table
    op.create_table(
        'speakers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('transcript_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('label', sa.String(length=64), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['transcript_id'], ['transcripts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('transcript_id', 'label', name='uq_speaker_transcript_label')
    )
    op.create_index('ix_speakers_transcript_label', 'speakers', ['transcript_id', 'label'], unique=False)


def downgrade() -> None:
    op.drop_table('speakers')
    op.drop_table('transcript_segments')
    op.drop_table('transcript_words')
    op.drop_table('transcripts')
    op.drop_column('jobs', 'partial_results')
    op.drop_column('videos', 'audio_key')
    op.drop_column('videos', 'proxy_key')
    op.drop_column('videos', 'has_audio')
    op.drop_column('videos', 'fps')
    op.drop_column('videos', 'height')
    op.drop_column('videos', 'width')
