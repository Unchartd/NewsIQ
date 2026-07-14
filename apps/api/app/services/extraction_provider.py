import asyncio
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum
from typing import Any

import httpx
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)


class FailureType(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED_TIMEOUT = "FAILED_TIMEOUT"
    FAILED_403 = "FAILED_403"
    FAILED_404 = "FAILED_404"
    FAILED_CLOUDFLARE = "FAILED_CLOUDFLARE"
    FAILED_EMPTY = "FAILED_EMPTY"
    FAILED_JS = "FAILED_JS"
    FAILED_UNKNOWN = "FAILED_UNKNOWN"


class ExtractionResult(BaseModel):
    success: bool
    provider: str
    extractor: str | None = None
    title: str | None = None
    content: str | None = None
    authors: str | None = None
    published_at: datetime | None = None
    language: str | None = "en"
    error_code: int | None = None
    error_reason: FailureType | None = None
    latency_ms: float = 0.0
    execution_id: str
    diagnostics: dict[str, Any] | None = None


class ExtractionProvider(ABC):
    @abstractmethod
    async def extract(self, url: str, execution_id: str) -> ExtractionResult:
        """Extract article content from a single URL."""
        pass


class LocalCrawlerProvider(ExtractionProvider):
    async def extract(self, url: str, execution_id: str) -> ExtractionResult:
        from app.services.crawler_service import crawler_service

        start_time = time.perf_counter()
        html, diagnostics = await crawler_service.fetch_html(url)

        res = ExtractionResult(
            success=False,
            provider="local",
            execution_id=execution_id,
            error_code=diagnostics.get("status_code"),
            latency_ms=(time.perf_counter() - start_time) * 1000.0,
            diagnostics=diagnostics,
        )

        failure_reason_raw = diagnostics.get("failure_reason")
        if failure_reason_raw == "BOT_BLOCKED":
            res.error_reason = FailureType.FAILED_CLOUDFLARE
        elif failure_reason_raw == "TIMEOUT":
            res.error_reason = FailureType.FAILED_TIMEOUT
        elif failure_reason_raw == "EMPTY_HTML":
            res.error_reason = FailureType.FAILED_EMPTY
        elif diagnostics.get("status_code") in (404, 410):
            res.error_reason = FailureType.FAILED_404
        elif diagnostics.get("status_code") in (401, 403):
            res.error_reason = FailureType.FAILED_403
        else:
            res.error_reason = FailureType.FAILED_UNKNOWN

        if not html:
            return res

        # Fallback extraction chain
        parsed = await asyncio.to_thread(crawler_service._extract_newspaper, url, html)
        if parsed and parsed.get("content"):
            res.success = True
            res.title = parsed.get("title")
            res.content = parsed.get("content")
            res.authors = parsed.get("author")
            res.published_at = parsed.get("published_at")
            res.extractor = "newspaper4k"
            res.error_reason = FailureType.SUCCESS
            return res

        parsed = await asyncio.to_thread(crawler_service._extract_trafilatura, html)
        if parsed and parsed.get("content"):
            res.success = True
            res.title = parsed.get("title")
            res.content = parsed.get("content")
            res.authors = parsed.get("author")
            res.published_at = parsed.get("published_at")
            res.extractor = "trafilatura"
            res.error_reason = FailureType.SUCCESS
            return res

        parsed = await asyncio.to_thread(crawler_service._extract_readability, html)
        if parsed and parsed.get("content"):
            res.success = True
            res.title = parsed.get("title")
            res.content = parsed.get("content")
            res.extractor = "readability-lxml"
            res.error_reason = FailureType.SUCCESS
            return res

        parsed = await asyncio.to_thread(crawler_service._extract_custom_cleaner, html)
        if parsed and parsed.get("content"):
            res.success = True
            res.title = parsed.get("title")
            res.content = parsed.get("content")
            res.extractor = "custom-bs4"
            res.error_reason = FailureType.SUCCESS
            return res

        res.error_reason = FailureType.FAILED_EMPTY
        return res


class TavilyExtractProvider(ExtractionProvider):
    async def extract_batch(
        self, urls: list[str], execution_ids: list[str]
    ) -> list[ExtractionResult]:
        """Tavily Extract API: executes a single batch request for up to 5 URLs."""
        if not urls:
            return []

        start_time = time.perf_counter()
        results_map = {
            url: ExtractionResult(
                success=False,
                provider="tavily",
                execution_id=exec_id,
                error_reason=FailureType.FAILED_UNKNOWN,
            )
            for url, exec_id in zip(urls, execution_ids)
        }

        if not settings.TAVILY_API_KEY:
            logger.warning("Tavily API key is not configured.")
            for res in results_map.values():
                res.error_reason = FailureType.FAILED_UNKNOWN
                res.error_code = 401
            return list(results_map.values())

        try:
            payload = {
                "urls": urls,
                "extract_depth": "basic",
                "include_images": True,
            }
            headers = {
                "Authorization": f"Bearer {settings.TAVILY_API_KEY}",
                "Content-Type": "application/json",
            }
            timeout_cfg = settings.EXTRACTION_PROVIDER_TIMEOUT or 30

            async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                response = await client.post(
                    "https://api.tavily.com/extract", json=payload, headers=headers
                )
                latency = (time.perf_counter() - start_time) * 1000.0

                if response.status_code == 200:
                    data = response.json()
                    # Parse successful results
                    for item in data.get("results", []):
                        url = item.get("url")
                        if url in results_map:
                            res = results_map[url]
                            res.success = True
                            res.content = item.get("raw_content")
                            # Tavily doesn't explicitly return parsed metadata in basic Extract but let's check
                            res.title = item.get("title")
                            res.error_reason = FailureType.SUCCESS
                            res.latency_ms = latency

                    # Parse failures
                    for item in data.get("failed_results", []):
                        url = item.get("url")
                        if url in results_map:
                            res = results_map[url]
                            res.success = False
                            res.error_reason = FailureType.FAILED_UNKNOWN
                            res.latency_ms = latency
                else:
                    for res in results_map.values():
                        res.error_code = response.status_code
                        res.latency_ms = latency
                        if response.status_code in (401, 403):
                            res.error_reason = FailureType.FAILED_403
                        else:
                            res.error_reason = FailureType.FAILED_UNKNOWN
        except httpx.TimeoutException:
            latency = (time.perf_counter() - start_time) * 1000.0
            for res in results_map.values():
                res.error_reason = FailureType.FAILED_TIMEOUT
                res.latency_ms = latency
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000.0
            for res in results_map.values():
                res.error_reason = FailureType.FAILED_UNKNOWN
                res.latency_ms = latency
                logger.error("Tavily extract request failed: %s", e)

        return list(results_map.values())

    async def extract(self, url: str, execution_id: str) -> ExtractionResult:
        res = await self.extract_batch([url], [execution_id])
        return res[0]


class FirecrawlProvider(ExtractionProvider):
    async def extract(self, url: str, execution_id: str) -> ExtractionResult:
        """Firecrawl Scrape API for fallback extraction of a single URL."""
        start_time = time.perf_counter()
        res = ExtractionResult(
            success=False,
            provider="firecrawl",
            execution_id=execution_id,
            error_reason=FailureType.FAILED_UNKNOWN,
        )

        if not settings.FIRECRAWL_API_KEY:
            logger.warning("Firecrawl API key is not configured.")
            res.error_code = 401
            res.error_reason = FailureType.FAILED_UNKNOWN
            res.latency_ms = (time.perf_counter() - start_time) * 1000.0
            return res

        try:
            payload = {
                "url": url,
                "formats": ["markdown"],
            }
            headers = {
                "Authorization": f"Bearer {settings.FIRECRAWL_API_KEY}",
                "Content-Type": "application/json",
            }
            timeout_cfg = settings.EXTRACTION_PROVIDER_TIMEOUT or 30

            async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                response = await client.post(
                    "https://api.firecrawl.dev/v1/scrape", json=payload, headers=headers
                )
                res.latency_ms = (time.perf_counter() - start_time) * 1000.0
                res.error_code = response.status_code

                if response.status_code == 200:
                    data = response.json()
                    if data.get("success") and "data" in data:
                        scrape_data = data["data"]
                        res.success = True
                        res.content = scrape_data.get("markdown")

                        metadata = scrape_data.get("metadata", {})
                        res.title = metadata.get("title")
                        res.authors = metadata.get("author")

                        pub_raw = metadata.get("published_at") or metadata.get("date")
                        if pub_raw:
                            try:
                                from dateutil import parser

                                res.published_at = parser.parse(pub_raw).replace(tzinfo=None)
                            except Exception:
                                pass
                        res.error_reason = FailureType.SUCCESS
                    else:
                        res.error_reason = FailureType.FAILED_UNKNOWN
                else:
                    if response.status_code in (401, 403):
                        res.error_reason = FailureType.FAILED_403
                    else:
                        res.error_reason = FailureType.FAILED_UNKNOWN
        except httpx.TimeoutException:
            res.error_reason = FailureType.FAILED_TIMEOUT
            res.latency_ms = (time.perf_counter() - start_time) * 1000.0
        except Exception as e:
            res.error_reason = FailureType.FAILED_UNKNOWN
            res.latency_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error("Firecrawl scrape request failed: %s", e)

        return res
