"""Inngest cron functions — schedule all 6 ingestion agents.

Cadences (per spec §8):
  prices_agent   — every 1 hour   (commodity markets)
  gdelt_agent    — every 1 hour   (global events)
  logistics_agent — every 1 hour  (port/shipping)
  press_agent    — every 2 hours  (trade press RSS)
  demand_agent   — every 4 hours  (hyperscaler press rooms)
  sec_agent      — every 24 hours (SEC EDGAR filings)

Registration: imported in main.py and served at /api/inngest.
"""

from __future__ import annotations

import logging

import inngest
import inngest.fast_api

logger = logging.getLogger(__name__)

# Inngest client — signing key required in prod; dev mode works without it.
from apps.api.settings import settings as _settings

inngest_client = inngest.Inngest(
    app_id="cis-ingestion",
    signing_key=_settings.inngest_signing_key or None,
    is_production=_settings.is_production,
    event_key=_settings.inngest_event_key or None,
)


def _make_agent_fn(
    fn_id: str,
    cron: str,
    agent_import: str,
    agent_class: str,
    lookback_hours: int | None = None,
) -> inngest.Function:
    """Factory: produces a cron function that runs a single ingestion agent."""

    @inngest_client.create_function(
        fn_id=fn_id,
        trigger=inngest.TriggerCron(cron=cron),
        concurrency=[inngest.Concurrency(limit=1)],  # no parallel overlapping runs
    )
    async def _fn(ctx: inngest.Context, step: inngest.Step) -> dict:
        import importlib

        async def run_agent() -> dict:
            module = importlib.import_module(agent_import)
            AgentClass = getattr(module, agent_class)
            agent = AgentClass()
            state = await agent.run(lookback_hours=lookback_hours)
            return {
                "pulled": len(state.raw_items),
                "pre_filtered": len(state.pre_filtered),
                "llm_scored": len(state.llm_scored),
                "escalated": len(state.escalated),
                "errors": state.errors,
                "trace_id": state.trace_id,
            }

        result = await step.run("run_agent", run_agent)
        logger.info("[%s] Inngest run complete: %s", fn_id, result)
        return result

    return _fn


# ── Registered functions ──────────────────────────────────────────────────────

prices_fn = _make_agent_fn(
    fn_id="cis/prices-agent",
    cron="0 * * * *",  # every hour at :00
    agent_import="apps.api.ingest.sources.prices_agent",
    agent_class="PricesAgent",
    lookback_hours=2,
)

gdelt_fn = _make_agent_fn(
    fn_id="cis/gdelt-agent",
    cron="15 * * * *",  # every hour at :15 (stagger from prices)
    agent_import="apps.api.ingest.sources.gdelt_agent",
    agent_class="GdeltAgent",
    lookback_hours=1,
)

logistics_fn = _make_agent_fn(
    fn_id="cis/logistics-agent",
    cron="30 * * * *",  # every hour at :30
    agent_import="apps.api.ingest.sources.logistics_agent",
    agent_class="LogisticsAgent",
    lookback_hours=1,
)

press_fn = _make_agent_fn(
    fn_id="cis/press-agent",
    cron="0 */2 * * *",  # every 2 hours
    agent_import="apps.api.ingest.sources.press_agent",
    agent_class="PressAgent",
    lookback_hours=3,
)

demand_fn = _make_agent_fn(
    fn_id="cis/demand-agent",
    cron="0 */4 * * *",  # every 4 hours
    agent_import="apps.api.ingest.sources.demand_agent",
    agent_class="DemandAgent",
    lookback_hours=5,
)

sec_fn = _make_agent_fn(
    fn_id="cis/sec-agent",
    cron="0 6 * * *",  # daily at 06:00 UTC
    agent_import="apps.api.ingest.sources.sec_agent",
    agent_class="SecAgent",
    lookback_hours=25,
)

# All functions for FastAPI registration
ALL_FUNCTIONS = [prices_fn, gdelt_fn, logistics_fn, press_fn, demand_fn, sec_fn]
