"""Unit tests for PreCrawlerDecisionEngine and MicroClusterService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ingestion.pre_crawler_engine import PreCrawlerDecision, PreCrawlerDecisionEngine
from app.services.micro_cluster_service import MicroCluster, MicroClusterService


@pytest.mark.asyncio
async def test_pre_crawler_decision_engine_new_url():
    engine = PreCrawlerDecisionEngine()
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_res

    with patch(
        "app.ingestion.pre_crawler_engine.url_bloom_filter.exists", new_callable=AsyncMock
    ) as mock_bloom:
        mock_bloom.return_value = False
        decision = await engine.evaluate_url(
            "https://www.cnbc.com/2026/07/08/apple-test.html", mock_session
        )

        assert isinstance(decision, PreCrawlerDecision)
        assert decision.should_crawl is True
        assert decision.duplicate_reason == "NEW_URL"
        assert decision.canonical_url.startswith("https://")


def test_micro_cluster_service_partitioning():
    service = MicroClusterService()

    art1 = {
        "source_name": "Reuters",
        "title": "Apple commits $30 billion to Broadcom",
        "embedding_vector": [0.1] * 768,
        "extracted_entities": [{"value": "Apple"}, {"value": "Broadcom"}],
        "extracted_events": [{"event_type": "ECONOMIC_EVENT"}],
    }

    art2 = {
        "source_name": "CNBC",
        "title": "Apple commits $30B to Broadcom for chipmaking",
        "embedding_vector": [0.1] * 768,
        "extracted_entities": [{"value": "Apple"}, {"value": "Broadcom"}],
        "extracted_events": [{"event_type": "ECONOMIC_EVENT"}],
    }

    clusters = service.partition_micro_clusters([art1, art2])

    assert len(clusters) >= 1
    assert isinstance(clusters[0], MicroCluster)
    assert clusters[0].member_count == 2
    assert len(clusters[0].centroid_vector) == 768
    assert clusters[0].dominant_event == "ECONOMIC_EVENT"
