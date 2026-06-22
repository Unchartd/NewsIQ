"""Service for ingesting news articles from RSS feeds and other news APIs."""

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import Any

import feedparser
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils import canonicalize_url
from app.models.models import Article, Source
from app.services.crawler_service import crawler_service

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
                    return datetime.fromtimestamp(time.mktime(parsed), tz=UTC).replace(tzinfo=None)
                except Exception:
                    pass
        return datetime.utcnow()

    async def ingest_rss_source(self, source: Source, session: AsyncSession) -> int:
        """Ingest articles from a source's RSS feed."""
        source_name = source.name
        source_id = source.id

        if not source.rss_url:
            logger.warning("Source '%s' does not have an RSS URL.", source_name)
            return 0

        logger.info("Starting ingestion for source: %s (%s)", source_name, source.rss_url)
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(source.rss_url)
                response.raise_for_status()
                feed_data = response.text
        except Exception as e:
            logger.error("Failed to fetch RSS feed for '%s': %s", source_name, e)
            return 0

        # Parse the RSS feed using feedparser (which parses the text directly)
        parsed_feed = feedparser.parse(feed_data)
        new_articles_count = 0

        # Identify new entries to process
        new_entries = []
        for entry in parsed_feed.entries:
            raw_url = getattr(entry, "link", None)
            if not raw_url:
                continue
            url = canonicalize_url(raw_url)

            # Deduplication: Check if article with this URL already exists
            stmt = select(Article).where(Article.url == url)
            res = await session.execute(stmt)
            if res.scalar_one_or_none():
                continue
            new_entries.append((entry, url))

        if not new_entries:
            logger.info("No new articles found for '%s'", source_name)
            return 0

        # Crawl concurrently with a semaphore
        sem = asyncio.Semaphore(5)

        async def crawl_with_semaphore(
            e: Any, u: str
        ) -> tuple[Any, str, dict[str, Any] | None]:
            async with sem:
                try:
                    crawled = await crawler_service.crawl_article(u)
                    return e, u, crawled
                except Exception as ex:
                    logger.error("Error crawling article %s: %s", u, ex)
                    return e, u, None

        tasks = [crawl_with_semaphore(entry, url) for entry, url in new_entries]
        crawled_results = await asyncio.gather(*tasks)

        for entry, url, crawled in crawled_results:
            title = getattr(entry, "title", "Untitled Article")
            description = self.clean_html(getattr(entry, "summary", ""))
            
            content_value = self.clean_html(
                getattr(entry, "content", [{"value": ""}])[0].get("value", "")
            )
            fallback_content = content_value if content_value else description
            
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

            # Integrate crawled data
            if crawled and crawled.get("content"):
                content = crawled["content"]
                if crawled.get("author") and not author:
                    author = crawled["author"]
                if crawled.get("image_url") and not image_url:
                    image_url = crawled["image_url"]
                if (not title or title == "Untitled Article") and crawled.get("title"):
                    title = crawled["title"]
            else:
                content = fallback_content

            article = Article(
                source_id=source_id,
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
                logger.info(
                    "Ingested %d new articles for source '%s'", new_articles_count, source_name
                )
            except Exception as e:
                await session.rollback()
                logger.error("Failed to save ingested articles for '%s': %s", source_name, e)
                return 0
        else:
            logger.info("No new articles found for '%s'", source_name)

        return new_articles_count

    async def ingest_all_active_sources(self, session: AsyncSession) -> dict[str, int]:
        """Ingest articles from all active news sources sequentially to prevent concurrent database session usage."""
        stmt = select(Source.id).where(Source.active)
        result = await session.execute(stmt)
        source_ids = result.scalars().all()

        results = {}
        for source_id in source_ids:
            # Query each source fresh to prevent SQLAlchemy greenlet/expired attribute issues after commits
            source_stmt = select(Source).where(Source.id == source_id)
            source_result = await session.execute(source_stmt)
            source = source_result.scalar_one_or_none()
            if not source:
                continue
            source_name = source.name
            try:
                count = await self.ingest_rss_source(source, session)
                results[source_name] = count
            except Exception as e:
                logger.error("Error during ingestion for %s: %s", source_name, e)
                results[source_name] = 0

        return results


ingestion_service = IngestionService()
