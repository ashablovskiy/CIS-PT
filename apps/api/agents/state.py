"""Typed state for the LangGraph impact assessment pipeline."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ReasoningStep(BaseModel):
    step: int
    claim: str
    grounded_in: dict[str, Any]  # {signal_id, source_url} or {node_id, node_type}
    inference: str


class AssessmentState(BaseModel):
    """State threaded through all 7 nodes of the assessment pipeline."""

    signal_id: UUID
    signal_payload: dict[str, Any]

    # Populated by each node
    triage_passed: bool = False
    graph_context: list[dict[str, Any]] = Field(default_factory=list)
    similar_past: list[dict[str, Any]] = Field(default_factory=list)
    contract_matches: list[dict[str, Any]] = Field(default_factory=list)

    # Synthesizer output
    summary: str = ""
    affected_entities: dict[str, Any] = Field(default_factory=dict)
    affected_clauses: list[dict[str, Any]] = Field(default_factory=list)
    impact_by_dimension: dict[str, Any] = Field(default_factory=dict)
    reasoning_chain: list[ReasoningStep] = Field(default_factory=list)
    confidence: float = 0.0

    # Critic
    critic_passed: bool = False
    critic_notes: str = ""

    # Meta
    agent_version: str = "0.1.0"
    dspy_program_version: str = "v0"
    trace_id: str | None = None
    errors: list[str] = Field(default_factory=list)
