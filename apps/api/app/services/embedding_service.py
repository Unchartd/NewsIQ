"""Embedding service — delegate to centralized AI Gateway."""

import asyncio
import hashlib
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Canonical embedding dimension for the entire pipeline.
EMBEDDING_DIM = 768


class EmbeddingService:
    """Generates text embeddings via the central AI Gateway."""

    @staticmethod
    def _prepare_text(text: str) -> str:
        """Normalize and truncate text before embedding."""
        if not text:
            return ""
        from app.services.context_extractor import context_extractor

        # Extract optimized paragraph-aware context up to 8000 chars first
        optimized = context_extractor.extract(text, max_chars=8000)
        return optimized.replace("\n", " ").replace("\r", " ").strip()

    @staticmethod
    def _cache_key(text: str) -> str:
        """Construct a model-aware cache key for embeddings."""
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        model = settings.EMBEDDING_MODEL or "gemini-embedding-001"
        return f"newsiq:embedding:{model}:{text_hash}"

    async def get_embedding(self, text: str) -> list[float]:
        """Return a single 768-dim embedding vector for the given text.

        Checks Redis cache first, then calls AI Gateway.
        """
        if not text or not text.strip():
            return [0.0] * EMBEDDING_DIM

        clean = self._prepare_text(text)
        cache_enabled = getattr(settings, "EMBEDDING_CACHE_ENABLED", True)

        # Redis Cache Lookup
        if cache_enabled:
            try:
                from app.services.cache_service import cache_service

                key = self._cache_key(clean)
                cached = await cache_service.get(key)
                if cached:
                    logger.debug("Embedding cache HIT for key: %s", key)
                    return cached
            except Exception as e:
                logger.warning("Failed to lookup embedding in cache: %s", e)

        # Call AI Gateway
        from app.ai.gateway import ai_gateway

        try:
            vector = await ai_gateway.embeddings(clean)
        except Exception as exc:
            logger.error("AI Gateway embedding failed: %s", exc)
            raise exc

        # Redis Cache Store
        if cache_enabled:
            try:
                from app.services.cache_service import cache_service

                key = self._cache_key(clean)
                await cache_service.set(key, vector, ttl=30 * 24 * 60 * 60)
            except Exception as e:
                logger.warning("Failed to save embedding to cache: %s", e)

        return vector

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Return 768-dim embeddings for a batch of texts.

        Leverages Redis cache and delegates API calls to AI Gateway.
        """
        if not texts:
            return []

        clean_texts = [self._prepare_text(t) if t else "" for t in texts]

        results: list[list[float] | None] = [None] * len(clean_texts)
        miss_indices: list[int] = []
        miss_texts: list[str] = []

        cache_enabled = getattr(settings, "EMBEDDING_CACHE_ENABLED", True)

        if cache_enabled:
            from app.services.cache_service import cache_service

            for idx, text in enumerate(clean_texts):
                if not text:
                    results[idx] = [0.0] * EMBEDDING_DIM
                    continue
                try:
                    key = self._cache_key(text)
                    cached = await cache_service.get(key)
                    if cached:
                        results[idx] = cached
                    else:
                        miss_indices.append(idx)
                        miss_texts.append(text)
                except Exception as e:
                    logger.warning("Failed to check batch cache: %s", e)
                    miss_indices.append(idx)
                    miss_texts.append(text)
        else:
            for idx, text in enumerate(clean_texts):
                if not text:
                    results[idx] = [0.0] * EMBEDDING_DIM
                else:
                    miss_indices.append(idx)
                    miss_texts.append(text)

        # Fetch cache misses from AI Gateway
        if miss_texts:
            logger.info(
                "Embedding cache miss for %d of %d texts. Fetching from AI Gateway.",
                len(miss_texts),
                len(texts),
            )
            from app.ai.gateway import ai_gateway

            try:
                tasks = [ai_gateway.embeddings(t) for t in miss_texts]
                fetched_vectors = await asyncio.gather(*tasks)
            except Exception as exc:
                logger.error("AI Gateway batch embedding failed: %s", exc)
                raise exc

            # Store results and cache
            for idx, vec in zip(miss_indices, fetched_vectors):
                results[idx] = vec
                if cache_enabled:
                    try:
                        from app.services.cache_service import cache_service

                        key = self._cache_key(clean_texts[idx])
                        await cache_service.set(key, vec, ttl=30 * 24 * 60 * 60)
                    except Exception as e:
                        logger.warning("Failed to store embedding in cache: %s", e)

        return [r for r in results if r is not None]


embedding_service = EmbeddingService()
