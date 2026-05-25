"""Neo4j client wrapper — single async driver, FastAPI DI-compatible."""

from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncGraphDatabase, AsyncDriver

from apps.api.settings import settings

logger = logging.getLogger(__name__)

_driver: AsyncDriver | None = None


async def get_driver() -> AsyncDriver:
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
        await _driver.verify_connectivity()
        logger.info("Neo4j driver connected to %s", settings.neo4j_uri)
    return _driver


async def close_driver() -> None:
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None


class Neo4jClient:
    """Thin wrapper exposing typed query helpers."""

    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    async def run(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        """Execute a read query and return a list of record dicts."""
        async with self._driver.session() as session:
            result = await session.run(cypher, **params)
            return [dict(record) async for record in result]

    async def write(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        """Execute a write query inside a transaction."""
        async with self._driver.session() as session:
            result = await session.execute_write(
                lambda tx: tx.run(cypher, **params)
            )
            return [dict(record) for record in result]


async def get_neo4j_client() -> Neo4jClient:
    """FastAPI dependency — yields a Neo4jClient backed by the module driver."""
    driver = await get_driver()
    return Neo4jClient(driver)
