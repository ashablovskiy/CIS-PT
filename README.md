# CIS — Contract Intelligence System

> Contract-grounded supply-chain intelligence for power transformer procurement.
> Ingests real signals → maps them onto a supplier knowledge graph → produces clause-level impact assessments → learns from analyst corrections via DSPy optimization.

**Status: v0.8 — fully functional, deployed on Render**

---

## What this is

CIS demonstrates that a sourcing-domain intelligence system can move from *"scores in a dashboard"* to *"defensible, contract-grounded arguments that improve over time"* — running on real data, not mocked.

**The wedge vs incumbents (Everstream, Resilinc, Interos):**

1. **Clause-level contract reasoning** — not "copper risk is amber," but "which contracts have a steel indexation clause and what is the recalculation trigger threshold?"
2. **Transparent multi-hop reasoning** — signal → commodity → supplier → contract → exposure, each step cited to a source.
3. **Adaptive feedback loop** — analyst accept/edit/reject decisions build DSPy training examples; a weekly MIPROv2 run recompiles the synthesizer prompt automatically.
4. **Agentic ingestion** — six parallel LLM-driven agents (GDELT, prices, logistics, press, demand, SEC EDGAR), not a single scraper.
5. **XGBoost price enrichment** — magnitude estimates from a commodity-price model (MAE 6.1%) augment every LLM assessment.

---

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, uv |
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind v4 |
| Relational DB | Neon Postgres + pgvector (1024-dim Voyage embeddings) |
| Knowledge graph | Neo4j AuraDB (supplier → plant → port → lane) |
| LLM — reasoning | Claude Opus `claude-opus-4-5-20251101` via DSPy |
| LLM — bulk | Claude Haiku `claude-haiku-4-5-20251001` |
| Embeddings | Voyage AI `voyage-3-large` (1024 dim) |
| Agent orchestration | LangGraph 1.2 (7-node StateGraph) |
| Prompt optimization | DSPy 3.2 + MIPROv2 |
| Scheduling | Inngest (9 cron functions) |
| ML enrichment | XGBoost — commodity price impact model |
| Observability | LangSmith |
| Deployment | Render (API + web) |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  6 Ingestion Agents (Inngest crons, 15–60 min cadence)      │
│  GDELT · Prices · Logistics · Press · Demand · SEC EDGAR    │
└───────────────────┬─────────────────────────────────────────┘
                    │ Signals (Postgres + pgvector)
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  Relevance Scorer (Haiku)                                   │
│  escalate / classify / discard                              │
└───────────────────┬─────────────────────────────────────────┘
                    │ escalated signals
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  LangGraph Assessment Pipeline (7 nodes)                    │
│  triage → graph_retrieval → similarity_search →             │
│  contract_matching → synthesizer → critic → persist         │
│                                                             │
│  Synthesizer: Claude Opus via DSPy ImpactAssessment sig.   │
│  + XGBoost price magnitude enrichment                       │
└───────────────────┬─────────────────────────────────────────┘
                    │ Assessments (Postgres)
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  Next.js Dashboard                                          │
│  Signal volume chart · Assessment detail · Prompt editor   │
│  Analyst feedback → DSPy training examples → optimizer     │
└─────────────────────────────────────────────────────────────┘
```

---

## Local setup

### Prerequisites

- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- [pnpm](https://pnpm.io/) — `npm i -g pnpm`
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — for local Postgres + Neo4j
- (Optional) `brew install libomp` — needed for XGBoost on macOS

### 1. Clone and install

```bash
git clone <repo-url>
cd CIM_v.0
uv sync                  # Python deps → .venv
pnpm install             # Node deps (all workspaces)
```

### 2. Configure environment

```bash
cp .env.example .env
# Required: ANTHROPIC_API_KEY, VOYAGE_API_KEY
# Required: DATABASE_URL, DATABASE_SYNC_URL (Neon or local Docker)
# Required: NEO4J_URI, NEO4J_PASSWORD
# Optional: LANGSMITH_API_KEY, INNGEST_EVENT_KEY, GCP_PROJECT_ID
```

### 3. Start local infrastructure

```bash
docker compose up -d     # Postgres (pgvector:pg16) + Neo4j
```

### 4. Run database migrations

```bash
uv run alembic upgrade head
```

### 5. Seed data

```bash
# Seed prompt templates (relevance_scorer, triage_classifier, critic, daily_brief)
uv run python scripts/seed_prompts.py

# Seed Neo4j knowledge graph (suppliers, plants, ports, lanes)
uv run python scripts/seed_graph.py

# Generate sample contracts
uv run python scripts/generate_contracts.py
```

### 6. (Optional) Train XGBoost price model

```bash
# Fetches 2 years of commodity prices from yfinance — requires internet
# Runtime ~2 minutes; persists models to apps/api/ml/models/
uv run python scripts/train_price_model.py
```

### 7. Start services

**Terminal 1 — API:**
```bash
uv run uvicorn apps.api.main:app --reload
# → http://localhost:8000/docs
```

**Terminal 2 — Web:**
```bash
cd apps/web && pnpm dev
# → http://localhost:3000
```

---

## Key API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health |
| GET | `/api/signals` | Recent signals (filterable by decision, hours) |
| GET | `/api/signals/stats` | Volume stats + time series for chart |
| GET | `/api/assessments` | Assessment list |
| GET | `/api/assessments/{id}` | Full assessment detail |
| POST | `/api/feedback` | Submit analyst feedback (accept/edit/reject) |
| GET | `/api/feedback/stats` | Feedback counts + optimizer readiness |
| GET | `/api/prompts` | Active prompt versions |
| PUT | `/api/prompts/{name}` | Publish new prompt version (hot-reloads) |
| GET | `/api/briefs/latest` | Latest daily scout brief |
| POST | `/api/inngest` | Inngest webhook (cron triggers) |

Full interactive docs: `http://localhost:8000/docs`

---

## Project structure

```
apps/
  api/
    assess/nodes/      LangGraph pipeline nodes (7 nodes)
    agents/            LangGraph state definition
    db/                SQLAlchemy models + Alembic migrations
    dspy_lab/          DSPy signatures, optimizer, training data
    ingest/            Ingestion runner + relevance scorer
    inngest_functions/ Cron definitions (9 functions)
    ml/                XGBoost price impact estimator
    prompts/           Prompt registry (DB-backed, 5-min TTL cache)
    routes/            FastAPI route handlers
    scout/             Daily Scout Agent (brief generation)
  web/
    app/               Next.js App Router pages
      assessments/     Assessment list + detail
      signals/         Signal explorer
      admin/prompts/   Prompt editor UI
eval/
  run_eval.py          Tier 1/2/3 evaluation harness
scripts/
  seed_prompts.py      Seed prompt_templates table
  seed_graph.py        Seed Neo4j knowledge graph
  train_price_model.py Train XGBoost from yfinance data
tests/
  unit/
    test_metrics.py          DSPy metric tests (15)
    test_prompt_registry.py  Prompt registry tests (13)
    test_feedback_training.py Feedback → training example tests (11)
    test_price_impact.py     XGBoost estimator tests (18)
```

---

## Feedback → optimization loop

1. Analyst views an assessment and clicks **Accept**, **Needs Edit**, or **Reject**
2. Accept/Edit writes a `DspyTrainingExample` row (weight 1.0 / 1.5)
3. `GET /api/feedback/stats` reports `optimizer_ready: true` once ≥5 examples exist
4. The **weekly Inngest cron** (Sunday 04:00 UTC) runs MIPROv2 with all training examples
5. Compiled program saved to `apps/api/dspy_lab/compiled/`; loaded at next API restart

---

## Prompt management

All four Haiku prompts (`relevance_scorer`, `triage_classifier`, `critic`, `daily_brief`) are stored in the `prompt_templates` table with full version history. The admin UI at `/admin/prompts` lets you edit and publish new versions — changes take effect within 5 minutes (cache TTL) with no deploy needed.

---

## Deployment (Render)

```bash
# Deploy via render.yaml Blueprint:
# 1. Push this repo to GitHub
# 2. In Render dashboard: New → Blueprint → point at render.yaml
# 3. Fill in env var values for all `sync: false` keys
# 4. Deploy
```

The `render.yaml` defines two services:
- `cis-api` — Docker (FastAPI), auto-built from `Dockerfile`
- `cis-web` — Node (Next.js pnpm build + start)

---

## Cost

Target ≤ $150/month. Anthropic API is the main driver (~$90–115/month at steady-state ingestion cadence). XGBoost inference is free (runs in-process). See `.env.example` for per-model budget cap settings.

| Service | Est. monthly |
|---------|-------------|
| Anthropic (Haiku + Opus) | $90–115 |
| Neon Postgres | $0 (free tier) |
| Neo4j AuraDB | $0 (free tier) |
| Voyage AI | $5–10 |
| Render (2 services) | $14 |
| **Total** | **~$120–140** |
