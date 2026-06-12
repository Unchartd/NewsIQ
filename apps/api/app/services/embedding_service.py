"""Service for generating high-quality text embeddings using OpenAI or fallback."""

import hashlib
import logging
from typing import List

import numpy as np
from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service to handle vector embeddings generation."""

    def __init__(self):
        self.client = None
        if settings.OPENAI_API_KEY:
            self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        else:
            logger.warning(
                "OPENAI_API_KEY is not set. Embedding service will run in fallback mock mode (1536 dims)."
            )

    def _generate_mock_embedding(self, text: str, dimensions: int = 1536) -> List[float]:
        """Generate a deterministic mock embedding vector based on SHA-256 hash of the input text."""
        # Use SHA-256 to hash the input text
        hasher = hashlib.sha256(text.encode("utf-8"))
        hash_bytes = hasher.digest()
        
        # Seed a pseudo-random generator with the hash bytes to ensure determinism
        seed = int.from_bytes(hash_bytes[:4], byteorder="big")
        rng = np.random.default_rng(seed)
        
        # Generate random values and normalize the vector to unit length
        vector = rng.standard_normal(dimensions)
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
            
        return vector.tolist()

    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding vector for a given text.
        
        Uses OpenAI text-embedding-3-small (1536 dimensions) if API key is set,
        otherwise falls back to generating a deterministic mock vector.
        """
        if not text or not text.strip():
            # Return zero vector for empty text
            return [0.0] * 1536

        if self.client:
            try:
                # Clean up text to avoid token issues
                clean_text = text.replace("\n", " ").strip()
                response = await self.client.embeddings.create(
                    input=[clean_text],
                    model=settings.EMBEDDING_MODEL
                )
                return response.data[0].embedding
            except Exception as e:
                logger.error("OpenAI embedding generation failed: %s. Falling back to mock.", e)
                # Fall through to mock on error
        
        return self._generate_mock_embedding(text)

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for a list of texts in batch."""
        if not texts:
            return []

        if self.client:
            try:
                clean_texts = [t.replace("\n", " ").strip() if t else "" for t in texts]
                response = await self.client.embeddings.create(
                    input=clean_texts,
                    model=settings.EMBEDDING_MODEL
                )
                return [item.embedding for item in response.data]
            except Exception as e:
                logger.error("OpenAI batch embedding generation failed: %s. Falling back to mock.", e)
                # Fall through to mock on error
        
        return [self._generate_mock_embedding(t) for t in texts]


embedding_service = EmbeddingService()
