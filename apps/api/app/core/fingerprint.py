"""Utility for generating deterministic hashes of article contents."""

import hashlib
import logging

logger = logging.getLogger(__name__)


def compute_fingerprints(
    url: str, normalized_title: str | None, normalized_body: str | None
) -> dict[str, str]:
    """
    Computes fingerprints for an article.

    Args:
        url: The canonical URL of the article.
        normalized_title: The title after normalization (lowercased, stripped, etc).
            Accepts None — treated as empty string.
        normalized_body: The article content after normalization (HTML stripped, etc).
            Accepts None — treated as empty string to avoid the string "None" being
            incorporated into the hash payload when content extraction fails.

    Returns:
        dict: Containing 'url_hash' and 'content_hash'.
    """
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()

    # Guard against None so failed extractions don't produce the literal string "None"
    # in the hash payload, which would create collisions across all content-less articles
    # with the same title.
    safe_title = normalized_title or ""
    safe_body = normalized_body or ""

    # Hash normalized content ignoring author, timestamps, etc.
    content_payload = f"{safe_title}\n\n{safe_body}"
    content_hash = hashlib.sha256(content_payload.encode("utf-8")).hexdigest()

    return {"url_hash": url_hash, "content_hash": content_hash}
