import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime
from typing import Any

from app.core.config import settings
from app.services.cache_service import cache_service
from app.services.extraction_provider import (
    ExtractionResult,
    FailureType,
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
        import time

        from app.core.metrics import (
            newsiq_crawler_attempts_total,
            newsiq_crawler_fallback_rate,
            newsiq_crawler_local_success_rate,
            newsiq_crawler_provider_attempts_total,
            newsiq_crawler_provider_cost_total,
            newsiq_crawler_provider_failure_total,
            newsiq_crawler_provider_latency_seconds,
            newsiq_crawler_provider_success_total,
        )
        from app.core.utils import canonicalize_url

        newsiq_crawler_attempts_total.inc()

        c_url = canonicalize_url(url)
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
                    # Convert published_at back to datetime if exists
                    if cached_data.get("published_at"):
                        cached_data["published_at"] = datetime.fromisoformat(
                            cached_data["published_at"].replace("Z", "+00:00")
                        ).replace(tzinfo=None)

                    # Return compatible format for downstream services
                    res = ExtractionResult(**cached_data)
                    return self._to_legacy_dict(res)
            except Exception as e:
                logger.warning("Failed to check idempotency cache: %s", e)

        # 2. Attempt 1: Local Crawler
        logger.info("Attempting local extraction for: %s", url)
        newsiq_crawler_provider_attempts_total.labels(provider="local").inc()
        local_start = time.perf_counter()

        local_res = await self.local_provider.extract(c_url, f"local_{url_hash}")
        local_latency = time.perf_counter() - local_start
        newsiq_crawler_provider_latency_seconds.labels(provider="local").observe(local_latency)

        if local_res.success:
            logger.info("Local extraction succeeded for: %s", url)
            newsiq_crawler_provider_success_total.labels(provider="local").inc()
            newsiq_crawler_local_success_rate.inc()
            await self._set_idempotency_cache(idempotency_key, local_res)
            return self._to_legacy_dict(local_res)

        logger.warning("Local extraction failed for %s. Reason: %s", url, local_res.error_reason)
        newsiq_crawler_provider_failure_total.labels(provider="local").inc()

        # Failure Classification: Stop immediately on 404 / Gone
        if local_res.error_reason == FailureType.FAILED_404:
            logger.warning(
                "Permanent failure (404/Gone) detected for %s. Stopping extraction.", url
            )
            return self._to_legacy_dict(local_res)

        # 3. Attempt 2: Tavily Extract (with Redis distributed batching)
        newsiq_crawler_fallback_rate.inc()
        logger.info("Routing %s to Tavily Extract batch queue", url)
        newsiq_crawler_provider_attempts_total.labels(provider="tavily").inc()
        tavily_start = time.perf_counter()

        tavily_res = await self.extract_via_tavily_batch(c_url, f"tavily_{url_hash}")
        tavily_latency = time.perf_counter() - tavily_start
        newsiq_crawler_provider_latency_seconds.labels(provider="tavily").observe(tavily_latency)

        if tavily_res.success:
            logger.info("Tavily extraction succeeded for: %s", url)
            newsiq_crawler_provider_success_total.labels(provider="tavily").inc()
            # 1 credit per 5 URLs = 0.2 credits per URL. Let's record cost (1 credit = $0.01 estimation)
            newsiq_crawler_provider_cost_total.labels(provider="tavily").inc(0.2)
            await self._set_idempotency_cache(idempotency_key, tavily_res)
            return self._to_legacy_dict(tavily_res)

        logger.warning("Tavily extraction failed for %s. Reason: %s", url, tavily_res.error_reason)
        newsiq_crawler_provider_failure_total.labels(provider="tavily").inc()

        # 4. Attempt 3: Firecrawl Scrape (final synchronous fallback)
        logger.info("Routing %s to Firecrawl Scrape", url)
        newsiq_crawler_provider_attempts_total.labels(provider="firecrawl").inc()
        firecrawl_start = time.perf_counter()

        firecrawl_res = await self.firecrawl_provider.extract(c_url, f"firecrawl_{url_hash}")
        firecrawl_latency = time.perf_counter() - firecrawl_start
        newsiq_crawler_provider_latency_seconds.labels(provider="firecrawl").observe(
            firecrawl_latency
        )

        if firecrawl_res.success:
            logger.info("Firecrawl extraction succeeded for: %s", url)
            newsiq_crawler_provider_success_total.labels(provider="firecrawl").inc()
            # Firecrawl cost is 1 credit per scrape
            newsiq_crawler_provider_cost_total.labels(provider="firecrawl").inc(1.0)
            await self._set_idempotency_cache(idempotency_key, firecrawl_res)
            return self._to_legacy_dict(firecrawl_res)

        logger.error("All extraction providers failed for URL: %s", url)
        newsiq_crawler_provider_failure_total.labels(provider="firecrawl").inc()
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

        try:
            buffer_key = "extraction:tavily_buffer"
            status_key = f"extraction:tavily_status:{execution_id}"
            result_key = f"extraction:result:{execution_id}"

            # Record that we are pending
            await redis_client.set(status_key, "pending", ex=600)

            # Push payload to Redis list
            payload = json.dumps(
                {"url": url, "execution_id": execution_id, "timestamp": time.time()}
            )
            await redis_client.rpush(buffer_key, payload)  # type: ignore[misc]

            # Try to acquire the leader lock (5 seconds lock TTL)
            leader_key = "extraction:tavily_leader"
            is_leader = await redis_client.set(leader_key, "1", ex=5, nx=True)

            if is_leader:
                logger.info("Acquired Tavily leader lock; orchestrating batch flush.")
                try:
                    # Low Traffic Batch Flush: Wait up to TAVILY_BATCH_TIMEOUT_SECONDS
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

                        results = await self.tavily_provider.extract_batch(
                            batch_urls, batch_exec_ids
                        )

                        # Store results in Redis and update status
                        for res in results:
                            res_key = f"extraction:result:{res.execution_id}"
                            st_key = f"extraction:tavily_status:{res.execution_id}"
                            await redis_client.set(res_key, res.model_dump_json(), ex=600)
                            await redis_client.set(
                                st_key, "success" if res.success else "failed", ex=600
                            )
                finally:
                    # Release the leader lock
                    await redis_client.delete(leader_key)

            # Both Leader and Workers poll their result_key
            max_poll_time = (settings.TAVILY_BATCH_TIMEOUT_SECONDS or 2) + 5
            poll_start = time.time()
            while time.time() - poll_start < max_poll_time:
                status = await redis_client.get(status_key)
                if status in ("success", "failed"):
                    raw_res = await redis_client.get(result_key)
                    if raw_res:
                        newsiq_crawler_batch_wait_time_seconds.observe(time.time() - poll_start)
                        # Clean up result and status keys immediately
                        await redis_client.delete(status_key)
                        await redis_client.delete(result_key)
                        return ExtractionResult.model_validate_json(raw_res)
                await asyncio.sleep(0.2)

            # If polling times out: clean up keys and do self-extraction fallback
            logger.warning(
                "Polling timed out for execution_id %s; executing individual fallback.",
                execution_id,
            )
            await redis_client.delete(status_key)
            await redis_client.delete(result_key)
            return await self.tavily_provider.extract(url, execution_id)

        except Exception as e:
            logger.error(
                "Error in Tavily batch coordination: %s. Falling back to individual Tavily.", e
            )
            return await self.tavily_provider.extract(url, execution_id)

    async def _set_idempotency_cache(self, key: str, result: ExtractionResult) -> None:
        """Stores the result in idempotency cache for 10 minutes."""
        redis_client = cache_service._redis
        if redis_client:
            try:
                ttl = settings.EXTRACTION_RESULT_TTL_SECONDS or 600
                await redis_client.set(key, result.model_dump_json(), ex=ttl)
            except Exception as e:
                logger.warning("Failed to set idempotency cache: %s", e)

    def _to_legacy_dict(self, result: ExtractionResult) -> dict[str, Any]:
        """Convert ExtractionResult model to the dictionary format expected by crawler callers."""
        failure_reason = None
        if not result.success:
            if result.error_reason == FailureType.FAILED_404:
                failure_reason = "HTTP_ERROR"
            elif result.error_reason == FailureType.FAILED_403:
                failure_reason = "HTTP_ERROR"
            elif result.error_reason == FailureType.FAILED_CLOUDFLARE:
                failure_reason = "BOT_BLOCKED"
            elif result.error_reason == FailureType.FAILED_TIMEOUT:
                failure_reason = "TIMEOUT"
            elif result.error_reason == FailureType.FAILED_EMPTY:
                failure_reason = "EXTRACTION_FAILED"
            else:
                failure_reason = "EXTRACTION_FAILED"

        diagnostics = {
            "fetch_method": result.provider,
            "status_code": result.error_code,
            "failure_reason": failure_reason,
            "duration_ms": result.latency_ms,
        }
        if result.diagnostics:
            diagnostics.update(result.diagnostics)
            if not result.success and failure_reason:
                diagnostics["failure_reason"] = failure_reason

        return {
            "success": result.success,
            "title": result.title,
            "content": result.content,
            "author": result.authors,
            "image_url": None,  # Kept for backward compatibility
            "published_at": result.published_at,
            "extractor": result.extractor or result.provider,
            "diagnostics": diagnostics,
        }


extraction_manager = ExtractionManager()
