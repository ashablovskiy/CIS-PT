"""signal_relevance: add analyst_score, impact_type, impact_tier

Adds proper analyst-override and per-signal impact categorisation columns
to signal_relevance so we can:

  - Distinguish analyst overrides from the rule-filter score (rule_score
    was being mis-used in the UI as if it were an analyst signal).
  - Store a domain-specific impact_type per signal (mechanism on the
    transformer supply chain, e.g. "GOES input cost ↑") instead of
    deriving a generic label from the agent source.
  - Tier signals 1 (high) → 4 (noise) so the UI can hide low-impact
    items by default.

Revision ID: 62150047f085
Revises: 5d22c99a5782
Create Date: 2026-05-26 18:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "62150047f085"
down_revision: Union[str, None] = "5d22c99a5782"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("signal_relevance", sa.Column("analyst_score", sa.Float(), nullable=True))
    op.add_column("signal_relevance", sa.Column("impact_type",   sa.String(), nullable=True))
    op.add_column("signal_relevance", sa.Column("impact_tier",   sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("signal_relevance", "impact_tier")
    op.drop_column("signal_relevance", "impact_type")
    op.drop_column("signal_relevance", "analyst_score")
