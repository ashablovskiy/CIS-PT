"""Add ant_state_json column to network_snapshot for Layer-2 state persistence.

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "b2c3d4e5f6a1"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "network_snapshot",
        sa.Column("ant_state_json", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("network_snapshot", "ant_state_json")
