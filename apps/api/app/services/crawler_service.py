import asyncio
import logging
import re
from datetime import datetime
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

    async def fetch_html(self, url: str) -> str | None:
        """Fetch raw HTML content of a URL asynchronously."""
        try:
            async with httpx.AsyncClient(
                timeout=10.0, follow_redirects=True, headers=self.headers
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
        except Exception as e:
            logger.warning("Failed to fetch HTML for %s: %s", url, e)
            return None

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

    async def crawl_article(self, url: str) -> dict[str, Any] | None:
        """Crawl a URL and extract its full-text content using the fallback stack."""
        html = await self.fetch_html(url)
        if not html:
            return None

        # Execute CPU-bound parsers in threads to avoid blocking asyncio event loop
        # Try newspaper4k
        result = await asyncio.to_thread(self._extract_newspaper, url, html)
        if result:
            logger.info("Successfully extracted article from %s using newspaper4k", url)
            return result

        # Try trafilatura
        result = await asyncio.to_thread(self._extract_trafilatura, html)
        if result:
            logger.info("Successfully extracted article from %s using trafilatura", url)
            return result

        # Try readability-lxml
        result = await asyncio.to_thread(self._extract_readability, html)
        if result:
            logger.info("Successfully extracted article from %s using readability-lxml", url)
            return result

        # Try custom BeautifulSoup cleaner
        result = await asyncio.to_thread(self._extract_custom_cleaner, html)
        if result:
            logger.info("Successfully extracted article from %s using custom-bs4 cleaner", url)
            return result

        logger.warning("All extractors failed to retrieve content from: %s", url)
        return None


crawler_service = CrawlerService()
