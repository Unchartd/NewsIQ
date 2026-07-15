from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any
from urllib.parse import urlparse

from app.core.config import settings
from app.services.cache_service import cache_service
from app.services.extraction.types import (
    ExtractionFailure,
    ExtractionResult,
)
from app.services.extraction_provider import (
    FirecrawlProvider,
    LocalCrawlerProvider,
    TavilyExtractProvider,
)

logger = logging.getLogger(__name__)


class ExtractionManager:
    def __init__(self) -> None:
        self.local_provider = LocalCrawlerProvider()
        self.tavily_provider = TavilyExtractProvider()
        self.firecrawl_provider = FirecrawlProvider()

    async def crawl_article(self, url: str) -> dict[str, Any]:
        """Orchestrate article extraction across local, Tavily, and Firecrawl providers."""
        from app.core.metrics import (
            newsiq_crawler_attempts_total,
            newsiq_crawler_failure_reason_total,
            newsiq_crawler_fallback_count_v2,
            newsiq_crawler_fallback_rate,
            newsiq_crawler_local_success_rate,
            newsiq_crawler_provider_attempts_total,
            newsiq_crawler_provider_attempts_total_v2,
            newsiq_crawler_provider_cost_total,
            newsiq_crawler_provider_cost_total_v2,
            newsiq_crawler_provider_failure_total,
            newsiq_crawler_provider_failure_total_v2,
            newsiq_crawler_provider_latency_seconds,
            newsiq_crawler_provider_latency_seconds_v2,
            newsiq_crawler_provider_success_total,
            newsiq_crawler_provider_success_total_v2,
        )
        from app.core.utils import canonicalize_url

        newsiq_crawler_attempts_total.inc()

        c_url = canonicalize_url(url)
        parsed_url = urlparse(c_url)
        domain = parsed_url.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]

        url_hash = hashlib.sha256(c_url.encode("utf-8")).hexdigest()
        idempotency_key = f"extraction:idempotency:{url_hash}"

        # 1. Check Idempotency Cache
        redis_client = cache_service._redis
        if redis_client:
            try:
                cached_json = await redis_client.get(idempotency_key)
                if cached_json:
                    logger.info("Idempotency cache hit for URL: %s", url)
                    cached_data = json.loads(cached_json)
                    res = ExtractionResult.from_dict(cached_data)
                    return self._to_legacy_dict(res)
            except Exception as e:
                logger.warning("Failed to check idempotency cache: %s", e)

        # 2. Attempt 1: Local Crawler
        logger.info("Attempting local extraction for: %s", url)
        newsiq_crawler_provider_attempts_total.labels(provider="local").inc()
        newsiq_crawler_provider_attempts_total_v2.labels(provider="local", domain=domain).inc()
        local_start = time.perf_counter()

        local_res = await self.local_provider.extract(c_url, f"local_{url_hash}")
        local_latency = time.perf_counter() - local_start
        newsiq_crawler_provider_latency_seconds.labels(provider="local").observe(local_latency)
        newsiq_crawler_provider_latency_seconds_v2.labels(provider="local", domain=domain).observe(
            local_latency
        )

        # Persist metrics in DomainExtractionPolicy table
        content_len = len(local_res.content) if local_res.content else 0
        await self._update_domain_policy(
            domain=domain,
            provider="local",
            success=local_res.success,
            latency_ms=local_res.diagnostics.latency_ms,
            content_length=content_len,
        )

        if local_res.success:
            logger.info("Local extraction succeeded for: %s", url)
            newsiq_crawler_provider_success_total.labels(provider="local").inc()
            newsiq_crawler_provider_success_total_v2.labels(provider="local", domain=domain).inc()
            newsiq_crawler_local_success_rate.inc()
            await self._set_idempotency_cache(idempotency_key, local_res)
            return self._to_legacy_dict(local_res)

        logger.warning("Local extraction failed for %s. Reason: %s", url, local_res.failure)
        newsiq_crawler_provider_failure_total.labels(provider="local").inc()
        newsiq_crawler_provider_failure_total_v2.labels(
            provider="local", failure_reason=local_res.failure.value, domain=domain
        ).inc()
        newsiq_crawler_failure_reason_total.labels(
            provider="local", failure_reason=local_res.failure.value, domain=domain
        ).inc()

        # Failure Classification: Stop immediately on 404 / Gone
        if local_res.failure == ExtractionFailure.HTTP_404:
            logger.warning(
                "Permanent failure (404/Gone) detected for %s. Stopping extraction.", url
            )
            return self._to_legacy_dict(local_res)

        # 3. Attempt 2: Tavily Extract (with Redis distributed batching)
        newsiq_crawler_fallback_rate.inc()
        newsiq_crawler_fallback_count_v2.labels(domain=domain).inc()
        logger.info("Routing %s to Tavily Extract batch queue", url)
        newsiq_crawler_provider_attempts_total.labels(provider="tavily").inc()
        newsiq_crawler_provider_attempts_total_v2.labels(provider="tavily", domain=domain).inc()
        tavily_start = time.perf_counter()

        tavily_res = await self.extract_via_tavily_batch(c_url, f"tavily_{url_hash}")
        tavily_latency = time.perf_counter() - tavily_start
        newsiq_crawler_provider_latency_seconds.labels(provider="tavily").observe(tavily_latency)
        newsiq_crawler_provider_latency_seconds_v2.labels(provider="tavily", domain=domain).observe(
            tavily_latency
        )

        tavily_content_len = len(tavily_res.content) if tavily_res.content else 0
        await self._update_domain_policy(
            domain=domain,
            provider="tavily",
            success=tavily_res.success,
            latency_ms=tavily_res.diagnostics.latency_ms,
            content_length=tavily_content_len,
        )

        if tavily_res.success:
            logger.info("Tavily extraction succeeded for: %s", url)
            newsiq_crawler_provider_success_total.labels(provider="tavily").inc()
            newsiq_crawler_provider_success_total_v2.labels(provider="tavily", domain=domain).inc()
            # 1 credit per 5 URLs = 0.2 credits per URL. Let's record cost (1 credit = $0.01 estimation)
            newsiq_crawler_provider_cost_total.labels(provider="tavily").inc(0.2)
            newsiq_crawler_provider_cost_total_v2.labels(provider="tavily", domain=domain).inc(0.2)
            await self._set_idempotency_cache(idempotency_key, tavily_res)
            return self._to_legacy_dict(tavily_res)

        logger.warning("Tavily extraction failed for %s. Reason: %s", url, tavily_res.failure)
        newsiq_crawler_provider_failure_total.labels(provider="tavily").inc()
        newsiq_crawler_provider_failure_total_v2.labels(
            provider="tavily", failure_reason=tavily_res.failure.value, domain=domain
        ).inc()
        newsiq_crawler_failure_reason_total.labels(
            provider="tavily", failure_reason=tavily_res.failure.value, domain=domain
        ).inc()

        # 4. Attempt 3: Firecrawl Scrape (final synchronous fallback)
        logger.info("Routing %s to Firecrawl Scrape", url)
        newsiq_crawler_provider_attempts_total.labels(provider="firecrawl").inc()
        newsiq_crawler_provider_attempts_total_v2.labels(provider="firecrawl", domain=domain).inc()
        firecrawl_start = time.perf_counter()

        firecrawl_res = await self.firecrawl_provider.extract(c_url, f"firecrawl_{url_hash}")
        firecrawl_latency = time.perf_counter() - firecrawl_start
        newsiq_crawler_provider_latency_seconds.labels(provider="firecrawl").observe(
            firecrawl_latency
        )
        newsiq_crawler_provider_latency_seconds_v2.labels(
            provider="firecrawl", domain=domain
        ).observe(firecrawl_latency)

        firecrawl_content_len = len(firecrawl_res.content) if firecrawl_res.content else 0
        await self._update_domain_policy(
            domain=domain,
            provider="firecrawl",
            success=firecrawl_res.success,
            latency_ms=firecrawl_res.diagnostics.latency_ms,
            content_length=firecrawl_content_len,
        )

        if firecrawl_res.success:
            logger.info("Firecrawl extraction succeeded for: %s", url)
            newsiq_crawler_provider_success_total.labels(provider="firecrawl").inc()
            newsiq_crawler_provider_success_total_v2.labels(
                provider="firecrawl", domain=domain
            ).inc()
            # Firecrawl cost is 1 credit per scrape
            newsiq_crawler_provider_cost_total.labels(provider="firecrawl").inc(1.0)
            newsiq_crawler_provider_cost_total_v2.labels(provider="firecrawl", domain=domain).inc(
                1.0
            )
            await self._set_idempotency_cache(idempotency_key, firecrawl_res)
            return self._to_legacy_dict(firecrawl_res)

        logger.error("All extraction providers failed for URL: %s", url)
        newsiq_crawler_provider_failure_total.labels(provider="firecrawl").inc()
        newsiq_crawler_provider_failure_total_v2.labels(
            provider="firecrawl", failure_reason=firecrawl_res.failure.value, domain=domain
        ).inc()
        newsiq_crawler_failure_reason_total.labels(
            provider="firecrawl", failure_reason=firecrawl_res.failure.value, domain=domain
        ).inc()
        return self._to_legacy_dict(firecrawl_res)

    async def extract_via_tavily_batch(self, url: str, execution_id: str) -> ExtractionResult:
        """Adds URL to Tavily Redis buffer, orchestrating the batch leader election and polling."""
        from app.core.metrics import (
            newsiq_crawler_batch_wait_time_seconds,
            newsiq_crawler_redis_batch_flush_total,
            newsiq_crawler_tavily_batch_requests_total,
            newsiq_crawler_tavily_urls_processed_total,
        )

        redis_client = cache_service._redis

        # Fail-open if Redis is unavailable: make individual non-batched Tavily call
        if not redis_client:
            logger.warning("Redis is unavailable; falling back to non-batched Tavily call.")
            return await self.tavily_provider.extract(url, execution_id)

        payload_str = json.dumps(
            {"url": url, "execution_id": execution_id, "timestamp": time.time()}
        )
        buffer_key = "extraction:tavily_buffer"
        status_key = f"extraction:tavily_status:{execution_id}"
        result_key = f"extraction:result:{execution_id}"
        leader_key = "extraction:tavily_leader"

        try:
            # Record that we are pending
            await redis_client.set(status_key, "pending", ex=600)

            # Push payload to Redis list
            await redis_client.rpush(buffer_key, payload_str)  # type: ignore[misc]

            max_poll_time = (settings.TAVILY_BATCH_TIMEOUT_SECONDS or 2) + 5
            poll_start = time.time()

            while time.time() - poll_start < max_poll_time:
                # Check A: Result ready
                status = await redis_client.get(status_key)
                if status in ("success", "failed"):
                    raw_res = await redis_client.get(result_key)
                    if raw_res:
                        newsiq_crawler_batch_wait_time_seconds.observe(time.time() - poll_start)
                        await redis_client.delete(status_key)
                        await redis_client.delete(result_key)
                        return ExtractionResult.from_dict(json.loads(raw_res))

                # Check B: Leadership Acquisition (if still pending)
                # If leader lock is free, try to acquire it
                is_leader = await redis_client.set(leader_key, "1", ex=5, nx=True)
                if is_leader:
                    logger.info("Acquired Tavily leader lock; orchestrating batch flush.")
                    try:
                        # Wait up to TAVILY_BATCH_TIMEOUT_SECONDS for others to arrive
                        start_wait = time.time()
                        batch_timeout = settings.TAVILY_BATCH_TIMEOUT_SECONDS or 2
                        batch_size = settings.TAVILY_BATCH_SIZE or 5

                        while time.time() - start_wait < batch_timeout:
                            length = await redis_client.llen(buffer_key)  # type: ignore[misc]
                            if length >= batch_size:
                                break
                            await asyncio.sleep(0.1)

                        # Pop up to batch_size URLs
                        batch_payloads = []
                        for _ in range(batch_size):
                            p = await redis_client.lpop(buffer_key)  # type: ignore[misc]
                            if p:
                                batch_payloads.append(json.loads(p))
                            else:
                                break

                        if batch_payloads:
                            newsiq_crawler_redis_batch_flush_total.inc()
                            batch_urls = [p["url"] for p in batch_payloads]
                            batch_exec_ids = [p["execution_id"] for p in batch_payloads]

                            logger.info(
                                "Leader executing Tavily batch extraction for %d URLs", len(batch_urls)
                            )
                            newsiq_crawler_tavily_batch_requests_total.inc()
                            newsiq_crawler_tavily_urls_processed_total.inc(len(batch_urls))

                            url_to_exec_id = {p["url"]: p["execution_id"] for p in batch_payloads}

                            results = await self.tavily_provider.extract_batch(
                                batch_urls, batch_exec_ids
                            )

                            # Store results in Redis and update status
                            for res in results:
                                exec_id = url_to_exec_id.get(res.url)
                                if exec_id:
                                    res_key = f"extraction:result:{exec_id}"
                                    st_key = f"extraction:tavily_status:{exec_id}"
                                    await redis_client.set(res_key, json.dumps(res.to_dict()), ex=600)
                                    await redis_client.set(
                                        st_key, "success" if res.success else "failed", ex=600
                                    )
                    finally:
                        # Release the leader lock
                        await redis_client.delete(leader_key)

                # Check C: Sleep before retry
                await asyncio.sleep(0.2)

            # If polling times out: clean up keys, remove from buffer if still present, and do individual fallback
            logger.warning(
                "Polling timed out for execution_id %s; executing individual fallback.",
                execution_id,
            )
            await redis_client.lrem(buffer_key, 0, payload_str)  # type: ignore[misc]
            await redis_client.delete(status_key)
            await redis_client.delete(result_key)
            return await self.tavily_provider.extract(url, execution_id)

        except Exception as e:
            logger.error(
                "Error in Tavily batch coordination: %s. Falling back to individual Tavily.", e
            )
            # Safe cleanup attempt
            try:
                await redis_client.lrem(buffer_key, 0, payload_str)  # type: ignore[misc]
                await redis_client.delete(status_key)
                await redis_client.delete(result_key)
            except Exception:
                pass
            return await self.tavily_provider.extract(url, execution_id)

    async def _set_idempotency_cache(self, key: str, result: ExtractionResult) -> None:
        """Stores the result in idempotency cache for 10 minutes."""
        redis_client = cache_service._redis
        if redis_client:
            try:
                ttl = settings.EXTRACTION_RESULT_TTL_SECONDS or 600
                await redis_client.set(key, json.dumps(result.to_dict()), ex=ttl)
            except Exception as e:
                logger.warning("Failed to set idempotency cache: %s", e)

    async def _update_domain_policy(
        self,
        domain: str,
        provider: str,
        success: bool,
        latency_ms: float,
        content_length: int,
    ) -> None:
        """Asynchronously updates or inserts the DomainExtractionPolicy table for metrics tracking."""
        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.models.models import DomainExtractionPolicy

        async with async_session_factory() as session:
            try:
                stmt = select(DomainExtractionPolicy).where(DomainExtractionPolicy.domain == domain)
                res = await session.execute(stmt)
                policy = res.scalar_one_or_none()

                # Exponential Moving Average factor (alpha = 0.1)
                alpha = 0.1

                if not policy:
                    policy = DomainExtractionPolicy(
                        domain=domain,
                        local_success_rate=1.0 if (provider == "local" and success) else 0.0,
                        tavily_success_rate=1.0 if (provider == "tavily" and success) else 0.0,
                        firecrawl_success_rate=1.0
                        if (provider == "firecrawl" and success)
                        else 0.0,
                        average_latency=latency_ms,
                        average_content_length=float(content_length),
                        last_success_provider=provider if success else None,
                        confidence_score=1.0 if success else 0.0,
                    )
                    session.add(policy)
                else:
                    if provider == "local":
                        policy.local_success_rate = (
                            policy.local_success_rate * (1.0 - alpha)
                            + (1.0 if success else 0.0) * alpha
                        )
                    elif provider == "tavily":
                        policy.tavily_success_rate = (
                            policy.tavily_success_rate * (1.0 - alpha)
                            + (1.0 if success else 0.0) * alpha
                        )
                    elif provider == "firecrawl":
                        policy.firecrawl_success_rate = (
                            policy.firecrawl_success_rate * (1.0 - alpha)
                            + (1.0 if success else 0.0) * alpha
                        )

                    policy.average_latency = (
                        policy.average_latency * (1.0 - alpha) + latency_ms * alpha
                    )
                    if success:
                        policy.average_content_length = (
                            policy.average_content_length * (1.0 - alpha)
                            + float(content_length) * alpha
                        )
                        policy.last_success_provider = provider

                    policy.confidence_score = (
                        policy.local_success_rate * 0.5
                        + policy.tavily_success_rate * 0.3
                        + policy.firecrawl_success_rate * 0.2
                    )

                await session.commit()
            except Exception as e:
                logger.warning(
                    "Failed to update DomainExtractionPolicy for domain %s: %s", domain, e
                )

    def _to_legacy_dict(self, result: ExtractionResult) -> dict[str, Any]:
        """Convert ExtractionResult dataclass to the dictionary format expected by crawler callers."""
        failure_reason = None
        if not result.success:
            if result.failure == ExtractionFailure.HTTP_404:
                failure_reason = "HTTP_ERROR"
            elif result.failure == ExtractionFailure.HTTP_403:
                failure_reason = "HTTP_ERROR"
            elif result.failure == ExtractionFailure.BOT_BLOCKED:
                failure_reason = "BOT_BLOCKED"
            elif result.failure == ExtractionFailure.TIMEOUT:
                failure_reason = "TIMEOUT"
            elif result.failure == ExtractionFailure.EMPTY_HTML:
                failure_reason = "EXTRACTION_FAILED"
            else:
                failure_reason = "EXTRACTION_FAILED"

        diagnostics = {
            "fetch_method": result.diagnostics.fetch_method or result.diagnostics.provider,
            "status_code": result.diagnostics.status_code,
            "failure_reason": failure_reason,
            "duration_ms": result.diagnostics.latency_ms,
            "attempts": result.diagnostics.attempts,
            "bot_detected": result.diagnostics.bot_detected,
            "notes": result.diagnostics.notes,
        }

        extractor = result.provider
        for note in result.diagnostics.notes:
            if note.startswith("extractor: "):
                extractor = note[len("extractor: ") :]
                break

        return {
            "success": result.success,
            "title": result.title,
            "content": result.content,
            "author": result.author,
            "image_url": result.image_url,
            "published_at": result.published_at,
            "extractor": extractor,
            "diagnostics": diagnostics,
        }


extraction_manager = ExtractionManager()
