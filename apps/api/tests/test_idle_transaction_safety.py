"""Regression tests for idle-in-transaction kills during long LLM phases.

Production Postgres runs idle_in_transaction_session_timeout = 30s. Any
backend that sits inside an open transaction without issuing a statement for
30 seconds is killed. Two code paths did exactly that:

  * run_batch_clustering acquired its advisory lock on a dedicated connection,
    which autobegan a transaction that was never committed. It idled for the
    whole clustering run (minutes of LLM synthesis), was killed, and the kill
    both crashed the run with "connection is closed" AND silently released
    the advisory lock mid-run — reopening the concurrent-execution hole the
    lock exists to close.

  * _run_batch_clustering_locked / extract_events_task held an open read
    transaction across sequential LLM calls with no intervening statements.

The fix is the same in each place: COMMIT before the long non-DB phase.
Session-level advisory locks survive COMMIT (only disconnect or explicit
unlock releases them), and expire_on_commit=False keeps loaded ORM objects
usable afterwards.
"""

import asyncio
import inspect

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.services.clustering_service import clustering_service
from app.workers import tasks

# ── Source-level guards ───────────────────────────────────────────────────────


def test_lock_connection_transaction_is_committed_after_acquire():
    """The advisory-lock connection must not idle inside an open transaction.

    Without the commit, idle_in_transaction_session_timeout kills the backend
    mid-run, which crashes clustering AND releases the global lock while the
    run is still writing.
    """
    src = inspect.getsource(clustering_service.run_batch_clustering)
    acquire = src.index("pg_try_advisory_lock")
    run = src.index("_run_batch_clustering_locked")
    between = src[acquire:run]
    assert "lock_conn.commit()" in between, (
        "the lock connection's implicit transaction must be committed after "
        "acquiring the advisory lock and before the long clustering run"
    )


def test_batch_read_transaction_closed_before_llm_verification():
    """The batch read transaction must end before the agent-verification loop."""
    src = inspect.getsource(clustering_service._run_batch_clustering_locked)
    reads_done = src.index("art_ent_map[art_id].add(ent_id)")
    # Anchor on the call site, not the bare name — comments may mention it.
    llm_loop = src.index("await self._verify_merge_with_agents(")
    between = src[reads_done:llm_loop]
    assert "await session.commit()" in between, (
        "the read transaction must be committed before sequential LLM calls, "
        "or idle_in_transaction_session_timeout kills the session connection"
    )


def test_extract_events_read_transaction_closed_before_llm_loop():
    src = inspect.getsource(tasks.extract_events_task)
    fetch = src.index("No articles pending event extraction")
    llm = src.index("event_service.extract_events")
    between = src[fetch:llm]
    assert "await session.commit()" in between, (
        "extract_events_task must close its read transaction before the "
        "per-article LLM extraction loop"
    )


# ── Behavioral proof against a real Postgres ─────────────────────────────────


def _database_url() -> str:
    url = settings.DATABASE_URL
    if "?" in url:
        url = url.split("?")[0]
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


async def _postgres_reachable() -> bool:
    try:
        probe = create_async_engine(_database_url(), pool_pre_ping=True)
        try:
            async with probe.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        finally:
            await probe.dispose()
    except Exception:
        return False


@pytest.mark.asyncio
async def test_committed_lock_survives_idle_and_keeps_advisory_lock():
    """Prove the fix's premise end-to-end on a real backend.

    With idle_in_transaction_session_timeout set aggressively low:
      * a connection that COMMITs after taking a session-level advisory lock
        survives idling past the timeout and still holds the lock;
      * a connection left inside an open transaction is killed by the same
        idle period (the pre-fix behaviour).
    """
    if not await _postgres_reachable():
        pytest.skip("live Postgres not reachable — behavioral proof runs in CI")

    lock_id = 424242424
    engine = create_async_engine(_database_url())
    try:
        # Fixed pattern: acquire, COMMIT, idle past the timeout, still usable
        # and still holding the lock.
        async with engine.connect() as lock_conn:
            await lock_conn.execute(text("SET idle_in_transaction_session_timeout = '500ms'"))
            got = await lock_conn.execute(text("SELECT pg_try_advisory_lock(:i)"), {"i": lock_id})
            assert got.scalar() is True
            await lock_conn.commit()

            await asyncio.sleep(1.2)  # idle well past the 500ms timeout

            held = await lock_conn.execute(
                text(
                    "SELECT count(*) FROM pg_locks "
                    "WHERE locktype='advisory' AND pid = pg_backend_pid()"
                )
            )
            assert held.scalar() == 1, "advisory lock must survive both COMMIT and the idle"
            await lock_conn.execute(text("SELECT pg_advisory_unlock(:i)"), {"i": lock_id})
            await lock_conn.commit()

        # Pre-fix pattern: same idle inside an open transaction gets killed.
        async with engine.connect() as dead_conn:
            await dead_conn.execute(text("SET idle_in_transaction_session_timeout = '500ms'"))
            await dead_conn.execute(text("SELECT 1"))  # autobegin, never committed
            await asyncio.sleep(1.2)
            with pytest.raises(Exception, match="closed|terminat|InterfaceError"):
                await dead_conn.execute(text("SELECT 1"))
    finally:
        await engine.dispose()
