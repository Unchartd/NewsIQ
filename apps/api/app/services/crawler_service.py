import asyncio
import logging
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class CrawlerService:
    """Crawler service that fetches full-text article contents using a fallback stack.

    Stack:
    1. newspaper4k (Primary) - Excellent metadata and text parser.
    2. trafilatura (Secondary) - High precision text extractor.
    3. readability-lxml (Tertiary) - Structural DOM density extraction.
    4. Custom BS4 Cleaner (Quaternary) - Strip boilerplate & extract remaining text.
    """

    def __init__(self) -> None:
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    async def fetch_html(self, url: str) -> tuple[str | None, dict[str, Any]]:
        """Fetch raw HTML content of a URL using a progressive, multi-level fetch strategy.

        Returns (html_content, diagnostics_dict).
        """
        import time
        from app.core.metrics import (
            newsiq_crawler_http_success_total,
            newsiq_crawler_http_failure_total,
            newsiq_crawler_bot_block_total,
            newsiq_crawler_timeout_total,
            newsiq_crawler_empty_html_total,
        )

        start_time = time.perf_counter()
        diagnostics = {
            "fetch_method": "none",
            "status_code": None,
            "failure_reason": None,
            "duration_ms": 0.0,
        }

        # Anti-bot detection helper
        def check_bot_blocking(html: str) -> bool:
            if not html:
                return False
            lowered = html.lower()
            block_signals = [
                "checking your browser",
                "please enable js",
                "enable javascript",
                "access denied",
                "cloudflare",
                "cmsg",
                "security check",
                "ddos protection",
                "attention required",
                "bot detection",
                "robot check",
                "distil networks",
            ]
            return any(sig in lowered for sig in block_signals)

        # Attempt 1: httpx with normal browser headers
        logger.info("Attempt 1: Fetching %s via httpx", url)
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout=30.0, connect=10.0),
                follow_redirects=True,
                headers=self.headers
            ) as client:
                response = await client.get(url)
                diagnostics["status_code"] = response.status_code
                diagnostics["fetch_method"] = "httpx"

                if response.status_code == 200:
                    html = response.text
                    if not html or not html.strip():
                        newsiq_crawler_empty_html_total.inc()
                        diagnostics["failure_reason"] = "EMPTY_HTML"
                        logger.warning("Attempt 1 returned empty HTML for %s", url)
                    elif check_bot_blocking(html):
                        newsiq_crawler_bot_block_total.inc()
                        diagnostics["failure_reason"] = "BOT_BLOCKED"
                        logger.warning("Attempt 1 blocked by bot protection for %s", url)
                    else:
                        newsiq_crawler_http_success_total.inc()
                        diagnostics["duration_ms"] = (time.perf_counter() - start_time) * 1000
                        return html, diagnostics
                else:
                    newsiq_crawler_http_failure_total.labels(reason=str(response.status_code)).inc()
                    if response.status_code in (401, 403):
                        newsiq_crawler_bot_block_total.inc()
                        diagnostics["failure_reason"] = "BOT_BLOCKED"
                    else:
                        diagnostics["failure_reason"] = "HTTP_ERROR"
                    logger.warning("Attempt 1 failed with status %d for %s", response.status_code, url)
        except httpx.TimeoutException as te:
            newsiq_crawler_timeout_total.inc()
            newsiq_crawler_http_failure_total.labels(reason="TimeoutException").inc()
            diagnostics["failure_reason"] = "TIMEOUT"
            logger.warning("Attempt 1 timed out for %s: %s", url, te)
        except Exception as e:
            err_name = type(e).__name__
            newsiq_crawler_http_failure_total.labels(reason=err_name).inc()
            diagnostics["failure_reason"] = "HTTP_ERROR"
            logger.warning("Attempt 1 failed for %s: %s", url, e)

        # Attempt 2: curl-cffi Chrome TLS impersonation
        logger.info("Attempt 2: Fetching %s via curl-cffi Chrome impersonation", url)
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate="chrome") as session:
                response = await session.get(url, timeout=30.0)
                diagnostics["status_code"] = response.status_code
                diagnostics["fetch_method"] = "curl_cffi_chrome"

                if response.status_code == 200:
                    html = response.text
                    if not html or not html.strip():
                        newsiq_crawler_empty_html_total.inc()
                        diagnostics["failure_reason"] = "EMPTY_HTML"
                        logger.warning("Attempt 2 returned empty HTML for %s", url)
                    elif check_bot_blocking(html):
                        newsiq_crawler_bot_block_total.inc()
                        diagnostics["failure_reason"] = "BOT_BLOCKED"
                        logger.warning("Attempt 2 blocked by bot protection for %s", url)
                    else:
                        newsiq_crawler_http_success_total.inc()
                        diagnostics["failure_reason"] = None
                        diagnostics["duration_ms"] = (time.perf_counter() - start_time) * 1000
                        return html, diagnostics
                else:
                    newsiq_crawler_http_failure_total.labels(reason=f"curl_{response.status_code}").inc()
                    if response.status_code in (401, 403):
                        newsiq_crawler_bot_block_total.inc()
                        diagnostics["failure_reason"] = "BOT_BLOCKED"
                    else:
                        diagnostics["failure_reason"] = "HTTP_ERROR"
                    logger.warning("Attempt 2 failed with status %d for %s", response.status_code, url)
        except Exception as e:
            err_name = f"curl_{type(e).__name__}"
            newsiq_crawler_http_failure_total.labels(reason=err_name).inc()
            if "timeout" in str(e).lower():
                newsiq_crawler_timeout_total.inc()
                diagnostics["failure_reason"] = "TIMEOUT"
            else:
                diagnostics["failure_reason"] = "HTTP_ERROR"
            logger.warning("Attempt 2 failed for %s: %s", url, e)

        # Attempt 3: curl-cffi Safari/Firefox retry with longer timeout
        logger.info("Attempt 3: Fetching %s via curl-cffi Safari/Firefox impersonation", url)
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate="safari") as session:
                response = await session.get(url, timeout=45.0)
                diagnostics["status_code"] = response.status_code
                diagnostics["fetch_method"] = "curl_cffi_safari"

                if response.status_code == 200:
                    html = response.text
                    if not html or not html.strip():
                        newsiq_crawler_empty_html_total.inc()
                        diagnostics["failure_reason"] = "EMPTY_HTML"
                        logger.warning("Attempt 3 returned empty HTML for %s", url)
                    elif check_bot_blocking(html):
                        newsiq_crawler_bot_block_total.inc()
                        diagnostics["failure_reason"] = "BOT_BLOCKED"
                        logger.warning("Attempt 3 blocked by bot protection for %s", url)
                    else:
                        newsiq_crawler_http_success_total.inc()
                        diagnostics["failure_reason"] = None
                        diagnostics["duration_ms"] = (time.perf_counter() - start_time) * 1000
                        return html, diagnostics
                else:
                    newsiq_crawler_http_failure_total.labels(reason=f"curl_safari_{response.status_code}").inc()
                    if response.status_code in (401, 403):
                        newsiq_crawler_bot_block_total.inc()
                        diagnostics["failure_reason"] = "BOT_BLOCKED"
                    else:
                        diagnostics["failure_reason"] = "HTTP_ERROR"
                    logger.warning("Attempt 3 failed with status %d for %s", response.status_code, url)
        except Exception as e:
            err_name = f"curl_safari_{type(e).__name__}"
            newsiq_crawler_http_failure_total.labels(reason=err_name).inc()
            if "timeout" in str(e).lower():
                newsiq_crawler_timeout_total.inc()
                diagnostics["failure_reason"] = "TIMEOUT"
            else:
                diagnostics["failure_reason"] = "HTTP_ERROR"
            logger.warning("Attempt 3 failed for %s: %s", url, e)

        diagnostics["duration_ms"] = (time.perf_counter() - start_time) * 1000
        return None, diagnostics

    def _extract_newspaper(self, url: str, html: str) -> dict[str, Any] | None:
        """Extract article content using newspaper4k."""
        try:
            import newspaper

            article = newspaper.article(url=url, language="en", input_html=html)
            text = article.text.strip() if article.text else ""
            if len(text) >= 150:
                # Format authors list
                authors = ", ".join(article.authors) if article.authors else None
                # Parse date if available
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

            # Extract title if possible
            title = None
            if soup.title:
                title = soup.title.string.strip() if soup.title.string else None
            elif soup.h1:
                title = soup.h1.get_text().strip()

            text = soup.get_text(separator=" ", strip=True)
            # Remove multiple spaces/newlines
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

    async def crawl_article(self, url: str) -> dict[str, Any]:
        """Crawl a URL, clean, validate, extract content, and return full results & diagnostics.

        Always returns a dictionary containing at least 'success' and 'diagnostics'.
        """
        import time
        from app.core.metrics import (
            newsiq_crawler_extraction_success_total,
            newsiq_crawler_extraction_failure_total,
        )

        start_time = time.perf_counter()
        
        # 1. Fetch raw HTML
        html, diagnostics = await self.fetch_html(url)
        
        result_template = {
            "success": False,
            "title": None,
            "content": None,
            "author": None,
            "image_url": None,
            "published_at": None,
            "extractor": None,
            "diagnostics": diagnostics,
        }

        if not html:
            # failure_reason is already populated by fetch_html
            diagnostics["duration_ms"] = (time.perf_counter() - start_time) * 1000
            return result_template

        # 2. Pre-validate HTML content length
        if not html.strip():
            diagnostics["failure_reason"] = "EMPTY_HTML"
            diagnostics["duration_ms"] = (time.perf_counter() - start_time) * 1000
            return result_template

        # 3. Fallback extraction chain
        # Try newspaper4k
        extraction_res = await asyncio.to_thread(self._extract_newspaper, url, html)
        if extraction_res and extraction_res.get("content"):
            logger.info("Successfully extracted article from %s using newspaper4k", url)
            newsiq_crawler_extraction_success_total.labels(extractor="newspaper4k").inc()
            result_template.update(extraction_res)
            result_template["success"] = True
            diagnostics["duration_ms"] = (time.perf_counter() - start_time) * 1000
            return result_template

        # Try trafilatura
        extraction_res = await asyncio.to_thread(self._extract_trafilatura, html)
        if extraction_res and extraction_res.get("content"):
            logger.info("Successfully extracted article from %s using trafilatura", url)
            newsiq_crawler_extraction_success_total.labels(extractor="trafilatura").inc()
            result_template.update(extraction_res)
            result_template["success"] = True
            diagnostics["duration_ms"] = (time.perf_counter() - start_time) * 1000
            return result_template

        # Try readability-lxml
        extraction_res = await asyncio.to_thread(self._extract_readability, html)
        if extraction_res and extraction_res.get("content"):
            logger.info("Successfully extracted article from %s using readability-lxml", url)
            newsiq_crawler_extraction_success_total.labels(extractor="readability-lxml").inc()
            result_template.update(extraction_res)
            result_template["success"] = True
            diagnostics["duration_ms"] = (time.perf_counter() - start_time) * 1000
            return result_template

        # Try custom BeautifulSoup cleaner
        extraction_res = await asyncio.to_thread(self._extract_custom_cleaner, html)
        if extraction_res and extraction_res.get("content"):
            logger.info("Successfully extracted article from %s using custom-bs4 cleaner", url)
            newsiq_crawler_extraction_success_total.labels(extractor="custom-bs4").inc()
            result_template.update(extraction_res)
            result_template["success"] = True
            diagnostics["duration_ms"] = (time.perf_counter() - start_time) * 1000
            return result_template

        # 4. Check if extracted content was too short or empty
        newsiq_crawler_extraction_failure_total.inc()
        diagnostics["failure_reason"] = "EXTRACTION_FAILED"
        logger.warning("All extractors failed to retrieve content from: %s", url)
        diagnostics["duration_ms"] = (time.perf_counter() - start_time) * 1000
        return result_template


crawler_service = CrawlerService()
