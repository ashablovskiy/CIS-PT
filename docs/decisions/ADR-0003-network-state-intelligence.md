# ADR-0003: Industrial Network State Intelligence

**Status:** Proposed
**Date:** 2026-05-29
**Supersedes:** none (extends the existing event-intelligence pipeline)

---

## Context

The system today does **event intelligence**: ingest signal → score severity in isolation →
escalate the high-severity ones. This is good at finding and ranking individual events, but it
is structurally blind to the thing that actually causes industrial disruptions — the
**accumulation and interaction of many individually-minor signals** across an interconnected
network of actors.

We want to evolve from answering *"What happened?"* to *"What is happening to the network?"*
and ultimately *"What is likely to happen next?"*.

Conceptually this is Actor-Network Theory (Latour): outcomes emerge from networks of
interacting actors, not from single important events. Quantitatively it is network science
(centrality, propagation), complex-systems theory (emergence), and state estimation.

### What we already have (verified against the live DB)

- **Neo4j graph**: **307 nodes** across 9 labels (Plant 87, Supplier 54, DemandSource 50,
  Port 29, Country 26, Material 22, Lane 16, Commodity 14, Category 9) and **1,342 edges**
  across 13 relationship types (`USES_MATERIAL` 541, `SUB_TIER_OF` 280, `SHIPS_VIA` 128,
  `OPERATED_BY` 87, `LOCATED_IN` 87, `ALTERNATIVE_TO` 44, `BELONGS_TO_THEME` 44, `ON_LANE` 36,
  `PRODUCES` 30, `DRIVES_DEMAND_FOR` 18, `CONSTRAINS` 17, `IS_FORM_OF` 15, `DEMAND_PULLS_ON` 15).
- **Node properties**: every node carries `impact_weight` (0–1) and `criticality`
  (critical/high/medium/low) — the per-actor prior.
- **Edge properties**: edges do **not** carry a numeric `weight`. Some carry `severity`
  (CONSTRAINS) or `criticality`/`impact_weight` (IS_FORM_OF). Phase 2 must therefore **derive**
  a numeric edge weight from a per-rel-type base × a categorical→numeric severity map, with a
  documented default. (Real task, not a free assumption.)
- **Signals** in Postgres with `impact_tier`, `impact_type`, `llm_score`, `analyst_score`,
  `reasoning`.
- **Graph-prior scorer**: `runner._top_graph_priors` already detects which graph entities a
  signal mentions (the `[graph_priors]` annotation) — but discards that mapping after scoring.
- **Assessment pipeline** with a `graph_retriever` node (1–2 hop Cypher expansion) and a Neo4j
  client at `apps/api/graph/client.py`.
- **Frontend**: nav is a `NAV` array in `apps/web/app/layout.tsx` (Daily Brief `/` / Signals /
  Assessments / Agents / Prompts). There is **no** existing graph-viz component — Phase 4 builds
  one (lightweight SVG/canvas, or add a force-sim lib). **No `/api/graph` router exists yet**;
  the Neo4j client is `apps/api/graph/client.py` with helpers in `queries.py`.
- Inngest cron infra + Daily Scout batch-job pattern to copy.

### The gap

1. Signal→actor links are computed (triage + scorer) but **never persisted** as a queryable
   mapping. No way to ask "how much pressure is on actor X right now?"
2. There is **no network-level computation** — no centrality, no pressure propagation, no
   state estimate, no health trend.
3. Edges have no numeric weight yet — propagation math needs one derived first.

---

## Decision

Build an **Industrial Network State Engine** as a new layer on top of the existing pipeline.
Events become *observations that inject pressure into actors*; the primary output becomes a
**network-state assessment**, not a ranked event list. Five phases, each independently shippable.

---

### Phase 0 — Edge weights (prerequisite, small)

Derive a numeric `w ∈ (0,1]` per edge so propagation has something to flow along.
- Per-rel-type base weight (e.g. `CONSTRAINS` 0.9, `USES_MATERIAL` 0.8, `SUB_TIER_OF` 0.7,
  `SHIPS_VIA` 0.6, `ON_LANE` 0.6, `OPERATED_BY` 0.5, `ALTERNATIVE_TO` -0.5 (relieves), …).
- Multiply by severity/criticality map (`critical`=1.0, `high`=0.8, `medium`=0.5, `low`=0.3),
  default 0.5 when absent.
- Computed in-memory at graph-load time (Phase 2), not written back to Neo4j. Documented in one
  table in `network/weights.py` so it's tunable.

---

### Phase 1 — Signal→Actor grounding (the foundation)

Persist every signal as a weighted link to the graph actors it affects.

- New Postgres table `signal_actor_link`:
  `(signal_id, actor_name, actor_label, match_kind, pressure, created_at)`
  - `match_kind`: `direct` (named in signal) | `expanded` (graph neighbor from triage walk)
  - `pressure` = `effective_score × tier_weight × match_factor`
    (tier_weight: T1=1.0, T2=0.7, T3=0.4, T4=0.1; match_factor: direct=1.0, expanded=0.5)
- Populate from the two places that already do entity matching:
  - ingestion scorer (`runner._top_graph_priors`) → direct links at persist time
  - assessment `graph_retriever` → expanded links
- Backfill script maps the existing ~300 signals via the same `entity_priors` logic.

**Deliverable:** every signal grounded to actors; queryable "which signals touch actor X."

---

### Phase 2 — Network State Engine (the core)

New module `apps/api/network/` (depends on `networkx`):

- **`topology.py`** — load Neo4j → `networkx.DiGraph`, apply Phase-0 weights, normalise edge
  direction so influence flows dependent → dependency. Cached, refreshed on demand.
- **`influence.py`** — **systemic influence** (static): weighted PageRank on the reversed
  dependency graph, blended with node `impact_weight`. Answers "which actor is most
  depended-upon," not "biggest."
- **`pressure.py`** — **dynamic pressure** (signal-driven):
  - `direct_pressure(a)` = Σ linked-signal `pressure × recency_decay` (~14-day half-life).
  - `propagated_pressure(a)` = **personalized PageRank** seeded by the direct-pressure vector
    → pressure diffuses along weighted edges and concentrates where paths converge. This is the
    formal "unrelated signals combining and reinforcing."
- **`state.py`** — derived outputs:
  - **Hotspots**: propagated ≫ direct pressure above threshold (multi-path convergence).
  - **Emerging bottlenecks**: high influence ∧ rising pressure ∧ high criticality.
  - **Propagation paths**: strongest weighted paths from high-pressure sources to critical
    downstream actors (OEMs, demand centers).
  - **Ecosystem health**: fragility index Σ(centrality × pressure) → 0–1 +
    label (`resilient`/`constrained`/`fragile`).

**Deliverable:** given current signals + graph, produce a full network-state object.

---

### Phase 3 — State snapshots over time (state estimation)

- New table `network_snapshot`: `(id, computed_at, health_index, health_label, top_actors_json,
  hotspots_json, bottlenecks_json, signal_window_hours, signal_count)`.
- Inngest cron computes + persists every 6h (and on demand).
- The snapshot **sequence** is exactly the observation series a future HMM would consume — but
  Phase 3 ships the deterministic estimate first.

**Deliverable:** a time series of network state ("constrained for 9 days").

---

### Phase 4 — API + Frontend ("Network State" surface)

- New router `/api/network`: `GET /state`, `/actors`, `/hotspots`,
  `/propagation/{actor}`, `/health` (time series).
- New frontend page **`/network`** (added to the `NAV` array in `layout.tsx`, near top):
  - Ecosystem health gauge + trend sparkline
  - Systemic-influence leaderboard
  - Pressure-hotspot cards → expand to converging signals
  - Propagation view — new lightweight graph-viz component (no existing one to reuse)
  - "What changed since last snapshot" diff

**Deliverable:** network-state assessment becomes the primary surface.

---

### Phase 5 — Wire state back into assessments & brief

- **Synthesizer**: inject current network state as context
  (`network_state: constrained (0.63); actor X under rising pressure`).
- **Daily Scout brief**: lead with network state + what changed, then supporting signals.

**Deliverable:** the system reasons in network terms end-to-end.

---

## Quantitative methods (summary)

| Question | Method |
|---|---|
| Highest systemic influence? | Weighted PageRank on reversed dependency graph × `impact_weight` |
| Where is pressure accumulating? | Personalized PageRank seeded by signal-pressure vector |
| How does pressure propagate? | Strongest weighted paths (networkx) |
| Emerging bottleneck? | influence ∧ rising pressure ∧ criticality |
| Is the ecosystem fragile? | Fragility index Σ(centrality × pressure), trended over snapshots |

---

## Consequences

**Positive**
- Detects distributed/emergent disruptions invisible to per-event scoring.
- Additive — reuses graph, scorer, pipeline, Neo4j client, NetworkGraph component. Existing
  per-signal event view is untouched (no regression).
- Snapshot series sets up the HMM/forecasting layer cleanly later.
- Product story shifts from "alert feed" to "ecosystem radar."

**Negative / risks**
- Parameters (decay half-life, propagation damping, edge weights, health thresholds) need
  calibration. Mitigation: all in config with documented defaults; refine with backtest data.
- Recompute cadence must be bounded (cron every 6h + on-demand, not per-signal). PageRank on
  307 nodes is sub-second, so cost is trivial.
- New `networkx` dependency (pure-Python, well-maintained, no native build).

---

## Rollout order

P0 (edge weights) → P1 (grounding) → P2 (engine) → P3 (snapshots) → P4 (API+UI) →
P5 (feedback into assess/brief). P0–P2 alone already answer "highest systemic influence" and
"where is pressure accumulating."
