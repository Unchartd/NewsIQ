"""Pytest configuration and common fixtures."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

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
