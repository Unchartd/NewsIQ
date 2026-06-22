"""Pytest configuration and common fixtures."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock

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
    from unittest.mock import MagicMock
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()  # flush is async in AsyncSession
    session.refresh = AsyncMock() # refresh is async in AsyncSession

    # Mock begin_nested() for savepoints / nested transactions
    nested_mock = AsyncMock()
    nested_mock.__aenter__ = AsyncMock(return_value=nested_mock)
    nested_mock.__aexit__ = AsyncMock(return_value=None)
    session.begin_nested = MagicMock(return_value=nested_mock)

    return session

