import abc
import logging
from typing import Any

from app.ingestion.gnews_client import gnews_client

logger = logging.getLogger(__name__)


class DiscoveryProvider(abc.ABC):
    """Abstract Base Class (Interface) for News Discovery Providers."""

    @abc.abstractmethod
    async def search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        """Search similar news articles using this provider."""
        pass

    async def resolve_url(self, url: str) -> str:
        """Resolve a provider-specific redirect/masked URL to its direct canonical publisher URL.

        Default implementation returns the URL unchanged.
        """
        return url


class GoogleRSSDiscoveryProvider(DiscoveryProvider):
    """Discovery Provider using Google News RSS search queries."""

    async def search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        try:
            results = await gnews_client.search_articles(query=query, max_articles=max_results)
            return results
        except Exception as exc:
            logger.error("GoogleRSSDiscoveryProvider: Search failed for query '%s': %s", query, exc)
            return []

    async def resolve_url(self, url: str) -> str:
        if "news.google.com" not in url:
            return url
        try:
            from googlenewsdecoder import new_decoderv1
            import asyncio
            # Execute base decoder in a thread because it does blocking network/parsing calls
            decoded = await asyncio.to_thread(new_decoderv1, url, interval=1)
            if decoded.get("status") and decoded.get("decoded_url"):
                resolved = decoded["decoded_url"]
                logger.info("GoogleRSSDiscoveryProvider: Decoded Google News redirect URL from %s to %s", url, resolved)
                return resolved
            logger.warning("GoogleRSSDiscoveryProvider: Failed to decode URL %s: %s", url, decoded.get("message"))
        except Exception as exc:
            logger.warning("GoogleRSSDiscoveryProvider: Error decoding URL %s: %s", url, exc)
        return url


def get_discovery_provider(name: str) -> DiscoveryProvider:
    """Factory resolver to get a DiscoveryProvider instance by name."""
    name_clean = name.lower().strip()
    if name_clean == "google_rss":
        return GoogleRSSDiscoveryProvider()

    # Default fallback
    logger.warning("Unknown discovery provider '%s'. Falling back to google_rss.", name)
    return GoogleRSSDiscoveryProvider()
