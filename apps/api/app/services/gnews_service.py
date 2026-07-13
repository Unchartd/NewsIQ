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

import asyncio
import logging
import re
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.utils import canonicalize_url
from app.ingestion.gnews_client import DEFAULT_CATEGORIES, DEFAULT_COUNTRIES, gnews_client
from app.models.models import Article, Source
from app.services.crawler_service import crawler_service

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
        res = await session.execute(select(Source).where(Source.name.ilike(name_clean)))
        source = res.scalars().first()
        if source:
            return source

        # 2. Slug match
        candidate_slug = self._slugify(name_clean)
        res = await session.execute(select(Source).where(Source.slug == candidate_slug))
        source = res.scalars().first()
        if source:
            return source

        # 3. Domain match from URL
        if gnews_source_url:
            domain = re.sub(r"https?://(www\.)?", "", gnews_source_url).rstrip("/")
            res = await session.execute(
                select(Source).where(Source.website_url.ilike(f"%{domain}%"))
            )
            source = res.scalars().first()
            if source:
                return source

        # 4. Auto-create a new Source (GNews surfaces publishers we don't have seeded)
        #    Use a nested transaction (SAVEPOINT) so that a UniqueViolation on concurrent
        #    inserts only rolls back this INSERT — not the entire ingest transaction.
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
            async with session.begin_nested():
                await session.flush()  # Get the ID without committing the outer transaction
            return new_source
        except Exception as exc:
            # SAVEPOINT rolled back automatically — outer transaction is still alive.
            # Re-query by slug to return the winner from a concurrent insert.
            logger.warning(
                "GNews: auto-create race/conflict for source '%s' (%s) — re-querying winner.",
                name_clean,
                exc,
            )
            try:
                res = await session.execute(select(Source).where(Source.slug == candidate_slug))
                return res.scalars().first()
            except Exception as requery_exc:
                logger.error(
                    "GNews: re-query after source conflict failed for '%s': %s",
                    name_clean,
                    requery_exc,
                )
                return None

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

        # Filter new articles and resolve sources first
        new_articles_to_crawl = []
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

            new_articles_to_crawl.append((art_dict, url, source))

        if not new_articles_to_crawl:
            return 0

        # Crawl concurrently with a semaphore
        sem = asyncio.Semaphore(5)

        async def crawl_with_semaphore(
            a: dict, u: str, s: Source
        ) -> tuple[dict, str, Source, dict[str, Any] | None]:
            async with sem:
                try:
                    crawled = await crawler_service.crawl_article(u)
                    return a, u, s, crawled
                except Exception as ex:
                    logger.error("Error crawling GNews article %s: %s", u, ex)
                    return a, u, s, None

        tasks = [
            crawl_with_semaphore(art_dict, url, source)
            for art_dict, url, source in new_articles_to_crawl
        ]
        crawled_results = await asyncio.gather(*tasks)

        new_count = 0
        for art_dict, url, source, crawled in crawled_results:
            title = art_dict["title"]
            description = art_dict["description"]
            fallback_content = art_dict["content"]
            author = art_dict.get("author")
            image_url = art_dict.get("image_url")
            published_at = art_dict["published_at"]

            # Integrate crawled data
            if crawled and crawled.get("content"):
                content = crawled["content"]
                if crawled.get("author") and not author:
                    author = crawled["author"]
                if crawled.get("image_url") and not image_url:
                    image_url = crawled["image_url"]
                if not title and crawled.get("title"):
                    title = crawled["title"]
            else:
                content = fallback_content

            article = Article(
                source_id=source.id,
                title=title,
                description=description,
                content=content,
                url=url,
                author=author,
                language=art_dict.get("language", "en"),
                image_url=image_url,
                published_at=published_at,
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

    async def _incr_metric(self, name: str, amount: int = 1) -> None:
        """Helper to increment a daily discovery metric in Redis."""
        if not self._redis:
            return
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        key = f"discovery:metrics:{today_str}"
        try:
            await self._redis.hincrby(key, name, amount)  # type: ignore
            await self._redis.expire(key, 7 * 24 * 3600, nx=True)
        except Exception as exc:
            logger.debug("Failed to increment Redis metric '%s': %s", name, exc)

    async def _add_latency_metric(self, name: str, latency_ms: int) -> None:
        """Helper to track sum of latencies and call count in Redis."""
        if not self._redis:
            return
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        key = f"discovery:metrics:{today_str}"
        try:
            await self._redis.hincrby(key, f"{name}_sum_ms", latency_ms)  # type: ignore
            await self._redis.hincrby(key, f"{name}_count", 1)  # type: ignore
            await self._redis.expire(key, 7 * 24 * 3600, nx=True)
        except Exception as exc:
            logger.debug("Failed to add latency metric for '%s': %s", name, exc)

    async def search_and_ingest_similar_articles(
        self,
        title: str,
        session: AsyncSession,
        max_articles: int | None = None,
        pub_date: datetime | None = None,
    ) -> dict[str, Any]:
        """Search similar news articles using configured provider and ingest matching results.

        This method is config-driven, rate-limited, and runs database operations sequentially.
        """
        import hashlib
        import json
        import time

        from app.core.fingerprint import compute_fingerprints

        start_time = time.perf_counter()
        max_results = max_articles if max_articles is not None else settings.DISCOVERY_MAX_RESULTS

        # 1. Headline Normalization (Phase 1 Clean)
        from app.services.ingestion_service import IngestionService

        normalized = IngestionService.normalize_headline(title)

        metadata: dict[str, Any] = {
            "searched": False,
            "cache_hit": False,
            "urls_found": 0,
            "downloaded": 0,
            "persisted": 0,
            "duplicates": 0,
            "duration_ms": 0,
            "skip_reason": None,
        }

        if not normalized or len(normalized) < 10:
            metadata["skip_reason"] = "normalization_too_short"
            return metadata

        headline_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

        # Check cache first
        cache_key = f"discovery:search_cache:{headline_hash}"
        lock_key = f"discovery:search_lock:{headline_hash}"

        discovered_urls = []
        cache_hit = False

        if self._redis:
            try:
                cached_data = await self._redis.get(cache_key)
                if cached_data:
                    discovered_urls = json.loads(cached_data)
                    cache_hit = True
                    metadata["cache_hit"] = True
                    await self._incr_metric("search_skipped_cache")
            except Exception as exc:
                logger.warning("Failed to query Redis search cache: %s", exc)

        if not cache_hit:
            # Check execution lock to prevent concurrent searches
            if self._redis:
                try:
                    acquired = await self._redis.set(
                        lock_key, "1", ex=settings.DISCOVERY_LOCK_TTL, nx=True
                    )
                    if not acquired:
                        metadata["skip_reason"] = "search_locked"
                        await self._incr_metric("search_lock_skip")
                        return metadata
                except Exception as exc:
                    logger.warning("Failed to check Redis search lock: %s", exc)

            # Execute search
            metadata["searched"] = True
            await self._incr_metric("searches_triggered")
            await self._incr_metric("search_cache_miss")

            search_start = time.perf_counter()
            try:
                # Limit the search query to 8-10 words to make a clean query
                query_words = normalized.split()[:10]
                query = " ".join(query_words)

                # Fetch search results using configured provider with 3.0s timeout
                from app.ingestion import get_discovery_provider

                provider = get_discovery_provider(settings.DISCOVERY_PROVIDER)

                raw_results = await asyncio.wait_for(
                    provider.search(
                        query=query, max_results=max_results * 3
                    ),  # Fetch extra to allow ranking/diversity
                    timeout=3.0,
                )

                # Rank and filter raw search results to enforce diversity and quality
                discovered_urls = self.rank_and_filter_search_results(
                    results=raw_results,
                    original_title=title,
                    original_pub_date=pub_date,
                    max_results=max_results,
                )

                # Write to search cache
                if self._redis:
                    await self._redis.set(
                        cache_key, json.dumps(discovered_urls), ex=settings.DISCOVERY_CACHE_TTL
                    )
            except TimeoutError:
                logger.warning("Discovery search provider timed out for query: '%s'", normalized)
                await self._incr_metric("search_timeout")
                discovered_urls = []
            except Exception as exc:
                logger.error("Discovery search provider failed for query '%s': %s", normalized, exc)
                await self._incr_metric("search_failed")
                discovered_urls = []
            finally:
                # Release lock
                if self._redis:
                    try:
                        await self._redis.delete(lock_key)
                    except Exception:
                        pass
                search_end = time.perf_counter()
                search_latency_ms = int((search_end - search_start) * 1000)
                await self._add_latency_metric("search_latency", search_latency_ms)
        else:
            await self._incr_metric("search_cache_hit")

        if not discovered_urls:
            metadata["duration_ms"] = int((time.perf_counter() - start_time) * 1000)
            return metadata

        metadata["urls_found"] = len(discovered_urls)
        await self._incr_metric("urls_found", len(discovered_urls))

        # Concurrently Ingest Discovered URLs
        # Bounded concurrency: Semaphore from settings
        sem = asyncio.Semaphore(settings.DISCOVERY_MAX_CONCURRENT_DOWNLOADS)
        from app.services.ingestion_service import url_bloom_filter

        async def process_discovered_url(url: str) -> dict[str, Any] | None:
            async with sem:
                url_canonical = canonicalize_url(url)
                url_hash = compute_fingerprints(url_canonical, "", "")["url_hash"]

                # 1. Early Bloom Filter Check (checked FIRST before database lookups)
                if await url_bloom_filter.exists(url_hash):
                    await self._incr_metric("bloom_filter_skip")
                    await self._incr_metric("url_duplicates")
                    return {"status": "bloom_filtered"}

                # 2. Crawl Article concurrently (HTTP network request, no session access)
                crawl_start = time.perf_counter()
                try:
                    crawled = await crawler_service.crawl_article(url_canonical)
                    crawl_time_ms = int((time.perf_counter() - crawl_start) * 1000)
                    await self._add_latency_metric("download_time", crawl_time_ms)
                    if crawled and crawled.get("content"):
                        return {
                            "status": "success",
                            "crawled": crawled,
                            "url": url_canonical,
                            "url_hash": url_hash,
                        }
                except Exception as crawl_exc:
                    logger.debug(
                        "Failed to crawl search discovery URL %s: %s", url_canonical, crawl_exc
                    )

                return None

        tasks = [process_discovered_url(u) for u in discovered_urls]
        results = await asyncio.gather(*tasks)

        # Ingest successful crawls sequentially to protect the DB session from concurrent queries
        new_count = 0
        for res_dict in results:
            if not res_dict:
                continue
            if res_dict.get("status") == "success":
                crawled = res_dict["crawled"]
                url = res_dict["url"]
                url_hash = res_dict["url_hash"]

                metadata["downloaded"] += 1
                await self._incr_metric("urls_downloaded")

                # 1. Database check (safe sequential check)
                res = await session.execute(select(Article).where(Article.url == url))
                if res.scalar_one_or_none():
                    await url_bloom_filter.add(url_hash)
                    await self._incr_metric("db_url_skip")
                    await self._incr_metric("url_duplicates")
                    continue

                # Resolve source using the crawl result metadata or fallbacks
                gnews_source_name = crawled.get("source_name")
                gnews_source_url = crawled.get("source_url")

                source = await self._resolve_source(
                    gnews_source_name=gnews_source_name,
                    gnews_source_url=gnews_source_url,
                    session=session,
                )
                if not source:
                    continue

                content = crawled["content"]
                title_val = crawled.get("title") or "Untitled Discovered Article"

                fingerprints = compute_fingerprints(
                    url,
                    title_val.lower().strip(),
                    content.lower().strip(),
                )
                content_hash = fingerprints["content_hash"]

                # Stage 2: Content exact duplicate check
                dup_res = await session.execute(
                    select(Article).where(Article.content_hash == content_hash)
                )
                duplicate_existing = dup_res.scalar_one_or_none()
                if duplicate_existing:
                    metadata["duplicates"] += 1
                    await self._incr_metric("fingerprint_skip")
                    await self._incr_metric("fingerprint_duplicates")
                    continue

                article = Article(
                    source_id=source.id,
                    title=title_val,
                    description=crawled.get("description", ""),
                    content=content,
                    url=url,
                    author=crawled.get("author"),
                    language="en",
                    image_url=crawled.get("image_url"),
                    published_at=crawled.get("published_at") or datetime.utcnow(),
                    crawled_at=datetime.utcnow(),
                    embedding_status="pending",
                    created_at=datetime.utcnow(),
                    url_hash=url_hash,
                    content_hash=content_hash,
                    fingerprint_version=1,
                )
                session.add(article)
                await url_bloom_filter.add(url_hash)
                new_count += 1

        if new_count > 0:
            try:
                await session.commit()
                metadata["persisted"] = new_count
                await self._incr_metric("urls_persisted", new_count)
            except Exception as commit_exc:
                await session.rollback()
                logger.error("Failed to commit discovery articles: %s", commit_exc)

        metadata["duration_ms"] = int((time.perf_counter() - start_time) * 1000)
        return metadata

    @staticmethod
    def _get_base_domain(url: str) -> str:
        """Extract base domain from a URL for domain diversity filtering."""
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]
            return netloc
        except Exception:
            return ""

    def rank_and_filter_search_results(
        self,
        results: list[dict[str, Any]],
        original_title: str,
        original_pub_date: datetime | None,
        max_results: int,
    ) -> list[str]:
        """Rank search results using RapidFuzz & Jaccard, enforcing base domain diversity."""
        if not results:
            return []

        import rapidfuzz

        from app.services.ingestion_service import IngestionService
        from app.services.ner_service_v2 import ner_service_v2

        orig_clean = IngestionService.normalize_headline(original_title)
        orig_words = set(orig_clean.split())

        # 1. Extract original title entities for overlap comparison
        orig_entities = {
            e["value"].lower().strip() for e in ner_service_v2.extract_entities_sync(original_title)
        }

        scored_candidates = []
        for art in results:
            url = art.get("url")
            if not url:
                continue

            title = art.get("title", "")
            desc = art.get("description", "") or art.get("content", "") or ""

            title_clean = IngestionService.normalize_headline(title)
            title_words = set(title_clean.split())

            # Title overlap (Jaccard similarity)
            jaccard = 0.0
            if orig_words and title_words:
                jaccard = len(orig_words.intersection(title_words)) / len(
                    orig_words.union(title_words)
                )
            score = jaccard * 40.0

            # Fuzzy Token set ratio title similarity
            fuzzy_ratio = 0.0
            try:
                fuzzy_ratio = rapidfuzz.fuzz.token_set_ratio(orig_clean, title_clean) / 100.0
            except Exception:
                pass
            score += fuzzy_ratio * 40.0

            # Entity and location overlap
            cand_entities = {
                e["value"].lower().strip()
                for e in ner_service_v2.extract_entities_sync(title + " " + desc)
            }
            entity_overlap = 0.0
            if orig_entities and cand_entities:
                entity_overlap = len(orig_entities.intersection(cand_entities)) / len(
                    orig_entities.union(cand_entities)
                )
            score += entity_overlap * 20.0

            # Publisher Trust Weight modifier from config
            gnews_source_name = art.get("gnews_source_name")
            trust_weight = 0.0
            if gnews_source_name:
                source_lower = gnews_source_name.lower().strip()
                for pub_key, weight in settings.DISCOVERY_TRUSTED_PUBLISHERS.items():
                    if pub_key.lower().strip() in source_lower:
                        trust_weight = weight
                        break

            domain = self._get_base_domain(url)
            for pub_key, weight in settings.DISCOVERY_TRUSTED_PUBLISHERS.items():
                if pub_key.lower().strip() in domain:
                    trust_weight = max(trust_weight, weight)
                    break

            # Scale score by trust weight
            score = score * (1.0 + trust_weight)

            # Time difference proximity
            pub_date = art.get("published_at")
            if pub_date and original_pub_date:
                time_diff_hours = abs((pub_date - original_pub_date).total_seconds()) / 3600.0
                if time_diff_hours <= 12.0:
                    score += 10.0 * (1.0 - (time_diff_hours / 12.0))

            scored_candidates.append({"url": url, "domain": domain, "score": score})

        # Sort candidates by score descending
        scored_candidates.sort(key=lambda x: x["score"], reverse=True)

        # Enforce base domain diversity: Only keep first article per domain
        seen_domains = set()
        final_urls = []
        for cand in scored_candidates:
            domain = cand["domain"]
            if domain and domain in seen_domains:
                continue
            seen_domains.add(domain)
            final_urls.append(cand["url"])
            if len(final_urls) >= max_results:
                break

        return final_urls

    async def generate_discovery_reports(self, session: AsyncSession) -> dict[str, Any]:
        """Compile Hourly, Daily, and Rolling 7-Day Discovery reports and KPIs."""
        import json
        from datetime import datetime, timedelta

        from sqlalchemy import distinct, func, select

        from app.models.models import Article, Story, StoryArticle

        now = datetime.utcnow()
        today_str = now.strftime("%Y-%m-%d")

        async def get_metrics_for_date(date_str: str) -> dict[str, int]:
            metrics = {}
            if self._redis:
                try:
                    raw = await self._redis.hgetall(f"discovery:metrics:{date_str}")  # type: ignore
                    metrics = {k: int(v) for k, v in raw.items()}
                except Exception:
                    pass
            return metrics

        async def get_sources_per_story_stats() -> tuple[float, float]:
            try:
                subq = (
                    select(
                        StoryArticle.story_id,
                        func.count(distinct(Article.source_id)).label("source_count"),
                    )
                    .join(Article, StoryArticle.article_id == Article.id)
                    .group_by(StoryArticle.story_id)
                )
                res = await session.execute(subq)
                counts = [float(row[1]) for row in res.all()]
                if not counts:
                    return 1.0, 1.0

                avg_val = sum(counts) / len(counts)

                counts.sort()
                n = len(counts)
                if n % 2 == 1:
                    median_val = counts[n // 2]
                else:
                    median_val = (counts[n // 2 - 1] + counts[n // 2]) / 2.0

                return round(avg_val, 2), round(median_val, 2)
            except Exception as exc:
                logger.warning("Failed to calculate story source statistics: %s", exc)
                return 1.0, 1.0

        async def get_discovery_effectiveness(days: int = 1) -> dict[str, int]:
            cutoff = now - timedelta(days=days)
            try:
                clustered_stmt = (
                    select(func.count(distinct(StoryArticle.article_id)))
                    .join(Article, StoryArticle.article_id == Article.id)
                    .where(Article.created_at >= cutoff)
                )
                clustered_count = await session.scalar(clustered_stmt) or 0

                stories_stmt = select(func.count(Story.id)).where(Story.created_at >= cutoff)
                stories_count = await session.scalar(stories_stmt) or 0

                return {"clustered": clustered_count, "synthesized": stories_count}
            except Exception as exc:
                logger.warning("Failed to calculate discovery effectiveness: %s", exc)
                return {"clustered": 0, "synthesized": 0}

        daily_metrics = await get_metrics_for_date(today_str)
        daily_eff = await get_discovery_effectiveness(days=1)
        avg_src_daily, med_src_daily = await get_sources_per_story_stats()

        daily_report = {
            "rss_processed": daily_metrics.get("rss_processed", 0),
            "searches_triggered": daily_metrics.get("searches_triggered", 0),
            "search_cache_hits": daily_metrics.get("search_cache_hit", 0)
            or daily_metrics.get("search_skipped_cache", 0),
            "search_lock_skips": daily_metrics.get("search_lock_skip", 0)
            or daily_metrics.get("search_skipped_search_locked", 0),
            "urls_found": daily_metrics.get("urls_found", 0),
            "urls_downloaded": daily_metrics.get("urls_downloaded", 0),
            "bloom_filter_skips": daily_metrics.get("bloom_filter_skip", 0)
            or daily_metrics.get("url_duplicates", 0),
            "db_url_skips": daily_metrics.get("db_url_skip", 0)
            or daily_metrics.get("search_skipped_db_filtered", 0),
            "fingerprint_skips": daily_metrics.get("fingerprint_skip", 0)
            or daily_metrics.get("fingerprint_duplicates", 0),
            "articles_persisted": daily_metrics.get("urls_persisted", 0),
            "articles_clustered": daily_eff["clustered"],
            "stories_synthesized": daily_eff["synthesized"],
            "avg_sources_per_story": avg_src_daily,
            "median_sources_per_story": med_src_daily,
        }

        # Compile 7-day rolling report
        rolling_metrics: dict[str, int] = {}
        for i in range(7):
            d_str = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            m = await get_metrics_for_date(d_str)
            for k, v in m.items():
                rolling_metrics[k] = rolling_metrics.get(k, 0) + v
        rolling_eff = await get_discovery_effectiveness(days=7)

        rolling_report = {
            "rss_processed": rolling_metrics.get("rss_processed", 0),
            "searches_triggered": rolling_metrics.get("searches_triggered", 0),
            "search_cache_hits": rolling_metrics.get("search_cache_hit", 0)
            or rolling_metrics.get("search_skipped_cache", 0),
            "urls_found": rolling_metrics.get("urls_found", 0),
            "urls_downloaded": rolling_metrics.get("urls_downloaded", 0),
            "bloom_filter_skips": rolling_metrics.get("bloom_filter_skip", 0)
            or rolling_metrics.get("url_duplicates", 0),
            "db_url_skips": rolling_metrics.get("db_url_skip", 0),
            "fingerprint_skips": rolling_metrics.get("fingerprint_skip", 0)
            or rolling_metrics.get("fingerprint_duplicates", 0),
            "articles_persisted": rolling_metrics.get("urls_persisted", 0),
            "articles_clustered": rolling_eff["clustered"],
            "stories_synthesized": rolling_eff["synthesized"],
            "avg_sources_per_story": avg_src_daily,
            "median_sources_per_story": med_src_daily,
        }

        hourly_report = {
            "rss_processed_last_hour": daily_metrics.get("rss_processed", 0),
            "searches_triggered_last_hour": daily_metrics.get("searches_triggered", 0),
            "articles_persisted_last_hour": daily_metrics.get("urls_persisted", 0),
        }

        full_reports = {
            "date": today_str,
            "hourly": hourly_report,
            "daily": daily_report,
            "rolling_7d": rolling_report,
        }

        if self._redis:
            try:
                await self._redis.set(
                    f"discovery:report:{today_str}", json.dumps(full_reports), ex=7 * 24 * 3600
                )
            except Exception as exc:
                logger.warning("Failed to save discovery reports to Redis: %s", exc)

        # Log report summary
        logger.info(
            "=== DAILY DISCOVERY QUALITY REPORT (%s) ===\n"
            "RSS Articles Processed:  %d\n"
            "Google Searches:         %d\n"
            "Search Cache Hits:       %d\n"
            "URLs Found:              %d\n"
            "URLs Downloaded:         %d\n"
            "Bloom Filter Skips:      %d\n"
            "DB URL Skips:            %d\n"
            "Fingerprint Skips:       %d\n"
            "Articles Persisted:      %d\n"
            "Articles Clustered:      %d\n"
            "Stories Synthesized:     %d\n"
            "Average Sources/Story:   %.2f\n"
            "Median Sources/Story:    %.2f\n"
            "============================================",
            today_str,
            daily_report["rss_processed"],
            daily_report["searches_triggered"],
            daily_report["search_cache_hits"],
            daily_report["urls_found"],
            daily_report["urls_downloaded"],
            daily_report["bloom_filter_skips"],
            daily_report["db_url_skips"],
            daily_report["fingerprint_skips"],
            daily_report["articles_persisted"],
            daily_report["articles_clustered"],
            daily_report["stories_synthesized"],
            daily_report["avg_sources_per_story"],
            daily_report["median_sources_per_story"],
        )
        return full_reports

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
        logger.info(
            "GNews ingestion complete: %d new articles across %d feeds.", total, len(results)
        )
        return results


gnews_service = GNewsService()
