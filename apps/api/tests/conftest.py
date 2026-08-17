"""Pytest configuration and common fixtures."""
# ruff: noqa: E402, I001

import os

# Disable Langfuse integration for all unit tests to avoid hanging on HTTP timeouts
os.environ["LANGFUSE_PUBLIC_KEY"] = ""
os.environ["LANGFUSE_SECRET_KEY"] = ""

# Bypass RateLimitMiddleware for all tests to prevent connecting to Redis
from app.core.rate_limiter import RateLimitMiddleware


async def _mock_rate_limit_dispatch(self, request, call_next):
    return await call_next(request)


RateLimitMiddleware.dispatch = _mock_rate_limit_dispatch

# Replace real Redis with an in-memory fake during tests.
#
# Patch the *factory*, not CacheService._redis. Nulling the property deletes
# the per-loop client lifecycle from the class, so no test could exercise it —
# which is how the connection leak that exhausted Redis in production (BUG-27)
# stayed invisible to the suite.
#
# A working fake (rather than None) also matters for correctness: several
# gates now fail CLOSED when the cache is unreachable — notably the per-story
# synthesis cost gate, since spend is tracked only in Redis and proceeding
# blind would mean unmetered LLM spend. With no cache at all, those gates would
# refuse everything and the tests would exercise nothing.
import fnmatch as _fnmatch

import app.services.cache_service as _cache_mod


class _FakeRedis:
    """Minimal async Redis stand-in covering the operations this app uses."""

    def __init__(self) -> None:
        self._store: dict[str, object] = {}

    async def get(self, key):
        return self._store.get(key)

    async def set(self, key, value, ex=None, nx=False, xx=False):
        exists = key in self._store
        if (nx and exists) or (xx and not exists):
            return None
        self._store[key] = value
        return True

    async def delete(self, *keys):
        for k in keys:
            self._store.pop(k, None)
        return len(keys)

    async def scan_iter(self, match="*"):
        for k in [k for k in self._store if _fnmatch.fnmatch(k, match)]:
            yield k

    async def ping(self):
        return True

    async def incr(self, key):
        self._store[key] = int(self._store.get(key, 0)) + 1
        return self._store[key]

    async def incrbyfloat(self, key, amount):
        self._store[key] = float(self._store.get(key, 0.0)) + float(amount)
        return self._store[key]

    async def expire(self, key, ttl):
        return True

    async def llen(self, key):
        return 0

    async def xadd(self, *args, **kwargs):
        return "0-0"

    async def info(self, section=None):
        return {"connected_clients": 1}

    async def aclose(self):
        return None

    async def close(self):
        return None


_cache_mod._make_redis_client = lambda url: _FakeRedis()

# Mock ExtractionManager._update_domain_policy globally to prevent DB connection attempts
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.extraction_manager import ExtractionManager

# The original is kept so tests that need to exercise the real statement (see
# test_domain_policy_upsert.py) can reach it without lifting the global mock.
ExtractionManager._real_update_domain_policy = ExtractionManager._update_domain_policy
ExtractionManager._update_domain_policy = AsyncMock()

# Bypass structured logging Redis publisher globally during tests to prevent connecting to Redis.
# The original is kept so tests that need to exercise the real processor (see
# test_stage_log_persistence.py) can reach it without lifting the global bypass.
import app.core.structured_logging as sl

sl._real_store_and_publish_log = sl._store_and_publish_log
sl._store_and_publish_log = lambda logger, method_name, event_dict: event_dict

# Bypass PipelineCache._record_metric globally during tests to disable Redis metric publishing
from app.services.pipeline_cache import PipelineCache

PipelineCache._record_metric = staticmethod(lambda stage, operation: None)

# Bypass Qdrant remote compatibility check during client initialization to prevent hanging/connecting
from qdrant_client.async_qdrant_remote import AsyncQdrantRemote
from qdrant_client.qdrant_remote import QdrantRemote

AsyncQdrantRemote._check_compatibility = lambda *args, **kwargs: None
QdrantRemote._check_compatibility = lambda *args, **kwargs: None

# Bypass Qdrant vector_service retrieve_vectors globally during tests to prevent connecting to Qdrant
from app.services.vector_service import vector_service

vector_service.retrieve_vectors = AsyncMock(return_value={})

# Bypass gnews_service._redis globally during tests to disable Redis connection attempts
from app.services.gnews_service import gnews_service

gnews_service._redis = None

import asyncio
from collections.abc import Generator

import pytest


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db_session():
    """Mock SQLAlchemy AsyncSession."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()  # flush is async in AsyncSession
    session.refresh = AsyncMock()  # refresh is async in AsyncSession

    # Mock begin_nested() for savepoints / nested transactions
    nested_mock = AsyncMock()
    nested_mock.__aenter__ = AsyncMock(return_value=nested_mock)
    nested_mock.__aexit__ = AsyncMock(return_value=None)
    session.begin_nested = MagicMock(return_value=nested_mock)

    return session


@pytest.fixture(autouse=True)
def mock_clustering_lock_connection():
    """Provide a fake dedicated connection for the global clustering advisory lock.

    run_batch_clustering takes pg_try_advisory_lock on its own connection from
    the engine — it cannot use the session, because AsyncSession returns its
    connection to the pool on every commit, which strands a session-scoped
    advisory lock on a pooled connection and permanently blocks later runs.
    Tests drive a fully mocked session, so the engine must be stubbed too or
    they attempt a real asyncpg connect and fail across event loops.
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    lock_conn = AsyncMock()
    acquired = MagicMock()
    acquired.scalar.return_value = True
    lock_conn.execute = AsyncMock(return_value=acquired)

    connect_cm = AsyncMock()
    connect_cm.__aenter__ = AsyncMock(return_value=lock_conn)
    connect_cm.__aexit__ = AsyncMock(return_value=None)

    fake_engine = MagicMock()
    fake_engine.connect = MagicMock(return_value=connect_cm)

    with patch("app.services.clustering_service.engine", fake_engine):
        yield lock_conn


@pytest.fixture(autouse=True)
def mock_trace_persistence():
    """Disable database and redis persistence/events for PipelineRun and StageSpan in tests."""
    with (
        patch("app.core.trace.PipelineRun._persist", new_callable=AsyncMock) as mock_persist_run,
        patch(
            "app.core.trace.StageSpan._persist_db_status", new_callable=AsyncMock
        ) as mock_persist_span,
        patch("app.core.trace.publish_pipeline_event", new_callable=AsyncMock) as mock_pub_event,
    ):
        yield mock_persist_run, mock_persist_span, mock_pub_event


@pytest.fixture(scope="session", autouse=True)
def initialize_test_prompt_repository():
    """Ensure PromptRepository is initialized for all tests."""
    from app.ai.prompts import repository as repo_module

    if repo_module.prompt_repository is None:
        from app.ai.prompts.compiler import PromptCompiler
        from app.ai.prompts.loader import PromptLoader
        from app.ai.prompts.repository import PromptRepository

        loader = PromptLoader()
        raw = loader.load_all()
        compiler = PromptCompiler()
        compiled = compiler.compile_all(raw)
        repo_module.prompt_repository = PromptRepository(compiled)
