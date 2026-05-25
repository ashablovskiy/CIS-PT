# Architecture overview

See `PROJECT_SPEC.md §5` for the full diagram.

## Component map

| Component | Tech | Location |
|---|---|---|
| API backend | FastAPI + Python 3.12 | `apps/api/` |
| Frontend | Next.js 15 + TypeScript | `apps/web/` |
| Relational DB + vectors | Neon Postgres + pgvector | cloud (local: docker) |
| Knowledge graph | Neo4j AuraDB Free | cloud (local: docker) |
| LLM (reasoning) | Claude Opus 4.7 | Anthropic API |
| LLM (bulk) | Claude Haiku 4.5 | Anthropic API |
| Embeddings | Voyage voyage-3-large | Voyage AI API |
| Agent orchestration | LangGraph | `apps/api/agents/` |
| Prompt optimization | DSPy MIPROv2 | `apps/api/dspy_lab/` |
| Scheduling | Inngest | `apps/api/inngest_functions/` |
| Observability | LangSmith | cloud |

## Data flow

```
External sources → ingestion agents → 3-stage funnel → classified_signals
    → LangGraph assessment pipeline → assessments
    → Daily Scout (03:00 UTC) → daily_briefs
    → Frontend (Notion-style)
    ← user feedback → DSPy compile → improved synthesizer prompt
```

## Cost discipline

1. Per-agent daily cap ($1/day default). BudgetedClient enforces per-model cap.
2. Stage-1 rule-based filter must drop ≥ 90% of raw items before any LLM call.
3. Prompt-cache graph context, contract corpus, category strategy doc (1h Anthropic cache).
4. Embed once per `content_hash`; never re-embed.
5. BigQuery: every GDELT query uses `_PARTITIONTIME` partition pruning; target ≤ 5 GB/query.
6. DSPy compile is manual-gated.
7. Cap Opus calls to ~20/day.
