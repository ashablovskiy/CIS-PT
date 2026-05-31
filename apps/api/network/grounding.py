"""Phase 1 — signal → actor grounding.

Turns a scored signal into weighted links to the graph actors it affects, and
persists them to `signal_actor_link`. Reuses the same entity-prior matching the
relevance scorer already uses (`keyword_registry.get_entity_priors`), so the
grounding is consistent with how the signal was scored.

pressure = effective_score × tier_weight × match_factor
  tier_weight:  T1=1.0  T2=0.7  T3=0.4  T4=0.1  (None → 0.4)
  match_factor: direct=1.0  expanded=0.5
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.dialects.postgresql import insert

from apps.api.db.models import SignalActorLink
from apps.api.ingest.keyword_registry import registry as _kw_registry

logger = logging.getLogger(__name__)

_TIER_WEIGHT = {1: 1.0, 2: 0.7, 3: 0.4, 4: 0.1}
_MATCH_FACTOR = {"direct": 1.0, "expanded": 0.5}
_MAX_DIRECT_ACTORS = 6  # cap actors per signal to avoid over-spreading pressure


def tier_weight(tier: int | None) -> float:
    return _TIER_WEIGHT.get(tier, 0.4)


def compute_links(
    payload_text: str,
    effective_score: float | None,
    impact_tier: int | None,
) -> list[dict[str, Any]]:
    """Return direct actor links for a signal from its text + score.

    Each link: {actor_name, actor_label, match_kind, pressure}.
    """
    score = effective_score if effective_score is not None else 0.0
    if score <= 0:
        return []

    priors = _kw_registry.get_entity_priors()
    text = (payload_text or "").lower()

    # Dedup by actor name, keeping the highest-impact-weight match.
    seen: dict[str, dict] = {}
    for kw, meta in priors.items():
        if kw in text:
            name = meta["name"]
            if name not in seen or meta["impact_weight"] > seen[name]["impact_weight"]:
                seen[name] = meta

    tw = tier_weight(impact_tier)
    mf = _MATCH_FACTOR["direct"]

    links = []
    for meta in sorted(seen.values(), key=lambda m: m["impact_weight"], reverse=True)[:_MAX_DIRECT_ACTORS]:
        pressure = round(score * tw * mf, 4)
        if pressure <= 0:
            continue
        links.append({
            "actor_name": meta["name"],
            "actor_label": meta.get("label"),
            "match_kind": "direct",
            "pressure": pressure,
        })
    return links


def links_from_payload(payload: dict, effective_score: float | None, impact_tier: int | None) -> list[dict]:
    """Convenience: build the text blob the scorer sees, then compute links."""
    text_blob = json.dumps(payload, default=str)[:2000]
    return compute_links(text_blob, effective_score, impact_tier)


async def persist_links(session, signal_id, links: list[dict[str, Any]]) -> int:
    """Upsert actor links for a signal. Returns count written."""
    n = 0
    for link in links:
        stmt = (
            insert(SignalActorLink)
            .values(
                signal_id=signal_id,
                actor_name=link["actor_name"],
                actor_label=link.get("actor_label"),
                match_kind=link.get("match_kind", "direct"),
                pressure=link.get("pressure", 0.0),
            )
            .on_conflict_do_update(
                constraint="uq_signal_actor",
                set_={
                    "pressure": link.get("pressure", 0.0),
                    "actor_label": link.get("actor_label"),
                    "match_kind": link.get("match_kind", "direct"),
                },
            )
        )
        await session.execute(stmt)
        n += 1
    return n
