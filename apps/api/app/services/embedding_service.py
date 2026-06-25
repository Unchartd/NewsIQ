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
        return text.replace("\n", " ").replace("\r", " ").strip()[:8000]

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

            results = []
            for text in texts:
                max_retries = 5
                backoff = 2.0
                raw_val = None
                for attempt in range(max_retries):
                    try:
                        response = client.models.embed_content(
                            model=model,
                            contents=text,
                            config={"task_type": "RETRIEVAL_DOCUMENT"},
                        )
                        raw_val = response.embeddings[0].values
                        break
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

                if raw_val is None:
                    raise RuntimeError("Failed to retrieve embedding values after retries.")

                # Truncate and normalize to EMBEDDING_DIM (768)
                vec = np.array(raw_val[:EMBEDDING_DIM], dtype=np.float32)
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec /= norm
                results.append(vec.tolist())
            return results

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

    async def get_embedding(self, text: str) -> list[float]:
        """Return a single 768-dim embedding vector for the given text.

        Fallback chain: Gemini → OpenAI → Raise error.
        """
        if not text or not text.strip():
            return [0.0] * EMBEDDING_DIM

        clean = self._prepare_text(text)

        if self.gemini_enabled:
            try:
                vectors = await self._embed_with_gemini([clean])
                return vectors[0]
            except Exception as exc:
                logger.error("Gemini embedding failed: %s — trying OpenAI fallback.", exc)
                if not self.openai_enabled:
                    raise exc

        if self.openai_enabled and self._openai_client:
            try:
                vectors = await self._embed_with_openai([clean])
                return vectors[0]
            except Exception as exc:
                logger.error("OpenAI embedding failed: %s — raising error.", exc)
                raise exc

        raise RuntimeError(
            "No embedding providers configured or enabled (Gemini and OpenAI are both disabled)."
        )

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Return 768-dim embeddings for a batch of texts.

        Gemini processes all texts individually (no native batch endpoint in
        text-embedding-004). Falls back per-item on error.
        """
        if not texts:
            return []

        clean_texts = [self._prepare_text(t) if t else "" for t in texts]

        if self.gemini_enabled:
            try:
                return await self._embed_with_gemini(clean_texts)
            except Exception as exc:
                logger.error("Gemini batch embedding failed: %s — trying OpenAI.", exc)
                if not self.openai_enabled:
                    raise exc

        if self.openai_enabled and self._openai_client:
            try:
                return await self._embed_with_openai(clean_texts)
            except Exception as exc:
                logger.error("OpenAI batch embedding failed: %s — raising error.", exc)
                raise exc

        raise RuntimeError(
            "No embedding providers configured or enabled (Gemini and OpenAI are both disabled)."
        )


embedding_service = EmbeddingService()
