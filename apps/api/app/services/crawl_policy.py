"""Crawl policy: provider circuit breaking, domain routing, and per-domain pacing.

Three problems this solves, all measured in production:

1. Firecrawl ran out of credits and answered HTTP 402 to all 256 calls in a
   24h window — a 0% success rate that was invisible because non-200 responses
   were never logged and the cost metric only fired on success. A provider
   whose account is empty cannot succeed on any URL, so it must be tripped off
   rather than retried per-URL.

2. 878 of 2789 known domains have never once been extracted successfully by
   the local crawler, yet every article from them still burned all three local
   attempts (up to 105s of timeouts) before falling through to a paid provider.
   DomainExtractionPolicy already recorded this, but nothing read it.

3. 21.8% of consecutive crawls hit the same host, 12% within one second, with
   runs as long as 140 requests against a single host. There was no per-domain
   pacing anywhere — only a global concurrency semaphore, which bounds total
   load but says nothing about how it lands on any one publisher.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Callable

from app.core.config import settings
from app.services.cache_service import cache_service

logger = logging.getLogger(__name__)

_CIRCUIT_KEY = "crawl:provider_circuit:{provider}"
_PACER_KEY = "crawl:domain_pace:{domain}"


class ProviderCircuitBreaker:
    """Trips a paid provider off when its account, not the URL, is the problem."""

    @staticmethod
    async def is_open(provider: str) -> bool:
        """True when *provider* is currently disabled and must be skipped."""
        redis_client = cache_service._redis
        if not redis_client:
            return False
        try:
            return bool(await redis_client.get(_CIRCUIT_KEY.format(provider=provider)))
        except Exception as exc:  # a broken cache must never block extraction
            logger.warning("Circuit breaker check failed for %s: %s", provider, exc)
            return False

    @staticmethod
    async def trip(provider: str, reason: str, ttl_seconds: int) -> None:
        """Disable *provider* for *ttl_seconds*.

        The TTL doubles as the re-probe interval: when it expires the next
        request tries the provider again, so a topped-up account recovers on
        its own without a deploy. At the default six hours a dead provider
        costs four wasted calls a day instead of 256.
        """
        redis_client = cache_service._redis
        if not redis_client:
            return
        try:
            await redis_client.set(_CIRCUIT_KEY.format(provider=provider), reason, ex=ttl_seconds)
            logger.error(
                "Circuit OPEN for provider=%s (%s). Skipping it for %ds.",
                provider,
                reason,
                ttl_seconds,
            )
            from app.core.metrics import newsiq_crawler_provider_circuit_open_total

            newsiq_crawler_provider_circuit_open_total.labels(
                provider=provider, reason=reason
            ).inc()
        except Exception as exc:
            logger.warning("Failed to trip circuit for %s: %s", provider, exc)


class DomainPacer:
    """Enforces a minimum interval between requests to the same host.

    Implemented as a Redis SET NX PX lease so the interval holds across every
    Celery worker rather than per-process. Fails open: if the wait budget is
    exhausted the crawl proceeds anyway, because delaying an article is
    preferable to dropping it, but blocking the pipeline is not.
    """

    @staticmethod
    async def wait_turn(domain: str) -> bool:
        """Block until this worker may hit *domain*. Returns False if it gave up waiting."""
        redis_client = cache_service._redis
        if not redis_client or not domain:
            return True

        interval_ms = int(max(settings.CRAWL_DOMAIN_MIN_INTERVAL_SECONDS, 0.0) * 1000)
        if interval_ms <= 0:
            return True

        key = _PACER_KEY.format(domain=domain)
        deadline = time.monotonic() + settings.CRAWL_DOMAIN_MAX_WAIT_SECONDS

        while True:
            try:
                acquired = await redis_client.set(key, "1", nx=True, px=interval_ms)
            except Exception as exc:
                logger.warning("Domain pacer unavailable for %s: %s", domain, exc)
                return True

            if acquired:
                return True

            if time.monotonic() >= deadline:
                logger.info(
                    "Domain pacer gave up waiting for %s after %.0fs; proceeding.",
                    domain,
                    settings.CRAWL_DOMAIN_MAX_WAIT_SECONDS,
                )
                return False

            # Jitter so workers released together do not collide immediately.
            await asyncio.sleep(0.25 + random.random() * 0.25)


async def should_skip_local(domain: str) -> bool:
    """True when the local crawler has proven useless for *domain*.

    Requires a minimum sample count before trusting the record, so one unlucky
    timeout on a new domain cannot permanently route it to a paid provider. A
    small share of requests re-probe local anyway, so a site that removes its
    bot wall is rediscovered without manual intervention.
    """
    if not settings.CRAWL_DOMAIN_ROUTING_ENABLED or not domain:
        return False

    if random.random() < settings.CRAWL_LOCAL_REPROBE_RATE:
        return False

    from sqlalchemy import select

    from app.core.database import async_session_factory
    from app.models.models import DomainExtractionPolicy

    try:
        async with async_session_factory() as session:
            policy = (
                await session.execute(
                    select(DomainExtractionPolicy).where(DomainExtractionPolicy.domain == domain)
                )
            ).scalar_one_or_none()
    except Exception as exc:
        logger.warning("Domain routing lookup failed for %s: %s", domain, exc)
        return False

    if policy is None or policy.local_attempts < settings.CRAWL_SKIP_LOCAL_MIN_SAMPLES:
        return False

    if policy.local_success_rate >= 0.05:
        return False

    # Only skip local if something else actually works, otherwise we would be
    # spending credits on a domain nothing can extract.
    paid_works = max(policy.tavily_success_rate, policy.firecrawl_success_rate) > 0.2
    if not paid_works:
        return False

    logger.info(
        "Skipping local crawler for %s (local %.0f%% over %d attempts; paid provider works)",
        domain,
        policy.local_success_rate * 100,
        policy.local_attempts,
    )
    try:
        from app.core.metrics import newsiq_crawler_local_skipped_total

        newsiq_crawler_local_skipped_total.labels(domain=domain).inc()
    except Exception:
        pass
    return True


def host_of(url: str) -> str:
    """Hostname of *url*, lowercased and without a leading www."""
    from urllib.parse import urlparse

    try:
        return urlparse(url).netloc.lower().split(":")[0].removeprefix("www.")
    except Exception:
        return ""


def is_google_news_redirect(url: str) -> bool:
    """True when *url* is an undecoded news.google.com redirect.

    Matched on the parsed hostname rather than as a substring: a substring test
    also fires on https://elsewhere.example/news.google.com/x and, worse,
    accepts https://news.google.com.attacker.example/ as Google's own.
    """
    host = host_of(url)
    return host == "news.google.com" or host.endswith(".news.google.com")


def drop_unresolved_redirects(urls: list[str]) -> list[str]:
    """Remove Google News redirect URLs that could not be decoded.

    Crawling one fetches Google's own interstitial rather than journalism, and
    stores news.google.com as the article's publisher — which then pollutes the
    publisher-trust and source-diversity signals clustering depends on.
    """
    kept, dropped = [], 0
    for url in urls:
        if is_google_news_redirect(url):
            dropped += 1
            continue
        kept.append(url)
    if dropped:
        logger.warning("Dropped %d undecodable Google News redirect URL(s)", dropped)
    return kept


def interleave_by_domain(urls: list[str]) -> list[str]:
    """Round-robin URLs across hosts, preserving each host's relative order.

    Discovery returns URLs grouped by publisher and the dispatcher then sorted
    them by tier, so same-host URLs were queued back to back — production saw
    runs of up to 140 consecutive requests to one host. Spreading them means
    the per-domain pacer rarely has to block, so politeness costs no throughput.
    """
    from collections import OrderedDict, deque

    groups: OrderedDict[str, deque[str]] = OrderedDict()
    for url in urls:
        groups.setdefault(host_of(url), deque()).append(url)

    ordered: list[str] = []
    while groups:
        for host in list(groups):
            ordered.append(groups[host].popleft())
            if not groups[host]:
                del groups[host]
    return ordered


def order_crawl_urls(urls: list[str], tier_of: Callable[[str], int]) -> list[str]:
    """Order URLs for dispatch: tier priority first, domains interleaved within.

    Tier order is preserved because it encodes publisher quality, but within a
    tier no two consecutive URLs share a host unless that host is all that is
    left at that tier.
    """
    by_tier: dict[int, list[str]] = {}
    for url in urls:
        by_tier.setdefault(tier_of(url), []).append(url)

    ordered: list[str] = []
    for tier in sorted(by_tier):
        ordered.extend(interleave_by_domain(by_tier[tier]))
    return ordered


provider_circuit = ProviderCircuitBreaker()
domain_pacer = DomainPacer()
