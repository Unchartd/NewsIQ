"""Database infrastructure provider.

Wraps SQLAlchemy session factory behind a provider interface so that:
  - Business logic depends on DatabaseProvider, not SQLAlchemy directly
  - Health checks are centralised here
  - Future migration to a different ORM requires changes only in this module
"""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory


class DatabaseProvider:
    """Provides database sessions and health checks."""

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Yield a managed async database session.

        Commits on success, rolls back on exception, always closes.
        """
        async with async_session_factory() as sess:
            try:
                yield sess
                await sess.commit()
            except Exception:
                await sess.rollback()
                raise
            finally:
                await sess.close()

    async def health_check(self) -> dict:
        """Return a health status dict for the database connection.

        Returns:
            {"status": "ok"|"error", "latency_ms": float, "last_check": str}
        """
        t0 = time.monotonic()
        try:
            async with async_session_factory() as sess:
                await sess.execute(text("SELECT 1"))
            latency_ms = (time.monotonic() - t0) * 1000
            return {
                "status": "ok",
                "latency_ms": round(latency_ms, 2),
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "latency_ms": round((time.monotonic() - t0) * 1000, 2),
            }


# Singleton provider — FastAPI routes get_db() can use get_db or this provider
database_provider = DatabaseProvider()
