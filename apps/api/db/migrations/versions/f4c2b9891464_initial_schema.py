"""initial schema

Revision ID: f4c2b9891464
Revises:
Create Date: 2026-05-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f4c2b9891464"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── signals ───────────────────────────────────────────────────────────────
    op.create_table(
        "signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=True),
        sa.UniqueConstraint("source", "source_id", name="uq_signal_source_id"),
    )
    op.create_index("ix_signals_occurred_at", "signals", ["occurred_at"])
    op.create_index("ix_signals_content_hash", "signals", ["content_hash"])

    # ── signal_relevance ──────────────────────────────────────────────────────
    op.create_table(
        "signal_relevance",
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("signals.id"), primary_key=True),
        sa.Column("rule_score", sa.Float(), nullable=True),
        sa.Column("llm_score", sa.Float(), nullable=True),
        sa.Column("decision", sa.String(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("scored_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── classified_signals ────────────────────────────────────────────────────
    op.create_table(
        "classified_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("signals.id"), unique=True),
        sa.Column("event_class", sa.String(), nullable=True),
        sa.Column("geo_tags", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("graph_entities", postgresql.JSONB(), nullable=True),
        sa.Column("commodities", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("impact_dimensions", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("classifier_version", sa.String(), nullable=True),
        sa.Column("embedding", sa.Text(), nullable=True),   # stored as text until pgvector confirmed
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── contracts ─────────────────────────────────────────────────────────────
    op.create_table(
        "contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("external_id", sa.String(), unique=True, nullable=True),
        sa.Column("supplier_name", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("total_value_usd", sa.Numeric(), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
    )

    # ── contract_clauses ──────────────────────────────────────────────────────
    op.create_table(
        "contract_clauses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contracts.id")),
        sa.Column("clause_type", sa.String(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("references_commodities", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("parsed_params", postgresql.JSONB(), nullable=True),
        sa.Column("embedding", sa.Text(), nullable=True),
    )

    # ── assessments ───────────────────────────────────────────────────────────
    op.create_table(
        "assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("signals.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("agent_version", sa.String(), nullable=True),
        sa.Column("dspy_program_version", sa.String(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("affected_entities", postgresql.JSONB(), nullable=True),
        sa.Column("affected_clauses", postgresql.JSONB(), nullable=True),
        sa.Column("impact", postgresql.JSONB(), nullable=True),
        sa.Column("reasoning_chain", postgresql.JSONB(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(), server_default="pending"),
        sa.Column("raw_trace_id", sa.String(), nullable=True),
    )

    # ── daily_briefs ──────────────────────────────────────────────────────────
    op.create_table(
        "daily_briefs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brief_date", sa.Date(), unique=True, nullable=False),
        sa.Column("signal_count", sa.Integer(), nullable=True),
        sa.Column("themes", postgresql.JSONB(), nullable=True),
        sa.Column("body_markdown", sa.Text(), nullable=True),
        sa.Column("flagged_for_assessment", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("raw_trace_id", sa.String(), nullable=True),
    )

    # ── feedback ──────────────────────────────────────────────────────────────
    op.create_table(
        "feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assessments.id")),
        sa.Column("user_action", sa.String(), nullable=True),
        sa.Column("original_payload", postgresql.JSONB(), nullable=True),
        sa.Column("corrected_payload", postgresql.JSONB(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── dspy_training_examples ────────────────────────────────────────────────
    op.create_table(
        "dspy_training_examples",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("feedback_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("feedback.id")),
        sa.Column("inputs", postgresql.JSONB(), nullable=True),
        sa.Column("expected_outputs", postgresql.JSONB(), nullable=True),
        sa.Column("weight", sa.Float(), server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── dspy_programs ─────────────────────────────────────────────────────────
    op.create_table(
        "dspy_programs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("version", sa.String(), unique=True, nullable=False),
        sa.Column("serialized_program", postgresql.JSONB(), nullable=True),
        sa.Column("compile_metrics", postgresql.JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── agent_runs ────────────────────────────────────────────────────────────
    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_name", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("items_pulled", sa.Integer(), nullable=True),
        sa.Column("items_passed_rules", sa.Integer(), nullable=True),
        sa.Column("items_passed_llm", sa.Integer(), nullable=True),
        sa.Column("items_classified", sa.Integer(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("agent_runs")
    op.drop_table("dspy_programs")
    op.drop_table("dspy_training_examples")
    op.drop_table("feedback")
    op.drop_table("daily_briefs")
    op.drop_table("assessments")
    op.drop_table("contract_clauses")
    op.drop_table("contracts")
    op.drop_table("classified_signals")
    op.drop_table("signal_relevance")
    op.drop_table("signals")
