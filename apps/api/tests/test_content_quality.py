"""Regression tests: page furniture must never be stored as article content.

Every extractor in the chain treated any non-empty string as success, and the
last-resort BeautifulSoup cleaner returns `soup.get_text()` for the entire
page. When the article body could not be located — JS-rendered pages, consent
walls, Google News redirect shims — the pipeline stored the chrome instead.

Measured in production over 24h: 541 of 2,225 articles (24%) held navigation
menus or cookie-consent text, averaging 31,903 characters against 6,637 for
genuine articles. Those get embedded, so they cluster by site template rather
than by topic, and events are extracted from GDPR boilerplate.

The fixtures below are shortened but structurally faithful copies of real
rejected production content.
"""

import inspect

import pytest

from app.services.content_quality import assess_article_content

# ── Real shapes seen in production ───────────────────────────────────────────

CONSENT_WALL = (
    "Continue without agreeing → With your agreement, we and our 159 partners "
    "use cookies or similar technologies to store, access, and process personal "
    "data like your visit on this website, IP addresses and cookie identifiers. "
    "Some partners do not ask for your consent to process your data and rely on "
    "their legitimate business interest. You can withdraw your consent or object "
    "to data processing based on legitimate interest at any time."
)

NAV_DUMP = (
    "[![NDTV News](blob:http://localhost/9d5c20)](https://www.ndtv.com/) "
    "[Videos](https://www.ndtv.com/video) [Live TV](https://www.ndtv.com/livetv) "
    "[Latest Videos](https://www.ndtv.com/video/latest) "
    "[Categories](https://www.ndtv.com/video/categories-list) "
    "[Shows](https://www.ndtv.com/video/shows) "
    "[Classics](https://www.ndtv.com/video/ndtv-classics) "
    "[Top videos](https://www.ndtv.com/video/top) "
    "[Advertisement](https://news.google.com/rss/articles/CBMiqwFBVV) "
    "[Home](https://www.ndtv.com/home) [World](https://www.ndtv.com/world) "
)

# Long enough to clear the length floor, so it exercises the prose check
# specifically — the real Yahoo Finance page was 1,348 characters of this.
ERROR_PAGE = (
    "Something went wrong Skip to navigation Skip to main content "
    "Skip to right column Yahoo Finance News Finance Sport More News "
    "Today's news World UK Weather Politics Science & Tech Lifestyle "
    "Health & Wellness Relationships Parenting Style & Beauty "
    "Horoscopes Shopping Travel Autos Homes Mail Plus Sign in Watchlists "
    "My Portfolio Markets Screeners Personal Finance Videos Crypto "
    "Currencies Futures World Indices Sectors Earnings Calendar "
    "Economic Calendar Stock Comparison Trending Tickers Top Gainers "
    "Top Losers Most Active Analyst Ratings Insider Transactions "
    "Fund Screener Options Screener Newsletters Terms Privacy Feedback"
)

REAL_ARTICLE = (
    "Officials confirmed on Tuesday that the death toll from the firecracker "
    "factory blast in Virudhunagar has risen to 23. Rescue teams worked through "
    "the night to search the debris, and district authorities said several of the "
    "injured remained in critical condition. The state government announced "
    "compensation for the families of those killed. A preliminary inquiry found "
    "that the unit had been storing chemicals beyond its licensed capacity. "
    "Police have registered a case against the owners, who are absconding."
)


@pytest.mark.parametrize(
    "text,expected_reason",
    [
        (CONSENT_WALL, "boilerplate_wall"),
        (NAV_DUMP, "link_farm"),
        (ERROR_PAGE, "not_prose"),
        ("Short stub.", "too_short"),
        ("", "empty"),
        (None, "empty"),
    ],
)
def test_page_furniture_is_rejected(text, expected_reason):
    ok, reason = assess_article_content(text)
    assert ok is False
    assert reason == expected_reason


def test_real_article_is_accepted():
    ok, reason = assess_article_content(REAL_ARTICLE)
    assert ok is True, f"genuine article rejected as {reason}"


def test_article_mentioning_cookies_in_passing_is_not_rejected():
    """The gate must key on consent-wall structure, not the word 'cookies'.

    A story *about* privacy regulation is a real article and must survive.
    """
    text = (
        "The regulator said on Monday that firms relying on cookies to track "
        "users must obtain clearer consent. The ruling follows a two-year "
        "investigation into advertising practices across the sector. Industry "
        "groups warned the decision could reshape online publishing economics, "
        "while privacy campaigners called it overdue. The watchdog said it would "
        "begin enforcement in the autumn and publish detailed guidance shortly."
    )
    ok, reason = assess_article_content(text)
    assert ok is True, f"legitimate privacy story rejected as {reason}"


# ── The gate must actually be wired into the extraction chain ────────────────


def test_every_provider_result_passes_through_the_quality_gate():
    """A gate only one provider consults is a gate that leaks.

    Firecrawl returned full-page markdown just as the local bs4 cleaner
    returned full-page text, so all three providers need the check.
    """
    from app.services.extraction_manager import ExtractionManager

    src = inspect.getsource(ExtractionManager.crawl_article)
    for provider in ("local_res", "tavily_res", "firecrawl_res"):
        assert f"_reject_if_low_quality({provider}" in src, (
            f"{provider} is not quality-checked; page furniture can still be stored"
        )


def test_rejection_demotes_success_and_records_a_reason():
    from app.services.extraction.types import ExtractionFailure

    src = inspect.getsource(
        __import__(
            "app.services.extraction_manager", fromlist=["ExtractionManager"]
        ).ExtractionManager._reject_if_low_quality
    )
    assert "res.success = False" in src, "a rejected extraction must not report success"
    assert "LOW_QUALITY_CONTENT" in src
    assert hasattr(ExtractionFailure, "LOW_QUALITY_CONTENT")
