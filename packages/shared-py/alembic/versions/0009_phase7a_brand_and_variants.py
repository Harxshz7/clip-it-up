"""0009 phase7a brand kit and auto-variants

Revision ID: 0009_phase7a_brand_and_variants
Revises: 0008_phase6_billing_and_ops
Create Date: 2026-10-14 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0009_phase7a_brand_and_variants'
down_revision: str | None = '0008_phase6_billing_and_ops'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. brand_assets
    op.create_table(
        'brand_assets',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('kind', sa.String(length=32), nullable=False),
        sa.Column('storage_key', sa.String(length=1024), nullable=False),
        sa.Column('filename', sa.String(length=512), nullable=False),
        sa.Column('content_type', sa.String(length=128), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=32), server_default='processing', nullable=False),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_brand_assets_user_id', 'brand_assets', ['user_id'])
    op.create_index('ix_brand_assets_kind', 'brand_assets', ['kind'])
    op.create_index('ix_brand_assets_status', 'brand_assets', ['status'])
    op.create_index('ix_brand_assets_user_kind', 'brand_assets', ['user_id', 'kind'])
    op.create_index('ix_brand_assets_created_at', 'brand_assets', ['created_at'])

    # 2. brand_kits
    op.create_table(
        'brand_kits',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('colors', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('fonts', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('logo_asset_id', sa.Uuid(), nullable=True),
        sa.Column('logo_position', sa.String(length=32), server_default='top_right', nullable=False),
        sa.Column('logo_opacity', sa.Float(), server_default='1.0', nullable=False),
        sa.Column('logo_scale', sa.Float(), server_default='0.15', nullable=False),
        sa.Column('caption_style_key', sa.String(length=64), nullable=True),
        sa.Column('caption_overrides', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('intro_asset_id', sa.Uuid(), nullable=True),
        sa.Column('outro_asset_id', sa.Uuid(), nullable=True),
        sa.Column('watermark_free_override', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['logo_asset_id'], ['brand_assets.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['intro_asset_id'], ['brand_assets.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['outro_asset_id'], ['brand_assets.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_brand_kits_user_id', 'brand_kits', ['user_id'])
    op.create_index('ix_brand_kits_user_default', 'brand_kits', ['user_id', 'is_default'])
    op.create_index('ix_brand_kits_created_at', 'brand_kits', ['created_at'])

    # 3. variant_sets
    op.create_table(
        'variant_sets',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('clip_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='ready', nullable=False),
        sa.Column('dimensions', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('requested_count', sa.Integer(), server_default='4', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['clip_id'], ['clips.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_variant_sets_clip_id', 'variant_sets', ['clip_id'])
    op.create_index('ix_variant_sets_user_id', 'variant_sets', ['user_id'])
    op.create_index('ix_variant_sets_clip_created', 'variant_sets', ['clip_id', 'created_at'])

    # 4. clip_variants
    op.create_table(
        'clip_variants',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('set_id', sa.Uuid(), nullable=False),
        sa.Column('edit_doc', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('label', sa.String(length=128), nullable=False),
        sa.Column('hook_text', sa.Text(), nullable=True),
        sa.Column('caption_style_key', sa.String(length=64), nullable=True),
        sa.Column('cta_text', sa.String(length=512), nullable=True),
        sa.Column('cta_style', sa.String(length=64), nullable=True),
        sa.Column('score_hint', sa.Float(), nullable=True),
        sa.Column('export_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['set_id'], ['variant_sets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['export_id'], ['exports.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_clip_variants_set_id', 'clip_variants', ['set_id'])
    op.create_index('ix_clip_variants_created_at', 'clip_variants', ['created_at'])

    # 5. Alter exports
    op.add_column('exports', sa.Column('variant_id', sa.Uuid(), nullable=True))
    op.add_column('exports', sa.Column('external_post_url', sa.String(length=1024), nullable=True))
    op.add_column('exports', sa.Column('performance_metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_foreign_key('fk_exports_variant_id', 'exports', 'clip_variants', ['variant_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_exports_variant_id', 'exports', ['variant_id'])


def downgrade() -> None:
    op.drop_constraint('fk_exports_variant_id', 'exports', type_='foreignkey')
    op.drop_index('ix_exports_variant_id', table_name='exports')
    op.drop_column('exports', 'performance_metrics')
    op.drop_column('exports', 'external_post_url')
    op.drop_column('exports', 'variant_id')

    op.drop_index('ix_clip_variants_created_at', table_name='clip_variants')
    op.drop_index('ix_clip_variants_set_id', table_name='clip_variants')
    op.drop_table('clip_variants')

    op.drop_index('ix_variant_sets_clip_created', table_name='variant_sets')
    op.drop_index('ix_variant_sets_user_id', table_name='variant_sets')
    op.drop_index('ix_variant_sets_clip_id', table_name='variant_sets')
    op.drop_table('variant_sets')

    op.drop_index('ix_brand_kits_created_at', table_name='brand_kits')
    op.drop_index('ix_brand_kits_user_default', table_name='brand_kits')
    op.drop_index('ix_brand_kits_user_id', table_name='brand_kits')
    op.drop_table('brand_kits')

    op.drop_index('ix_brand_assets_created_at', table_name='brand_assets')
    op.drop_index('ix_brand_assets_user_kind', table_name='brand_assets')
    op.drop_index('ix_brand_assets_status', table_name='brand_assets')
    op.drop_index('ix_brand_assets_kind', table_name='brand_assets')
    op.drop_index('ix_brand_assets_user_id', table_name='brand_assets')
    op.drop_table('brand_assets')
