"""Service for ingesting news articles from RSS feeds and other news APIs."""

import asyncio
import hashlib
import logging
import re
import time
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Any

import feedparser
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
        if pub_date:
            now_dt = datetime.now(UTC).replace(tzinfo=None)
            age_hours = (now_dt - pub_date).total_seconds() / 3600.0
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

        # 4. Entity Count using NerService v2 (sync)
        from app.services.ner_service_v2 import ner_service_v2

        entities = ner_service_v2.extract_entities_sync(title)

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

        entity_count = max(len(entities), proper_nouns)
        normalized_entity = min(1.0, entity_count / 4.0)

        # 5. Content length check (Normalized: 0.0 to 1.0)
        content_str = content or ""
        content_len = len(content_str)
        if content_len < 300:
            return -1.0, {"reason": "content_too_short", "score": -1.0}

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
        """Apply quality and prioritization filters using weighted Discovery Score model.

        .. deprecated::
            Use calculate_metadata_score() for the Story-First pipeline (metadata only,
            no content required). This method remains for the legacy Article-First path
            (GNews ingestion) and will be removed once that path is migrated.
        """
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
    def calculate_metadata_score(
        title: str | None,
        description: str | None,
        pub_date: datetime | None,
        source_name: str | None = None,
    ) -> tuple[float, dict[str, Any]]:
        """Metadata-only discovery score for the Story-First pipeline.

        Unlike calculate_discovery_score(), this does NOT require crawled content
        and does NOT apply a content-length gate. It is designed for RSS entry
        screening where only title, description, published_at, and source_name
        are available.

        Returns:
            (score, breakdown) where score is in [-1.0, 1.0].
            Negative scores indicate the entry should be skipped entirely.
        """
        if not title:
            return 0.0, {"reason": "missing_title"}

        # 1. Opinion/Editorial/Live-score gate (same exclusions as full scorer)
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

        # 2. Freshness (same 24-hour decay as full scorer)
        if pub_date:
            now_dt = datetime.now(UTC).replace(tzinfo=None)
            age_hours = (now_dt - pub_date).total_seconds() / 3600.0
            if age_hours > 24.0:
                return -1.0, {"reason": "stale_article", "score": -1.0}
            normalized_freshness = max(0.0, 1.0 - (age_hours / 24.0))
        else:
            normalized_freshness = 0.25

        # 3. Source trust weight
        normalized_trust = 0.0
        if source_name:
            source_lower = source_name.lower().strip()
            for pub_key, weight in settings.DISCOVERY_TRUSTED_PUBLISHERS.items():
                if pub_key.lower().strip() in source_lower:
                    normalized_trust = weight
                    break

        # 4. Entity count from title + description (no content available)
        from app.services.ner_service_v2 import ner_service_v2

        text_for_ner = f"{title} {description or ''}".strip()
        entities = ner_service_v2.extract_entities_sync(text_for_ner)

        # Proper-noun heuristic (same as full scorer)
        words = title.strip().split()
        proper_nouns = 0
        _stopwords = {
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
        }
        if words:
            first = words[0].rstrip(":,.-!\"'")
            if first and first[0].isupper() and first.lower() not in _stopwords:
                proper_nouns += 1
            for w in words[1:]:
                cleaned = w.rstrip(":,.-!\"'")
                if cleaned and cleaned[0].isupper():
                    proper_nouns += 1

        entity_count = max(len(entities), proper_nouns)
        normalized_entity = min(1.0, entity_count / 4.0)

        # 5. Weighted score
        # Content weight (DISCOVERY_CONTENT_WEIGHT) is redistributed proportionally
        # across freshness, trust, and entity since there is no content to score.
        w_fresh = settings.DISCOVERY_FRESHNESS_WEIGHT
        w_trust = settings.DISCOVERY_TRUST_WEIGHT
        w_ent = settings.DISCOVERY_ENTITY_WEIGHT
        w_cont = settings.DISCOVERY_CONTENT_WEIGHT

        # Redistribute content weight proportionally
        total_meta_weight = w_fresh + w_trust + w_ent
        scale = (total_meta_weight + w_cont) / total_meta_weight if total_meta_weight > 0 else 1.0

        final_score = (
            (w_fresh * normalized_freshness)
            + (w_trust * normalized_trust)
            + (w_ent * normalized_entity)
        ) * scale

        breakdown = {
            "freshness": round(normalized_freshness, 4),
            "trust": normalized_trust,
            "entity": normalized_entity,
            "entity_count": entity_count,
            "score": round(final_score, 4),
            "source": "metadata_only",
        }

        return final_score, breakdown

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
        return datetime.now(UTC).replace(tzinfo=None)

    async def ingest_rss_source(self, source: Source, session: AsyncSession) -> int:
        """Ingest articles from a source's RSS feed.

        Story-First path (STORY_FIRST_ENABLED=True — default):
            RSS entries are treated as metadata seeds. No HTTP crawling happens here.
            Each qualifying entry is upserted into StoryCandidate (deduplicated by
            headline hash). The dispatch_story_candidate_task fires after the
            collection window to run the Google News search and create CrawlTasks.

        Legacy path (STORY_FIRST_ENABLED=False):
            Original Article-First flow: crawl → persist → dispatch discovery.
        """
        if not source.rss_url:
            logger.info(
                "Source '%s' does not have an RSS URL; skipping RSS ingestion.", source.name
            )
            return 0

        feed_data = await self._fetch_feed(source.rss_url, source.name)
        if not feed_data:
            return 0

        feed_urls, url_to_entry = self._prepare_entries(feed_data)
        if not feed_urls:
            return 0

        existing_articles = await self._batch_existing_articles(feed_urls, session)

        if settings.STORY_FIRST_ENABLED:
            return await self._ingest_rss_story_first(
                feed_urls, url_to_entry, existing_articles, source, session
            )

        # ── Legacy Article-First path ─────────────────────────────────────────
        entries_to_crawl: list[tuple[Any, str, Article | None]] = [
            (url_to_entry[url], url, None) for url in feed_urls if url not in existing_articles
        ]
        crawled_results = await self._crawl_articles(entries_to_crawl)
        new_articles_count, discovery_candidates = await self._persist_articles(
            crawled_results, source, session
        )
        if discovery_candidates:
            await self._dispatch_discovery(discovery_candidates, source.name, session)
        return new_articles_count

    async def _ingest_rss_story_first(
        self,
        feed_urls: list[str],
        url_to_entry: dict[str, Any],
        existing_articles: dict[str, Any],
        source: Source,
        session: AsyncSession,
    ) -> int:
        """Story-First ingestion path: score metadata, upsert StoryCandidates.

        Returns the count of StoryCandidates dispatched (new or updated).
        No articles are crawled here. Crawling happens in discovery_crawl_task
        after dispatch_story_candidate_task completes the discovery search.
        """
        from app.services.gnews_service import gnews_service

        dispatched = 0
        for url in feed_urls:
            if url in existing_articles:
                continue  # already crawled and persisted

            entry = url_to_entry[url]
            title = getattr(entry, "title", None)
            description = self.clean_html(getattr(entry, "summary", "") or "")
            pub_date = self.parse_pub_date(entry)

            score, breakdown = self.calculate_metadata_score(
                title, description, pub_date, source.name
            )

            await gnews_service._incr_metric("rss_metadata_scored")

            if score < 0 or score < settings.STORY_FIRST_SCORE_THRESHOLD:
                skip_reason = breakdown.get("reason") or f"low_metadata_score_{int(score * 100)}"
                logger.debug(
                    "[StoryFirst] Skipping RSS entry '%s' — %s (score=%.2f)",
                    title,
                    skip_reason,
                    score,
                )
                await gnews_service._incr_metric(f"rss_skipped_{skip_reason}")
                continue

            rss_entry_meta = {
                "source_name": source.name,
                "url": url,
                "published_at": pub_date.isoformat() if pub_date else None,
                "score": round(score, 4),
                "title": title or "",
                "description": description[:500] if description else "",
            }

            await self._upsert_story_candidate(
                title=title or "",
                rss_entry_meta=rss_entry_meta,
                source=source,
                score=score,
                session=session,
            )
            dispatched += 1

        logger.info(
            "[StoryFirst] Ingested %s '%s': %d entries qualified, %d story candidates dispatched.",
            source.name,
            source.rss_url,
            dispatched,
            dispatched,
        )
        return dispatched

    async def _upsert_story_candidate(
        self,
        title: str,
        rss_entry_meta: dict[str, Any],
        source: Source,
        score: float,
        session: AsyncSession,
    ) -> None:
        """Deduplicate by headline hash and create or update a StoryCandidate.

        Strategy:
            1. Normalize headline → SHA256 query_hash.
            2. SETNX Redis key (STORY_CANDIDATE_DEDUP_TTL) → get existing SC id.
            3a. Existing → _attach_rss_source (updates count, triggers early dispatch).
            3b. New → INSERT StoryCandidate + INSERT DiscoveryTask +
                      dispatch_story_candidate_task.apply_async(eta=collect_until).
        """
        from app.models.models import (
            DiscoveryTask,
            DiscoveryTaskState,
            StoryCandidate,
            StoryCandidateState,
        )
        from app.services.cache_service import cache_service
        from app.workers.tasks import dispatch_story_candidate_task

        normalized_query = self.normalize_headline(title)
        if not normalized_query or len(normalized_query) < 10:
            logger.debug(
                "[StoryFirst] Skipping too-short headline after normalization: '%s'", title
            )
            return

        date_bucket = datetime.now(UTC).strftime("%Y-%m-%d")
        query_hash = hashlib.sha256(f"{normalized_query}:{date_bucket}".encode()).hexdigest()
        dedup_redis_key = f"story_candidate:query:{query_hash}:{date_bucket}"

        # ── Check Redis for existing StoryCandidate ─────────────────────────
        existing_id_str: str | None = None
        try:
            existing_id_str = await cache_service.get(dedup_redis_key)
        except Exception as e:
            logger.warning("[StoryFirst] Redis dedup read failed: %s", e)

        if existing_id_str:
            # Duplicate story detected — attach this RSS source
            try:
                import uuid

                existing_sc_id = uuid.UUID(existing_id_str)
                await self._attach_rss_source(existing_sc_id, rss_entry_meta, session)
            except Exception as e:
                logger.warning(
                    "[StoryFirst] Failed to attach RSS source to existing candidate: %s", e
                )
            return

        # ── New story — create StoryCandidate ─────────────────────────────────
        source_lower = source.name.lower()
        priority = (
            90
            if any(
                x in source_lower for x in ("reuters", "apnews", "associated press", "bloomberg")
            )
            else 50
        )
        priority_reason = "Trusted Source" if priority == 90 else "Standard"

        now = datetime.now(UTC).replace(tzinfo=None)
        collect_until = now + timedelta(seconds=settings.STORY_CANDIDATE_COLLECTION_WINDOW_SECONDS)
        idempotency_key = f"{settings.DISCOVERY_PROVIDER}:{query_hash}:{date_bucket}"

        story_candidate = StoryCandidate(
            normalized_query=normalized_query,
            query_hash=query_hash,
            date_bucket=date_bucket,
            headline=title,
            discovery_provider=settings.DISCOVERY_PROVIDER,
            status=StoryCandidateState.COLLECTING,
            priority=priority,
            priority_reason=priority_reason,
            rss_sources=[rss_entry_meta],
            rss_source_count=1,
            collect_until=collect_until,
            created_at=now,
        )
        session.add(story_candidate)

        try:
            async with session.begin_nested():
                await session.flush()  # get story_candidate.id without committing
        except IntegrityError:
            # Race condition: another worker won the UniqueConstraint race.
            # Re-query the winner and attach this source to it.
            logger.info(
                "[StoryFirst] StoryCandidate race for query '%s' — re-querying winner.",
                normalized_query,
            )
            await session.rollback()
            try:
                stmt = select(StoryCandidate).where(
                    StoryCandidate.query_hash == query_hash,
                    StoryCandidate.date_bucket == date_bucket,
                )
                res = await session.execute(stmt)
                winner = res.scalar_one_or_none()
                if winner:
                    await self._attach_rss_source(winner.id, rss_entry_meta, session)
            except Exception as re_e:
                logger.error("[StoryFirst] Failed to re-query winner StoryCandidate: %s", re_e)
            return

        # ── Create the associated DiscoveryTask ─────────────────────────────
        discovery_task = DiscoveryTask(
            story_candidate_id=story_candidate.id,
            article_id=None,  # Story-First: no article row at this stage
            query=normalized_query,
            provider=settings.DISCOVERY_PROVIDER,
            priority=priority,
            priority_reason=priority_reason,
            status=DiscoveryTaskState.PENDING,
            idempotency_key=idempotency_key,
            created_at=now,
        )
        session.add(discovery_task)

        try:
            async with session.begin_nested():
                await session.flush()
        except IntegrityError:
            # DiscoveryTask idempotency key already exists — normal on re-ingestion
            logger.info(
                "[StoryFirst] DiscoveryTask idempotency key hit for query '%s'.", normalized_query
            )
            await session.rollback()
            return

        await session.commit()

        # ── Set Redis dedup key so subsequent sources attach instead of create ─
        try:
            await cache_service.set(
                dedup_redis_key,
                str(story_candidate.id),
                ttl=settings.STORY_CANDIDATE_DEDUP_TTL,
            )
        except Exception as e:
            logger.warning("[StoryFirst] Redis dedup write failed: %s", e)

        # ── Schedule dispatch via ETA (collection window timeout path) ────────
        from app.core.trace import active_pipeline_run_ctx

        active_run = active_pipeline_run_ctx.get(None)
        run_id = str(active_run.id) if active_run else None
        trace_id = str(active_run.trace_id) if active_run else None

        dispatch_story_candidate_task.apply_async(
            args=[str(story_candidate.id), run_id, trace_id],
            eta=collect_until,
        )
        logger.info(
            "[StoryFirst] Created StoryCandidate %s for '%s' (priority=%d, dispatch_eta=%s).",
            story_candidate.id,
            title[:60],
            priority,
            collect_until.isoformat(),
        )

    async def _attach_rss_source(
        self,
        story_candidate_id: Any,
        rss_entry_meta: dict[str, Any],
        session: AsyncSession,
    ) -> None:
        """Attach an additional RSS source to an existing StoryCandidate.

        Increments rss_source_count. If the count reaches
        STORY_FIRST_EARLY_DISPATCH_THRESHOLD, fires dispatch_story_candidate_task
        immediately (bypassing the collection window ETA).
        """
        from app.models.models import StoryCandidate, StoryCandidateState
        from app.workers.tasks import dispatch_story_candidate_task

        stmt = select(StoryCandidate).where(StoryCandidate.id == story_candidate_id)
        res = await session.execute(stmt)
        sc = res.scalar_one_or_none()
        if not sc:
            logger.warning(
                "[StoryFirst] _attach_rss_source: StoryCandidate %s not found.",
                story_candidate_id,
            )
            return

        # Only attach if still in the COLLECTING phase
        if sc.status != StoryCandidateState.COLLECTING:
            logger.debug(
                "[StoryFirst] StoryCandidate %s is %s — skipping attach.",
                story_candidate_id,
                sc.status,
            )
            return

        current_sources = list(sc.rss_sources or [])
        # Avoid duplicates from the same source URL
        known_urls = {s.get("url") for s in current_sources}
        if rss_entry_meta.get("url") in known_urls:
            return

        current_sources.append(rss_entry_meta)
        sc.rss_sources = current_sources
        sc.rss_source_count = len(current_sources)

        await session.flush()

        logger.info(
            "[StoryFirst] Attached RSS source '%s' to StoryCandidate %s (count=%d).",
            rss_entry_meta.get("source_name"),
            story_candidate_id,
            sc.rss_source_count,
        )

        # ── Early dispatch: trigger search if enough publishers have attached ─
        if sc.rss_source_count >= settings.STORY_FIRST_EARLY_DISPATCH_THRESHOLD:
            # Transition to DISCOVERING to prevent the ETA task from also running
            sc.status = StoryCandidateState.DISCOVERING
            sc.search_dispatched_at = datetime.now(UTC).replace(tzinfo=None)
            await session.commit()

            from app.core.trace import active_pipeline_run_ctx

            active_run = active_pipeline_run_ctx.get(None)
            run_id = str(active_run.id) if active_run else None
            trace_id = str(active_run.trace_id) if active_run else None

            dispatch_story_candidate_task.delay(str(story_candidate_id), run_id, trace_id)
            logger.info(
                "[StoryFirst] Early dispatch triggered for StoryCandidate %s "
                "(%d publishers reached threshold=%d).",
                story_candidate_id,
                sc.rss_source_count,
                settings.STORY_FIRST_EARLY_DISPATCH_THRESHOLD,
            )
        else:
            await session.commit()

    async def _fetch_feed(self, rss_url: str, source_name: str) -> str | None:
        """Fetch raw RSS feed content."""
        logger.info("Starting ingestion for source: %s (%s)", source_name, rss_url)
        try:
            from app.core.http_client import http_client_pool

            client = http_client_pool.client
            response = await client.get(rss_url, timeout=15.0, follow_redirects=True)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error("Failed to fetch RSS feed for '%s': %s", source_name, e)
            return None

    def _prepare_entries(self, feed_data: str) -> tuple[list[str], dict[str, Any]]:
        """Parse RSS feed data and return canonicalized URLs and mapping to entries."""
        parsed_feed = feedparser.parse(feed_data)
        feed_urls = []
        url_to_entry = {}
        for entry in parsed_feed.entries:
            raw_url = getattr(entry, "link", None)
            if not raw_url:
                continue
            url = canonicalize_url(raw_url)
            feed_urls.append(url)
            url_to_entry[url] = entry
        return feed_urls, url_to_entry

    async def _batch_existing_articles(
        self, feed_urls: list[str], session: AsyncSession
    ) -> dict[str, Article]:
        """Query DB in a batch to find existing articles by URL."""
        existing_articles = {}
        if feed_urls:
            stmt = select(Article).where(Article.url.in_(feed_urls))
            res = await session.execute(stmt)
            for art in res.scalars().all():
                existing_articles[art.url] = art
        return existing_articles

    async def _crawl_articles(
        self, new_entries: list[tuple[Any, str, Article | None]]
    ) -> list[tuple[Any, str, dict[str, Any] | None, Article | None]]:
        """Crawl the list of new articles concurrently using settings.CRAWLER_MAX_CONCURRENT_REQUESTS.

        .. deprecated::
            Used by the legacy Article-First path (STORY_FIRST_ENABLED=False) and
            the GNews ingestion path. Will be removed once GNews is migrated to
            Story-First. Do not add new callers.
        """
        max_concurrent = settings.CRAWLER_MAX_CONCURRENT_REQUESTS or 5
        sem = asyncio.Semaphore(max_concurrent)

        async def crawl_with_semaphore(
            e: Any, u: str, existing: Article | None
        ) -> tuple[Any, str, dict[str, Any] | None, Article | None]:
            async with sem:
                try:
                    crawled = await crawler_service.crawl_article(u)
                    return e, u, crawled, existing
                except Exception as ex:
                    logger.error("Error crawling article %s: %s", u, ex)
                    return e, u, None, existing

        tasks = [crawl_with_semaphore(entry, url, existing) for entry, url, existing in new_entries]
        return await asyncio.gather(*tasks)

    async def _persist_articles(
        self,
        crawled_results: list[tuple[Any, str, dict[str, Any] | None, Article | None]],
        source: Source,
        session: AsyncSession,
    ) -> tuple[int, list[Article]]:
        """Parse, check duplicate contents, and save/update articles to the database.

        .. deprecated::
            Used by the legacy Article-First path (STORY_FIRST_ENABLED=False) and
            the GNews ingestion path. Will be removed once GNews is migrated to
            Story-First. Do not add new callers.
        """
        source_id = source.id
        new_articles_count = 0
        discovery_candidates = []

        # ---------- pass 1: compute all fingerprints to enable batch dedup ----------
        # This avoids the N+1 pattern of one SELECT per article for content_hash.
        _PerEntryRow = tuple[
            Any,  # entry (feedparser entry object)
            str,  # url
            dict[str, Any] | None,  # crawled result
            Article | None,  # existing_article
            str,  # url_hash
            str,  # content_hash
            Any,  # title (str)
            str,  # description
            Any,  # content (str)
            Any,  # author (str | None)
            datetime,  # published_at
            Any,  # image_url (str | None)
        ]
        per_entry: list[_PerEntryRow] = []

        for entry, url, crawled, existing_article in crawled_results:
            title = getattr(entry, "title", "Untitled Article")
            description = self.clean_html(getattr(entry, "summary", ""))

            content_value = self.clean_html(
                getattr(entry, "content", [{"value": ""}])[0].get("value", "")
            )
            fallback_content = content_value if content_value else description

            author = getattr(entry, "author", None)
            published_at = self.parse_pub_date(entry)

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

            fingerprints = compute_fingerprints(
                url,
                title.lower().strip() if title else "",
                content.lower().strip() if content else "",
            )
            url_hash = fingerprints["url_hash"]
            content_hash = fingerprints["content_hash"]

            per_entry.append(
                (
                    entry,
                    url,
                    crawled,
                    existing_article,
                    url_hash,
                    content_hash,
                    title,
                    description,
                    content,
                    author,
                    published_at,
                    image_url,
                )
            )

        # ---------- pass 2: PERF-02 — batch content_hash lookup (single IN query) ----------
        # Collect hashes for genuinely new URLs only (existing_article is None)
        new_content_hashes = [
            row[5]  # content_hash is at index 5
            for row in per_entry
            if row[3] is None  # existing_article is at index 3; None means new URL
        ]
        duplicate_map: dict[str, Article] = {}
        if new_content_hashes:
            dup_stmt = select(Article).where(Article.content_hash.in_(new_content_hashes))
            dup_res = await session.execute(dup_stmt)
            for dup_art in dup_res.scalars().all():
                # Keep first match per hash (there may be multiple duplicates)
                if dup_art.content_hash is not None and dup_art.content_hash not in duplicate_map:
                    duplicate_map[dup_art.content_hash] = dup_art

        # ---------- pass 3: persist ----------
        for row in per_entry:
            (
                entry,
                url,
                crawled,
                existing_article,
                url_hash,
                content_hash,
                title,
                description,
                content,
                author,
                published_at,
                image_url,
            ) = row

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

            duplicate_existing = duplicate_map.get(content_hash)

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
                crawled_at=datetime.now(UTC).replace(tzinfo=None),
                embedding_status="pending",
                created_at=datetime.now(UTC).replace(tzinfo=None),
                url_hash=url_hash,
                content_hash=content_hash,
                fingerprint_version=1,
                duplicate_of_article_id=duplicate_existing.id if duplicate_existing else None,
            )
            session.add(article)
            await url_bloom_filter.add(url_hash)
            new_articles_count += 1

            if not duplicate_existing:
                discovery_candidates.append(article)

        return new_articles_count, discovery_candidates

    async def _dispatch_discovery(
        self, discovery_candidates: list[Article], source_name: str, session: AsyncSession
    ) -> None:
        """Create DiscoveryTask records and dispatch asynchronously to the Celery search queue.

        .. deprecated::
            Used by the legacy Article-First path (STORY_FIRST_ENABLED=False) and
            the GNews ingestion path. In the Story-First path, StoryCandidate
            creation and dispatch happens in _upsert_story_candidate().
            Will be removed once GNews is migrated. Do not add new callers.
        """
        from app.models.models import DiscoveryTask, DiscoveryTaskState
        from app.services.gnews_service import gnews_service
        from app.workers.tasks import discovery_search_task

        for art_obj in discovery_candidates:
            await gnews_service._incr_metric("rss_processed")

            should_search, skip_reason = self.should_prioritize_discovery(
                art_obj.title, art_obj.content, art_obj.published_at, source_name
            )
            if not should_search:
                await gnews_service._incr_metric(f"search_skipped_{skip_reason}")
                continue

            normalized_query = self.normalize_headline(art_obj.title)

            priority = 50
            priority_reason = "Standard"
            source_lower = (source_name or "").lower()
            if any(
                x in source_lower for x in ("reuters", "apnews", "associated press", "bloomberg")
            ):
                priority = 90
                priority_reason = "Trusted Source"

            query_hash = hashlib.sha256(normalized_query.encode("utf-8")).hexdigest()
            date_bucket = datetime.now(UTC).strftime("%Y-%m-%d")
            idempotency_key = f"{settings.DISCOVERY_PROVIDER}:{query_hash}:{date_bucket}"

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

                from app.core.trace import active_pipeline_run_ctx

                active_run = active_pipeline_run_ctx.get(None)
                run_id = str(active_run.id) if active_run else None
                trace_id = str(active_run.trace_id) if active_run else None
                discovery_search_task.delay(str(new_task.id), run_id=run_id, trace_id=trace_id)
                logger.info(
                    "Enqueued asynchronous DiscoveryTask %s for article %s (Priority: %d)",
                    new_task.id,
                    art_obj.id,
                    priority,
                )
            except IntegrityError as task_exc:
                # BUG-05: IntegrityError is the expected idempotency path (unique constraint on
                # idempotency_key). Log at INFO. All other exceptions are unexpected and must
                # surface at ERROR level so they appear in alerting.
                logger.info(
                    "DiscoveryTask for query '%s' already exists (idempotency key hit): %s",
                    normalized_query,
                    task_exc,
                )
                if session.in_transaction():
                    await session.rollback()
            except Exception as task_exc:
                logger.error(
                    "Unexpected error dispatching DiscoveryTask for query '%s': %s",
                    normalized_query,
                    task_exc,
                )
                if session.in_transaction():
                    await session.rollback()

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
