from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.core.metrics import (
    newsiq_crawler_bot_block_total,
    newsiq_crawler_empty_html_total,
    newsiq_crawler_http_failure_total,
    newsiq_crawler_http_success_total,
    newsiq_crawler_timeout_total,
)

logger = logging.getLogger(__name__)


class CrawlerService:
    """Crawler service that fetches full-text article contents using a progressive, multi-level fetch strategy."""

    def __init__(self) -> None:
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    @staticmethod
    def check_bot_blocking(html: str | None) -> bool:
        """Helper to detect bot protection/Cloudflare block screens in HTML content."""
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

    async def fetch_html(self, url: str) -> tuple[str | None, dict[str, Any]]:
        """Fetch raw HTML content of a URL using a progressive, multi-level fetch strategy.

        Returns (html_content, diagnostics_dict).
        """
        start_time = time.perf_counter()
        diagnostics = {
            "fetch_method": "none",
            "status_code": None,
            "failure_reason": None,
            "duration_ms": 0.0,
        }

        # Attempt 1: httpx with normal browser headers
        logger.info("Attempt 1: Fetching %s via httpx", url)
        try:
            from app.core.http_client import http_client_pool
            client = http_client_pool.client
            response = await client.get(
                url,
                timeout=httpx.Timeout(timeout=30.0, connect=10.0),
                follow_redirects=True,
                headers=self.headers,
            )
            diagnostics["status_code"] = response.status_code
            diagnostics["fetch_method"] = "httpx"

            if response.status_code == 200:
                html = response.text
                if not html or not html.strip():
                    newsiq_crawler_empty_html_total.inc()
                    diagnostics["failure_reason"] = "EMPTY_HTML"
                    logger.warning("Attempt 1 returned empty HTML for %s", url)
                elif self.check_bot_blocking(html):
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
                logger.warning(
                    "Attempt 1 failed with status %d for %s", response.status_code, url
                )
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
                    elif self.check_bot_blocking(html):
                        newsiq_crawler_bot_block_total.inc()
                        diagnostics["failure_reason"] = "BOT_BLOCKED"
                        logger.warning("Attempt 2 blocked by bot protection for %s", url)
                    else:
                        newsiq_crawler_http_success_total.inc()
                        diagnostics["failure_reason"] = None
                        diagnostics["duration_ms"] = (time.perf_counter() - start_time) * 1000
                        return html, diagnostics
                else:
                    newsiq_crawler_http_failure_total.labels(
                        reason=f"curl_{response.status_code}"
                    ).inc()
                    if response.status_code in (401, 403):
                        newsiq_crawler_bot_block_total.inc()
                        diagnostics["failure_reason"] = "BOT_BLOCKED"
                    else:
                        diagnostics["failure_reason"] = "HTTP_ERROR"
                    logger.warning(
                        "Attempt 2 failed with status %d for %s", response.status_code, url
                    )
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
                    elif self.check_bot_blocking(html):
                        newsiq_crawler_bot_block_total.inc()
                        diagnostics["failure_reason"] = "BOT_BLOCKED"
                        logger.warning("Attempt 3 blocked by bot protection for %s", url)
                    else:
                        newsiq_crawler_http_success_total.inc()
                        diagnostics["failure_reason"] = None
                        diagnostics["duration_ms"] = (time.perf_counter() - start_time) * 1000
                        return html, diagnostics
                else:
                    newsiq_crawler_http_failure_total.labels(
                        reason=f"curl_safari_{response.status_code}"
                    ).inc()
                    if response.status_code in (401, 403):
                        newsiq_crawler_bot_block_total.inc()
                        diagnostics["failure_reason"] = "BOT_BLOCKED"
                    else:
                        diagnostics["failure_reason"] = "HTTP_ERROR"
                    logger.warning(
                        "Attempt 3 failed with status %d for %s", response.status_code, url
                    )
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

    async def crawl_article(self, url: str) -> dict[str, Any]:
        """Crawl a URL, clean, validate, extract content, and return full results & diagnostics.

        Always returns a dictionary containing at least 'success' and 'diagnostics'.
        """
        from app.services.extraction_manager import extraction_manager

        return await extraction_manager.crawl_article(url)


crawler_service = CrawlerService()
