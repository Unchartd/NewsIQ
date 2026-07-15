import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)


class HTTPClientPool:
    """Centralized, keepalive-optimized shared HTTP client session pool to prevent socket leaks."""

    def __init__(self) -> None:
        self._clients: dict[int, httpx.AsyncClient] = {}

    @property
    def client(self) -> httpx.AsyncClient:
        try:
            loop = asyncio.get_running_loop()
            loop_id = id(loop)
        except RuntimeError:
            loop_id = 0

        if loop_id not in self._clients:
            # Set connection limits suitable for high concurrency
            limits = httpx.Limits(
                max_keepalive_connections=50,
                max_connections=100,
                keepalive_expiry=30.0,
            )
            # Default timeout configuration
            timeout = httpx.Timeout(timeout=10.0, connect=5.0)

            self._clients[loop_id] = httpx.AsyncClient(
                limits=limits,
                timeout=timeout,
            )
            logger.info("Shared HTTP client session pool initialized for loop %s.", loop_id)
        return self._clients[loop_id]

    async def close(self) -> None:
        """Close all shared client sessions and release all connection pools."""
        for loop_id, client in list(self._clients.items()):
            try:
                await client.aclose()
            except Exception as e:
                logger.warning("Error closing shared httpx client for loop %s: %s", loop_id, e)
        self._clients.clear()


http_client_pool = HTTPClientPool()
