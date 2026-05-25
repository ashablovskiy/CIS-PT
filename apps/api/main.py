"""CIS FastAPI application entry point."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


# ── Route registration (stubs — filled in per week) ──────────────────────────
# from apps.api.routes import signals, assessments, contracts, briefs, agents, feedback, optimization
# app.include_router(signals.router, prefix="/api/signals", tags=["signals"])
# app.include_router(assessments.router, prefix="/api/assessments", tags=["assessments"])
# app.include_router(contracts.router, prefix="/api/contracts", tags=["contracts"])
# app.include_router(briefs.router, prefix="/api/briefs", tags=["briefs"])
# app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
# app.include_router(feedback.router, prefix="/api/feedback", tags=["feedback"])
# app.include_router(optimization.router, prefix="/api/optimization", tags=["optimization"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("apps.api.main:app", host="0.0.0.0", port=8000, reload=True)
