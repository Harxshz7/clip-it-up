"""0010 phase7b multi-person framing and screen content layouts

Revision ID: 0010_phase7b_layouts
Revises: 0009_phase7a_brand_and_variants
Create Date: 2026-10-26 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0010_phase7b_layouts"
down_revision: str | None = "0009_phase7a_brand_and_variants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add layout JSONB column to clip_reframes (nullable for lazy migration & v1 backwards compatibility)
    op.add_column(
        "clip_reframes",
        sa.Column("layout", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("clip_reframes", "layout")
