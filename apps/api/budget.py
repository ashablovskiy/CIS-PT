"""BudgetedClient — wraps the Anthropic SDK with per-model daily spend caps.

Usage:
    from apps.api.budget import budgeted_client

    response = await budgeted_client.messages_create(
        model="claude-haiku-4-5-20251001",
        ...
    )
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any

import anthropic

from apps.api.settings import settings

logger = logging.getLogger(__name__)

# Anthropic pricing (USD per 1M tokens, as of 2025-05).
# Update these if pricing changes.
_PRICING: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "claude-opus-4-7": {"input": 15.00, "output": 75.00},
    # Fallback for unknown models — conservative estimate.
    "_default": {"input": 15.00, "output": 75.00},
}

_MODEL_CAPS: dict[str, float] = {
    "claude-haiku-4-5-20251001": settings.budget_cap_haiku_usd,
    "claude-opus-4-7": settings.budget_cap_opus_usd,
}


def _cost_for_usage(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = _PRICING.get(model, _PRICING["_default"])
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


class _DailySpend:
    """In-memory daily spend tracker (resets at UTC midnight)."""

    def __init__(self) -> None:
        self._totals: dict[str, float] = {}
        self._date: date = datetime.now(UTC).date()

    def _reset_if_new_day(self) -> None:
        today = datetime.now(UTC).date()
        if today != self._date:
            self._totals = {}
            self._date = today

    def add(self, model: str, cost: float) -> None:
        self._reset_if_new_day()
        self._totals[model] = self._totals.get(model, 0.0) + cost

    def get(self, model: str) -> float:
        self._reset_if_new_day()
        return self._totals.get(model, 0.0)

    def check_cap(self, model: str) -> None:
        """Raise BudgetExceededError if daily cap for model is exceeded."""
        cap = _MODEL_CAPS.get(model)
        if cap is None:
            return
        spent = self.get(model)
        if spent >= cap:
            raise BudgetExceededError(
                model=model,
                spent=spent,
                cap=cap,
            )


class BudgetExceededError(Exception):
    def __init__(self, model: str, spent: float, cap: float) -> None:
        self.model = model
        self.spent = spent
        self.cap = cap
        super().__init__(
            f"Daily budget exceeded for {model}: "
            f"${spent:.4f} spent >= ${cap:.2f} cap. "
            "Resets at 00:00 UTC."
        )


class BudgetedClient:
    """Thin async wrapper around anthropic.AsyncAnthropic with daily cost caps."""

    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._spend = _DailySpend()

    async def messages_create(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> anthropic.types.Message:
        self._spend.check_cap(model)

        response = await self._client.messages.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            **kwargs,
        )

        # Record cost from actual usage.
        usage = response.usage
        cost = _cost_for_usage(model, usage.input_tokens, usage.output_tokens)
        self._spend.add(model, cost)

        logger.debug(
            "LLM call | model=%s tokens_in=%d tokens_out=%d cost=$%.4f daily_total=$%.4f",
            model,
            usage.input_tokens,
            usage.output_tokens,
            cost,
            self._spend.get(model),
        )
        return response

    def daily_spend(self, model: str) -> float:
        return self._spend.get(model)

    def all_daily_spend(self) -> dict[str, float]:
        return dict(self._spend._totals)


# Module-level singleton.
budgeted_client = BudgetedClient()
