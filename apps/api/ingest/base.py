"""Base ingestion agent types and LangGraph subgraph skeleton.

Each per-source agent instantiates this pattern:
  plan_pull → execute_pull → rule_prefilter → llm_relevance_score → route → store_telemetry
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RawItem(BaseModel):
    """A single raw item pulled from an external source."""

    source: str
    source_id: str | None = None
    url: str | None = None
    occurred_at: datetime
    raw_payload: dict[str, Any]
    content_hash: str | None = None


class ScoredItem(BaseModel):
    """A RawItem that has passed the rule-based pre-filter and been LLM-scored."""

    item: RawItem
    rule_score: float = 0.0
    llm_score: float | None = None
    llm_reasoning: str | None = None
    decision: str | None = None  # discard | review | classify | escalate


class IngestionState(BaseModel):
    """Typed state threaded through all ingestion agent nodes."""

    agent_name: str
    pull_window: tuple[datetime, datetime]
    raw_items: list[RawItem] = Field(default_factory=list)
    pre_filtered: list[RawItem] = Field(default_factory=list)
    llm_scored: list[ScoredItem] = Field(default_factory=list)
    escalated: list[ScoredItem] = Field(default_factory=list)
    discarded: list[ScoredItem] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    cost_usd: float = 0.0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    trace_id: str | None = None
