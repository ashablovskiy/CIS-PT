# CIS — Contract Intelligence System

> A sourcing intelligence prototype that ingests real commodity-market signals, maps them onto a power-transformer supply knowledge graph, produces contract-clause-aware impact assessments, and learns from category-manager corrections via DSPy prompt optimization.

**Status:** Week 1 / 6 — foundation scaffold

---

## What this is

CIS demonstrates that a sourcing-domain intelligence system can move from *"scores in a dashboard"* to *"defensible, contract-grounded arguments that improve over time"* — running on real data, in production.

**The wedge vs incumbents (Everstream, Resilinc, Interos):**

1. **Clause-level contract reasoning** — not "copper risk is amber," but "which contracts have a steel indexation clause and what is the recalculation trigger?"
2. **Transparent multi-hop reasoning** — signal → commodity → supplier → contract → exposure, cited at every step.
3. **Adaptive feedback loop** — category-manager corrections enter a DSPy compile pipeline that recompiles the synthesizer prompt.
4. **Agentic ingestion** — six LLM-driven agents at the data layer, not just at reasoning.

---

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, uv |
| Frontend | Next.js 15 (App Router), TypeScript, shadcn/ui, Tailwind |
| Graph viz | React Flow |
| Relational DB | Neon Postgres + pgvector |
| Knowledge graph | Neo4j AuraDB Free |
| LLM (reasoning) | Claude Opus 4.7 |
| LLM (bulk) | Claude Haiku 4.5 |
| Embeddings | Voyage AI voyage-3-large |
| Agents | LangGraph |
| Prompt opt. | DSPy MIPROv2 |
| Scheduling | Inngest |
| Observability | LangSmith |

---

## Local setup

### Prerequisites

- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- [pnpm](https://pnpm.io/) — `npm i -g pnpm`
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — for local Postgres + Neo4j

### 1. Clone and install

```bash
git clone https://github.com/ashablovskiy/CIS-PT.git
cd CIS-PT
uv sync                  # Python deps + .venv
pnpm install             # Node deps (all workspaces)
```

### 2. Configure environment

```bash
cp .env.example .env
# Fill in: ANTHROPIC_API_KEY, VOYAGE_API_KEY, DATABASE_URL, NEO4J_*, LANGSMITH_API_KEY
```

### 3. Start local infra

```bash
docker compose up -d     # Postgres (pgvector) + Neo4j
```

### 4. Run migrations

```bash
uv run alembic upgrade head
```

### 5. Start API

```bash
uv run uvicorn apps.api.main:app --reload
# → http://localhost:8000/docs
```

### 6. Start web

```bash
cd apps/web && pnpm dev
# → http://localhost:3000
```

---

## Project structure

```
apps/api/        FastAPI backend
apps/web/        Next.js frontend
docs/            Architecture, domain primer, data source notes
eval/            Golden scenarios + evaluation harness
scripts/         One-off scripts (seed graph, generate contracts, backfill)
packages/shared/ Generated TypeScript types from FastAPI OpenAPI
```

See `PROJECT_SPEC.md` for the full spec and `docs/architecture.md` for component map.

---

## Cost

Target ≤ $150/month. Anthropic API is the main cost driver (~$90–115/month).
See `PROJECT_SPEC.md §16` for full breakdown and cost discipline rules.
