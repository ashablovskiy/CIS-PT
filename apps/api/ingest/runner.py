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

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from tenacity import retry, stop_after_attempt, wait_exponential

from apps.api.budget import BudgetExceededError, budgeted_client
from apps.api.db.models import AgentRun, Signal, SignalRelevance
from apps.api.ingest.base import IngestionState, RawItem, ScoredItem
from apps.api.ingest.keyword_registry import registry as _kw_registry
from apps.api.prompts.registry import registry as _prompt_registry
from apps.api.settings import settings

logger = logging.getLogger(__name__)


def _top_graph_priors(text: str, priors: dict[str, dict], max_n: int = 3) -> list[dict]:
    """Return the top-N highest-weight graph entities mentioned in `text`.

    Scans `priors` (keyword → entity_meta from KeywordRegistry.get_entity_priors())
    against the signal text.  De-duplicated by entity name — the same entity
    matched via different aliases counts once, keeping the highest weight.
    """
    seen: dict[str, dict] = {}
    for kw, meta in priors.items():
        if kw in text:
            name = meta["name"]
            if name not in seen or meta["impact_weight"] > seen[name]["impact_weight"]:
                seen[name] = meta
    return sorted(seen.values(), key=lambda m: m["impact_weight"], reverse=True)[:max_n]

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
    """Create an async engine stripping sslmode (psycopg2-style) and passing ssl=True to asyncpg.

    Uses NullPool — no connection is held between operations. This is the recommended
    approach for Neon serverless (and any serverless Postgres) where idle connections
    are dropped by the server after ~5 minutes, causing reconnection failures in long-
    running scripts. NullPool creates a fresh TCP connection for each DB session and
    closes it immediately — eliminating all idle-connection timeout failures.
    """
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    ssl_mode = (params.pop("sslmode", ["disable"])[0]).lower()
    # strip params asyncpg doesn't understand (Neon pooler adds these)
    params.pop("channel_binding", None)
    new_query = urlencode({k: v[0] for k, v in params.items()})
    clean_url = urlunparse(parsed._replace(query=new_query))
    connect_args = {"ssl": True} if ssl_mode in ("require", "verify-ca", "verify-full") else {}
    # 60 s — matches asyncpg default but made explicit; Neon pooler cold-start
    # can take 30-45 s in some regions. Railway proxy has its own 30 s limit so
    # we keep the API health-check capped separately via asyncio.wait_for.
    connect_args["timeout"] = 60
    return create_async_engine(
        clean_url,
        poolclass=NullPool,   # no idle connections — safe for Neon serverless
        connect_args=connect_args,
    )


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

        # Smaller batches + more tokens: scorer v2 emits 5 fields per item
        # (relevance, tier, impact_type, mechanism, reasoning) so a 10-item
        # batch at 1024 tokens routinely truncates. 5 items / 2048 tokens
        # leaves comfortable headroom (~400 tokens per item).
        batch_size = 5
        scored: list[ScoredItem] = []

        for i in range(0, len(state.pre_filtered), batch_size):
            batch = state.pre_filtered[i : i + batch_size]
            try:
                scored_batch = await self._score_batch(batch)
            except Exception as exc:
                # LLM unavailable (API timeout, budget exhausted, etc.) — fall
                # back to rule-based scoring: assign 0.4 (review tier) so items
                # are persisted for later manual review rather than lost.
                logger.warning(
                    "[%s] LLM batch %d-%d failed (%s) — using rule-based fallback (score=0.4)",
                    self.agent_name, i, i + len(batch), type(exc).__name__,
                )
                scored_batch = [
                    ScoredItem(
                        item=item,
                        rule_score=1.0,
                        llm_score=0.4,
                        llm_reasoning="llm_unavailable_rule_fallback",
                    )
                    for item in batch
                ]
            scored.extend(scored_batch)

        state.llm_scored = scored
        return state

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _score_batch(self, items: list[RawItem]) -> list[ScoredItem]:
        entity_priors = _kw_registry.get_entity_priors()

        descriptions = []
        for idx, item in enumerate(items):
            payload_str = json.dumps(item.raw_payload, default=str)[:300]
            # Scan the full (but capped) payload text for graph entity matches.
            # This is the same text blob used by the rule pre-filter, just longer.
            text_blob = json.dumps(item.raw_payload, default=str)[:2000].lower()
            top = _top_graph_priors(text_blob, entity_priors)

            desc = f"{idx+1}. source={item.source} url={item.url or 'n/a'}\n{payload_str}"
            if top:
                priors_str = ", ".join(
                    f"{m['name']} ({m['label']}, {m['criticality']}, w={m['impact_weight']:.2f})"
                    for m in top
                )
                desc += f"\n[graph_priors: {priors_str}]"
            descriptions.append(desc)

        user_msg = "Score each signal:\n\n" + "\n\n---\n\n".join(descriptions)

        response = await budgeted_client.messages_create(
            model=_HAIKU,
            max_tokens=2048,
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
            tier = score_obj.get("tier")
            try:
                tier = int(tier) if tier is not None else None
            except (TypeError, ValueError):
                tier = None
            results.append(
                ScoredItem(
                    item=item,
                    rule_score=1.0,  # passed rule filter
                    llm_score=float(score_obj.get("relevance", 0.0)),
                    llm_reasoning=score_obj.get("reasoning", ""),
                    impact_tier=tier,
                    impact_type=score_obj.get("impact_type"),
                    mechanism=score_obj.get("mechanism"),
                    signal_kind=score_obj.get("signal_kind"),
                    what_changed=score_obj.get("what_changed"),
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
        # ── Pre-compute event-clustering embeddings (outside DB transaction) ──
        # One batch Voyage API call for all items in this persist batch.
        # Embeddings are stored on signals.embedding and used to assign event_id,
        # which prevents multiple news sources covering the same event from each
        # contributing full pressure to ANT nodes.
        cluster_embeddings: list[list[float] | None] = [None] * len(items)
        # Retry embedding up to 2 times — a transient Voyage failure leaves
        # event_id=NULL which causes ANT Layer 2 to double-count duplicate events.
        for _attempt in range(2):
            try:
                from apps.api.assess.embeddings import embed_texts
                from apps.api.network.event_cluster import payload_to_cluster_text
                texts = [payload_to_cluster_text(s.item.raw_payload) for s in items]
                vecs = await embed_texts(texts)
                for i, v in enumerate(vecs):
                    cluster_embeddings[i] = v
                break   # success
            except Exception as exc:
                if _attempt == 0:
                    logger.warning(
                        "[%s] Embedding attempt 1 failed (%s) — retrying…",
                        self.agent_name, exc,
                    )
                    await asyncio.sleep(3)
                else:
                    logger.warning(
                        "[%s] Embedding failed after 2 attempts (%s) — "
                        "signals stored without event_id. Run recluster_events.py "
                        "to backfill embeddings and fix ANT dedup.",
                        self.agent_name, exc,
                    )

        async with self._session_factory() as session:
            async with session.begin():
                # ── Pass 1: insert signals, relevance rows, and actor links ───
                # We store the embedding on the signal row here so it is
                # visible to the within-batch cluster query in Pass 2.
                new_signal_ids: list[Any] = []  # None = signal already existed

                for scored, embedding in zip(items, cluster_embeddings):
                    item = scored.item
                    stmt = (
                        insert(Signal)
                        .values(
                            source=item.source,
                            source_id=item.source_id,
                            raw_payload=item.raw_payload,
                            url=item.url,
                            occurred_at=item.occurred_at,
                            content_hash=item.content_hash,
                            embedding=embedding,  # may be None if Voyage failed
                        )
                        .on_conflict_do_nothing(constraint="uq_signal_source_id")
                        .returning(Signal.id)
                    )
                    result = await session.execute(stmt)
                    row = result.fetchone()
                    if row is None:
                        # Signal already existed — fetch its id for relevance row.
                        existing = await session.execute(
                            select(Signal.id).where(
                                Signal.source == item.source,
                                Signal.source_id == item.source_id,
                            )
                        )
                        signal_id = existing.scalar_one_or_none()
                        new_signal_ids.append(None)  # mark as pre-existing
                    else:
                        signal_id = row[0]
                        new_signal_ids.append(signal_id)

                    if signal_id is None:
                        continue

                    # Upsert signal_relevance.
                    # NB: analyst_score is intentionally NOT touched here — only
                    # the PATCH /api/signals/{id}/score endpoint may write to it.
                    rel_stmt = (
                        insert(SignalRelevance)
                        .values(
                            signal_id=signal_id,
                            rule_score=scored.rule_score,
                            llm_score=scored.llm_score,
                            decision=scored.decision,
                            reasoning=scored.llm_reasoning,
                            impact_type=scored.impact_type,
                            impact_tier=scored.impact_tier,
                            mechanism=scored.mechanism,
                            signal_kind=scored.signal_kind,
                            what_changed=scored.what_changed,
                        )
                        .on_conflict_do_update(
                            index_elements=["signal_id"],
                            set_={
                                "llm_score": scored.llm_score,
                                "decision": scored.decision,
                                "reasoning": scored.llm_reasoning,
                                "impact_type": scored.impact_type,
                                "impact_tier": scored.impact_tier,
                                "mechanism": scored.mechanism,
                                "signal_kind": scored.signal_kind,
                                "what_changed": scored.what_changed,
                            },
                        )
                    )
                    await session.execute(rel_stmt)

                    # ── Network grounding: link signal → graph actors ──────────
                    # Pressure = llm_score × tier_weight × match_factor.
                    try:
                        from apps.api.network.grounding import (
                            links_from_payload, persist_links,
                        )
                        links = links_from_payload(
                            item.raw_payload, scored.llm_score, scored.impact_tier
                        )
                        if links:
                            await persist_links(session, signal_id, links)
                    except Exception as exc:
                        logger.debug("[%s] actor grounding skipped: %s",
                                     self.agent_name, exc)

                # ── Flush so Pass-1 inserts are visible within this transaction ─
                # Required for within-batch cross-source dedup: if Reuters and
                # Bloomberg both arrive in the same ingest run, Bloomberg must
                # be able to find Reuters in the cluster query.
                await session.flush()

                # ── Pass 2: assign event_ids to newly inserted signals ─────────
                from apps.api.network.event_cluster import find_event_cluster

                clustered_count = 0
                for scored, embedding, sig_id in zip(
                    items, cluster_embeddings, new_signal_ids
                ):
                    # Skip: signal already existed, or embedding unavailable.
                    if sig_id is None or embedding is None:
                        continue
                    try:
                        event_id = await find_event_cluster(
                            session,
                            sig_id,
                            embedding,
                            scored.item.occurred_at,
                            scored.item.source,
                        )
                        await session.execute(
                            update(Signal)
                            .where(Signal.id == sig_id)
                            .values(event_id=event_id)
                        )
                        if event_id != sig_id:
                            clustered_count += 1
                            logger.info(
                                "[%s] Clustered signal %s → canonical event %s",
                                self.agent_name, sig_id, event_id,
                            )
                    except Exception as exc:
                        logger.debug(
                            "[%s] Event-cluster assignment failed for %s: %s",
                            self.agent_name, sig_id, exc,
                        )

                if clustered_count:
                    logger.info(
                        "[%s] Event clustering: %d/%d signals merged into existing clusters",
                        self.agent_name, clustered_count, len(items),
                    )

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
