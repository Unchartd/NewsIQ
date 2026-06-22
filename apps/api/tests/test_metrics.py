"""Unit tests for the Prometheus metrics integration."""

from fastapi.testclient import TestClient

from app.main import app


def test_metrics_endpoint(monkeypatch):
    """Verify that the /metrics endpoint returns prometheus metrics."""
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    client = TestClient(app)
    response = client.get("/metrics")
    
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    
    # Check that our custom metrics are declared in the registry output
    content = response.text
    assert "# HELP newsiq_latency_seconds" in content
    assert "# TYPE newsiq_latency_seconds histogram" in content
    assert "# HELP newsiq_token_usage_total" in content
    assert "# TYPE newsiq_token_usage_total counter" in content
    assert "# HELP newsiq_provider_calls_total" in content
    assert "# HELP newsiq_llm_cost_dollars" in content
