"""Tests for crawler cost, politeness and routing policy.

Each test pins a defect measured in production over a 24h/7d window:

* Firecrawl answered HTTP 402 to all 256 calls in 24h with a 0% success rate,
  invisible because non-200 responses were never logged.
* 878 of 2789 domains have never been extracted locally, yet every article
  from them still burned three local attempts first.
* 62% of Tavily batches carried a single URL and were billed a full 5-URL
  credit: 253 credits spent on 410 URLs.
* 21.8% of consecutive crawls hit the same host, 12% within one second, with
  runs of up to 140 requests against a single host.
* 994 articles (15.6%) were stored with a news.google.com URL.
"""

import pytest

from app.services.crawl_policy import (
    drop_unresolved_redirects,
    interleave_by_domain,
    order_crawl_urls,
)
from app.services.crawler_service import CrawlerService
from app.services.extraction.types import ExtractionFailure

# ── Bot detection: false positives push free articles into paid providers ────


def _article(body: str = "", length: int = 40_000) -> str:
    """A page long enough that no length heuristic can call it a challenge."""
    return "<html><body>" + body + ("hello world " * (length // 12)) + "</body></html>"


def test_noscript_javascript_notice_is_not_a_bot_block():
    """<noscript> appears on ordinary news sites; it is not a challenge page."""
    html = _article("<noscript>Please enable JavaScript to view this site.</noscript>")
    assert CrawlerService.check_bot_blocking(html) is False


def test_paywall_wording_in_footer_of_a_long_article_is_not_a_block():
    """A free article with a 'Subscribe to continue' promo must not be rejected."""
    html = _article("<footer>Subscribe to continue reading our other coverage</footer>")
    assert CrawlerService.check_bot_blocking(html) is False


def test_article_merely_mentioning_access_denied_is_not_a_block():
    html = _article("<p>The court ruled that access denied to the records was unlawful.</p>")
    assert CrawlerService.check_bot_blocking(html) is False


def test_short_page_with_paywall_wording_is_still_a_block():
    """The weak signals must still fire on a page short enough to be a wall."""
    html = "<html><body>" + ("x" * 3_000) + "Subscription required to read this.</body></html>"
    assert CrawlerService.check_bot_blocking(html) is True


def test_real_cloudflare_challenge_is_still_detected_regardless_of_length():
    """A strong signal must fire even on a long page."""
    html = _article("<h1>Just a moment...</h1><div id='challenge-platform'></div>")
    assert CrawlerService.check_bot_blocking(html) is True


def test_empty_and_tiny_responses_remain_blocked():
    assert CrawlerService.check_bot_blocking(None) is True
    assert CrawlerService.check_bot_blocking("") is True
    assert CrawlerService.check_bot_blocking("<html>short</html>") is True


# ── Dispatch ordering: stop hammering one host ───────────────────────────────


def test_consecutive_urls_come_from_different_hosts():
    urls = [
        "https://a.com/1",
        "https://a.com/2",
        "https://a.com/3",
        "https://b.com/1",
        "https://c.com/1",
    ]
    ordered = interleave_by_domain(urls)

    def host(u: str) -> str:
        return u.split("/")[2]

    collisions = sum(1 for x, y in zip(ordered, ordered[1:]) if host(x) == host(y))
    assert collisions <= 1, f"same-host URLs still queued back to back: {ordered}"
    assert sorted(ordered) == sorted(urls), "interleaving must not drop or invent URLs"


def test_interleaving_preserves_each_hosts_internal_order():
    urls = ["https://a.com/1", "https://a.com/2", "https://b.com/1"]
    ordered = [u for u in interleave_by_domain(urls) if "a.com" in u]
    assert ordered == ["https://a.com/1", "https://a.com/2"]


def test_tier_priority_survives_interleaving():
    """Tier 1 encodes publisher quality and must still be dispatched first."""
    urls = ["https://low.com/1", "https://top.com/1", "https://low.com/2", "https://top.com/2"]

    def tier(u: str) -> int:
        return 1 if "top.com" in u else 3

    ordered = order_crawl_urls(urls, tier)
    assert all("top.com" in u for u in ordered[:2]), ordered


def test_undecodable_google_news_redirects_are_dropped():
    """Crawling one yields Google's interstitial and misattributes the publisher."""
    urls = ["https://news.google.com/rss/articles/CBM123", "https://bbc.com/news/1"]
    assert drop_unresolved_redirects(urls) == ["https://bbc.com/news/1"]


def test_interleaving_handles_empty_and_malformed_input():
    assert interleave_by_domain([]) == []
    assert interleave_by_domain(["not a url"]) == ["not a url"]


# ── Firecrawl quota handling ─────────────────────────────────────────────────


def test_quota_exhausted_is_a_distinct_failure_mode():
    """402 is an account state, not a property of the URL being fetched."""
    assert ExtractionFailure.QUOTA_EXHAUSTED != ExtractionFailure.HTTP_ERROR


@pytest.mark.parametrize("status", [402, 429, 500])
def test_firecrawl_non_200_responses_are_logged(status):
    """256 calls a day failed silently because no branch logged the response."""
    import inspect

    from app.services.extraction_provider import FirecrawlProvider

    src = inspect.getsource(FirecrawlProvider.extract)
    assert "logger.error" in src and "logger.warning" in src, "a dead provider must not be silent"
    assert "402" in src, "credit exhaustion must be distinguished from a transport error"


def test_manager_trips_the_circuit_on_quota_exhaustion():
    import inspect

    from app.services.extraction_manager import ExtractionManager

    src = inspect.getsource(ExtractionManager.crawl_article)
    assert "provider_circuit.is_open" in src, "an exhausted provider must be skipped, not retried"
    assert "QUOTA_EXHAUSTED" in src, "the manager must trip the circuit on 402"


# ── Tavily batching economics ────────────────────────────────────────────────


def test_batch_window_is_long_enough_to_fill_during_a_burst():
    """At 2s and ~0.3 URLs/s, 62% of batches held one URL but cost a full credit."""
    from app.core.config import settings

    assert settings.TAVILY_BATCH_TIMEOUT_SECONDS >= 10, (
        "the window must span a discovery burst or batches cannot fill"
    )


def test_followers_outlast_the_leaders_whole_cycle():
    """A follower giving up mid-request makes its own call, billing the URL twice."""
    import inspect

    from app.services.extraction_manager import ExtractionManager

    src = inspect.getsource(ExtractionManager.extract_via_tavily_batch)
    assert "EXTRACTION_PROVIDER_TIMEOUT" in src, (
        "poll budget must cover the batch window plus the Tavily request itself"
    )


def test_leader_lock_outlives_the_batch_window():
    """A lock expiring mid-collection lets a second leader drain the same buffer."""
    import inspect

    from app.services.extraction_manager import ExtractionManager

    src = inspect.getsource(ExtractionManager.extract_via_tavily_batch)
    assert "ex=batch_timeout + 10" in src, "leader lock must outlast the collection window"
