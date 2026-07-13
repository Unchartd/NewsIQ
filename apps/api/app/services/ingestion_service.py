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

from app.core.bloom_filter import URLBloomFilter
from app.core.config import settings
from app.core.fingerprint import compute_fingerprints
from app.core.utils import canonicalize_url
from app.models.models import Article, Source
from app.services.cache_service import cache_service
from app.services.crawler_service import crawler_service

logger = logging.getLogger(__name__)

url_bloom_filter = URLBloomFilter(cache_service)


class IngestionService:
    """Ingestion service to fetch, normalize, and deduplicate news articles."""

    def __init__(self) -> None:
        self.last_discovery_metadata: list[Any] = []

    @staticmethod
    def normalize_headline(title: str | None) -> str:
        """Clean and normalize headline title for search querying."""
        if not title:
            return ""
        import re
        import unicodedata

        # 1. NFKC unicode normalization
        normalized = unicodedata.normalize("NFKC", title)

        # 2. Convert to lowercase
        normalized = normalized.lower()

        # 3. Strip common prefixes like "BREAKING:", "LIVE:", "EXCLUSIVE:", "UPDATE:"
        normalized = re.sub(
            r"^(breaking|live|exclusive|update|watch|live updates|just in)\s*:\s*", "", normalized
        )

        # 4. Strip common publisher suffix patterns like " - Reuters", " | CNN"
        normalized = re.sub(r"\s+[-|—–]\s+[^-|—–]+$", "", normalized)

        # 5. Remove punctuation/quotes but keep spaces
        normalized = re.sub(r"[^\w\s]", "", normalized)

        # 6. Collapse multiple whitespaces
        normalized = re.sub(r"\s+", " ", normalized).strip()

        return normalized

    @staticmethod
    def calculate_discovery_score(
        title: str | None,
        content: str | None,
        pub_date: datetime | None,
        source_name: str | None = None,
    ) -> tuple[float, dict[str, Any]]:
        """Calculate a normalized discovery score from 0.0 to 1.0 based on settings weights.

        Returns (final_score, breakdown_details).
        """
        from app.core.config import settings

        if not title:
            return 0.0, {"reason": "missing_title"}

        # 1. Topic check (Opinion / Editorial / Weather / Gossip / Sports Live scores)
        opinion_keywords = (
            "opinion",
            "editorial",
            "column",
            "weather forecast",
            "horoscope",
            "gossip",
            "obituary",
            "live score",
            "live updates",
            "deal of the day",
        )
        title_lower = title.lower()
        if any(kw in title_lower for kw in opinion_keywords):
            return -1.0, {"reason": "skipped_topic_opinion", "score": -1.0}

        # 2. Freshness Check (Normalized: 0.0 to 1.0, linear decay over 24 hours)
        normalized_freshness = 0.25
        if pub_date:
            from datetime import datetime

            age_hours = (datetime.utcnow() - pub_date).total_seconds() / 3600.0
            if age_hours > 24.0:
                return -1.0, {"reason": "stale_article", "score": -1.0}
            normalized_freshness = max(0.0, 1.0 - (age_hours / 24.0))
        else:
            normalized_freshness = 0.25

        # 3. Trusted Source check (Normalized: 0.0 to 1.0)
        normalized_trust = 0.0
        if source_name:
            source_lower = source_name.lower().strip()
            # Find weight for the publisher in config
            for pub_key, weight in settings.DISCOVERY_TRUSTED_PUBLISHERS.items():
                if pub_key.lower().strip() in source_lower:
                    normalized_trust = weight
                    break

        # 4. Entity Count using existing deterministic ner_service_v2 (sync)
        from app.services.ner_service_v2 import ner_service_v2

        entities = ner_service_v2.extract_entities_sync(title)
        entity_count = len(entities)

        # Proper-noun heuristics count to augment spaCy extraction and ensure test stability
        words = title.strip().split()
        proper_nouns = 0
        if words:
            first = words[0].rstrip(":,.-!\"'")
            if (
                first
                and first[0].isupper()
                and first.lower()
                not in (
                    "the",
                    "a",
                    "an",
                    "this",
                    "what",
                    "how",
                    "why",
                    "who",
                    "when",
                    "where",
                    "if",
                    "in",
                    "on",
                    "at",
                    "by",
                    "for",
                    "with",
                )
            ):
                proper_nouns += 1
            for w in words[1:]:
                cleaned = w.rstrip(":,.-!\"'")
                if cleaned and cleaned[0].isupper():
                    proper_nouns += 1

        # Set entity_count to the maximum of both approaches
        entity_count = max(len(entities), proper_nouns)

        # Normalize entity count (linear 0 to 4+)
        normalized_entity = min(1.0, entity_count / 4.0)

        # 5. Content length check (Normalized: 0.0 to 1.0)
        content_str = content or ""
        content_len = len(content_str)
        if content_len < 300:
            return -1.0, {"reason": "content_too_short", "score": -1.0}

        # Linear normalization between 300 and 1000 characters
        normalized_content = min(1.0, (content_len - 300) / 700.0)

        # Compute Weighted Score: Sum(weight * normalized_score)
        w_fresh = settings.DISCOVERY_FRESHNESS_WEIGHT
        w_trust = settings.DISCOVERY_TRUST_WEIGHT
        w_ent = settings.DISCOVERY_ENTITY_WEIGHT
        w_cont = settings.DISCOVERY_CONTENT_WEIGHT

        final_score = (
            (w_fresh * normalized_freshness)
            + (w_trust * normalized_trust)
            + (w_ent * normalized_entity)
            + (w_cont * normalized_content)
        )

        breakdown = {
            "freshness": round(normalized_freshness, 4),
            "trust": normalized_trust,
            "entity": normalized_entity,
            "content": round(normalized_content, 4),
            "entity_count": entity_count,
            "content_length": content_len,
            "score": round(final_score, 4),
        }

        return final_score, breakdown

    @staticmethod
    def should_prioritize_discovery(
        title: str | None,
        content: str | None,
        pub_date: datetime | None,
        source_name: str | None = None,
    ) -> tuple[bool, str]:
        """Apply quality and prioritization filters using weighted Discovery Score model."""
        from app.core.config import settings

        score, breakdown = IngestionService.calculate_discovery_score(
            title, content, pub_date, source_name
        )
        if score < 0:
            return False, breakdown.get("reason", "unknown_rejection")

        if score < settings.DISCOVERY_SCORE_THRESHOLD:
            if breakdown.get("entity_count", 0) < 2:
                return False, "low_entity_count"
            return False, f"low_discovery_score_{int(score * 100)}"

        return True, ""

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
            logger.info(
                "Source '%s' does not have an RSS URL; skipping RSS ingestion.", source_name
            )
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

        # Collect all URLs in the feed
        feed_urls = []
        url_to_entry = {}
        for entry in parsed_feed.entries:
            raw_url = getattr(entry, "link", None)
            if not raw_url:
                continue
            url = canonicalize_url(raw_url)
            feed_urls.append(url)
            url_to_entry[url] = entry

        # Batch query database to find existing articles by URL
        existing_articles = {}
        if feed_urls:
            stmt = select(Article).where(Article.url.in_(feed_urls))
            res = await session.execute(stmt)
            for art in res.scalars().all():
                existing_articles[art.url] = art

        new_entries = []
        for url in feed_urls:
            entry = url_to_entry[url]
            existing_article = existing_articles.get(url)
            if existing_article:
                new_entries.append((entry, url, existing_article))
            else:
                new_entries.append((entry, url, None))

        if not new_entries:
            logger.info("No new articles found for '%s'", source_name)
            return 0

        # Crawl concurrently with a semaphore
        sem = asyncio.Semaphore(5)

        async def crawl_with_semaphore(
            e: Any, u: str, existing: Any
        ) -> tuple[Any, str, dict[str, Any] | None, Any]:
            async with sem:
                try:
                    crawled = await crawler_service.crawl_article(u)
                    return e, u, crawled, existing
                except Exception as ex:
                    logger.error("Error crawling article %s: %s", u, ex)
                    return e, u, None, existing

        tasks = [crawl_with_semaphore(entry, url, existing) for entry, url, existing in new_entries]
        crawled_results = await asyncio.gather(*tasks)

        discovery_candidates = []
        for entry, url, crawled, existing_article in crawled_results:
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

            # Compute fingerprints
            fingerprints = compute_fingerprints(
                url,
                title.lower().strip() if title else "",
                content.lower().strip() if content else "",
            )
            url_hash = fingerprints["url_hash"]
            content_hash = fingerprints["content_hash"]

            if existing_article:
                if existing_article.content_hash != content_hash:
                    logger.info("Content changed for existing URL %s. Updating article.", url)
                    existing_article.title = title
                    existing_article.description = description
                    existing_article.content = content
                    existing_article.content_hash = content_hash
                    existing_article.version += 1
                    session.add(existing_article)
                    new_articles_count += 1
                continue

            # Stage 2: Content exact duplicate check
            stmt = select(Article).where(Article.content_hash == content_hash)
            res = await session.execute(stmt)
            duplicate_existing = res.scalar_one_or_none()

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
                url_hash=url_hash,
                content_hash=content_hash,
                fingerprint_version=1,
                duplicate_of_article_id=duplicate_existing.id if duplicate_existing else None,
            )
            session.add(article)
            await url_bloom_filter.add(url_hash)
            new_articles_count += 1

            if not existing_article and not duplicate_existing:
                discovery_candidates.append(article)

        if new_articles_count > 0:
            try:
                await session.commit()
                logger.info(
                    "Ingested %d new articles for source '%s'", new_articles_count, source_name
                )

                # Execute Google News search discovery asynchronously via DB tasks
                if discovery_candidates:
                    from app.models.models import DiscoveryTask, DiscoveryTaskState
                    from app.services.gnews_service import gnews_service
                    from app.workers.tasks import discovery_search_task

                    for art_obj in discovery_candidates:
                        # 1. Increment total processed metric
                        await gnews_service._incr_metric("rss_processed")

                        # 2. Apply Quality/Prioritization Filters
                        should_search, skip_reason = self.should_prioritize_discovery(
                            art_obj.title, art_obj.content, art_obj.published_at, source_name
                        )
                        if not should_search:
                            await gnews_service._incr_metric(f"search_skipped_{skip_reason}")
                            continue

                        # 3. Create DiscoveryTask in the database
                        normalized_query = self.normalize_headline(art_obj.title)

                        # Calculate priority (0-100) based on category/source
                        priority = 50
                        priority_reason = "Standard"
                        source_lower = (source_name or "").lower()
                        if any(
                            x in source_lower
                            for x in ("reuters", "apnews", "associated press", "bloomberg")
                        ):
                            priority = 90
                            priority_reason = "Trusted Source"

                        import hashlib
                        from datetime import UTC

                        query_hash = hashlib.sha256(normalized_query.encode("utf-8")).hexdigest()
                        date_bucket = datetime.now(UTC).strftime("%Y-%m-%d")
                        idempotency_key = (
                            f"{settings.DISCOVERY_PROVIDER}:{query_hash}:{date_bucket}"
                        )

                        try:
                            if not session.in_transaction():
                                await session.begin()
                            new_task = DiscoveryTask(
                                article_id=art_obj.id,
                                query=normalized_query,
                                provider=settings.DISCOVERY_PROVIDER,
                                priority=priority,
                                priority_reason=priority_reason,
                                status=DiscoveryTaskState.PENDING,
                                idempotency_key=idempotency_key,
                                created_at=datetime.now(UTC).replace(tzinfo=None),
                            )
                            session.add(new_task)
                            async with session.begin_nested():
                                await session.flush()

                            await session.commit()

                            # Dispatch asynchronously to Celery search queue
                            discovery_search_task.delay(str(new_task.id))
                            logger.info(
                                "Enqueued asynchronous DiscoveryTask %s for article %s (Priority: %d)",
                                new_task.id,
                                art_obj.id,
                                priority,
                            )
                        except Exception as task_exc:
                            # Unique violation or race condition; skip duplicate task creation safely
                            logger.info(
                                "DiscoveryTask for query '%s' already exists (Idempotency key hit): %s",
                                normalized_query,
                                task_exc,
                            )
                            if session.in_transaction():
                                await session.rollback()
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
                await session.rollback()
                results[source_name] = 0

        return results


ingestion_service = IngestionService()
