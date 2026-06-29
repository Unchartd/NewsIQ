"""Unit tests for the pipeline failures admin API endpoints."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.deps import require_admin
from app.main import app
from app.models.models import User
from app.models.observability_models import PipelineFailureModel


@pytest.fixture(autouse=True)
def override_admin_auth():
    """Override require_admin dependency to bypass JWT auth for admin tests."""
    mock_admin = User(id=uuid.uuid4(), email="admin@newsiq.io", role="admin")
    app.dependency_overrides[require_admin] = lambda: mock_admin
    yield
    app.dependency_overrides.pop(require_admin, None)


def test_list_failures_endpoint():
    """Verify that GET /admin/failures returns registered failures."""
    mock_failure = PipelineFailureModel(
        id=uuid.uuid4(),
        trace_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        stage="event_extraction",
        error_category="data_error",
        error_code="EMPTY_ARTICLE",
        exception="ValueError: Empty article",
        stack_trace="Traceback...",
        retry_count=0,
        latency=0.1,
        resolved=False,
    )

    from app.core.database import get_db

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_failure]
    mock_res.scalars.return_value = mock_scalars
    mock_res.scalar.return_value = 1
    mock_db.execute.return_value = mock_res

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        client = TestClient(app)
        response = client.get("/api/v1/admin/failures?resolved=false")

        assert response.status_code == 200
        data = response.json()
        assert "failures" in data
        assert len(data["failures"]) == 1
        assert data["failures"][0]["stage"] == "event_extraction"
        assert data["failures"][0]["errorCode"] == "EMPTY_ARTICLE"
        assert data["total"] == 1
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_get_failure_detail_endpoint():
    """Verify that GET /admin/failures/{id} returns details for a failure."""
    failure_id = uuid.uuid4()
    mock_failure = PipelineFailureModel(
        id=failure_id,
        trace_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        stage="event_extraction",
        error_category="data_error",
        error_code="EMPTY_ARTICLE",
        exception="ValueError: Empty article",
        stack_trace="Traceback...",
        retry_count=0,
        latency=0.1,
        resolved=False,
    )

    from app.core.database import get_db
    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_failure
    mock_db.execute.return_value = mock_res

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/admin/failures/{failure_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["failureId"] == str(failure_id)
        assert data["stage"] == "event_extraction"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_resolve_failure_endpoint():
    """Verify that POST /admin/failures/{id}/resolve marks failure as resolved."""
    failure_id = uuid.uuid4()
    mock_failure = PipelineFailureModel(
        id=failure_id,
        trace_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        stage="event_extraction",
        error_category="data_error",
        error_code="EMPTY_ARTICLE",
        exception="ValueError: Empty article",
        stack_trace="Traceback...",
        retry_count=0,
        latency=0.1,
        resolved=False,
    )

    from app.core.database import get_db
    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_failure
    mock_db.execute.return_value = mock_res

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/admin/failures/{failure_id}/resolve",
            json={"resolution_notes": "fixed"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["resolved"] is True
        assert data["resolutionNotes"] == "fixed"
        mock_db.commit.assert_called_once()
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_failure_analytics_endpoint():
    """Verify that GET /admin/failure-analytics returns Sentry-like charting data."""
    from app.core.database import get_db
    mock_db = AsyncMock()

    # Sequential queries in the endpoint:
    # 1. select total failures count
    # 2. select resolved failures count
    # 3. select top failing stages (group by stage)
    # 4. select common provider failures (group by provider)
    # 5. select count where error_code = RESOURCE_EXHAUSTED
    # 6. select count where error_code = RATE_LIMIT_EXCEEDED
    # 7. select avg retry_count
    # 8. select provider health (group by provider)
    # 9. select failures daily trend (group by day)
    # 10. select successes daily trend (group by day)

    mock_res_total = MagicMock()
    mock_res_total.scalar.return_value = 10

    mock_res_resolved = MagicMock()
    mock_res_resolved.scalar.return_value = 3

    mock_res_stages = MagicMock()
    mock_res_stages.scalars.return_value = MagicMock(all=lambda: [("event_extraction", 5)])

    mock_res_providers = MagicMock()
    mock_res_providers.scalars.return_value = MagicMock(all=lambda: [("google", 4)])

    mock_res_quota = MagicMock()
    mock_res_quota.scalar.return_value = 1

    mock_res_rate = MagicMock()
    mock_res_rate.scalar.return_value = 2

    mock_res_avg = MagicMock()
    mock_res_avg.scalar.return_value = 1.5

    # For health, we iterate over it or call scalars().all()
    # In code:
    # res_health = await db.execute(stmt_health)
    # for r in res_health:
    # So res_health itself must be iterable!
    mock_res_health = MagicMock()
    mock_res_health.__iter__.return_value = iter([("google", 10, 2)])

    # Trends:
    # res_fail_trend = await db.execute(stmt_fail_trend)
    # failures_by_day = {r[0]... for r in res_fail_trend}
    mock_res_fail_trend = MagicMock()
    mock_res_fail_trend.__iter__.return_value = iter([])

    mock_res_succ_trend = MagicMock()
    mock_res_succ_trend.__iter__.return_value = iter([])

    mock_db.execute.side_effect = [
        mock_res_total,
        mock_res_resolved,
        mock_res_stages,
        mock_res_providers,
        mock_res_quota,
        mock_res_rate,
        mock_res_avg,
        mock_res_health,
        mock_res_fail_trend,
        mock_res_succ_trend,
    ]

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        client = TestClient(app)
        response = client.get("/api/v1/admin/failure-analytics")

        assert response.status_code == 200
        data = response.json()
        assert data["totalFailures"] == 10
        assert data["resolvedFailures"] == 3
        assert data["unresolvedFailures"] == 7
        assert data["avgRetries"] == 1.5
        assert len(data["dailyTrends"]) == 14
    finally:
        app.dependency_overrides.pop(get_db, None)
