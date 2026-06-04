"""Add event clustering: embedding + event_id on signals table.

Each signal gets a 1024-dim embedding at ingest time so semantically similar
signals from different sources can be grouped into one "event cluster". The
event_id column is a self-referencing FK pointing to the canonical (first-seen)
signal for a given real-world event.

ANT pressure computation groups signals by event_id and takes the MAX per
cluster instead of summing, preventing N news sources covering the same event
from inflating ANT node pressure N-fold.

Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
Create Date: 2026-06-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import UUID

revision = "c3d4e5f6a1b2"
down_revision = "b2c3d4e5f6a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent — vector extension is already present from earlier migration
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 1. Ingest-time embedding for event-cluster lookups (1024-dim, same as
    #    classified_signals.embedding but computed earlier in the pipeline).
    op.add_column(
        "signals",
        sa.Column("embedding", Vector(1024), nullable=True),
    )

    # 2. event_id: self-referencing FK to the canonical signal for this event
    #    cluster.  NULL  = legacy row or singleton (not yet clustered).
    #    event_id = id   = this signal IS the canonical event.
    #    event_id = X    = another signal with id=X is the canonical event.
    op.add_column(
        "signals",
        sa.Column("event_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_signal_event_id",
        "signals",
        "signals",
        ["event_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_signals_event_id", "signals", ["event_id"])

    # 3. HNSW index for fast approximate cosine search.
    #    Performs well across all table sizes (no minimum-rows requirement).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_signals_embedding_hnsw "
        "ON signals USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_signals_embedding_hnsw")
    op.drop_index("ix_signals_event_id", table_name="signals")
    op.drop_constraint("fk_signal_event_id", "signals", type_="foreignkey")
    op.drop_column("signals", "event_id")
    op.drop_column("signals", "embedding")
