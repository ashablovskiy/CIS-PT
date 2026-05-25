# ADR-0001: Static, version-controlled seed data

Date: 2026-05-25
Status: Accepted

## Context

The PROJECT_SPEC requires seeded data of two kinds:

1. A **knowledge graph** in Neo4j with ~80–120 power-transformer supply nodes and ~200 edges.
2. **5–10 mocked contracts** with realistic clause prose AND structured `parsed_params`.

The spec describes contracts as "Claude-generated once, then committed to the repo as static seed data." This ADR locks that decision in for **both** graph and contracts.

## Decision

All seed data lives **statically in the repo** under `scripts/seed_data/`:

- `transformers_graph.py` — Python module with `NODES` and `EDGES` lists. Hand-curated against PROJECT_SPEC §4 (domain primer).
- `contracts.json` — fully-formed contract objects with clause prose authored once by Claude (Opus), now version-controlled.
- `category_strategy.json` — single category-strategy doc loaded as context by ingestion + assessment agents.

Loader scripts (`seed_graph.py`, `seed_db.py`) read these files and are **idempotent** — they `MERGE` into Neo4j and use `ON CONFLICT DO NOTHING` patterns into Postgres so re-runs don't duplicate.

The `generate_contracts.py` script is preserved as an **escape hatch** for regeneration but is not on the default seed path. Running it overwrites `contracts.json` and requires `ANTHROPIC_API_KEY`.

## Consequences

**Positive**
- Demos are deterministic — same seed every time, no surprises.
- Zero Anthropic API cost during local dev / setup.
- New contributors can clone + seed without an API key.
- Diffs in seed data are reviewable as plain text in PRs.
- The seed itself becomes part of the project's documented domain understanding.

**Negative**
- Updating the seed (e.g., adding a new supplier) requires editing files directly. Acceptable at MVP scale (~10 suppliers, ~8 contracts).
- The contract prose is fixed in the repo — if we want variety per demo, we'd need to extend `generate_contracts.py` later.

## Alternatives considered

- **Generate at startup via Claude.** Rejected: non-deterministic, costs money on every seed, fails without API key.
- **Faker-style synthetic generation.** Rejected: produces unrealistic clause language; the demo's credibility depends on clauses that read like real procurement contracts.
- **Use a public CUAD-style contract dataset.** Rejected: those are general commercial contracts, not power-transformer-specific. The wedge of this project is clause-level domain realism.
