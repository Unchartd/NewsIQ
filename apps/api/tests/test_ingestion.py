"""Unit tests for the news ingestion and embedding services."""

from unittest.mock import MagicMock, patch

import pytest

from app.models.models import Source
from app.services.embedding_service import embedding_service
from app.services.ingestion_service import ingestion_service


def test_clean_html():
    """Verify HTML tags are stripped from strings correctly."""
    dirty_html = "<p>Hello <b>World</b>! Check out <a href='https://example.com'>this link</a>.</p>"
    cleaned = ingestion_service.clean_html(dirty_html)
    assert "Hello" in cleaned
    assert "World" in cleaned
    assert "Check out this link" in cleaned
    assert "<p>" not in cleaned


def test_clean_html_none():
    """Verify None values are handled gracefully."""
    assert ingestion_service.clean_html(None) == ""


def test_generate_mock_embedding():
    """Verify that deterministic mock embeddings generate vectors of length 1536."""
    text1 = "Breaking news about AI developments."
    text2 = "Breaking news about AI developments."
    text3 = "Different news story headline."

    vec1 = embedding_service._generate_mock_embedding(text1)
    vec2 = embedding_service._generate_mock_embedding(text2)
    vec3 = embedding_service._generate_mock_embedding(text3)

    assert len(vec1) == 1536
    assert len(vec2) == 1536
    assert len(vec3) == 1536

    # Check determinism: same input must yield same vector
    assert vec1 == vec2
    # Check variance: different input must yield different vector
    assert vec1 != vec3

    # Check normalization: vector norm should be approximately 1.0
    import math

    norm = math.sqrt(sum(x * x for x in vec1))
    assert abs(norm - 1.0) < 1e-5


@pytest.mark.asyncio
async def test_ingest_rss_source_no_new(mock_db_session):
    """Verify that ingestion service handles duplicate URLs (returns 0 new)."""
    # Mocking active source
    source = Source(
        id=MagicMock(),
        name="Test News",
        slug="test-news",
        rss_url="http://example.com/rss",
        active=True,
    )

    # Mock DB query to return an existing article (simulating a duplicate URL)
    existing_article = MagicMock()
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = existing_article
    mock_db_session.execute.return_value = mock_execute_result

    # Mock RSS Feed XML
    mock_xml = """<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
        <channel>
            <title>Test News Channel</title>
            <link>http://example.com</link>
            <item>
                <title>Duplicate News Article</title>
                <link>http://example.com/article1</link>
                <description>Some description</description>
                <pubDate>Fri, 12 Jun 2026 10:00:00 GMT</pubDate>
            </item>
        </channel>
    </rss>
    """

    class MockResponse:
        def __init__(self, text, status_code=200):
            self.text = text
            self.status_code = status_code

        def raise_for_status(self):
            pass

    # Patch httpx.AsyncClient.get to return our mock XML
    with patch("httpx.AsyncClient.get", return_value=MockResponse(mock_xml)):
        count = await ingestion_service.ingest_rss_source(source, mock_db_session)
        assert count == 0
