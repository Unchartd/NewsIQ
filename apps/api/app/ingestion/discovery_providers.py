import abc
import logging
from typing import Any
from app.ingestion.gnews_client import gnews_client

logger = logging.getLogger(__name__)

class DiscoveryProvider(abc.ABC):
    """Abstract Base Class (Interface) for News Discovery Providers."""

    @abc.abstractmethod
    async def search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        """Search similar news articles using this provider.
        
        Returns:
            list[dict[str, Any]]: A list of normalized article dictionaries:
                - title (str)
                - url (str)
                - description (str)
                - published_at (datetime)
                - gnews_source_name (str | None)
                - gnews_source_url (str | None)
        """
        pass


class GoogleRSSDiscoveryProvider(DiscoveryProvider):
    """Discovery Provider using Google News RSS search queries."""

    async def search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        try:
            results = await gnews_client.search_articles(query=query, max_articles=max_results)
            return results
        except Exception as exc:
            logger.error("GoogleRSSDiscoveryProvider: Search failed for query '%s': %s", query, exc)
            return []


def get_discovery_provider(name: str) -> DiscoveryProvider:
    """Factory resolver to get a DiscoveryProvider instance by name."""
    name_clean = name.lower().strip()
    if name_clean == "google_rss":
        return GoogleRSSDiscoveryProvider()
    
    # Default fallback
    logger.warning("Unknown discovery provider '%s'. Falling back to google_rss.", name)
    return GoogleRSSDiscoveryProvider()
