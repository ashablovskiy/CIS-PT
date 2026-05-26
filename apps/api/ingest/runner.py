"""Base ingestion agent — LangGraph subgraph, telemetry, LLM relevance scoring.

Every per-source agent subclasses BaseIngestionAgent and implements:
  - pull(window) → list[RawItem]
  - keyword_rules() → list[str]   (lowercase keywords for rule-based pre-filter)

The pipeline:
  execute_pull → rule_prefilter → llm_relevance_score → route → store_telemetry
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import textwrap
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tenacity import retry, stop_after_attempt, wait_exponential

from apps.api.budget import BudgetExceededError, budgeted_client
from apps.api.db.models import AgentRun, Signal, SignalRelevance
from apps.api.ingest.base import IngestionState, RawItem, ScoredItem
from apps.api.prompts.registry import registry as _prompt_registry
from apps.api.settings import settings

logger = logging.getLogger(__name__)

# Haiku model used for all relevance scoring.
_HAIKU = "claude-haiku-4-5-20251001"

# Routing thresholds (spec §8.3)
_ESCALATE_THRESHOLD = 0.6
_REVIEW_THRESHOLD = 0.3


def _content_hash(payload: dict[str, Any]) -> str:
    """Stable SHA-256 of the JSON-serialized payload for cross-source dedup."""
    serialized = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(serialized).hexdigest()[:32]


def _make_asyncpg_engine(url: str):
    """Create an async engine stripping sslmode (psycopg2-style) and passing ssl=True to asyncpg."""
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    ssl_mode = (params.pop("sslmode", ["disable"])[0]).lower()
    new_query = urlencode({k: v[0] for k, v in params.items()})
    clean_url = urlunparse(parsed._replace(query=new_query))
    connect_args = {"ssl": True} if ssl_mode in ("require", "verify-ca", "verify-full") else {}
    return create_async_engine(clean_url, pool_pre_ping=True, connect_args=connect_args)


def _make_engine():
    return _make_asyncpg_engine(settings.database_url)


class BaseIngestionAgent(ABC):
    """Abstract base for all per-source ingestion agents."""

    agent_name: str = "base"

    def __init__(self) -> None:
        self._engine = _make_engine()
        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    # ── Subclass interface ────────────────────────────────────────────────────

    @abstractmethod
    async def pull(self, window: tuple[datetime, datetime]) -> list[RawItem]:
        """Pull raw items from the source for the given time window."""

    @abstractmethod
    def keyword_rules(self) -> list[str]:
        """Lowercase keywords; a hit on ANY of them keeps the item in stage-1."""

    def default_lookback_hours(self) -> int:
        """How many hours back to pull on a default run."""
        return 2

    # ── Main entry point ──────────────────────────────────────────────────────

    async def run(self, lookback_hours: int | None = None) -> IngestionState:
        """Execute the full ingestion pipeline and return the final state."""
        now = datetime.now(UTC)
        hours = lookback_hours or self.default_lookback_hours()
        window = (now - timedelta(hours=hours), now)

        state = IngestionState(
            agent_name=self.agent_name,
            pull_window=window,
            started_at=now,
            trace_id=str(uuid4()),
        )
        logger.info("[%s] Starting run | window=%dh | trace=%s", self.agent_name, hours, state.trace_id)

        try:
            state = await self._execute_pull(state)
            state = await self._rule_prefilter(state)
            state = await self._llm_relevance_score(state)
            state = await self._route_and_persist(state)
        except BudgetExceededError as exc:
            state.errors.append(f"budget_exceeded: {exc}")
            logger.warning("[%s] %s", self.agent_name, exc)
        except Exception as exc:
            state.errors.append(str(exc))
            logger.exception("[%s] Unhandled error", self.agent_name)
        finally:
            state.finished_at = datetime.now(UTC)
            await self._store_telemetry(state)

        logger.info(
            "[%s] Done | pulled=%d pre_filtered=%d llm_scored=%d escalated=%d errors=%d",
            self.agent_name,
            len(state.raw_items),
            len(state.pre_filtered),
            len(state.llm_scored),
            len(state.escalated),
            len(state.errors),
        )
        return state

    # ── Pipeline nodes ────────────────────────────────────────────────────────

    async def _execute_pull(self, state: IngestionState) -> IngestionState:
        try:
            items = await self.pull(state.pull_window)
            for item in items:
                if not item.content_hash:
                    item.content_hash = _content_hash(item.raw_payload)
            state.raw_items = items
        except Exception as exc:
            state.errors.append(f"pull_error: {exc}")
            logger.error("[%s] Pull failed: %s", self.agent_name, exc)
        return state

    async def _rule_prefilter(self, state: IngestionState) -> IngestionState:
        keywords = [k.lower() for k in self.keyword_rules()]
        kept: list[RawItem] = []
        for item in state.raw_items:
            text_blob = json.dumps(item.raw_payload, default=str).lower()
            if any(kw in text_blob for kw in keywords):
                kept.append(item)
        dropped = len(state.raw_items) - len(kept)
        logger.debug("[%s] Rule filter: kept %d / %d (dropped %d)", self.agent_name, len(kept), len(state.raw_items), dropped)
        state.pre_filtered = kept
        return state

    async def _llm_relevance_score(self, state: IngestionState) -> IngestionState:
        if not state.pre_filtered:
            return state

        batch_size = 10
        scored: list[ScoredItem] = []

        for i in range(0, len(state.pre_filtered), batch_size):
            batch = state.pre_filtered[i : i + batch_size]
            scored_batch = await self._score_batch(batch)
            scored.extend(scored_batch)

        state.llm_scored = scored
        return state

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _score_batch(self, items: list[RawItem]) -> list[ScoredItem]:
        descriptions = []
        for idx, item in enumerate(items):
            payload_str = json.dumps(item.raw_payload, default=str)[:300]
            descriptions.append(f"{idx+1}. source={item.source} url={item.url or 'n/a'}\n{payload_str}")

        user_msg = "Score each signal:\n\n" + "\n\n---\n\n".join(descriptions)

        response = await budgeted_client.messages_create(
            model=_HAIKU,
            max_tokens=1024,
            system=await _prompt_registry.aget("relevance_scorer"),
            messages=[{"role": "user", "content": user_msg}],
        )

        raw_text = response.content[0].text.strip()
        # Strip markdown fences if present
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip()

        # Try strict parse first; fall back to recovering a partial array
        try:
            scores = json.loads(raw_text)
        except json.JSONDecodeError:
            # Response was truncated — recover whatever complete objects exist
            logger.warning(
                "[%s] JSON truncated in score batch (%d items); recovering partial",
                self.agent_name, len(items),
            )
            try:
                # Find the last complete JSON object boundary
                bracket = raw_text.rfind("},")
                if bracket == -1:
                    bracket = raw_text.rfind("}")
                partial = raw_text[: bracket + 1].rstrip().rstrip(",") + "]"
                if not partial.startswith("["):
                    partial = "[" + partial
                scores = json.loads(partial)
            except Exception:
                scores = []

        results: list[ScoredItem] = []
        for item, score_obj in zip(items, scores):
            results.append(
                ScoredItem(
                    item=item,
                    rule_score=1.0,  # passed rule filter
                    llm_score=float(score_obj.get("relevance", 0.0)),
                    llm_reasoning=score_obj.get("reasoning", ""),
                )
            )
        # Items beyond what the LLM returned get a neutral score (won't escalate)
        for item in items[len(scores):]:
            results.append(
                ScoredItem(
                    item=item,
                    rule_score=1.0,
                    llm_score=0.0,
                    llm_reasoning="scoring_truncated",
                )
            )
        return results

    async def _route_and_persist(self, state: IngestionState) -> IngestionState:
        escalated: list[ScoredItem] = []
        discarded: list[ScoredItem] = []

        to_persist: list[ScoredItem] = []
        for scored in state.llm_scored:
            score = scored.llm_score or 0.0
            if score >= _ESCALATE_THRESHOLD:
                scored.decision = "escalate"
                escalated.append(scored)
                to_persist.append(scored)
            elif score >= _REVIEW_THRESHOLD:
                scored.decision = "review"
                to_persist.append(scored)
            else:
                scored.decision = "discard"
                discarded.append(scored)

        state.escalated = escalated
        state.discarded = discarded

        if to_persist:
            await self._persist_signals(to_persist)

        return state

    async def _persist_signals(self, items: list[ScoredItem]) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                for scored in items:
                    item = scored.item
                    # Upsert into signals (ON CONFLICT DO NOTHING for dedup).
                    stmt = (
                        insert(Signal)
                        .values(
                            source=item.source,
                            source_id=item.source_id,
                            raw_payload=item.raw_payload,
                            url=item.url,
                            occurred_at=item.occurred_at,
                            content_hash=item.content_hash,
                        )
                        .on_conflict_do_nothing(constraint="uq_signal_source_id")
                        .returning(Signal.id)
                    )
                    result = await session.execute(stmt)
                    row = result.fetchone()
                    if row is None:
                        # Already existed — fetch existing id for the relevance row.
                        existing = await session.execute(
                            select(Signal.id).where(
                                Signal.source == item.source,
                                Signal.source_id == item.source_id,
                            )
                        )
                        signal_id = existing.scalar_one_or_none()
                    else:
                        signal_id = row[0]

                    if signal_id is None:
                        continue

                    # Upsert signal_relevance.
                    rel_stmt = (
                        insert(SignalRelevance)
                        .values(
                            signal_id=signal_id,
                            rule_score=scored.rule_score,
                            llm_score=scored.llm_score,
                            decision=scored.decision,
                            reasoning=scored.llm_reasoning,
                        )
                        .on_conflict_do_update(
                            index_elements=["signal_id"],
                            set_={
                                "llm_score": scored.llm_score,
                                "decision": scored.decision,
                                "reasoning": scored.llm_reasoning,
                            },
                        )
                    )
                    await session.execute(rel_stmt)

    async def _store_telemetry(self, state: IngestionState) -> None:
        cost = budgeted_client.daily_spend(_HAIKU)
        async with self._session_factory() as session:
            async with session.begin():
                run = AgentRun(
                    agent_name=state.agent_name,
                    started_at=state.started_at,
                    finished_at=state.finished_at,
                    status="error" if state.errors else "ok",
                    items_pulled=len(state.raw_items),
                    items_passed_rules=len(state.pre_filtered),
                    items_passed_llm=len(state.llm_scored),
                    items_classified=len(state.escalated),
                    cost_usd=cost,
                    notes="; ".join(state.errors) if state.errors else None,
                    trace_id=state.trace_id,
                )
                session.add(run)

    async def last_run_at(self) -> datetime | None:
        """Return the start time of the most recent successful run, or None."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(AgentRun.started_at)
                .where(AgentRun.agent_name == self.agent_name, AgentRun.status == "ok")
                .order_by(AgentRun.started_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
