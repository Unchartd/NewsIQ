"""Service for interacting with Qdrant vector database."""

import logging
import uuid
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from app.core.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "articles"
DIMENSION = 1536


class VectorService:
    """Vector database service utilizing Qdrant Client."""

    def __init__(self):
        # Initialize async client
        self.client = AsyncQdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            timeout=10.0,
        )
        self._collection_created = False

    async def init_collection(self) -> None:
        """Create the collection if it does not exist."""
        if self._collection_created:
            return

        try:
            # Check if collection exists
            exists = await self.client.collection_exists(collection_name=COLLECTION_NAME)
            if not exists:
                logger.info("Creating Qdrant collection: %s", COLLECTION_NAME)
                await self.client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=models.VectorParams(
                        size=DIMENSION,
                        distance=models.Distance.COSINE,
                    ),
                )
            self._collection_created = True
        except Exception as e:
            logger.error("Failed to initialize Qdrant collection: %s", e)
            raise

    async def upsert_article(
        self, article_id: uuid.UUID, vector: list[float], payload: dict[str, Any]
    ) -> None:
        """Upsert a single article embedding with metadata payload."""
        await self.init_collection()
        try:
            # Convert UUID to string for Qdrant compatibility (Qdrant accepts UUID strings directly as points ID)
            point_id = str(article_id)
            await self.client.upsert(
                collection_name=COLLECTION_NAME,
                points=[
                    models.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload,
                    )
                ],
            )
        except Exception as e:
            logger.error("Failed to upsert article embedding %s: %s", article_id, e)
            raise

    async def search_similar(
        self, vector: list[float], limit: int = 10, score_threshold: float = 0.7
    ) -> list[dict[str, Any]]:
        """Search for similar article vectors."""
        await self.init_collection()
        try:
            results = await self.client.search(
                collection_name=COLLECTION_NAME,
                query_vector=vector,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=True,
            )
            return [
                {
                    "id": uuid.UUID(r.id) if isinstance(r.id, str) else r.id,
                    "score": r.score,
                    "payload": r.payload,
                    "vector": r.vector,
                }
                for r in results
            ]
        except Exception as e:
            logger.error("Failed to search similar vectors in Qdrant: %s", e)
            return []

    async def delete_article(self, article_id: uuid.UUID) -> None:
        """Delete an article vector from Qdrant."""
        await self.init_collection()
        try:
            point_id = str(article_id)
            await self.client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=models.PointIdsList(
                    points=[point_id],
                ),
            )
        except Exception as e:
            logger.error("Failed to delete article embedding %s: %s", article_id, e)


vector_service = VectorService()
