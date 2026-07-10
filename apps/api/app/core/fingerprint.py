"""Utility for generating deterministic hashes of article contents."""

import hashlib
import logging

logger = logging.getLogger(__name__)


def compute_fingerprints(url: str, normalized_title: str, normalized_body: str) -> dict[str, str]:
    """
    Computes fingerprints for an article.

    Args:
        url: The canonical URL of the article.
        normalized_title: The title after normalization (lowercased, stripped, etc).
        normalized_body: The article content after normalization (HTML stripped, etc).

    Returns:
        dict: Containing 'url_hash' and 'content_hash'.
    """
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()

    # Hash normalized content ignoring author, timestamps, etc.
    content_payload = f"{normalized_title}\n\n{normalized_body}"
    content_hash = hashlib.sha256(content_payload.encode("utf-8")).hexdigest()

    return {"url_hash": url_hash, "content_hash": content_hash}
