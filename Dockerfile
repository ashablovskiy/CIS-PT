# ── CIS API — Production Dockerfile ─────────────────────────────────────────
# Multi-stage build: builder installs deps, runtime is minimal.
# Targets Python 3.12 + uv for fast dependency resolution.

# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set work dir
WORKDIR /app

# Copy dependency manifests first (better layer caching)
COPY pyproject.toml uv.lock ./

# Install dependencies into a virtual env at /app/.venv
RUN uv sync --frozen --no-dev --no-install-project

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Install system deps needed at runtime (libpq for asyncpg, curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy virtual env from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY apps/    apps/
COPY scripts/ scripts/
COPY __init__.py ./

# uv / venv activation
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Railway injects $PORT; fall back to 8000 for other platforms.
EXPOSE 8000

# Healthcheck uses the same dynamic port.
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=5 \
  CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Shell form so ${PORT:-8000} is evaluated at runtime.
CMD uvicorn apps.api.main:app \
    --host 0.0.0.0 \
    --port ${PORT:-8000} \
    --workers 2 \
    --log-level info
