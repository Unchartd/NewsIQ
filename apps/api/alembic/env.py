"""Alembic environment configuration for async SQLAlchemy.

Migration URL Strategy:
  - Uses DATABASE_DIRECT_URL (non-pooled, no PgBouncer) for migrations.
  - PgBouncer (Neon's pooled endpoint) does not support DDL commands reliably.
  - Falls back to DATABASE_URL if DATABASE_DIRECT_URL is not configured.

This means:
  - App uses: postgresql+asyncpg://...neon.tech/db?pgbouncer=true  (pooled)
  - Alembic uses: postgresql+asyncpg://...neon.tech/db             (direct)
"""

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

# Ensure the project root (apps/api) is on sys.path so 'app' is importable
# regardless of how alembic is invoked (uv run, venv .exe, or system alembic).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import settings

# Import all models so metadata is populated
from app.core.database import Base
from app.models import *  # noqa: F401, F403

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Migration URL ─────────────────────────────────────────────────────────────
# Use the direct (non-pooled) URL for migrations.
# Neon's PgBouncer pooled endpoint does not support DDL reliably.
_migration_url = settings.database_direct_url or settings.DATABASE_URL
if "?" in _migration_url:
    _migration_url = _migration_url.split("?")[0]

if _migration_url.startswith("postgresql://"):
    _migration_url = _migration_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _migration_url.startswith("postgres://"):
    _migration_url = _migration_url.replace("postgres://", "postgresql+asyncpg://", 1)

config.set_main_option("sqlalchemy.url", _migration_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — generates SQL scripts without a live connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    from alembic.script import ScriptDirectory
    from sqlalchemy import inspect, text

    inspector = inspect(connection)
    tables = inspector.get_table_names()

    if "alembic_version" not in tables:
        # Fresh database: create all tables from metadata and stamp head
        with connection.begin():
            Base.metadata.create_all(bind=connection)

            # Get the head revision ID
            script = ScriptDirectory.from_config(config)
            head_revision = script.get_current_head()

            # Create alembic_version table and insert head revision
            connection.execute(
                text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)")
            )
            connection.execute(
                text("INSERT INTO alembic_version (version_num) VALUES (:head)"),
                {"head": head_revision},
            )
        return

    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with an async engine.

    Uses NullPool to avoid connection pool overhead during migrations.
    This is the correct approach for short-lived migration processes.
    """
    connect_args = {}
    url = config.get_main_option("sqlalchemy.url")
    if settings.DATABASE_SSL or (url and "neon.tech" in url):
        import ssl
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_ctx

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations — bridges sync Alembic with async SQLAlchemy."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
