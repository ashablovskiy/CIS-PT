"""Database session factory — asyncpg-compatible, SSL-aware."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.ingest.runner import _make_asyncpg_engine
from apps.api.settings import settings

# Reuse the SSL-aware engine builder (strips psycopg2-style sslmode, passes ssl=True)
engine = _make_asyncpg_engine(settings.database_url)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
