"""alter_embedding_columns_to_vector

Revision ID: 8c9bc429e119
Revises: f4c2b9891464
Create Date: 2026-05-26 10:02:32.581128

Changes text → vector(1024) for:
  - classified_signals.embedding
  - contract_clauses.embedding

The initial migration created these as Text() as a placeholder.
Voyage AI is now configured (1024-dim voyage-3-large model).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = '8c9bc429e119'
down_revision: str = 'f4c2b9891464'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure vector extension is present (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.alter_column(
        'classified_signals', 'embedding',
        existing_type=sa.Text(),
        type_=Vector(1024),
        existing_nullable=True,
        postgresql_using="embedding::vector(1024)",
    )
    op.alter_column(
        'contract_clauses', 'embedding',
        existing_type=sa.Text(),
        type_=Vector(1024),
        existing_nullable=True,
        postgresql_using="embedding::vector(1024)",
    )


def downgrade() -> None:
    op.alter_column(
        'contract_clauses', 'embedding',
        existing_type=Vector(1024),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        'classified_signals', 'embedding',
        existing_type=Vector(1024),
        type_=sa.Text(),
        existing_nullable=True,
    )
