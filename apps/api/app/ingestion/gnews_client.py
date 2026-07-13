"""Google News RSS feed client.
This client fetches Google News RSS feeds and normalizes articles to our internal format.
"""

import logging
import time
from datetime import UTC, datetime
from typing import Any

import feedparser
import httpx

logger = logging.getLogger(__name__)

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

MAP_CATEGORY_TO_TOPIC = {
    "general": "WORLD",
    "world": "WORLD",
    "nation": "NATION",
    "business": "BUSINESS",
    "technology": "TECHNOLOGY",
    "entertainment": "ENTERTAINMENT",
    "sports": "SPORTS",
    "science": "SCIENCE",
    "health": "HEALTH",
}

DEFAULT_CATEGORIES = ["general", "technology"]
DEFAULT_COUNTRIES = ["us", "in"]


class GNewsClient:
    """Async client that fetches and parses the free Google News RSS feed."""

    def __init__(self) -> None:
        self.enabled = True  # Free RSS feed is always enabled

    async def fetch_top_headlines(
        self,
        category: str = "general",
        country: str = "us",
        language: str = "en",
        max_articles: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch top headline articles from Google News RSS for a category and country."""
        country_upper = country.upper()

        # Build the RSS URL based on category
        topic = MAP_CATEGORY_TO_TOPIC.get(category, "WORLD")
        if category == "general":
            url = f"https://news.google.com/rss?hl=en-{country_upper}&gl={country_upper}&ceid={country_upper}:en"
        else:
            url = f"https://news.google.com/rss/headlines/section/topic/{topic}?hl=en-{country_upper}&gl={country_upper}&ceid={country_upper}:en"

        logger.info("Fetching Google News RSS from: %s", url)
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                feed_data = response.text
        except Exception as exc:
            logger.error("Failed to fetch Google News RSS for %s/%s: %s", category, country, exc)
            return []

        parsed_feed = feedparser.parse(feed_data)
        entries = parsed_feed.entries[:max_articles]

        normalized = []
        for entry in entries:
            title = getattr(entry, "title", "Untitled")
            link = getattr(entry, "link", "")
            description = getattr(entry, "summary", "")

            # Parse published date
            published_at = datetime.utcnow()
            parsed_date = getattr(entry, "published_parsed", None)
            if parsed_date:
                try:
                    published_at = datetime.fromtimestamp(time.mktime(parsed_date), tz=UTC).replace(
                        tzinfo=None
                    )
                except Exception:
                    pass

            # Extract source information
            source_name = None
            source_url = None
            source_obj = getattr(entry, "source", None)
            if source_obj:
                source_name = getattr(source_obj, "title", None)
                source_url = getattr(source_obj, "url", None)

            # Fallback source name parsing from title (e.g. "Headline - Source Name")
            if not source_name and " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0]
                source_name = parts[1]

            normalized.append(
                {
                    "title": title.strip(),
                    "description": description.strip(),
                    "content": description.strip(),  # Fallback to description, crawler will get full text
                    "url": link,
                    "image_url": None,
                    "published_at": published_at,
                    "author": None,
                    "language": "en",
                    "category_slug": GNEWS_CATEGORY_MAP.get(category, "world"),
                    "country_code": country_upper,
                    "gnews_source_name": source_name.strip() if source_name else None,
                    "gnews_source_url": source_url,
                }
            )

        logger.info(
            "Google News RSS: fetched %d articles for category=%s country=%s",
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
        """Search Google News RSS for articles matching a query string."""
        import urllib.parse

        encoded_query = urllib.parse.quote_plus(query)

        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        logger.info("Searching Google News RSS: %s", url)
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                feed_data = response.text
        except Exception as exc:
            logger.error("Google News RSS search failed for query '%s': %s", query, exc)
            return []

        parsed_feed = feedparser.parse(feed_data)
        entries = parsed_feed.entries[:max_articles]

        normalized = []
        for entry in entries:
            title = getattr(entry, "title", "Untitled")
            link = getattr(entry, "link", "")
            description = getattr(entry, "summary", "")

            published_at = datetime.utcnow()
            parsed_date = getattr(entry, "published_parsed", None)
            if parsed_date:
                try:
                    published_at = datetime.fromtimestamp(time.mktime(parsed_date), tz=UTC).replace(
                        tzinfo=None
                    )
                except Exception:
                    pass

            source_name = None
            source_url = None
            source_obj = getattr(entry, "source", None)
            if source_obj:
                source_name = getattr(source_obj, "title", None)
                source_url = getattr(source_obj, "url", None)

            if not source_name and " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0]
                source_name = parts[1]

            normalized.append(
                {
                    "title": title.strip(),
                    "description": description.strip(),
                    "content": description.strip(),
                    "url": link,
                    "image_url": None,
                    "published_at": published_at,
                    "author": None,
                    "language": "en",
                    "category_slug": "world",
                    "country_code": "US",
                    "gnews_source_name": source_name.strip() if source_name else None,
                    "gnews_source_url": source_url,
                }
            )

        return normalized


gnews_client = GNewsClient()
