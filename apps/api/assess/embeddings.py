"""Voyage AI embedding helper — 1024-dim vectors for pgvector search."""

from __future__ import annotations

import logging

import voyageai

from apps.api.settings import settings

logger = logging.getLogger(__name__)

_client: voyageai.AsyncClient | None = None
MODEL = "voyage-3-large"
DIMS = 1024


def _get_client() -> voyageai.AsyncClient:
    global _client
    if _client is None:
        _client = voyageai.AsyncClient(api_key=settings.voyage_api_key)
    return _client


async def embed_text(text: str) -> list[float]:
    """Embed a single text string. Returns a 1024-dim float list."""
    client = _get_client()
    result = await client.embed([text[:8000]], model=MODEL, input_type="document")
    return result.embeddings[0]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch embed up to 128 texts."""
    if not texts:
        return []
    client = _get_client()
    truncated = [t[:8000] for t in texts]
    result = await client.embed(truncated, model=MODEL, input_type="document")
    return result.embeddings


async def embed_query(text: str) -> list[float]:
    """Embed a query string (uses query input_type for better retrieval)."""
    client = _get_client()
    result = await client.embed([text[:8000]], model=MODEL, input_type="query")
    return result.embeddings[0]
