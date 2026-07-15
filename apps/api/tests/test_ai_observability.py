"""Unit tests for AI execution provenance, capability routing, and admin analytics endpoints."""

from unittest.mock import MagicMock, patch

import pytest

from app.ai.router.capability_router import capability_router
from app.api.v1.admin import (
    get_cache_effectiveness,
    get_context_analytics,
    get_cost_forecasting,
    get_hallucination_analytics,
    get_model_benchmarks,
    get_prompt_analytics,
    get_provider_sla,
)


@pytest.mark.asyncio
async def test_capability_routing_resolution():
    """Verify that capability routing correctly maps abstract capabilities to models (Phase 9)."""
    # Verify that capability keys resolve correctly
    routes = capability_router.get_model_route("extraction-speed")
    assert len(routes) > 0
    # For extraction-speed, verify the route maps to the resolved model configuration
    # In testing mode it always returns mock, but let's temporarily bypass/test resolution
    with patch("sys.argv", ["pytest"]):
        # Mock sys.argv detection behaves as testing, returning mock
        routes_test = capability_router.get_model_route("extraction-speed")
        assert routes_test[0][2]["model"] == "mock"


@pytest.mark.asyncio
async def test_prompt_analytics_endpoint(mock_db_session):
    """Verify get_prompt_analytics queries the DB and formats responses correctly (Phase 2)."""
    mock_row = MagicMock()
    mock_row.prompt_name = "summary_generation"
    mock_row.prompt_version = "1.0.0"
    mock_row.total_runs = 10
    mock_row.successes = 9
    mock_row.avg_latency_ms = 1200.0
    mock_row.avg_cost = 0.003
    mock_row.schema_repairs = 1
    mock_row.failed_runs = 1
    mock_row.avg_retries = 0.2
    mock_row.cache_hits = 2

    mock_result = MagicMock()
    mock_result.all.return_value = [mock_row]
    mock_db_session.execute.return_value = mock_result

    res = await get_prompt_analytics(db=mock_db_session)
    assert len(res) == 1
    assert res[0].prompt_name == "summary_generation"
    assert res[0].success_rate == 0.9
    assert res[0].cache_hit_rate == 0.2
    assert res[0].validation_failures == 2


@pytest.mark.asyncio
async def test_model_benchmarks_endpoint(mock_db_session):
    """Verify get_model_benchmarks queries the DB and formats responses correctly (Phase 3)."""
    mock_row = MagicMock()
    mock_row.model = "gemini-2.5-pro"
    mock_row.capability = "reasoning-heavy"
    mock_row.total_runs = 5
    mock_row.successes = 5
    mock_row.avg_latency_ms = 2200.0
    mock_row.input_tokens = 5000
    mock_row.output_tokens = 1000
    mock_row.schema_repairs = 0
    mock_row.failed_runs = 0
    mock_row.total_retries = 0
    mock_row.avg_cost = 0.005
    mock_row.total_fallbacks = 1

    mock_result = MagicMock()
    mock_result.all.return_value = [mock_row]
    mock_db_session.execute.return_value = mock_result

    res = await get_model_benchmarks(db=mock_db_session)
    assert len(res) == 1
    assert res[0].model == "gemini-2.5-pro"
    assert res[0].success_rate == 1.0
    assert res[0].json_validity_rate == 1.0
    assert res[0].fallback_frequency == 0.2


@pytest.mark.asyncio
async def test_context_analytics_endpoint(mock_db_session):
    """Verify get_context_analytics computes percentiles and identifies outliers (Phase 4)."""
    mock_result = MagicMock()
    mock_result.all.return_value = [
        ("summary_generation", 1000, 200),
        ("summary_generation", 2000, 300),
        ("summary_generation", 15000, 1000),  # outlier
    ]
    mock_db_session.execute.return_value = mock_result

    res = await get_context_analytics(db=mock_db_session)
    assert len(res) == 1
    assert res[0].stage == "summary_generation"
    assert res[0].abnormally_large_count == 1
    assert res[0].total_runs == 3
    assert res[0].max_total_tokens == 16000


@pytest.mark.asyncio
async def test_cache_effectiveness_endpoint(mock_db_session):
    """Verify get_cache_effectiveness groups correctly and flags low value cache stages (Phase 5)."""
    mock_row = MagicMock()
    mock_row.stage = "ner_extraction"
    mock_row.prompt_name = "ner"
    mock_row.model = "gemini-3.1-flash-lite"
    mock_row.total_requests = 100
    mock_row.hits = 5  # 5% hit rate -> low value

    mock_result = MagicMock()
    mock_result.all.return_value = [mock_row]
    mock_db_session.execute.return_value = mock_result

    res = await get_cache_effectiveness(db=mock_db_session)
    assert len(res) == 1
    assert res[0].stage == "ner_extraction"
    assert res[0].hit_rate == 0.05
    assert res[0].low_value is True


@pytest.mark.asyncio
async def test_hallucination_analytics_endpoint(mock_db_session):
    """Verify get_hallucination_analytics calculates facts and contradiction rates (Phase 6)."""
    mock_row = MagicMock()
    mock_row.total = 10
    mock_row.avg_claims = 1.2
    mock_row.avg_citations = 0.5
    mock_row.total_contras = 2
    mock_row.avg_bias = 0.1
    mock_row.avg_regen = 0.3
    mock_row.avg_conf = 0.95

    mock_result = MagicMock()
    mock_result.first.return_value = mock_row
    mock_db_session.execute.return_value = mock_result

    res = await get_hallucination_analytics(db=mock_db_session)
    assert res.total_reflections == 10
    assert res.avg_unsupported_claims == 1.2
    assert res.contradiction_rate == 0.2
    assert res.avg_reflection_confidence == 0.95


@pytest.mark.asyncio
async def test_cost_forecasting_endpoint(mock_db_session):
    """Verify get_cost_forecasting returns variable volume tier forecasts (Phase 7)."""
    # Mock article cost query result
    mock_art_res = MagicMock()
    mock_art_res.first.return_value = (100.0, 1000)  # avg 0.10 per article
    # Mock story cost query result
    mock_story_res = MagicMock()
    mock_story_res.first.return_value = (50.0, 100)  # avg 0.50 per story

    mock_db_session.execute.side_effect = [mock_art_res, mock_story_res]

    res = await get_cost_forecasting(db=mock_db_session)
    assert res.avg_cost_per_article == 0.10
    assert res.avg_cost_per_story == 0.50
    assert len(res.forecasts) == 5
    # For volume 10000 (daily_cost = 10000 * 0.10 + 2000 * 0.50 = 2000)
    assert res.forecasts[0].volume == 10000
    assert res.forecasts[0].daily_cost == 2000.0


@pytest.mark.asyncio
async def test_provider_sla_endpoint(mock_db_session):
    """Verify get_provider_sla aggregates availability and latency per provider (Phase 8)."""
    mock_row = MagicMock()
    mock_row.provider = "gemini"
    mock_row.total = 10
    mock_row.successes = 9
    mock_row.latency = 800.0
    mock_row.retries = 2
    mock_row.fallbacks = 1

    mock_result = MagicMock()
    mock_result.all.return_value = [mock_row]
    mock_db_session.execute.return_value = mock_result

    res = await get_provider_sla(db=mock_db_session)
    assert len(res) == 1
    assert res[0].provider == "gemini"
    assert res[0].availability == 0.9
    assert res[0].fallback_rate == 0.1
