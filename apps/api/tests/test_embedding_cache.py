from unittest.mock import AsyncMock, patch

import pytest

import app.ai.gateway
from app.services.embedding_service import EMBEDDING_DIM, EmbeddingService


def test_embedding_cache_key():
    service = EmbeddingService()
    key = service._cache_key("test text")
    assert "newsiq:embedding:" in key


@pytest.mark.asyncio
@patch("app.services.cache_service.cache_service.get", new_callable=AsyncMock)
async def test_get_embedding_cache_hit(mock_cache_get):
    service = EmbeddingService()
    # Mock cache hit
    dummy_vector = [0.1] * EMBEDDING_DIM
    mock_cache_get.return_value = dummy_vector

    vec = await service.get_embedding("cached text")
    assert vec == dummy_vector
    mock_cache_get.assert_called_once()


@pytest.mark.asyncio
@patch("app.services.cache_service.cache_service.get", new_callable=AsyncMock)
@patch("app.services.cache_service.cache_service.set", new_callable=AsyncMock)
async def test_get_embedding_cache_miss(mock_cache_set, mock_cache_get):
    service = EmbeddingService()
    # Mock cache miss
    mock_cache_get.return_value = None

    dummy_vector = [0.2] * EMBEDDING_DIM

    with patch("app.ai.gateway.ai_gateway.embeddings", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = dummy_vector

        vec = await service.get_embedding("uncached text")
        assert vec == dummy_vector
        mock_embed.assert_called_once_with("uncached text")

    mock_cache_get.assert_called_once()
    mock_cache_set.assert_called_once()


@pytest.mark.asyncio
@patch("app.services.cache_service.cache_service.get", new_callable=AsyncMock)
@patch("app.services.cache_service.cache_service.set", new_callable=AsyncMock)
async def test_get_embeddings_batch_hybrid(mock_cache_set, mock_cache_get):
    service = EmbeddingService()

    # We query 2 texts: text1 (hit) and text2 (miss)
    dummy_vec1 = [0.1] * EMBEDDING_DIM
    dummy_vec2 = [0.2] * EMBEDDING_DIM

    # Mock cache get returns dummy_vec1 for the first key and None for the second
    mock_cache_get.side_effect = [dummy_vec1, None]

    with patch("app.ai.gateway.ai_gateway.embeddings", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = dummy_vec2

        vecs = await service.get_embeddings(["text1", "text2"])
        assert len(vecs) == 2
        assert vecs[0] == dummy_vec1
        assert vecs[1] == dummy_vec2

        # Verify provider was only called for text2 (the miss)
        mock_embed.assert_called_once_with("text2")

    assert mock_cache_get.call_count == 2
    mock_cache_set.assert_called_once()
