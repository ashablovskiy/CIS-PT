"""network state intelligence: signal_actor_link + network_snapshot

Revision ID: a1b2c3d4e5f6
Revises: 62150047f085
Create Date: 2026-05-29

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "a1b2c3d4e5f6"
down_revision = "62150047f085"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_actor_link",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("signal_id", UUID(as_uuid=True),
                  sa.ForeignKey("signals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_name", sa.String(), nullable=False),
        sa.Column("actor_label", sa.String(), nullable=True),
        sa.Column("match_kind", sa.String(), nullable=False),
        sa.Column("pressure", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("signal_id", "actor_name", name="uq_signal_actor"),
    )
    op.create_index("ix_signal_actor_link_signal_id", "signal_actor_link", ["signal_id"])
    op.create_index("ix_signal_actor_link_actor_name", "signal_actor_link", ["actor_name"])

    op.create_table(
        "network_snapshot",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("health_index", sa.Float(), nullable=True),
        sa.Column("health_label", sa.String(), nullable=True),
        sa.Column("top_actors_json", JSONB, nullable=True),
        sa.Column("hotspots_json", JSONB, nullable=True),
        sa.Column("bottlenecks_json", JSONB, nullable=True),
        sa.Column("signal_window_hours", sa.Integer(), nullable=True),
        sa.Column("signal_count", sa.Integer(), nullable=True),
    )
    op.create_index("ix_network_snapshot_computed_at", "network_snapshot", ["computed_at"])


def downgrade() -> None:
    op.drop_index("ix_network_snapshot_computed_at", table_name="network_snapshot")
    op.drop_table("network_snapshot")
    op.drop_index("ix_signal_actor_link_actor_name", table_name="signal_actor_link")
    op.drop_index("ix_signal_actor_link_signal_id", table_name="signal_actor_link")
    op.drop_table("signal_actor_link")
