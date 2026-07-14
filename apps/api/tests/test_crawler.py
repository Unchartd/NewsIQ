"""Unit tests for the CrawlerService and extraction fallback stack."""

from unittest.mock import patch

import pytest

from app.services.crawler_service import crawler_service


def test_extract_newspaper():
    """Verify newspaper4k extracts content from HTML."""
    sample_html = """
    <html>
        <head>
            <title>Test Article Title</title>
        </head>
        <body>
            <h1>Test Article Title</h1>
            <p class="author">By Jane Doe</p>
            <p>This is the first paragraph of a substantial article about python programming. It needs to be at least 150 characters to pass the length verification, so we are writing a lot of text here. Let's make sure it contains enough sentences to be valid and robust.</p>
        </body>
    </html>
    """
    url = "https://example.com/test-article"
    result = crawler_service._extract_newspaper(url, sample_html)
    assert result is not None
    assert result["title"] == "Test Article Title"
    assert "substantial article about python" in result["content"]
    assert result["extractor"] == "newspaper4k"


def test_extract_trafilatura():
    """Verify trafilatura extracts content from HTML when newspaper4k fails."""
    sample_html = """
    <html>
        <body>
            <h1>Trafilatura Title</h1>
            <p>This is some content that is specifically designed to test the trafilatura extractor. Trafilatura is extremely precise at extracting main texts and discarding boilerplate. Let's write enough text so it passes the length check of 150 characters.</p>
        </body>
    </html>
    """
    result = crawler_service._extract_trafilatura(sample_html)
    assert result is not None
    assert "specifically designed to test" in result["content"]
    assert result["extractor"] == "trafilatura"


def test_extract_readability():
    """Verify readability-lxml extracts content from HTML."""
    sample_html = """
    <html>
        <body>
            <div id="content">
                <h1>Readability Title</h1>
                <p>This is a block of text designed to test the readability-lxml fallback parser. Readability looks at DOM density to find the main article container. We need to write at least 150 characters here so that the minimum length check passes successfully.</p>
            </div>
        </body>
    </html>
    """
    result = crawler_service._extract_readability(sample_html)
    assert result is not None
    assert "designed to test the readability-lxml" in result["content"]
    assert result["extractor"] == "readability-lxml"


def test_extract_custom_cleaner():
    """Verify custom bs4 cleaner scrubs boilerplate."""
    sample_html = """
    <html>
        <head><title>Custom Cleaner Title</title></head>
        <body>
            <nav>
                <a href="/home">Home</a>
            </nav>
            <div class="ads">
                Buy cheap things now!
            </div>
            <h1>Main Topic</h1>
            <p>This is the core content that we want to keep. The custom cleaner will strip out the nav tag and the div with the ad class, leaving only the main text. Let's write more text here so it reaches the required 150 character limit for extraction success.</p>
            <footer>
                Copyright 2026
            </footer>
        </body>
    </html>
    """
    result = crawler_service._extract_custom_cleaner(sample_html)
    assert result is not None
    assert "cheap things" not in result["content"]
    assert "Copyright" not in result["content"]
    assert "core content that we want to keep" in result["content"]
    assert result["extractor"] == "custom-bs4"


@pytest.mark.asyncio
async def test_crawl_article_fallback_chain():
    """Test the fallback logic when primary extractors fail."""
    url = "https://example.com/fallback-test"
    sample_html = "<html><body><p>Substantial text that is not captured by newspaper but will be captured by secondary fallback, let's write at least 150 characters here to make it pass the length requirements.</p></body></html>"

    with patch.object(
        crawler_service, "fetch_html", return_value=(sample_html, {"fetch_method": "test"})
    ):
        # 1. Newspaper fails (returns None), Trafilatura succeeds
        with patch.object(crawler_service, "_extract_newspaper", return_value=None):
            result = await crawler_service.crawl_article(url)
            assert result is not None
            assert result["success"] is True
            assert result["extractor"] == "trafilatura"

        # 2. Both Newspaper and Trafilatura fail, Readability succeeds
        with (
            patch.object(crawler_service, "_extract_newspaper", return_value=None),
            patch.object(crawler_service, "_extract_trafilatura", return_value=None),
        ):
            result = await crawler_service.crawl_article(url)
            assert result is not None
            assert result["success"] is True
            assert result["extractor"] == "readability-lxml"

        # 3. All primary fail, custom-bs4 succeeds
        with (
            patch.object(crawler_service, "_extract_newspaper", return_value=None),
            patch.object(crawler_service, "_extract_trafilatura", return_value=None),
            patch.object(crawler_service, "_extract_readability", return_value=None),
        ):
            result = await crawler_service.crawl_article(url)
            assert result is not None
            assert result["success"] is True
            assert result["extractor"] == "custom-bs4"

        # 4. All fail completely (including custom-bs4 length check)
        with (
            patch.object(crawler_service, "_extract_newspaper", return_value=None),
            patch.object(crawler_service, "_extract_trafilatura", return_value=None),
            patch.object(crawler_service, "_extract_readability", return_value=None),
            patch.object(crawler_service, "_extract_custom_cleaner", return_value=None),
        ):
            result = await crawler_service.crawl_article(url)
            assert result is not None
            assert result["success"] is False
            assert result["diagnostics"]["failure_reason"] == "EXTRACTION_FAILED"


@pytest.mark.asyncio
async def test_crawl_article_stealth_fallback():
    """Verify that when standard httpx fails, the crawler successfully falls back to curl-cffi."""
    import httpx

    url = "https://example.com/stealth-test"
    sample_html = "<html><body><p>Stealth fallback content to extract, let's write at least 150 characters here so that the minimum length check passes successfully and newspaper4k parses it.</p></body></html>"

    class MockCurlResponse:
        def __init__(self, text, status_code=200):
            self.text = text
            self.status_code = status_code

        def raise_for_status(self):
            pass

    # We patch httpx.AsyncClient.get to raise a TimeoutException
    # We patch curl_cffi AsyncSession.get to return MockCurlResponse
    with (
        patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Mocked timeout")),
        patch("curl_cffi.requests.AsyncSession.get", return_value=MockCurlResponse(sample_html)),
    ):
        result = await crawler_service.crawl_article(url)
        assert result["success"] is True
        assert result["diagnostics"]["fetch_method"] == "curl_cffi_chrome"
        assert result["diagnostics"]["failure_reason"] is None
        assert "Stealth fallback content" in result["content"]
