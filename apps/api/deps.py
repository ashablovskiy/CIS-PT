"""FastAPI dependency injection helpers."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.db.session import async_session_factory
from apps.api.graph.client import Neo4jClient, get_neo4j_client


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async SQLAlchemy session, closed on exit."""
    async with async_session_factory() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]
GraphClient = Annotated[Neo4jClient, Depends(get_neo4j_client)]
