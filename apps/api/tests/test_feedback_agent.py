import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.feedback_agent import (
    calculate_hhi,
    check_clustering_similarity,
    check_missing_entities,
    evaluate_story_quality,
)
from app.models.models import Article, Story


def test_calculate_hhi():
    # 1. Diverse sources (HHI should be low)
    articles_div = [
        Article(id=uuid.uuid4(), source_id=uuid.uuid4()),
        Article(id=uuid.uuid4(), source_id=uuid.uuid4()),
        Article(id=uuid.uuid4(), source_id=uuid.uuid4()),
        Article(id=uuid.uuid4(), source_id=uuid.uuid4()),
    ]
    hhi_div = calculate_hhi(articles_div)
    # 4 distinct sources = 4 * (0.25^2) = 0.25
    assert abs(hhi_div - 0.25) < 0.001

    # 2. Dominated by single source (HHI should be high)
    shared_src = uuid.uuid4()
    articles_dom = [
        Article(id=uuid.uuid4(), source_id=shared_src),
        Article(id=uuid.uuid4(), source_id=shared_src),
        Article(id=uuid.uuid4(), source_id=shared_src),
        Article(id=uuid.uuid4(), source_id=uuid.uuid4()),
    ]
    hhi_dom = calculate_hhi(articles_dom)
    # 3 from shared, 1 from other = (0.75^2) + (0.25^2) = 0.5625 + 0.0625 = 0.625
    assert abs(hhi_dom - 0.625) < 0.001


@pytest.mark.asyncio
async def test_check_clustering_similarity():
    art1_id = uuid.uuid4()
    art2_id = uuid.uuid4()
    articles = [
        Article(id=art1_id),
        Article(id=art2_id),
    ]

    # Perfect alignment (vectors match)
    mock_vectors = {
        str(art1_id): [1.0, 0.0, 0.0],
        str(art2_id): [1.0, 0.0, 0.0],
    }

    with patch(
        "app.services.vector_service.vector_service.retrieve_vectors", new_callable=AsyncMock
    ) as mock_retrieve:
        mock_retrieve.return_value = mock_vectors
        sim = await check_clustering_similarity(articles)
        assert abs(sim - 1.0) < 0.001

    # Partially aligned
    mock_vectors_partial = {
        str(art1_id): [1.0, 0.0, 0.0],
        str(art2_id): [0.707, 0.707, 0.0],  # 45 deg = 0.707 similarity
    }

    with patch(
        "app.services.vector_service.vector_service.retrieve_vectors", new_callable=AsyncMock
    ) as mock_retrieve:
        mock_retrieve.return_value = mock_vectors_partial
        sim = await check_clustering_similarity(articles)
        assert abs(sim - 0.707) < 0.01


def test_check_missing_entities():
    kg = {
        "nodes": [
            {"label": "Barack Obama", "type": "Person"},
            {"label": "White House", "type": "Location"},
            {"label": "Apple Inc.", "type": "Organization"},
            {"label": "some unimportant text node", "type": "Text"},
        ]
    }

    # Summary has everything
    summary_good = "Barack Obama visited the White House to talk about Apple Inc."
    missing = check_missing_entities(kg, summary_good)
    assert len(missing) == 0

    # Summary has omissions
    summary_bad = "A president visited a corporate headquarters."
    missing = check_missing_entities(kg, summary_bad)
    assert "Barack Obama" in missing
    assert "White House" in missing
    assert "Apple Inc." in missing


@pytest.mark.asyncio
async def test_evaluate_story_quality_programmatic_pass():
    story = Story(id=uuid.uuid4())

    from app.models.models import ArticleEvent

    # 4 distinct sources, HHI = 0.25 (good)
    articles = []
    for _ in range(4):
        art = Article(id=uuid.uuid4(), source_id=uuid.uuid4())
        art.events = [
            ArticleEvent(
                id=uuid.uuid4(), article_id=art.id, event_fingerprint="evt-1", event_type="test"
            )
        ]
        articles.append(art)

    kg = {
        "nodes": [
            {"label": "Alice", "type": "Person"},
            {"label": "Paris", "type": "Location"},
        ]
    }

    # High cosine similarity (mock vector check)
    mock_vectors = {str(a.id): [1.0, 0.0, 0.0] for a in articles}

    summary = "Alice travelled to Paris for vacation."

    with patch(
        "app.services.vector_service.vector_service.retrieve_vectors", new_callable=AsyncMock
    ) as mock_retrieve:
        mock_retrieve.return_value = mock_vectors

        # Test non-high-stakes category (e.g. sports) that should pass programmatically
        report = await evaluate_story_quality(
            story=story,
            articles=articles,
            kg=kg,
            contradictions=[],
            timeline=[],
            summary_text=summary,
            category_slug="sports",
            regeneration_count=0,
        )

        assert report.action == "publish"
        assert report.score >= 0.85
        assert not report.hallucination_detected
