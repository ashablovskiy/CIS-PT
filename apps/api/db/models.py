"""SQLAlchemy ORM models — mirrors the schema in PROJECT_SPEC.md §7.2."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


# ── Signals ──────────────────────────────────────────────────────────────────

class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_signal_source_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    source: Mapped[str] = mapped_column(String, nullable=False)
    source_id: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    relevance: Mapped[SignalRelevance | None] = relationship(back_populates="signal", uselist=False)
    classified: Mapped[ClassifiedSignal | None] = relationship(
        back_populates="signal", uselist=False
    )
    assessments: Mapped[list[Assessment]] = relationship(back_populates="signal")


class SignalRelevance(Base):
    __tablename__ = "signal_relevance"

    signal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("signals.id"), primary_key=True
    )
    rule_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    llm_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # True analyst override; null until a user manually re-scores via the UI
    analyst_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Domain-specific mechanism (controlled vocab from relevance_scorer prompt)
    impact_type: Mapped[str | None] = mapped_column(String, nullable=True)
    # 1 = direct/high, 2 = moderate, 3 = peripheral, 4 = noise (null = legacy/unscored)
    impact_tier: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decision: Mapped[str | None] = mapped_column(String, nullable=True)  # discard|classify|escalate
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    signal: Mapped[Signal] = relationship(back_populates="relevance")


class ClassifiedSignal(Base):
    __tablename__ = "classified_signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    signal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("signals.id"), unique=True
    )
    event_class: Mapped[str | None] = mapped_column(String, nullable=True)
    geo_tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    graph_entities: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    commodities: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    impact_dimensions: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    classifier_version: Mapped[str | None] = mapped_column(String, nullable=True)
    embedding: Mapped[Any | None] = mapped_column(Vector(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    signal: Mapped[Signal] = relationship(back_populates="classified")


# ── Contracts ─────────────────────────────────────────────────────────────────

class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    external_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    supplier_name: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    start_date: Mapped[Any | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[Any | None] = mapped_column(Date, nullable=True)
    total_value_usd: Mapped[Any | None] = mapped_column(Numeric, nullable=True)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    clauses: Mapped[list[ContractClause]] = relationship(back_populates="contract")


class ContractClause(Base):
    __tablename__ = "contract_clauses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id")
    )
    # force_majeure | indexation | escalation | ld | slot | incoterms |
    # delivery_obligation | heavy_lift
    clause_type: Mapped[str | None] = mapped_column(String, nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    references_commodities: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    parsed_params: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    embedding: Mapped[Any | None] = mapped_column(Vector(1024), nullable=True)

    contract: Mapped[Contract] = relationship(back_populates="clauses")


# ── Assessments ───────────────────────────────────────────────────────────────

class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    signal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("signals.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    agent_version: Mapped[str | None] = mapped_column(String, nullable=True)
    dspy_program_version: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    affected_entities: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    affected_clauses: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    impact: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    reasoning_chain: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    raw_trace_id: Mapped[str | None] = mapped_column(String, nullable=True)

    signal: Mapped[Signal | None] = relationship(back_populates="assessments")
    feedback: Mapped[list[Feedback]] = relationship(back_populates="assessment")


# ── Daily Briefs ──────────────────────────────────────────────────────────────

class DailyBrief(Base):
    __tablename__ = "daily_briefs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    brief_date: Mapped[Any] = mapped_column(Date, unique=True, nullable=False)
    signal_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    themes: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    body_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    flagged_for_assessment: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )  # UUID[] stored as text[]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    raw_trace_id: Mapped[str | None] = mapped_column(String, nullable=True)


# ── Feedback & DSPy ───────────────────────────────────────────────────────────

class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessments.id")
    )
    user_action: Mapped[str | None] = mapped_column(String, nullable=True)  # accept|edit|reject
    original_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    corrected_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    assessment: Mapped[Assessment] = relationship(back_populates="feedback")
    training_example: Mapped[DspyTrainingExample | None] = relationship(
        back_populates="feedback", uselist=False
    )


class DspyTrainingExample(Base):
    __tablename__ = "dspy_training_examples"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    feedback_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("feedback.id")
    )
    inputs: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    expected_outputs: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    feedback: Mapped[Feedback] = relationship(back_populates="training_example")


class DspyProgram(Base):
    __tablename__ = "dspy_programs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    version: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    serialized_program: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    compile_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── Prompt Registry ───────────────────────────────────────────────────────────

class PromptTemplate(Base):
    """Versioned storage for all LLM system prompts.

    One row per (name, version). Only one version per name is active at a time.
    Consumers call registry.get_prompt(name) which serves the active version from cache.
    """
    __tablename__ = "prompt_templates"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_prompt_name_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    system_text: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_hint: Mapped[str | None] = mapped_column(String, nullable=True)  # e.g. "haiku" | "opus"
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[str] = mapped_column(String, default="seed", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── Network State Intelligence ────────────────────────────────────────────────

class SignalActorLink(Base):
    """Grounds a signal to a graph actor (Supplier, Commodity, Plant, …) with a
    quantified pressure contribution. One row per (signal, actor).

    Populated at ingest (direct matches from the scorer's graph-prior scan) and
    during assessment (expanded matches from the graph_retriever walk). This is
    the foundation of the Network State Engine: "how much pressure is on actor X."
    """
    __tablename__ = "signal_actor_link"
    __table_args__ = (
        UniqueConstraint("signal_id", "actor_name", name="uq_signal_actor"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    signal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("signals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    actor_label: Mapped[str | None] = mapped_column(String, nullable=True)  # Supplier|Commodity|…
    match_kind: Mapped[str] = mapped_column(String, nullable=False)  # direct | expanded
    # Pressure this signal injects into the actor: effective_score × tier_weight × match_factor
    pressure: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class NetworkSnapshot(Base):
    """A point-in-time estimate of the industrial network's condition.

    Computed every ~6h (and on demand) by the Network State Engine. The sequence
    of snapshots is the state-estimation time series (and the future observation
    series for an HMM forecasting layer).
    """
    __tablename__ = "network_snapshot"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    health_index: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0–1 fragility
    health_label: Mapped[str | None] = mapped_column(String, nullable=True)  # resilient|constrained|fragile
    top_actors_json: Mapped[Any | None] = mapped_column(JSONB, nullable=True)   # influence leaderboard
    hotspots_json: Mapped[Any | None] = mapped_column(JSONB, nullable=True)     # pressure hotspots
    bottlenecks_json: Mapped[Any | None] = mapped_column(JSONB, nullable=True)  # emerging bottlenecks
    signal_window_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    signal_count: Mapped[int | None] = mapped_column(Integer, nullable=True)


# ── Agent telemetry ───────────────────────────────────────────────────────────

class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    agent_name: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)  # ok|error|budget_exceeded
    items_pulled: Mapped[int | None] = mapped_column(Integer, nullable=True)
    items_passed_rules: Mapped[int | None] = mapped_column(Integer, nullable=True)
    items_passed_llm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    items_classified: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Any | None] = mapped_column(Numeric, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String, nullable=True)
