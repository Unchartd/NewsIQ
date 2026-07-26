"""Pre-Crawler Decision Engine gatekeeper (Stages 06–13).

Evaluates candidate article URLs prior to crawler execution to eliminate
redundant HTTP downloads.
"""

import hashlib
import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.bloom_filter import URLBloomFilter
from app.core.config import settings
from app.core.utils import canonicalize_url
from app.ingestion.discovery_providers import GoogleRSSDiscoveryProvider
from app.models.models import Article
from app.services.cache_service import cache_service

logger = logging.getLogger(__name__)

url_bloom_filter = URLBloomFilter(cache_service)


@dataclass
class PreCrawlerDecision:
    """Pre-crawler duplicate decision object."""

    should_crawl: bool
    duplicate_reason: str
    original_url: str
    decoded_url: str
    canonical_url: str
    normalized_url: str
    url_hash: str
    existing_article_id: UUID | None = None
    existing_story_id: UUID | None = None


class PreCrawlerDecisionEngine:
    """Pre-crawler URL deduplication gatekeeper enforcing Stages 06-13."""

    def __init__(self) -> None:
        self.discovery_provider = GoogleRSSDiscoveryProvider()

    async def evaluate_url(
        self,
        url: str,
        session: AsyncSession,
        source_name: str | None = None,
    ) -> PreCrawlerDecision:
        """Evaluate pre-crawler deduplication gate.

        Pipeline Stages:
          06: Decode Google News redirect URL (if applicable)
          07: Canonical URL Builder
          08: Tracking Parameter Removal (utm_*, gclid, fbclid, ref)
          09: URL Normalization (lowercasing, trailing slash removal)
          10: SHA256 URL Hash Generation
          11: Redis Bloom Filter Lookup
          12: PostgreSQL DB Check for url_hash
          13: Decision Gate (should_crawl)
        """
        # Feature Flag check: if disabled, default to allow crawling
        if not getattr(settings, "PRE_CRAWLER_DEDUP_ENABLED", True):
            c_url = canonicalize_url(url)
            u_hash = hashlib.sha256(c_url.encode("utf-8")).hexdigest()
            return PreCrawlerDecision(
                should_crawl=True,
                duplicate_reason="FEATURE_FLAG_DISABLED",
                original_url=url,
                decoded_url=url,
                canonical_url=c_url,
                normalized_url=c_url.lower().rstrip("/"),
                url_hash=u_hash,
            )

        # Stage 06: Decode URL if Google redirect URL
        decoded_url = await self.discovery_provider.resolve_url(url)

        # Stage 07 & 08: Canonical URL building & tracking parameter removal
        canonical_url = canonicalize_url(decoded_url)

        # Stage 09: URL Normalization
        normalized_url = canonical_url.lower().strip().rstrip("/")

        # Stage 10: SHA256 URL Hash Generation
        url_hash = hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()

        # Stage 11: Redis Bloom Filter Check
        bloom_result = False
        try:
            bloom_result = await url_bloom_filter.exists(url_hash)
        except Exception as exc:
            logger.warning("PreCrawlerDecisionEngine: Bloom filter check failed: %s", exc)

        # Stage 12: PostgreSQL DB Duplicate Check
        db_article = None
        try:
            res = await session.execute(
                select(Article).where(Article.url_hash == url_hash).limit(1)
            )
            db_article = res.scalar_one_or_none()
        except Exception as exc:
            logger.error("PreCrawlerDecisionEngine: PostgreSQL check error: %s", exc)

        # Stage 13: Decision Gate Evaluation
        if db_article:
            logger.info(
                "[PreCrawler] Skip crawl for '%s' — FOUND_IN_DATABASE (Article ID: %s)",
                canonical_url,
                db_article.id,
            )
            return PreCrawlerDecision(
                should_crawl=False,
                duplicate_reason="FOUND_IN_DATABASE",
                original_url=url,
                decoded_url=decoded_url,
                canonical_url=canonical_url,
                normalized_url=normalized_url,
                url_hash=url_hash,
                existing_article_id=db_article.id,
                existing_story_id=getattr(db_article, "story_id", None),
            )
        elif bloom_result:
            logger.info(
                "[PreCrawler] Skip crawl for '%s' — FOUND_IN_BLOOM",
                canonical_url,
            )
            return PreCrawlerDecision(
                should_crawl=False,
                duplicate_reason="FOUND_IN_BLOOM",
                original_url=url,
                decoded_url=decoded_url,
                canonical_url=canonical_url,
                normalized_url=normalized_url,
                url_hash=url_hash,
            )

        logger.info(
            "[PreCrawler] Decision NEW_URL for '%s' (hash: %s...)",
            canonical_url,
            url_hash[:12],
        )
        return PreCrawlerDecision(
            should_crawl=True,
            duplicate_reason="NEW_URL",
            original_url=url,
            decoded_url=decoded_url,
            canonical_url=canonical_url,
            normalized_url=normalized_url,
            url_hash=url_hash,
        )


pre_crawler_engine = PreCrawlerDecisionEngine()
