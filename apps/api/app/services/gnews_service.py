"""GNews ingestion service — fetches articles from GNews API and stores them.

Rate-limit guard:
  - A Redis key "gnews:lock:{category}:{country}" with TTL=25min prevents
    re-fetching the same category+country before the next scheduled run.
  - On Redis unavailability, fetching proceeds (fail-open).

Deduplication:
  - Primary: URL exact match (same as RSS ingestion)
  - Secondary: gnews_source_name fuzzy match against our sources registry
    to resolve the correct source_id without manual mapping.
"""

import logging
import re
from datetime import UTC, datetime

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.utils import canonicalize_url
from app.ingestion.gnews_client import DEFAULT_CATEGORIES, DEFAULT_COUNTRIES, gnews_client
from app.models.models import Article, Source

logger = logging.getLogger(__name__)

# Redis TTL for per-category+country fetch lock (25 min — slightly under 30-min schedule)
GNEWS_LOCK_TTL_SECONDS = 25 * 60


class GNewsService:
    """Orchestrates GNews article fetching, source resolution, and persistence."""

    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None
        if settings.REDIS_URL:
            try:
                self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            except Exception as exc:
                logger.warning("GNewsService: could not connect to Redis: %s", exc)

    # ── Redis rate-limit guard ─────────────────────────────────────────────────

    async def _is_locked(self, category: str, country: str) -> bool:
        """Return True if this category+country was fetched recently."""
        if not self._redis:
            return False
        key = f"gnews:lock:{category}:{country}"
        try:
            return await self._redis.exists(key) == 1
        except Exception:
            return False

    async def _set_lock(self, category: str, country: str) -> None:
        """Set a rate-limit lock key so we skip the next fetch within 25 min."""
        if not self._redis:
            return
        key = f"gnews:lock:{category}:{country}"
        try:
            await self._redis.set(key, "1", ex=GNEWS_LOCK_TTL_SECONDS)
        except Exception as exc:
            logger.debug("Could not set GNews lock in Redis: %s", exc)

    # ── Source resolution ──────────────────────────────────────────────────────

    @staticmethod
    def _slugify(name: str) -> str:
        """Convert a source name to a slug for fuzzy matching."""
        return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

    async def _resolve_source(
        self,
        gnews_source_name: str | None,
        gnews_source_url: str | None,
        session: AsyncSession,
    ) -> Source | None:
        """Find the best matching Source record for a GNews article.

        Strategy:
        1. Exact name match (case-insensitive)
        2. Slug match derived from gnews_source_name
        3. Domain match from gnews_source_url vs Source.website_url
        4. Create a new Source record if nothing matches (enables auto-discovery)
        """
        if not gnews_source_name:
            return None

        name_clean = gnews_source_name.strip()

        # 1. Exact name match
        res = await session.execute(
            select(Source).where(Source.name.ilike(name_clean))
        )
        source = res.scalar_one_or_none()
        if source:
            return source

        # 2. Slug match
        candidate_slug = self._slugify(name_clean)
        res = await session.execute(
            select(Source).where(Source.slug == candidate_slug)
        )
        source = res.scalar_one_or_none()
        if source:
            return source

        # 3. Domain match from URL
        if gnews_source_url:
            domain = re.sub(r"https?://(www\.)?", "", gnews_source_url).rstrip("/")
            res = await session.execute(
                select(Source).where(Source.website_url.ilike(f"%{domain}%"))
            )
            source = res.scalar_one_or_none()
            if source:
                return source

        # 4. Auto-create a new Source (GNews surfaces publishers we don't have seeded)
        logger.info("GNews: auto-creating new source: '%s'", name_clean)
        new_source = Source(
            name=name_clean,
            slug=candidate_slug,
            website_url=gnews_source_url,
            logo_url=None,
            country_code="US",  # Default; will be refined if we get country context
            rss_url=None,
            active=True,
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
        session.add(new_source)
        try:
            await session.flush()  # Get the ID without committing
        except Exception as exc:
            await session.rollback()
            logger.warning("Failed to auto-create source '%s': %s", name_clean, exc)
            return None
        return new_source

    # ── Ingestion orchestration ────────────────────────────────────────────────

    async def ingest_category(
        self,
        category: str,
        country: str,
        session: AsyncSession,
    ) -> int:
        """Fetch and store GNews articles for one category+country combination.

        Returns the number of new articles inserted.
        """
        if not gnews_client.enabled:
            return 0

        # Rate-limit guard
        if await self._is_locked(category, country):
            logger.debug(
                "GNews: skipping %s/%s — fetched recently, lock active.", category, country
            )
            return 0

        articles_data = await gnews_client.fetch_top_headlines(
            category=category,
            country=country,
        )

        if not articles_data:
            return 0

        new_count = 0
        for art_dict in articles_data:
            raw_url = art_dict.get("url", "").strip()
            if not raw_url:
                continue
            url = canonicalize_url(raw_url)

            # URL deduplication
            res = await session.execute(select(Article).where(Article.url == url))
            if res.scalar_one_or_none():
                continue

            # Resolve source
            source = await self._resolve_source(
                gnews_source_name=art_dict.get("gnews_source_name"),
                gnews_source_url=art_dict.get("gnews_source_url"),
                session=session,
            )
            if not source:
                logger.debug("GNews: skipping article with no resolvable source: %s", url)
                continue

            article = Article(
                source_id=source.id,
                title=art_dict["title"],
                description=art_dict["description"],
                content=art_dict["content"],
                url=url,
                author=art_dict.get("author"),
                language=art_dict.get("language", "en"),
                image_url=art_dict.get("image_url"),
                published_at=art_dict["published_at"],
                crawled_at=datetime.now(UTC).replace(tzinfo=None),
                embedding_status="pending",
                created_at=datetime.now(UTC).replace(tzinfo=None),
            )
            session.add(article)
            new_count += 1

        if new_count > 0:
            try:
                await session.commit()
                logger.info(
                    "GNews: inserted %d new articles for %s/%s", new_count, category, country
                )
            except Exception as exc:
                await session.rollback()
                logger.error(
                    "GNews: failed to commit articles for %s/%s: %s", category, country, exc
                )
                return 0

        # Set lock to prevent duplicate fetches within the guard window
        await self._set_lock(category, country)
        return new_count

    async def ingest_all(self, session: AsyncSession) -> dict[str, int]:
        """Run GNews ingestion for all configured category × country combinations.

        Returns a dict mapping "{category}/{country}" → articles_inserted.
        """
        results: dict[str, int] = {}
        for category in DEFAULT_CATEGORIES:
            for country in DEFAULT_COUNTRIES:
                key = f"{category}/{country}"
                count = await self.ingest_category(category, country, session)
                results[key] = count
        total = sum(results.values())
        logger.info("GNews ingestion complete: %d new articles across %d feeds.", total, len(results))
        return results


gnews_service = GNewsService()
