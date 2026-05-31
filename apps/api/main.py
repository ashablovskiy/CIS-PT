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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_base_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Inngest (serves webhook at /api/inngest) ──────────────────────────────────
inngest.fast_api.serve(
    app,
    inngest_client,
    ALL_FUNCTIONS,
    serve_path="/api/inngest",
)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


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
