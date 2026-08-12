"""Qdrant vector database service for article embeddings.

Collection: "articles"
Dimensions: 768 (EMBEDDING_DIM)
Distance:   Cosine

Qdrant normalizes vectors on write when the distance is Cosine, so vectors read
back from here are unit length regardless of what the provider supplied.

On startup the service checks the live collection config. If the dimension does
not match EMBEDDING_DIM, the collection is dropped and recreated. This is safe
because the authoritative article data is in PostgreSQL — Qdrant only stores
the vectors — but it does mean every article must be re-embedded afterwards.
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
        # Keyed by id(loop); stores the loop itself so a recycled address
        # cannot hand back a client bound to a dead loop.
        self._clients: dict[int, tuple[Any, AsyncQdrantClient]] = {}
        self._collection_ready = False
        # One-shot per process: the collection's embedding model cannot change
        # under us without a redeploy or an explicit re-embed.
        self._space_checked = False
        self._mock_client: AsyncQdrantClient | None = None

    @property
    def client(self) -> AsyncQdrantClient:
        if self._mock_client is not None:
            return self._mock_client
        try:
            loop: Any = asyncio.get_running_loop()
            loop_id = id(loop)
        except RuntimeError:
            loop, loop_id = None, 0

        entry = self._clients.get(loop_id)
        if entry is not None:
            cached_loop, cached_client = entry
            if cached_loop is loop:
                return cached_client
            self._clients.pop(loop_id, None)

        client = AsyncQdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            timeout=30,
        )
        self._clients[loop_id] = (loop, client)
        return client

    # Setter/deleter must stay directly adjacent to the getter — an intervening
    # definition breaks the property association (mypy: "Name already defined").
    @client.setter
    def client(self, value: AsyncQdrantClient) -> None:
        self._mock_client = value

    @client.deleter
    def client(self) -> None:
        self._mock_client = None

    async def close_current_loop(self) -> None:
        """Close and forget the Qdrant client bound to the running event loop.

        Celery's run_async() creates a loop per task; without this every task
        strands an HTTP connection pool. Must be awaited inside the loop being
        torn down. Never raises.
        """
        if self._mock_client is not None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        entry = self._clients.pop(id(loop), None)
        if entry is None:
            return
        try:
            await entry[1].close()
        except Exception as e:
            logger.debug("VectorService: error closing Qdrant client: %s", e)
        # Collection readiness is per-client, not global — re-check on the next client.
        self._collection_ready = False

    @property
    def pool_count(self) -> int:
        """Number of live per-loop clients. Exposed for leak monitoring."""
        return len(self._clients)

    async def close(self) -> None:
        """Close all initialized Qdrant clients to prevent socket leaks."""
        for _, client in list(self._clients.values()):
            try:
                await client.close()
            except Exception as e:
                logger.warning("Error closing AsyncQdrantClient: %s", e)
        self._clients.clear()
        self._collection_ready = False

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

    async def _assert_embedding_space(self, payload: dict[str, Any]) -> None:
        """Refuse to mix embedding models within the shared collection.

        Vectors from different models are not comparable — the same sentence
        scores cosine 0.02 across two candidate models versus 0.84-0.92 for
        different paraphrases within one model, while Stage B matches at ~0.67.
        Writing a second model's vectors into this collection therefore
        silently produces articles that can never cluster.

        The check samples one existing point's recorded model. Mismatch raises
        rather than warns: a poisoned collection is only recoverable by a full
        re-embed (app/scripts/reembed_corpus.py), so it must not start.
        """
        incoming = payload.get("embedding_model")
        if not incoming or self._space_checked:
            return

        # Query points that actually CARRY provenance. Sampling arbitrary points
        # is not enough: vectors written before `embedding_model` was recorded
        # have no such field, and a sample of those would let a model switch
        # through silently — which is how a first version of this guard passed
        # its source-level test while failing against a real collection.
        try:
            points, _ = await self.client.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="embedding_model",
                            match=models.MatchExcept(**{"except": [incoming]}),
                        )
                    ]
                ),
                limit=1,
                with_payload=True,
                with_vectors=False,
            )
        except Exception as exc:  # collection missing, or filter unsupported
            logger.debug("Embedding-space check skipped: %s", exc)
            self._space_checked = True
            return

        self._space_checked = True
        if points:
            existing = (points[0].payload or {}).get("embedding_model")
            raise ValueError(
                f"Refusing to write '{incoming}' vectors into a collection that already "
                f"contains '{existing}' vectors. Mixing embedding models makes cosine "
                "similarity meaningless and silently breaks clustering. Re-embed the "
                "corpus first: python -m app.scripts.reembed_corpus"
            )

    async def upsert_article(
        self,
        article_id: uuid.UUID,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        """Insert or update a single article embedding with metadata."""
        await self.init_collection()
        await self._assert_embedding_space(payload)
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
