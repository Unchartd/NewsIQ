"""Unit tests for the admin debugger and observability endpoints."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.deps import require_admin
from app.main import app
from app.models.models import User
from app.schemas.admin_schemas import (
    ClusterDebuggerResponse,
    CostAnalyticsResponse,
    EntityDebuggerResponse,
    MetricsSummaryResponse,
    PipelineStatusResponse,
    StoryInspectorResponse,
    TimelineDebuggerResponse,
)


@pytest.fixture(autouse=True)
def override_admin_auth():
    """Override require_admin dependency to bypass JWT auth for admin tests."""
    mock_admin = User(id=uuid.uuid4(), email="admin@newsiq.io", role="admin")
    app.dependency_overrides[require_admin] = lambda: mock_admin
    yield
    app.dependency_overrides.pop(require_admin, None)


def test_inspect_story_endpoint():
    """Verify that GET /admin/stories/{story_id} invokes admin_service and returns data."""
    story_id = uuid.uuid4()
    mock_data = StoryInspectorResponse(
        id=story_id,
        headline="AI Breakthrough",
        short_summary="A short summary",
        created_at="2026-06-20T14:30:00",
        articles=[],
        events=[],
        entities=[],
        llm_traces=[],
        stage_runs=[],
        total_cost_usd=0.0,
    )

    with patch(
        "app.services.admin_service.admin_service.get_story_inspector_data",
        AsyncMock(return_value=mock_data),
    ) as mock_get:
        client = TestClient(app)
        response = client.get(f"/api/v1/admin/stories/{story_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(story_id)
        assert data["headline"] == "AI Breakthrough"
        mock_get.assert_called_once()


def test_pipeline_status_endpoint():
    """Verify that GET /admin/pipeline/status returns current pipeline run status."""
    mock_data = PipelineStatusResponse(
        run_id=uuid.uuid4(),
        status="running",
        stages=[],
    )

    with patch(
        "app.services.admin_service.admin_service.get_pipeline_status",
        AsyncMock(return_value=mock_data),
    ) as mock_get:
        client = TestClient(app)
        response = client.get("/api/v1/admin/pipeline/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        mock_get.assert_called_once()


def test_cost_analytics_endpoint():
    """Verify that GET /admin/costs returns token costs breakdown."""
    mock_data = CostAnalyticsResponse(
        total_cost_usd=1.25,
        breakdown=[],
    )

    with patch(
        "app.services.admin_service.admin_service.get_cost_analytics",
        AsyncMock(return_value=mock_data),
    ) as mock_get:
        client = TestClient(app)
        response = client.get("/api/v1/admin/costs")

        assert response.status_code == 200
        data = response.json()
        assert data["total_cost_usd"] == 1.25
        mock_get.assert_called_once()


def test_entity_debugger_endpoint():
    """Verify that GET /admin/entities returns entity counts and confidence."""
    mock_data = EntityDebuggerResponse(entities=[])

    with patch(
        "app.services.admin_service.admin_service.get_entity_debugger_data",
        AsyncMock(return_value=mock_data),
    ) as mock_get:
        client = TestClient(app)
        response = client.get("/api/v1/admin/entities")

        assert response.status_code == 200
        data = response.json()
        assert "entities" in data
        mock_get.assert_called_once()


def test_cluster_debugger_endpoint():
    """Verify that GET /admin/clusters returns grouping info."""
    mock_data = ClusterDebuggerResponse(clusters=[])

    with patch(
        "app.services.admin_service.admin_service.get_cluster_debugger_data",
        AsyncMock(return_value=mock_data),
    ) as mock_get:
        client = TestClient(app)
        response = client.get("/api/v1/admin/clusters")

        assert response.status_code == 200
        data = response.json()
        assert "clusters" in data
        mock_get.assert_called_once()


def test_timeline_debugger_endpoint():
    """Verify that GET /admin/timeline/{story_id} returns timeline details."""
    story_id = uuid.uuid4()
    mock_data = TimelineDebuggerResponse(
        story_id=story_id,
        timeline=[],
        contradictions=[],
    )

    with patch(
        "app.services.admin_service.admin_service.get_timeline_debugger_data",
        AsyncMock(return_value=mock_data),
    ) as mock_get:
        client = TestClient(app)
        response = client.get(f"/api/v1/admin/timeline/{story_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["story_id"] == str(story_id)
        mock_get.assert_called_once()


def test_metrics_summary_endpoint():
    """Verify that GET /admin/metrics/summary returns high-level metrics summary."""
    mock_data = MetricsSummaryResponse(
        total_pipeline_runs=10,
        failed_runs_count=1,
        total_llm_cost=0.50,
        total_tokens_consumed=10000,
        waiting_jobs_count=0,
        active_jobs_count=0,
    )

    with patch(
        "app.services.admin_service.admin_service.get_metrics_summary",
        AsyncMock(return_value=mock_data),
    ) as mock_get:
        client = TestClient(app)
        response = client.get("/api/v1/admin/metrics/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["total_pipeline_runs"] == 10
        assert data["total_llm_cost"] == 0.50
        mock_get.assert_called_once()
