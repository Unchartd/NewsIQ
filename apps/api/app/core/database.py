"""Async SQLAlchemy engine and session factory.

Tuned for cloud-managed PostgreSQL (Neon) with:
  - pool_pre_ping=True   → detects dropped connections before use (critical for serverless)
  - pool_recycle         → recycles connections to avoid stale serverless connections
  - SSL connect_args     → enforces SSL when DATABASE_SSL=True (Neon requires it)
  - Reduced pool_size    → respects Neon free-tier connection limits (max 5)

Switching back to self-hosted PostgreSQL:
  Set DATABASE_URL to your self-hosted endpoint and increase DB_POOL_SIZE
  in config. No code changes required.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# ── Connection arguments ──────────────────────────────────────────────────────
# SSL is required for Neon and most managed PostgreSQL providers.
# asyncpg passes connect_args directly to the underlying asyncpg.connect() call.
_connect_args: dict = {}
if settings.DATABASE_SSL:
    import ssl as _ssl

    _ssl_ctx = _ssl.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = _ssl.CERT_NONE
    _connect_args["ssl"] = _ssl_ctx

# ── Engine ─────────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    # Pool settings — conservative defaults for Neon free tier.
    # Increase DB_POOL_SIZE/DB_MAX_OVERFLOW in config for paid plans.
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    # pool_pre_ping — CRITICAL for serverless PostgreSQL.
    # Without this, a recycled connection that was dropped by Neon's
    # compute suspend will cause a cryptic asyncpg error on first use.
    pool_pre_ping=True,
    # Recycle connections after 5 minutes to avoid stale connections
    # after Neon autosuspend (which disconnects after 5 min of inactivity).
    pool_recycle=settings.DB_POOL_RECYCLE,
    connect_args=_connect_args,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session.

    Commits on success, rolls back on exception, always closes.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
