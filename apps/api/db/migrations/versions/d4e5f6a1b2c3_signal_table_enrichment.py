"""Signal table enrichment: new scorer + triage output columns.

signal_relevance:
  + mechanism      TEXT   — short causal sentence from relevance scorer
  + signal_kind    VARCHAR(50) — event type category from scorer
  + what_changed   TEXT   — one-sentence factual description from scorer

classified_signals:
  + triage_reasoning          TEXT   — triage classifier reasoning
  + secondary_event_classes   TEXT[] — up to 2 additional event class labels
  + state_change              JSONB  — {what, direction, magnitude} from triage

Revision ID: d4e5f6a1b2c3
Revises: c3d4e5f6a1b2
Create Date: 2026-06-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision = "d4e5f6a1b2c3"
down_revision = "c3d4e5f6a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── signal_relevance additions ────────────────────────────────────────────
    op.add_column("signal_relevance", sa.Column("mechanism",    sa.Text(),          nullable=True))
    op.add_column("signal_relevance", sa.Column("signal_kind",  sa.String(50),      nullable=True))
    op.add_column("signal_relevance", sa.Column("what_changed", sa.Text(),          nullable=True))

    # ── classified_signals additions ──────────────────────────────────────────
    op.add_column("classified_signals", sa.Column("triage_reasoning",        sa.Text(),          nullable=True))
    op.add_column("classified_signals", sa.Column("secondary_event_classes", ARRAY(sa.String()), nullable=True))
    op.add_column("classified_signals", sa.Column("state_change",            JSONB(),            nullable=True))


def downgrade() -> None:
    op.drop_column("classified_signals", "state_change")
    op.drop_column("classified_signals", "secondary_event_classes")
    op.drop_column("classified_signals", "triage_reasoning")
    op.drop_column("signal_relevance", "what_changed")
    op.drop_column("signal_relevance", "signal_kind")
    op.drop_column("signal_relevance", "mechanism")
