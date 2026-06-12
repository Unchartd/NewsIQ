"""Service for ingesting news articles from RSS feeds and other news APIs."""

import asyncio
from datetime import datetime, timezone
import logging
import time
from typing import Any

from bs4 import BeautifulSoup
import feedparser
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Article, Source

logger = logging.getLogger(__name__)


class IngestionService:
    """Ingestion service to fetch, normalize, and deduplicate news articles."""

    @staticmethod
    def clean_html(html_content: str | None) -> str:
        """Strip HTML tags and clean up whitespace."""
        if not html_content:
            return ""
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            return soup.get_text(separator=" ", strip=True)
        except Exception as e:
            logger.warning("Failed to clean HTML content: %s", e)
            return html_content

    @staticmethod
    def parse_pub_date(entry: Any) -> datetime:
        """Parse publication date from RSS entry, fallback to current time."""
        for field in ("published_parsed", "updated_parsed", "created_parsed"):
            parsed = getattr(entry, field, None)
            if parsed:
                try:
                    return datetime.fromtimestamp(time.mktime(parsed), tz=timezone.utc).replace(tzinfo=None)
                except Exception:
                    pass
        return datetime.utcnow()

    async def ingest_rss_source(self, source: Source, session: AsyncSession) -> int:
        """Ingest articles from a source's RSS feed."""
        if not source.rss_url:
            logger.warning("Source '%s' does not have an RSS URL.", source.name)
            return 0

        logger.info("Starting ingestion for source: %s (%s)", source.name, source.rss_url)
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(source.rss_url)
                response.raise_for_status()
                feed_data = response.text
        except Exception as e:
            logger.error("Failed to fetch RSS feed for '%s': %s", source.name, e)
            return 0

        # Parse the RSS feed using feedparser (which parses the text directly)
        parsed_feed = feedparser.parse(feed_data)
        new_articles_count = 0

        for entry in parsed_feed.entries:
            url = getattr(entry, "link", None)
            if not url:
                continue

            # Deduplication: Check if article with this URL already exists
            stmt = select(Article).where(Article.url == url)
            res = await session.execute(stmt)
            if res.scalar_one_or_none():
                continue

            title = getattr(entry, "title", "Untitled Article")
            description = self.clean_html(getattr(entry, "summary", ""))
            content = self.clean_html(getattr(entry, "content", [{"value": ""}])[0].get("value", ""))
            if not content:
                content = description  # Fallback

            author = getattr(entry, "author", None)
            published_at = self.parse_pub_date(entry)

            # Extract image if available in enclosures or media:content
            image_url = None
            if hasattr(entry, "enclosures"):
                for enc in entry.enclosures:
                    if enc.get("type", "").startswith("image/"):
                        image_url = enc.get("href")
                        break
            if not image_url and hasattr(entry, "media_content"):
                for media in entry.media_content:
                    if media.get("medium") == "image" or "image" in media.get("type", ""):
                        image_url = media.get("url")
                        break

            article = Article(
                source_id=source.id,
                title=title,
                description=description,
                content=content,
                url=url,
                author=author,
                language="en",
                image_url=image_url,
                published_at=published_at,
                crawled_at=datetime.utcnow(),
                embedding_status="pending",
                created_at=datetime.utcnow(),
            )
            session.add(article)
            new_articles_count += 1

        if new_articles_count > 0:
            try:
                await session.commit()
                logger.info("Ingested %d new articles for source '%s'", new_articles_count, source.name)
            except Exception as e:
                await session.rollback()
                logger.error("Failed to save ingested articles for '%s': %s", source.name, e)
                return 0
        else:
            logger.info("No new articles found for '%s'", source.name)

        return new_articles_count

    async def ingest_all_active_sources(self, session: AsyncSession) -> dict[str, int]:
        """Ingest articles from all active news sources."""
        stmt = select(Source).where(Source.active == True)
        result = await session.execute(stmt)
        sources = result.scalars().all()

        results = {}
        for source in sources:
            count = await self.ingest_rss_source(source, session)
            results[source.name] = count
        return results


ingestion_service = IngestionService()
