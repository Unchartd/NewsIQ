from __future__ import annotations

import asyncio
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.services.extraction.types import (
    ExtractionDiagnostics,
    ExtractionFailure,
    ExtractionResult,
)

logger = logging.getLogger(__name__)


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
        latency = (time.perf_counter() - start_time) * 1000.0

        status_code = diagnostics.get("status_code")
        notes = []
        if diagnostics.get("fetch_method"):
            notes.append(f"fetch_method: {diagnostics.get('fetch_method')}")

        failure_reason_raw = diagnostics.get("failure_reason")
        failure = None
        if failure_reason_raw == "BOT_BLOCKED":
            failure = ExtractionFailure.BOT_BLOCKED
        elif failure_reason_raw == "TIMEOUT":
            failure = ExtractionFailure.TIMEOUT
        elif failure_reason_raw == "EMPTY_HTML":
            failure = ExtractionFailure.EMPTY_HTML
        elif status_code == 404:
            failure = ExtractionFailure.HTTP_404
        elif status_code in (401, 403):
            failure = ExtractionFailure.HTTP_403
        elif failure_reason_raw == "HTTP_ERROR":
            failure = ExtractionFailure.HTTP_ERROR
        elif failure_reason_raw:
            failure = ExtractionFailure.UNKNOWN

        diag = ExtractionDiagnostics(
            provider="local",
            attempts=1,
            latency_ms=latency,
            status_code=status_code,
            bot_detected=bool(failure == ExtractionFailure.BOT_BLOCKED),
            notes=notes,
            fetch_method=diagnostics.get("fetch_method"),
        )

        res = ExtractionResult(
            success=False,
            provider="local",
            failure=failure or ExtractionFailure.UNKNOWN,
            url=url,
            title=None,
            content="",
            author=None,
            image_url=None,
            published_at=None,
            diagnostics=diag,
        )

        if not html:
            return res

        # Run extraction chain
        parsed = await asyncio.to_thread(self._extract_newspaper, url, html)
        if parsed and parsed.get("content"):
            res.success = True
            res.title = parsed.get("title")
            res.content = parsed.get("content")
            res.author = parsed.get("author")
            res.image_url = parsed.get("image_url")
            res.published_at = parsed.get("published_at")
            res.failure = ExtractionFailure.SUCCESS
            res.diagnostics.notes.append("extractor: newspaper4k")
            return res

        parsed = await asyncio.to_thread(self._extract_trafilatura, html)
        if parsed and parsed.get("content"):
            res.success = True
            res.title = parsed.get("title")
            res.content = parsed.get("content")
            res.author = parsed.get("author")
            res.published_at = parsed.get("published_at")
            res.failure = ExtractionFailure.SUCCESS
            res.diagnostics.notes.append("extractor: trafilatura")
            return res

        parsed = await asyncio.to_thread(self._extract_readability, html)
        if parsed and parsed.get("content"):
            res.success = True
            res.title = parsed.get("title")
            res.content = parsed.get("content")
            res.failure = ExtractionFailure.SUCCESS
            res.diagnostics.notes.append("extractor: readability-lxml")
            return res

        parsed = await asyncio.to_thread(self._extract_custom_cleaner, html)
        if parsed and parsed.get("content"):
            res.success = True
            res.title = parsed.get("title")
            res.content = parsed.get("content")
            res.failure = ExtractionFailure.SUCCESS
            res.diagnostics.notes.append("extractor: custom-bs4")
            return res

        res.failure = ExtractionFailure.PARSER_FAILED
        res.diagnostics.notes.append("all extractors failed to parse content")
        return res

    def _extract_newspaper(self, url: str, html: str) -> dict[str, Any] | None:
        """Extract article content using newspaper4k."""
        try:
            import newspaper

            article = newspaper.article(url=url, language="en", input_html=html)
            text = article.text.strip() if article.text else ""
            if len(text) >= 150:
                authors = ", ".join(article.authors) if article.authors else None
                publish_date = article.publish_date
                if publish_date and hasattr(publish_date, "replace"):
                    publish_date = publish_date.replace(tzinfo=None)

                return {
                    "content": text,
                    "title": article.title.strip() if article.title else None,
                    "author": authors,
                    "image_url": article.top_image if article.top_image else None,
                    "published_at": publish_date,
                    "extractor": "newspaper4k",
                }
        except Exception as e:
            logger.debug("newspaper4k extraction failed for %s: %s", url, e)
        return None

    def _extract_trafilatura(self, html: str) -> dict[str, Any] | None:
        """Extract article content using trafilatura."""
        try:
            import trafilatura

            text = trafilatura.extract(html, include_comments=False)
            if text:
                text = text.strip()
                if len(text) >= 150:
                    metadata = trafilatura.extract_metadata(html)
                    title = metadata.title.strip() if metadata and metadata.title else None
                    author = metadata.author.strip() if metadata and metadata.author else None
                    published_at = None
                    if metadata and metadata.date:
                        try:
                            from dateutil import parser

                            published_at = parser.parse(metadata.date).replace(tzinfo=None)
                        except Exception:
                            pass
                    return {
                        "content": text,
                        "title": title,
                        "author": author,
                        "image_url": None,
                        "published_at": published_at,
                        "extractor": "trafilatura",
                    }
        except Exception as e:
            logger.debug("trafilatura extraction failed: %s", e)
        return None

    def _extract_readability(self, html: str) -> dict[str, Any] | None:
        """Extract article content using readability-lxml."""
        try:
            from readability import Document

            doc = Document(html)
            summary_html = doc.summary()
            title = doc.title().strip() if doc.title() else None

            soup = BeautifulSoup(summary_html, "html.parser")
            text = soup.get_text(separator=" ", strip=True)
            if len(text) >= 150:
                return {
                    "content": text,
                    "title": title,
                    "author": None,
                    "image_url": None,
                    "published_at": None,
                    "extractor": "readability-lxml",
                }
        except Exception as e:
            logger.debug("readability-lxml extraction failed: %s", e)
        return None

    def _extract_custom_cleaner(self, html: str) -> dict[str, Any] | None:
        """Fallback custom BeautifulSoup cleaner to scrub boilerplate."""
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Decompose boilerplate elements
            for tag in ["script", "style", "iframe", "nav", "footer", "header", "form", "noscript"]:
                for el in soup.find_all(tag):
                    el.decompose()

            # Remove class/id with ad or navigation patterns
            patterns = [
                "ads",
                "advertisement",
                "ad-container",
                "social-share",
                "related-posts",
                "sidebar",
                "menu",
                "nav-links",
            ]
            for pattern in patterns:
                for el in soup.find_all(class_=re.compile(pattern, re.I)):
                    el.decompose()
                for el in soup.find_all(id=re.compile(pattern, re.I)):
                    el.decompose()

            title = None
            if soup.title:
                title = soup.title.string.strip() if soup.title.string else None
            elif soup.h1:
                title = soup.h1.get_text().strip()

            text = soup.get_text(separator=" ", strip=True)
            text = re.sub(r"\s+", " ", text).strip()

            if len(text) >= 150:
                return {
                    "content": text,
                    "title": title,
                    "author": None,
                    "image_url": None,
                    "published_at": None,
                    "extractor": "custom-bs4",
                }
        except Exception as e:
            logger.debug("custom-bs4 extraction failed: %s", e)
        return None


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
                failure=ExtractionFailure.UNKNOWN,
                url=url,
                title=None,
                content="",
                author=None,
                image_url=None,
                published_at=None,
                diagnostics=ExtractionDiagnostics(
                    provider="tavily",
                    attempts=1,
                    latency_ms=0.0,
                    status_code=None,
                    bot_detected=False,
                    notes=[],
                ),
            )
            for url, exec_id in zip(urls, execution_ids)
        }

        if not settings.TAVILY_API_KEY:
            logger.warning("Tavily API key is not configured.")
            for res in results_map.values():
                res.failure = ExtractionFailure.HTTP_401
                res.diagnostics.status_code = 401
                res.diagnostics.notes.append("API key missing")
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

                for res in results_map.values():
                    res.diagnostics.latency_ms = latency
                    res.diagnostics.status_code = response.status_code

                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("results", []):
                        url = item.get("url")
                        if url in results_map:
                            res = results_map[url]
                            res.success = True
                            res.content = item.get("raw_content") or ""
                            res.title = item.get("title")
                            res.failure = ExtractionFailure.SUCCESS

                    for item in data.get("failed_results", []):
                        url = item.get("url")
                        if url in results_map:
                            res = results_map[url]
                            res.success = False
                            res.failure = ExtractionFailure.HTTP_ERROR
                            res.diagnostics.notes.append(
                                item.get("error", "Tavily extraction failed")
                            )
                else:
                    for res in results_map.values():
                        if response.status_code in (401, 403):
                            res.failure = ExtractionFailure.HTTP_403
                        else:
                            res.failure = ExtractionFailure.HTTP_ERROR
        except httpx.TimeoutException:
            latency = (time.perf_counter() - start_time) * 1000.0
            for res in results_map.values():
                res.failure = ExtractionFailure.TIMEOUT
                res.diagnostics.latency_ms = latency
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000.0
            for res in results_map.values():
                res.failure = ExtractionFailure.UNKNOWN
                res.diagnostics.latency_ms = latency
                res.diagnostics.notes.append(str(e))
                logger.error("Tavily extract request failed: %s", e)

        return list(results_map.values())

    async def extract(self, url: str, execution_id: str) -> ExtractionResult:
        res = await self.extract_batch([url], [execution_id])
        return res[0]


class FirecrawlProvider(ExtractionProvider):
    async def extract(self, url: str, execution_id: str) -> ExtractionResult:
        """Firecrawl Scrape API for fallback extraction of a single URL."""
        start_time = time.perf_counter()
        diag = ExtractionDiagnostics(
            provider="firecrawl",
            attempts=1,
            latency_ms=0.0,
            status_code=None,
            bot_detected=False,
            notes=[],
        )
        res = ExtractionResult(
            success=False,
            provider="firecrawl",
            failure=ExtractionFailure.UNKNOWN,
            url=url,
            title=None,
            content="",
            author=None,
            image_url=None,
            published_at=None,
            diagnostics=diag,
        )

        if not settings.FIRECRAWL_API_KEY:
            logger.warning("Firecrawl API key is not configured.")
            res.diagnostics.status_code = 401
            res.failure = ExtractionFailure.HTTP_401
            res.diagnostics.notes.append("API key missing")
            res.diagnostics.latency_ms = (time.perf_counter() - start_time) * 1000.0
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
                res.diagnostics.latency_ms = (time.perf_counter() - start_time) * 1000.0
                res.diagnostics.status_code = response.status_code

                if response.status_code == 200:
                    data = response.json()
                    if data.get("success") and "data" in data:
                        scrape_data = data["data"]
                        res.success = True
                        res.content = scrape_data.get("markdown") or ""

                        metadata = scrape_data.get("metadata", {})
                        res.title = metadata.get("title")
                        res.author = metadata.get("author")

                        pub_raw = metadata.get("published_at") or metadata.get("date")
                        if pub_raw:
                            try:
                                from dateutil import parser

                                res.published_at = parser.parse(pub_raw).replace(tzinfo=None)
                            except Exception:
                                pass
                        res.failure = ExtractionFailure.SUCCESS
                    else:
                        res.failure = ExtractionFailure.UNKNOWN
                        res.diagnostics.notes.append(
                            data.get("error", "Firecrawl extraction failed")
                        )
                else:
                    if response.status_code in (401, 403):
                        res.failure = ExtractionFailure.HTTP_403
                    else:
                        res.failure = ExtractionFailure.HTTP_ERROR
        except httpx.TimeoutException:
            res.failure = ExtractionFailure.TIMEOUT
            res.diagnostics.latency_ms = (time.perf_counter() - start_time) * 1000.0
        except Exception as e:
            res.failure = ExtractionFailure.UNKNOWN
            res.diagnostics.latency_ms = (time.perf_counter() - start_time) * 1000.0
            res.diagnostics.notes.append(str(e))
            logger.error("Firecrawl scrape request failed: %s", e)

        return res
