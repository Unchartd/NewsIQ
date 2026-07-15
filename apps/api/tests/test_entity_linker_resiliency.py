from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.entity_linker import entity_linker


@pytest.mark.asyncio
async def test_wikidata_multi_resiliency_timeout():
    """Verify that _query_wikidata_multi returns [] on HTTP errors/timeouts instead of raising RetryError."""
    # Mock httpx.AsyncClient.get to raise a timeout error
    mock_get = AsyncMock(side_effect=httpx.ConnectTimeout("Connection timed out"))

    with patch("httpx.AsyncClient.get", mock_get):
        # We speed up the retry wait time in settings or retry state
        # by patching the stop_after_attempt and wait_exponential parameters temporarily.
        from tenacity import stop_after_attempt, wait_none

        # Access the underlying retrying controller of the decorated function
        orig_retry = entity_linker._query_wikidata_multi.retry

        with patch.object(orig_retry, "stop", stop_after_attempt(3)), \
             patch.object(orig_retry, "wait", wait_none()):

            results = await entity_linker._query_wikidata_multi("test query")

            # Assertions
            assert results == []
            assert mock_get.call_count == 3


@pytest.mark.asyncio
async def test_wikidata_single_resiliency_http_error():
    """Verify that _query_wikidata returns None on HTTP errors/timeouts instead of raising RetryError."""
    # Mock httpx.AsyncClient.get to return a mock response that raises HTTPStatusError
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        message="500 Internal Server Error",
        request=MagicMock(),
        response=mock_response
    )

    mock_get = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient.get", mock_get):
        from tenacity import stop_after_attempt, wait_none

        orig_multi_retry = entity_linker._query_wikidata_multi.retry
        orig_single_retry = entity_linker._query_wikidata.retry

        with patch.object(orig_multi_retry, "stop", stop_after_attempt(3)), \
             patch.object(orig_multi_retry, "wait", wait_none()), \
             patch.object(orig_single_retry, "stop", stop_after_attempt(3)), \
             patch.object(orig_single_retry, "wait", wait_none()):

            result = await entity_linker._query_wikidata("test query")

            # Assertions
            assert result is None
            assert mock_get.call_count == 3
