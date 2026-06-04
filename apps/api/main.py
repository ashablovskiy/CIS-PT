"""CIS FastAPI application entry point."""

from __future__ import annotations

import logging

import inngest.fast_api
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.inngest_functions.agent_crons import ALL_FUNCTIONS, inngest_client
from apps.api.settings import settings

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CIS — Contract Intelligence System",
    description="Power transformer sourcing intelligence: real signals, clause-level reasoning, adaptive learning.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Build allowed-origins list: always include localhost for dev, plus any
# additional domains from CORS_ORIGINS env var (comma-separated).
_cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]
if settings.web_base_url and settings.web_base_url not in _cors_origins:
    _cors_origins.append(settings.web_base_url)
for _origin in settings.cors_origins.split(","):
    _origin = _origin.strip()
    if _origin and _origin not in _cors_origins:
        _cors_origins.append(_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Inngest (serves webhook at /api/inngest) ──────────────────────────────────
# Only register if a real signing key is present.  Without it the API starts
# normally — scheduled agent crons are simply disabled.  This lets the service
# run on Railway without an Inngest account.
_inngest_key = settings.inngest_signing_key
_inngest_ready = bool(_inngest_key and _inngest_key != "signkey-FILL_ME_IN")

if _inngest_ready:
    inngest.fast_api.serve(
        app,
        inngest_client,
        ALL_FUNCTIONS,
        serve_path="/api/inngest",
    )
else:
    logger.info(
        "INNGEST_SIGNING_KEY not configured — agent cron schedule disabled. "
        "Set a real key to enable scheduled ingestion runs."
    )


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    import asyncio
    from sqlalchemy import text
    from apps.api.db.session import engine
    try:
        async def _ping():
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        await asyncio.wait_for(_ping(), timeout=5.0)
        db = "ok"
    except asyncio.TimeoutError:
        db = "timeout"
    except Exception as exc:
        db = f"error: {type(exc).__name__}"
    return {"status": "ok", "db": db, "environment": settings.environment}


# ── Route registration ────────────────────────────────────────────────────────
from apps.api.routes import agents, assessments, briefs, feedback, network, prompts, signals  # noqa: E402

app.include_router(signals.router,     prefix="/api/signals",     tags=["signals"])
app.include_router(assessments.router, prefix="/api/assessments", tags=["assessments"])
app.include_router(briefs.router,      prefix="/api/briefs",      tags=["briefs"])
app.include_router(agents.router,      prefix="/api/agents",      tags=["agents"])
app.include_router(feedback.router,    prefix="/api/feedback",    tags=["feedback"])
app.include_router(prompts.router,     prefix="/api/prompts",     tags=["admin"])
app.include_router(network.router,     prefix="/api/network",     tags=["network"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("apps.api.main:app", host="0.0.0.0", port=8000, reload=True)
