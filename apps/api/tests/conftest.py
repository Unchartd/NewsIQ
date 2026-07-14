"""Pytest configuration and common fixtures."""

import os
# Disable Langfuse integration for all unit tests to avoid hanging on HTTP timeouts
os.environ["LANGFUSE_PUBLIC_KEY"] = ""
os.environ["LANGFUSE_SECRET_KEY"] = ""

# Bypass RateLimitMiddleware for all tests to prevent connecting to Redis
from app.core.rate_limiter import RateLimitMiddleware
async def _mock_rate_limit_dispatch(self, request, call_next):
    return await call_next(request)
RateLimitMiddleware.dispatch = _mock_rate_limit_dispatch

# Bypass CacheService._redis globally during tests to disable Redis connection attempts
from app.services.cache_service import CacheService
CacheService._redis = None

# Mock ExtractionManager._update_domain_policy globally to prevent DB connection attempts
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.extraction_manager import ExtractionManager
ExtractionManager._update_domain_policy = AsyncMock()

# Bypass structured logging Redis publisher globally during tests to prevent connecting to Redis
import app.core.structured_logging as sl
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
