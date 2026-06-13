"""Meilisearch service for indexing and searching stories.

Provides full-text search over story headlines and summaries. Fails open:
if Meilisearch is unreachable, indexing is skipped and callers should fall
back to a PostgreSQL ILIKE query.
"""

import logging
from typing import Any

from meilisearch_python_sdk import AsyncClient

from app.core.config import settings

logger = logging.getLogger(__name__)

INDEX_NAME = "stories"


class SearchService:
    """Async Meilisearch wrapper for story search."""

    def __init__(self) -> None:
        self._client: AsyncClient | None = None
        self._index_ready = False
        if settings.MEILISEARCH_URL:
            try:
                self._client = AsyncClient(
                    settings.MEILISEARCH_URL, settings.MEILISEARCH_API_KEY or None
                )
            except Exception as e:  # pragma: no cover
                logger.error("Failed to initialize Meilisearch client: %s", e)

    @property
    def enabled(self) -> bool:
        return self._client is not None

    async def init_index(self) -> None:
        """Create the stories index and configure searchable/filterable attributes."""
        if not self._client or self._index_ready:
            return
        try:
            index = self._client.index(INDEX_NAME)
            await index.update_searchable_attributes(
                ["headline", "one_line_summary", "short_summary", "detailed_summary", "tags"]
            )
            await index.update_filterable_attributes(
                ["category_slug", "location_country", "story_status"]
            )
            await index.update_sortable_attributes(["trend_score", "updated_at"])
            self._index_ready = True
            logger.info("Meilisearch index '%s' configured.", INDEX_NAME)
        except Exception as e:
            logger.warning("Could not initialize Meilisearch index: %s", e)

    async def index_story(self, document: dict[str, Any]) -> None:
        """Add or update a single story document in the index."""
        if not self._client:
            return
        try:
            await self.init_index()
            await self._client.index(INDEX_NAME).add_documents([document])
        except Exception as e:
            logger.warning("Failed to index story %s: %s", document.get("id"), e)

    async def delete_story(self, story_id: str) -> None:
        """Remove a story from the index."""
        if not self._client:
            return
        try:
            await self._client.index(INDEX_NAME).delete_document(story_id)
        except Exception as e:
            logger.warning("Failed to delete story %s from index: %s", story_id, e)

    async def search(
        self,
        query: str,
        category: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[str] | None:
        """Search stories and return matching story IDs (ranked).

        Returns None if Meilisearch is unavailable so the caller can fall back
        to a PostgreSQL query.
        """
        if not self._client:
            return None
        try:
            await self.init_index()
            filters = f"category_slug = {category}" if category else None
            result = await self._client.index(INDEX_NAME).search(
                query,
                limit=limit,
                offset=offset,
                filter=filters,
                sort=["trend_score:desc"],
            )
            return [hit["id"] for hit in result.hits]
        except Exception as e:
            logger.warning("Meilisearch query failed for '%s': %s", query, e)
            return None


def build_story_document(story: Any, category_slug: str | None, tags: list[str]) -> dict[str, Any]:
    """Build a Meilisearch document from a Story ORM object."""
    return {
        "id": str(story.id),
        "headline": story.headline or "",
        "one_line_summary": story.one_line_summary or "",
        "short_summary": story.short_summary or "",
        "detailed_summary": story.detailed_summary or "",
        "tags": tags,
        "category_slug": category_slug or "",
        "location_country": story.location_country or "",
        "story_status": story.story_status or "active",
        "trend_score": float(story.trend_score) if story.trend_score is not None else 0.0,
        "updated_at": story.updated_at.isoformat() if story.updated_at else None,
    }


search_service = SearchService()
