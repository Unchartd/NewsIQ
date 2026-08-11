"""Regression tests for loop-bound client lifecycle (BUG-27).

Production incident these guard against: CacheService and VectorService keep one
client per event loop (their connections are loop-bound), and Celery's
run_async() creates a fresh loop per task. Nothing released those clients, so
every task invocation stranded a connection pool. Redis reached
"ERR max number of clients reached" (9993 of 10000 clients held by the worker),
which tripped the is_pipeline_paused() fail-safe and silently halted ingestion,
embedding, event extraction and clustering for ~9 days while every Celery task
continued to report success.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.cache_service import CacheService, redis_client
from app.services.vector_service import VectorService
from app.workers.tasks import run_async


def test_run_async_releases_loop_bound_clients(monkeypatch):
    """run_async must leave zero stranded client pools after each task."""
    from app.services import cache_service as cache_mod
    from app.services import vector_service as vector_mod

    cache = CacheService()
    vector = VectorService()

    made: list[AsyncMock] = []

    def _fake_redis(_url):
        client = AsyncMock()
        client.aclose = AsyncMock()
        made.append(client)
        return client

    monkeypatch.setattr(cache_mod, "_make_redis_client", _fake_redis)
    monkeypatch.setattr(cache_mod, "cache_service", cache)
    monkeypatch.setattr(vector_mod, "vector_service", vector)
    monkeypatch.setattr(vector_mod, "AsyncQdrantClient", lambda **kw: AsyncMock())

    async def fake_task():
        assert cache._redis is not None
        assert vector.client is not None

    for _ in range(25):
        run_async(fake_task())

    # The bug: these counters grew by one per task and never came down.
    assert cache.pool_count == 0, f"{cache.pool_count} Redis pools stranded"
    assert vector.pool_count == 0, f"{vector.pool_count} Qdrant pools stranded"
    assert made, "expected clients to have been created"
    assert all(c.aclose.await_count == 1 for c in made), "clients were not closed"


@pytest.mark.asyncio
async def test_close_current_loop_is_safe_without_a_client():
    """Teardown must never raise, even when nothing was ever created."""
    await CacheService().close_current_loop()
    await VectorService().close_current_loop()


@pytest.mark.asyncio
async def test_stale_client_from_recycled_loop_id_is_discarded(monkeypatch):
    """CPython recycles object ids; a new loop must not inherit a dead client."""
    from app.services import cache_service as cache_mod

    cache = CacheService()
    monkeypatch.setattr(cache_mod, "_make_redis_client", lambda _u: MagicMock(name="client"))

    real_loop = asyncio.get_running_loop()
    first = cache._redis

    # Forge an entry under the *current* loop id but bound to a different loop,
    # exactly as an id() collision would look.
    cache._clients[id(real_loop)] = (MagicMock(name="dead_loop"), MagicMock(name="dead_client"))

    second = cache._redis
    assert second is not first or second is not None
    stored_loop, _ = cache._clients[id(real_loop)]
    assert stored_loop is real_loop, "stale entry was returned instead of being discarded"


@pytest.mark.asyncio
async def test_redis_client_helper_closes_on_exception(monkeypatch):
    """The one-off helper must close even when the body raises.

    The old `from_url(...) ... await r.aclose()` pattern skipped the close
    whenever a command raised — and under Redis pressure commands raise
    constantly, so the leak accelerated exactly when it mattered.
    """
    from app.services import cache_service as cache_mod

    client = AsyncMock()
    client.aclose = AsyncMock()
    monkeypatch.setattr(cache_mod, "_make_redis_client", lambda _u: client)

    # Catch explicitly rather than with pytest.raises: static analysis cannot
    # see that pytest.raises suppresses the exception, and reports everything
    # after the block as unreachable.
    raised = False
    try:
        async with redis_client("redis://localhost:6379/0") as r:
            assert r is client
            raise RuntimeError("simulated Redis failure")
    except RuntimeError:
        raised = True

    assert raised, "the simulated failure should propagate to the caller"
    client.aclose.assert_awaited_once()
