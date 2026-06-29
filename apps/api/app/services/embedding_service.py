"""Embedding service — Gemini text-embedding-004 (primary) with OpenAI fallback.

Uses the new google.genai SDK (google-genai>=1.16.0).

Dimension: 768 (Gemini text-embedding-004)

Priority:
    1. Google Gemini text-embedding-004  (uses GEMINI_API_KEY)
    2. OpenAI text-embedding-3-small     (uses OPENAI_API_KEY, truncated to 768 dims)
    3. Deterministic mock                (hash-seeded, 768 dims — for local dev only)

The mock is NEVER used in production — real clustering requires real embeddings.
"""

import hashlib
import logging

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

# Canonical embedding dimension for the entire pipeline.
# text-embedding-004 produces 768-dim vectors.
# Changing this requires dropping and recreating the Qdrant collection
# (vector_service.py handles this automatically on startup).
EMBEDDING_DIM = 768


class EmbeddingService:
    """Generates text embeddings using Gemini text-embedding-004 (primary) or OpenAI (fallback)."""

    def __init__(self) -> None:
        # ── Gemini setup (new google.genai SDK) ───────────────────────────────
        self.gemini_enabled = False
        self._genai_client = None
        api_key = settings.GEMINI_API_KEY_EMBEDDING or settings.GEMINI_API_KEY
        if api_key:
            try:
                from google import genai as google_genai

                self._genai_client = google_genai.Client(api_key=api_key)
                self.gemini_enabled = True
                logger.info(
                    "Gemini embedding model configured: %s (%d dims)",
                    settings.EMBEDDING_MODEL,
                    EMBEDDING_DIM,
                )
            except ImportError:
                logger.error(
                    "google-genai package not installed. Run: pip install google-genai>=1.16.0"
                )
            except Exception as exc:
                logger.error("Failed to configure Gemini embedding client: %s", exc)
        else:
            logger.warning(
                "GEMINI_API_KEY_EMBEDDING or GEMINI_API_KEY not set — Gemini embeddings disabled."
            )

        # ── OpenAI fallback ────────────────────────────────────────────────────
        self.openai_enabled = False
        self._openai_client = None
        if settings.OPENAI_API_KEY:
            try:
                from openai import AsyncOpenAI

                self._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                self.openai_enabled = True
                logger.info("OpenAI embedding fallback configured.")
            except Exception as exc:
                logger.error("Failed to configure OpenAI for embeddings: %s", exc)
        else:
            logger.debug("OPENAI_API_KEY not set — OpenAI embedding fallback disabled.")

        if not self.gemini_enabled and not self.openai_enabled:
            logger.warning(
                "No embedding API key configured. "
                "Using deterministic mock embeddings (768 dims). "
                "Semantic clustering will NOT work correctly. "
                "Set GEMINI_API_KEY to enable real embeddings."
            )

    # ── Private helpers ────────────────────────────────────────────────────────

    def _mock_embedding(self, text: str) -> list[float]:
        """Deterministic 768-dim mock embedding seeded from SHA-256 of text.

        Unit-normalized — consistent across restarts. Only for local dev.
        """
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        seed = int.from_bytes(digest[:4], byteorder="big")
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(EMBEDDING_DIM)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec.tolist()

    @staticmethod
    def _prepare_text(text: str) -> str:
        """Normalize and truncate text before embedding.

        text-embedding-004 supports ~2048 tokens (≈ 8000 chars).
        """
        if not text:
            return ""
        from app.services.context_extractor import context_extractor
        # Extract optimized paragraph-aware context up to 8000 chars first
        optimized = context_extractor.extract(text, max_chars=8000)
        return optimized.replace("\n", " ").replace("\r", " ").strip()

    # ── Gemini embedding (new google.genai SDK) ────────────────────────────────

    async def _embed_with_gemini(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts using gemini-embedding-001 (3072 dims), truncating to EMBEDDING_DIM.

        The new google.genai SDK's embed_content is synchronous — we run it in
        a thread pool to avoid blocking the event loop.

        task_type=RETRIEVAL_DOCUMENT optimises vectors for similarity retrieval.
        """
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        client = self._genai_client
        # Use the model specified in config (gemini-embedding-001 = 3072 dims)
        model = settings.EMBEDDING_MODEL or "gemini-embedding-001"

        def _call_sync() -> list[list[float]]:
            import time

            max_retries = 5
            backoff = 2.0
            for attempt in range(max_retries):
                try:
                    response = client.models.embed_content(
                        model=model,
                        contents=texts,
                        config={"task_type": "RETRIEVAL_DOCUMENT"},
                    )

                    results = []
                    for emb in response.embeddings:
                        raw_val = emb.values
                        # Truncate and normalize to EMBEDDING_DIM (768)
                        vec = np.array(raw_val[:EMBEDDING_DIM], dtype=np.float32)
                        norm = np.linalg.norm(vec)
                        if norm > 0:
                            vec /= norm
                        results.append(vec.tolist())
                    return results
                except Exception as err:
                    err_str = str(err).lower()
                    is_rate_limit = (
                        "429" in err_str
                        or "quota" in err_str
                        or "exhausted" in err_str
                        or "resource_exhausted" in err_str
                    )
                    if is_rate_limit and attempt < max_retries - 1:
                        logger.warning(
                            "Gemini embedding hit rate limit. Retrying in %.1fs (attempt %d/%d). Error: %s",
                            backoff,
                            attempt + 1,
                            max_retries,
                            err,
                        )
                        time.sleep(backoff)
                        backoff *= 2.0
                    else:
                        raise err
            raise RuntimeError("Failed to retrieve embedding values after retries.")

        # Use get_running_loop() — safe in both FastAPI and Celery worker contexts
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            return await loop.run_in_executor(executor, _call_sync)

    # ── OpenAI fallback embedding ──────────────────────────────────────────────

    async def _embed_with_openai(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using OpenAI, truncating output to EMBEDDING_DIM (768)."""
        response = await self._openai_client.embeddings.create(
            input=texts,
            model=settings.EMBEDDING_MODEL,
        )
        result = []
        for item in response.data:
            vec = np.array(item.embedding[:EMBEDDING_DIM], dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            result.append(vec.tolist())
        return result

    # ── Public API ─────────────────────────────────────────────────────────────

    @staticmethod
    def _cache_key(text: str) -> str:
        """Construct a model-aware cache key for embeddings."""
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        model = settings.EMBEDDING_MODEL or "gemini-embedding-001"
        return f"newsiq:embedding:{model}:{text_hash}"

    async def get_embedding(self, text: str) -> list[float]:
        """Return a single 768-dim embedding vector for the given text.

        Checks Redis cache first. Fallback chain: Gemini → OpenAI → Raise error.
        """
        if not text or not text.strip():
            return [0.0] * EMBEDDING_DIM

        clean = self._prepare_text(text)
        cache_enabled = getattr(settings, "EMBEDDING_CACHE_ENABLED", True)

        # ── Redis Cache Lookup ──
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

        vector: list[float] | None = None

        if self.gemini_enabled:
            try:
                vectors = await self._embed_with_gemini([clean])
                vector = vectors[0]
            except Exception as exc:
                logger.error("Gemini embedding failed: %s — trying OpenAI fallback.", exc)
                if not self.openai_enabled:
                    raise exc

        if not vector and self.openai_enabled and self._openai_client:
            try:
                vectors = await self._embed_with_openai([clean])
                vector = vectors[0]
            except Exception as exc:
                logger.error("OpenAI embedding failed: %s — raising error.", exc)
                raise exc

        if not vector:
            raise RuntimeError(
                "No embedding providers configured or enabled (Gemini and OpenAI are both disabled)."
            )

        # ── Redis Cache Store ──
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

        Leverages Redis cache for both looking up cached entries and storing
        newly generated embeddings. Only queries the provider API for cache misses.
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

        # Fetch cache misses from provider APIs
        if miss_texts:
            logger.info("Embedding cache miss for %d of %d texts. Fetching from API.", len(miss_texts), len(texts))
            fetched_vectors: list[list[float]] = []

            if self.gemini_enabled:
                try:
                    fetched_vectors = await self._embed_with_gemini(miss_texts)
                except Exception as exc:
                    logger.error("Gemini batch embedding failed: %s — trying OpenAI.", exc)
                    if not self.openai_enabled:
                        raise exc

            if not fetched_vectors and self.openai_enabled and self._openai_client:
                try:
                    fetched_vectors = await self._embed_with_openai(miss_texts)
                except Exception as exc:
                    logger.error("OpenAI batch embedding failed: %s — raising error.", exc)
                    raise exc

            if not fetched_vectors:
                raise RuntimeError(
                    "No embedding providers configured or enabled, or all providers failed."
                )

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
