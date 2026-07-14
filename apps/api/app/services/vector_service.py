"""Qdrant vector database service for article embeddings.

Collection: "articles"
Dimensions: 3072 (gemini-embedding-001)
Distance:   Cosine

On startup the service checks the live collection config. If the dimension
does not match EMBEDDING_DIM (e.g. old 768-dim or 1536-dim collection exists),
the collection is recreated automatically. This is safe because the real article
data is in PostgreSQL — Qdrant only stores the vectors.
"""

import asyncio
import logging
import uuid
from typing import Any, cast

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from app.core.config import settings
from app.services.embedding_service import EMBEDDING_DIM

logger = logging.getLogger(__name__)

COLLECTION_NAME = "articles"


class VectorService:
    """Async Qdrant client wrapper with collection lifecycle management."""

    def __init__(self) -> None:
        self._clients: dict[int, AsyncQdrantClient] = {}
        self._collection_ready = False
        self._mock_client: AsyncQdrantClient | None = None

    @property
    def client(self) -> AsyncQdrantClient:
        if self._mock_client is not None:
            return self._mock_client
        try:
            loop = asyncio.get_running_loop()
            loop_id = id(loop)
        except RuntimeError:
            loop_id = 0

        if loop_id not in self._clients:
            self._clients[loop_id] = AsyncQdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                timeout=30,
            )
        return self._clients[loop_id]

    @client.setter
    def client(self, value: AsyncQdrantClient) -> None:
        self._mock_client = value

    @client.deleter
    def client(self) -> None:
        self._mock_client = None

    # ── Collection management ─────────────────────────────────────────────────

    async def init_collection(self) -> None:
        """Ensure the articles collection exists with the correct configuration.

        If a collection exists but has the wrong dimension (e.g., legacy 1536
        from the mock OpenAI setup), it is dropped and recreated.
        """
        if self._collection_ready:
            return

        try:
            exists = await self.client.collection_exists(collection_name=COLLECTION_NAME)

            if exists:
                info = await self.client.get_collection(collection_name=COLLECTION_NAME)
                live_dim = info.config.params.vectors.size  # type: ignore[union-attr]
                if live_dim != EMBEDDING_DIM:
                    logger.warning(
                        "Qdrant collection '%s' has dimension %d but pipeline requires %d. "
                        "Dropping and recreating — all embeddings will be regenerated.",
                        COLLECTION_NAME,
                        live_dim,
                        EMBEDDING_DIM,
                    )
                    await self.client.delete_collection(collection_name=COLLECTION_NAME)
                    exists = False

            if not exists:
                logger.info(
                    "Creating Qdrant collection '%s' with %d-dim Cosine vectors.",
                    COLLECTION_NAME,
                    EMBEDDING_DIM,
                )
                await self.client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=models.VectorParams(
                        size=EMBEDDING_DIM,
                        distance=models.Distance.COSINE,
                    ),
                    # Payload indexes for efficient filtering
                    optimizers_config=models.OptimizersConfigDiff(
                        indexing_threshold=20_000,
                    ),
                )
                # Index payload fields used in filtered searches
                await self.client.create_payload_index(
                    collection_name=COLLECTION_NAME,
                    field_name="published_at",
                    field_schema=models.PayloadSchemaType.DATETIME,
                )
                await self.client.create_payload_index(
                    collection_name=COLLECTION_NAME,
                    field_name="source_id",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )

            self._collection_ready = True
            logger.info("Qdrant collection '%s' is ready.", COLLECTION_NAME)

        except Exception as exc:
            logger.error("Failed to initialize Qdrant collection: %s", exc)
            raise

    # ── Write operations ──────────────────────────────────────────────────────

    async def upsert_article(
        self,
        article_id: uuid.UUID,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        """Insert or update a single article embedding with metadata."""
        await self.init_collection()
        try:
            await self.client.upsert(
                collection_name=COLLECTION_NAME,
                points=[
                    models.PointStruct(
                        id=str(article_id),
                        vector=vector,
                        payload=payload,
                    )
                ],
            )
        except Exception as exc:
            logger.error("Qdrant upsert failed for article %s: %s", article_id, exc)
            raise

    async def upsert_articles_batch(
        self,
        items: list[tuple[uuid.UUID, list[float], dict[str, Any]]],
    ) -> None:
        """Batch-upsert multiple article embeddings in a single Qdrant call.

        Args:
            items: List of (article_id, vector, payload) tuples.
        """
        if not items:
            return
        await self.init_collection()
        try:
            points = [
                models.PointStruct(id=str(aid), vector=vec, payload=pl) for aid, vec, pl in items
            ]
            await self.client.upsert(
                collection_name=COLLECTION_NAME,
                points=points,
            )
            logger.debug("Batch-upserted %d article vectors.", len(points))
        except Exception as exc:
            logger.error("Qdrant batch upsert failed: %s", exc)
            raise

    async def delete_article(self, article_id: uuid.UUID) -> None:
        """Remove an article's vector from Qdrant."""
        await self.init_collection()
        try:
            await self.client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=models.PointIdsList(points=[str(article_id)]),
            )
        except Exception as exc:
            logger.error("Qdrant delete failed for article %s: %s", article_id, exc)

    # ── Read operations ───────────────────────────────────────────────────────

    async def search_similar(
        self,
        vector: list[float],
        limit: int = 10,
        score_threshold: float = 0.70,
        published_after: str | None = None,
    ) -> list[dict[str, Any]]:
        """Find articles with similar embeddings using cosine similarity.

        Args:
            vector:           Query vector (768 dims).
            limit:            Maximum number of results to return.
            score_threshold:  Minimum cosine similarity (0.0–1.0).
            published_after:  ISO 8601 datetime string for recency filtering.
        """
        await self.init_collection()
        try:
            query_filter = None
            if published_after:
                query_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="published_at",
                            range=models.DatetimeRange(gte=published_after),
                        )
                    ]
                )

            # qdrant-client >= 1.7 uses query_points() instead of the deprecated search()
            response = await self.client.query_points(
                collection_name=COLLECTION_NAME,
                query=vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=query_filter,
                with_payload=True,
                with_vectors=True,
            )
            results = response.points  # QueryResponse.points = list[ScoredPoint]
            return [
                {
                    "id": uuid.UUID(r.id) if isinstance(r.id, str) else r.id,
                    "score": r.score,
                    "payload": r.payload,
                    "vector": r.vector,
                }
                for r in results
            ]
        except Exception as exc:
            logger.error("Qdrant similarity search failed: %s", exc)
            return []

    async def retrieve_vectors(self, article_ids: list[str]) -> dict[str, list[float]]:
        """Retrieve vectors for a list of article IDs.

        Returns a dict mapping article_id_str → vector, containing only
        IDs that have vectors in Qdrant.
        """
        await self.init_collection()
        if not article_ids:
            return {}
        try:
            points = await self.client.retrieve(
                collection_name=COLLECTION_NAME,
                ids=article_ids,
                with_vectors=True,
                with_payload=False,
            )
            return {str(p.id): cast(list[float], p.vector) for p in points if p.vector}
        except Exception as exc:
            logger.error("Qdrant retrieve failed: %s", exc)
            return {}


vector_service = VectorService()
