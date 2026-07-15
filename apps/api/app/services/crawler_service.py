"""Crawler service — progressive, multi-level HTML fetch strategy.

Fetch chain (in order):
  1. Pooled httpx  — fast path, Chrome 124 Windows headers
  2. curl-cffi chrome124 — Chrome TLS fingerprint (JA3/JA4), Chrome headers
  3. curl-cffi safari17_2 — Safari TLS fingerprint, macOS Safari headers

Short-circuit rules:
  - 404 → immediate abort (permanent signal, no retry)
  - BOT_BLOCKED on all three → return None

Design decisions:
  - Each attempt uses a different browser profile so TLS fingerprint and HTTP
    headers are always consistent with each other (mismatches are a detection
    signal for advanced WAF vendors like Cloudflare Enterprise, DataDome).
  - check_bot_blocking treats None as a failure (not a pass), adds length
    heuristic for challenge pages, and covers major WAF/CAPTCHA vendors.
  - _finalize / _handle_blocked helpers eliminate repeated diagnostic mutation
    that previously caused failure_reason inconsistencies across attempts.
"""

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

# ──────────────────────────────────────────────────────────────────────────────
# Browser profiles
#
# Each profile is a self-consistent set of headers for a specific browser
# version and OS. They are intentionally ordered to match the curl-cffi
# impersonation target used in each attempt:
#   BROWSER_PROFILES[0] → Chrome 124 Windows  (attempts 1 + 2)
#   BROWSER_PROFILES[1] → Firefox 125 Windows (unused by default, available
#                         for callers that want a third distinct fingerprint)
#   BROWSER_PROFILES[2] → Chrome 124 macOS / Safari-style (attempt 3)
#
# Important: Never mix a Chrome TLS fingerprint (impersonate="chrome*") with
# Firefox-style headers — advanced WAF vendors cross-check the JA3/JA4
# fingerprint against the User-Agent and Sec-Ch-Ua header family.
# ──────────────────────────────────────────────────────────────────────────────
BROWSER_PROFILES: list[dict[str, str]] = [
    {
        # Chrome 124 — Windows 10/11
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    },
    {
        # Firefox 125 — Windows 10/11
        # Intentionally omits Sec-Ch-Ua (Firefox does not send client hints).
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
            "Gecko/20100101 Firefox/125.0"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    },
    {
        # Chrome 124 — macOS Ventura (used with Safari TLS impersonation)
        # Using macOS UA + Sec-Ch-Ua-Platform=macOS is consistent with
        # safari17_2 impersonation target which emits macOS TLS extensions.
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Upgrade-Insecure-Requests": "1",
    },
]

# ──────────────────────────────────────────────────────────────────────────────
# Bot-block signal corpus
#
# Signals are grouped by WAF vendor / challenge type for readability and
# future maintainability. Add new signals here — they are automatically
# picked up by check_bot_blocking without any other code changes.
# ──────────────────────────────────────────────────────────────────────────────
_BOT_BLOCK_SIGNALS: tuple[str, ...] = (
    # ── Cloudflare ────────────────────────────────────────────────────────────
    "just a moment",
    "checking your browser",
    "challenge-platform",
    "cf-browser-verification",
    "__cf_chl",
    "ray id",
    "cf_clearance",
    # ── Generic bot/security walls ────────────────────────────────────────────
    "ddos protection",
    "security check",
    "bot detection",
    "robot check",
    "attention required",
    "access denied",
    "enable javascript",
    "please enable js",
    "verify you are human",
    "human verification",
    "press & hold",
    "are you a robot",
    # ── WAF vendors ───────────────────────────────────────────────────────────
    "distil networks",
    "perimeter x",
    "px-captcha",
    "datadome",
    "incapsula",
    "kasada",
    "akamai bot",
    # ── Paywalls that return HTTP 200 with a wall page ────────────────────────
    "subscribe to continue",
    "subscription required",
    "create a free account to continue",
    "sign in to read",
    "this article is for subscribers",
)

# Minimum byte length of a real article page.
# Challenge pages from Cloudflare / DataDome / PerimeterX are almost always
# short (~800–1 800 bytes). Legitimate articles are rarely under 2 000 bytes.
_MIN_REAL_PAGE_LENGTH: int = 2_000


class CrawlerService:
    """Fetch full-text HTML via a progressive, multi-level strategy.

    Each attempt uses a different TLS fingerprint + matching browser headers
    to maximise bypass probability against common WAF/CDN challenge systems.
    """

    # ------------------------------------------------------------------
    # Bot-block detection
    # ------------------------------------------------------------------

    @staticmethod
    def check_bot_blocking(html: str | None) -> bool:
        """Return True if *html* looks like a bot-challenge or paywall page.

        Treats None / empty string as blocked — callers should never interpret
        a missing response as "not blocked".
        """
        if not html:
            # None means the fetch itself failed — treat as blocked / failure.
            return True

        stripped = html.strip()

        # Very short pages are almost certainly challenge pages, not articles.
        if len(stripped) < _MIN_REAL_PAGE_LENGTH:
            return True

        lowered = stripped.lower()
        return any(sig in lowered for sig in _BOT_BLOCK_SIGNALS)

    # ------------------------------------------------------------------
    # Internal diagnostic helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _finalize(
        html: str,
        method: str,
        status: int,
        diagnostics: dict[str, Any],
        start_time: float,
    ) -> tuple[str, dict[str, Any]]:
        """Mark a successful fetch in *diagnostics* and fire the success metric."""
        diagnostics["fetch_method"] = method
        diagnostics["status_code"] = status
        diagnostics["failure_reason"] = None
        diagnostics["duration_ms"] = (time.perf_counter() - start_time) * 1000
        newsiq_crawler_http_success_total.inc()
        return html, diagnostics

    @staticmethod
    def _record_failure(
        reason: str,
        method: str,
        diagnostics: dict[str, Any],
        status: int | None = None,
    ) -> None:
        """Update *diagnostics* and fire the appropriate failure metric."""
        diagnostics["failure_reason"] = reason
        diagnostics["fetch_method"] = method
        if status is not None:
            diagnostics["status_code"] = status

        if reason == "BOT_BLOCKED":
            newsiq_crawler_bot_block_total.inc()
        elif reason == "EMPTY_HTML":
            newsiq_crawler_empty_html_total.inc()
        elif reason == "TIMEOUT":
            newsiq_crawler_timeout_total.inc()

    # ------------------------------------------------------------------
    # Core fetch
    # ------------------------------------------------------------------

    async def fetch_html(self, url: str) -> tuple[str | None, dict[str, Any]]:
        """Fetch raw HTML for *url* using a progressive, multi-level strategy.

        Returns ``(html_content, diagnostics)`` where *html_content* is ``None``
        on total failure.  *diagnostics* always contains:

        .. code-block:: python

            {
                "fetch_method":   str,          # last attempted method
                "status_code":    int | None,   # last HTTP status (or None)
                "failure_reason": str | None,   # None on success
                "duration_ms":    float,
            }
        """
        start_time = time.perf_counter()
        diagnostics: dict[str, Any] = {
            "fetch_method": "none",
            "status_code": None,
            "failure_reason": None,
            "duration_ms": 0.0,
        }

        # ── Attempt 1: Pooled httpx — Chrome 124 Windows headers ──────────────
        logger.info("Attempt 1 (httpx): fetching %s", url)
        try:
            from app.core.http_client import http_client_pool

            response = await http_client_pool.client.get(
                url,
                timeout=httpx.Timeout(timeout=30.0, connect=10.0),
                follow_redirects=True,
                headers=BROWSER_PROFILES[0],
            )
            status = response.status_code
            diagnostics["status_code"] = status

            if status == 200:
                html = response.text
                if not html or not html.strip():
                    self._record_failure("EMPTY_HTML", "httpx", diagnostics, status)
                    logger.warning("Attempt 1 (httpx): empty HTML for %s", url)
                elif self.check_bot_blocking(html):
                    self._record_failure("BOT_BLOCKED", "httpx", diagnostics, status)
                    newsiq_crawler_http_failure_total.labels(reason="bot_blocked_httpx").inc()
                    logger.warning("Attempt 1 (httpx): bot block detected for %s", url)
                else:
                    return self._finalize(html, "httpx", status, diagnostics, start_time)

            elif status == 404:
                # Hard permanent failure — skip remaining attempts entirely.
                self._record_failure("NOT_FOUND", "httpx", diagnostics, status)
                newsiq_crawler_http_failure_total.labels(reason="404").inc()
                logger.warning("Attempt 1 (httpx): 404 for %s — aborting fetch chain", url)
                diagnostics["duration_ms"] = (time.perf_counter() - start_time) * 1000
                return None, diagnostics

            elif status in (401, 403):
                self._record_failure("BOT_BLOCKED", "httpx", diagnostics, status)
                newsiq_crawler_http_failure_total.labels(reason=str(status)).inc()
                logger.warning("Attempt 1 (httpx): %d for %s", status, url)

            else:
                self._record_failure("HTTP_ERROR", "httpx", diagnostics, status)
                newsiq_crawler_http_failure_total.labels(reason=str(status)).inc()
                logger.warning("Attempt 1 (httpx): HTTP %d for %s", status, url)

        except httpx.TimeoutException as exc:
            self._record_failure("TIMEOUT", "httpx", diagnostics)
            newsiq_crawler_http_failure_total.labels(reason="TimeoutException").inc()
            logger.warning("Attempt 1 (httpx): timeout for %s — %s", url, exc)

        except Exception as exc:
            self._record_failure("HTTP_ERROR", "httpx", diagnostics)
            newsiq_crawler_http_failure_total.labels(reason=type(exc).__name__).inc()
            logger.warning("Attempt 1 (httpx): error for %s — %s", url, exc)

        # ── Attempt 2: curl-cffi chrome124 — Chrome TLS fingerprint ───────────
        # chrome124 emits the correct JA3/JA4 fingerprint for Chrome 124.
        # Paired with Chrome 124 Windows headers (BROWSER_PROFILES[0]) so the
        # TLS fingerprint and HTTP headers are internally consistent.
        logger.info("Attempt 2 (curl-cffi chrome124): fetching %s", url)
        try:
            from curl_cffi.requests import AsyncSession

            async with AsyncSession(impersonate="chrome124") as session:
                response = await session.get(
                    url,
                    timeout=30.0,
                    headers=BROWSER_PROFILES[0],
                )
                status = response.status_code
                diagnostics["status_code"] = status

                if status == 200:
                    html = response.text
                    if not html or not html.strip():
                        self._record_failure("EMPTY_HTML", "curl_cffi_chrome124", diagnostics, status)
                        logger.warning("Attempt 2 (curl-cffi): empty HTML for %s", url)
                    elif self.check_bot_blocking(html):
                        self._record_failure("BOT_BLOCKED", "curl_cffi_chrome124", diagnostics, status)
                        newsiq_crawler_http_failure_total.labels(reason="bot_blocked_curl_chrome").inc()
                        logger.warning("Attempt 2 (curl-cffi): bot block detected for %s", url)
                    else:
                        return self._finalize(html, "curl_cffi_chrome124", status, diagnostics, start_time)

                elif status in (401, 403):
                    self._record_failure("BOT_BLOCKED", "curl_cffi_chrome124", diagnostics, status)
                    newsiq_crawler_http_failure_total.labels(reason=f"curl_{status}").inc()
                    logger.warning("Attempt 2 (curl-cffi): %d for %s", status, url)

                else:
                    self._record_failure("HTTP_ERROR", "curl_cffi_chrome124", diagnostics, status)
                    newsiq_crawler_http_failure_total.labels(reason=f"curl_{status}").inc()
                    logger.warning("Attempt 2 (curl-cffi): HTTP %d for %s", status, url)

        except Exception as exc:
            is_timeout = "timeout" in str(exc).lower()
            reason = "TIMEOUT" if is_timeout else "HTTP_ERROR"
            self._record_failure(reason, "curl_cffi_chrome124", diagnostics)
            newsiq_crawler_http_failure_total.labels(reason=f"curl_{type(exc).__name__}").inc()
            if is_timeout:
                newsiq_crawler_timeout_total.inc()
            logger.warning("Attempt 2 (curl-cffi): error for %s — %s", url, exc)

        # ── Attempt 3: curl-cffi safari17_2 — Safari TLS fingerprint ──────────
        # safari17_2 emits a distinct JA3/JA4 fingerprint vs. Chrome, giving
        # a different bypass path against WAFs that fingerprint TLS.
        # Paired with Chrome 124 macOS headers (BROWSER_PROFILES[2]) which
        # are consistent with a macOS browser — avoids Windows UA + Safari TLS
        # mismatch that advanced detectors flag.
        logger.info("Attempt 3 (curl-cffi safari17_2): fetching %s", url)
        try:
            from curl_cffi.requests import AsyncSession

            async with AsyncSession(impersonate="safari17_2") as session:
                response = await session.get(
                    url,
                    timeout=45.0,
                    headers=BROWSER_PROFILES[2],
                )
                status = response.status_code
                diagnostics["status_code"] = status

                if status == 200:
                    html = response.text
                    if not html or not html.strip():
                        self._record_failure("EMPTY_HTML", "curl_cffi_safari17_2", diagnostics, status)
                        logger.warning("Attempt 3 (curl-cffi safari): empty HTML for %s", url)
                    elif self.check_bot_blocking(html):
                        self._record_failure("BOT_BLOCKED", "curl_cffi_safari17_2", diagnostics, status)
                        newsiq_crawler_http_failure_total.labels(reason="bot_blocked_curl_safari").inc()
                        logger.warning("Attempt 3 (curl-cffi safari): bot block detected for %s", url)
                    else:
                        return self._finalize(html, "curl_cffi_safari17_2", status, diagnostics, start_time)

                elif status in (401, 403):
                    self._record_failure("BOT_BLOCKED", "curl_cffi_safari17_2", diagnostics, status)
                    newsiq_crawler_http_failure_total.labels(reason=f"curl_safari_{status}").inc()
                    logger.warning("Attempt 3 (curl-cffi safari): %d for %s", status, url)

                else:
                    self._record_failure("HTTP_ERROR", "curl_cffi_safari17_2", diagnostics, status)
                    newsiq_crawler_http_failure_total.labels(reason=f"curl_safari_{status}").inc()
                    logger.warning("Attempt 3 (curl-cffi safari): HTTP %d for %s", status, url)

        except Exception as exc:
            is_timeout = "timeout" in str(exc).lower()
            reason = "TIMEOUT" if is_timeout else "HTTP_ERROR"
            self._record_failure(reason, "curl_cffi_safari17_2", diagnostics)
            newsiq_crawler_http_failure_total.labels(reason=f"curl_safari_{type(exc).__name__}").inc()
            if is_timeout:
                newsiq_crawler_timeout_total.inc()
            logger.warning("Attempt 3 (curl-cffi safari): error for %s — %s", url, exc)

        # All attempts exhausted
        diagnostics["duration_ms"] = (time.perf_counter() - start_time) * 1000
        return None, diagnostics

    # ------------------------------------------------------------------
    # Article crawl (delegates to extraction pipeline)
    # ------------------------------------------------------------------

    async def crawl_article(self, url: str) -> dict[str, Any]:
        """Crawl *url*, extract content, and return full results & diagnostics.

        Always returns a dict containing at least ``'success'`` and
        ``'diagnostics'`` keys.  Delegates to
        :mod:`app.services.extraction_manager` for content extraction.
        """
        from app.services.extraction_manager import extraction_manager

        return await extraction_manager.crawl_article(url)


crawler_service = CrawlerService()
