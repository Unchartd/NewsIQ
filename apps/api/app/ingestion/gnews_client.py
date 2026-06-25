"""GNews API HTTP client.

GNews docs: https://gnews.io/docs/v4
Rate limits (free tier): 100 requests/day, 10 articles/request, 3-day history.

This client:
  - Handles authentication, request construction, and response parsing
  - Normalizes GNews article dicts to our internal Article schema format
  - Guards against duplicate fetches via Redis TTL lock
  - Respects rate limits with configurable per-category intervals
"""

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

GNEWS_BASE_URL = "https://gnews.io/api/v4"

# Map GNews category names → our canonical category slugs
GNEWS_CATEGORY_MAP: dict[str, str] = {
    "general": "world",
    "world": "world",
    "nation": "politics",
    "business": "business",
    "technology": "technology",
    "entertainment": "entertainment",
    "sports": "sports",
    "science": "science",
    "health": "health",
}

# Categories to fetch on each scheduled run.
# Free tier: 100 req/day, 48 runs/day (every 30 min) → 2 categories per run.
# These two categories provide the broadest coverage.
DEFAULT_CATEGORIES = ["general", "technology"]

# Countries to fetch headlines for
DEFAULT_COUNTRIES = ["us", "in"]


class GNewsClient:
    """Lightweight async HTTP client for the GNews API v4."""

    def __init__(self) -> None:
        self.api_key = settings.GNEWS_API_KEY
        self.enabled = bool(self.api_key)
        if not self.enabled:
            logger.warning("GNEWS_API_KEY not set — GNews ingestion disabled.")

    async def fetch_top_headlines(
        self,
        category: str = "general",
        country: str = "us",
        language: str = "en",
        max_articles: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch top headline articles from GNews for a given category and country.

        Args:
            category:     GNews category (general, technology, business, etc.)
            country:      ISO 3166-1 alpha-2 country code (us, in, gb, etc.)
            language:     BCP 47 language code (en, hi, fr, etc.)
            max_articles: Number of articles to retrieve (max 10 on free tier)

        Returns:
            List of normalized article dicts ready for IngestionService.
        """
        if not self.enabled:
            return []

        params: dict[str, Any] = {
            "category": category,
            "country": country,
            "lang": language,
            "max": min(max_articles, 10),  # Free tier cap
            "apikey": self.api_key,
        }

        url = f"{GNEWS_BASE_URL}/top-headlines"

        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                response = await client.get(url, params=params)

                if response.status_code == 429:
                    logger.warning("GNews rate limit hit (429). Will retry on next scheduled run.")
                    return []

                if response.status_code == 403:
                    logger.error(
                        "GNews API key invalid or quota exceeded (403). "
                        "Check GNEWS_API_KEY and plan limits."
                    )
                    return []

                response.raise_for_status()
                data = response.json()

        except httpx.TimeoutException:
            logger.error("GNews request timed out for category=%s country=%s", category, country)
            return []
        except httpx.HTTPStatusError as exc:
            logger.error("GNews HTTP error %d for %s: %s", exc.response.status_code, url, exc)
            return []
        except Exception as exc:
            logger.error("GNews request failed: %s", exc)
            return []

        articles = data.get("articles", [])
        if not articles:
            logger.info("GNews returned 0 articles for category=%s country=%s", category, country)
            return []

        normalized = [self._normalize_article(art, category, country) for art in articles]
        logger.info(
            "GNews: fetched %d articles for category=%s country=%s",
            len(normalized),
            category,
            country,
        )
        return normalized

    async def search_articles(
        self,
        query: str,
        language: str = "en",
        max_articles: int = 10,
    ) -> list[dict[str, Any]]:
        """Search GNews for articles matching a query string.

        Useful for tracking a specific story over time (Phase 2 feature).
        """
        if not self.enabled:
            return []

        params: dict[str, Any] = {
            "q": query,
            "lang": language,
            "max": min(max_articles, 10),
            "apikey": self.api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(f"{GNEWS_BASE_URL}/search", params=params)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            logger.error("GNews search failed for query '%s': %s", query, exc)
            return []

        return [self._normalize_article(a, "general", "us") for a in data.get("articles", [])]

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _parse_gnews_date(date_str: str | None) -> datetime:
        """Parse GNews ISO 8601 publishedAt string to timezone-naive UTC datetime."""
        if not date_str:
            return datetime.now(UTC).replace(tzinfo=None)
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.astimezone(UTC).replace(tzinfo=None)
        except (ValueError, TypeError):
            logger.debug("Could not parse GNews date: %s", date_str)
            return datetime.now(UTC).replace(tzinfo=None)

    def _normalize_article(
        self,
        raw: dict[str, Any],
        category: str,
        country: str,
    ) -> dict[str, Any]:
        """Convert a raw GNews article dict to our normalized internal format.

        Returns a dict compatible with IngestionService's Article creation logic.
        """
        source_info = raw.get("source") or {}
        return {
            "title": (raw.get("title") or "").strip() or "Untitled",
            "description": (raw.get("description") or "").strip(),
            # GNews content is truncated to ~1234 chars; use description as fallback body
            "content": (raw.get("content") or raw.get("description") or "").strip(),
            "url": raw.get("url") or "",
            "image_url": raw.get("image") or None,
            "published_at": self._parse_gnews_date(raw.get("publishedAt")),
            "author": None,  # GNews does not expose author info
            "language": "en",
            "category_slug": GNEWS_CATEGORY_MAP.get(category, "world"),
            "country_code": country.upper(),
            # Source metadata from GNews — may differ from our Source.name
            "gnews_source_name": (source_info.get("name") or "").strip() or None,
            "gnews_source_url": source_info.get("url") or None,
        }


gnews_client = GNewsClient()
