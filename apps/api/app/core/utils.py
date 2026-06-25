"""Core utility functions, including URL canonicalization."""

import logging
from urllib.parse import parse_qsl, unquote, urlencode, urlparse, urlunparse

logger = logging.getLogger(__name__)


def canonicalize_url(url: str) -> str:
    """Normalize and canonicalize a URL for deduplication.

    - Scheme and host/domain are converted to lowercase.
    - Decodes percent-encoding.
    - Strips common query/tracking parameters (e.g. utm_*, ref, referrer, gclid, fbclid).
    - Removes trailing slash from path (unless path is just '/').
    - Drops fragment identifier.
    - Reconstructs a clean, normalized URL.
    """
    if not url:
        return ""
    try:
        # Decode percent-encoding first
        url = unquote(url.strip())
        parsed = urlparse(url)

        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path

        # Remove trailing slash from path (unless it's just '/')
        if path.endswith("/") and len(path) > 1:
            path = path[:-1]

        # Filter out common tracking parameters
        q_params = []
        tracking_params = {
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "ref",
            "referrer",
            "gclid",
            "fbclid",
        }
        for k, v in parse_qsl(parsed.query):
            if k.lower() not in tracking_params:
                q_params.append((k, v))

        # Reconstruct query string with sorted parameters for consistency
        query = urlencode(sorted(q_params)) if q_params else ""

        # Reconstruct URL (drop fragment)
        return urlunparse((scheme, netloc, path, parsed.params, query, ""))
    except Exception as e:
        logger.warning("Failed to canonicalize URL '%s': %s", url, e)
        return url
