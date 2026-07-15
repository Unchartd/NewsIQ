from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.http_client import http_client_pool
from app.services.vector_service import VectorService


@pytest.mark.asyncio
async def test_http_client_pool_lifecycle():
    """Verify that http_client_pool correctly creates, reuses, and closes the shared httpx.AsyncClient."""
    # Ensure pool is closed/fresh
    await http_client_pool.close()
    assert len(http_client_pool._clients) == 0

    # Get client - should instantiate it
    client1 = http_client_pool.client
    assert isinstance(client1, httpx.AsyncClient)
    assert len(http_client_pool._clients) == 1

    # Get client again - should return the exact same instance (reuse)
    client2 = http_client_pool.client
    assert client2 is client1

    # Close pool - should clean up
    await http_client_pool.close()
    assert len(http_client_pool._clients) == 0


@pytest.mark.asyncio
async def test_vector_service_client_cleanup():
    """Verify that VectorService.close() closes all loop-specific AsyncQdrantClients."""
    vector_svc = VectorService()

    # Create a couple of mock clients in the cache
    mock_client1 = MagicMock()
    mock_client1.close = AsyncMock()

    mock_client2 = MagicMock()
    mock_client2.close = AsyncMock()

    vector_svc._clients[111] = mock_client1
    vector_svc._clients[222] = mock_client2
    vector_svc._collection_ready = True

    # Call close
    await vector_svc.close()

    # Assertions
    mock_client1.close.assert_called_once()
    mock_client2.close.assert_called_once()
    assert len(vector_svc._clients) == 0
    assert vector_svc._collection_ready is False
