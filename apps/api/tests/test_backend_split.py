"""Unit tests for the Processing and User backend route isolation."""

import importlib
import pytest
from fastapi.testclient import TestClient
from app.core.config import settings


@pytest.fixture(autouse=True)
def reset_backend_role(monkeypatch):
    """Fixture to reset the BACKEND_SERVICE_ROLE setting and reload routing after tests."""
    yield
    monkeypatch.setattr(settings, "BACKEND_SERVICE_ROLE", "monolith")
    import app.api.v1.router
    import app.main
    importlib.reload(app.api.v1.router)
    importlib.reload(app.main)


def test_user_backend_routing(monkeypatch):
    """Verify that user-api loads only user-facing routes and hides admin routes."""
    monkeypatch.setattr(settings, "BACKEND_SERVICE_ROLE", "user")
    import app.api.v1.router
    import app.main
    importlib.reload(app.api.v1.router)
    importlib.reload(app.main)
    
    client = TestClient(app.main.app)
    
    # System ping is globally registered and should succeed
    assert client.get("/api/v1/ping").status_code == 200
    
    # User endpoint exists (auth or stories)
    assert client.post("/api/v1/auth/login").status_code in (400, 422)  # Bad request/missing body but route is found
    
    # Admin endpoint must be absent (404)
    assert client.get("/api/v1/admin/stats").status_code == 404


def test_processing_backend_routing(monkeypatch):
    """Verify that processing-api loads only SRE/admin-facing routes and hides user routes."""
    monkeypatch.setattr(settings, "BACKEND_SERVICE_ROLE", "processing")
    import app.api.v1.router
    import app.main
    importlib.reload(app.api.v1.router)
    importlib.reload(app.main)
    
    client = TestClient(app.main.app)
    
    # System ping should succeed
    assert client.get("/api/v1/ping").status_code == 200
    
    # User endpoint must be absent (404)
    assert client.post("/api/v1/auth/login").status_code == 404
    
    # Admin endpoint exists (returns 401/403 since unauthenticated, but NOT 404)
    assert client.get("/api/v1/admin/stats").status_code in (401, 403, 307)
