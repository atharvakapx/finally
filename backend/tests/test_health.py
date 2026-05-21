"""Smoke tests for the FastAPI walking skeleton (health + static mount)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    """Module-scoped TestClient that runs the lifespan context."""
    with TestClient(app) as c:
        yield c


class TestHealthEndpoint:
    """Tests for the /api/health endpoint and basic boot-path assertions."""

    def test_health_returns_ok_status(self, client: TestClient) -> None:
        """GET /api/health returns 200 with {"status": "ok"}."""
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_root_serves_placeholder_html(self, client: TestClient) -> None:
        """GET / returns 200 with text/html content type and FinAlly branding."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "FinAlly" in response.text

    def test_unknown_api_route_returns_404(self, client: TestClient) -> None:
        """GET /api/does-not-exist returns 404 (API routes take priority over static mount)."""
        response = client.get("/api/does-not-exist")
        assert response.status_code == 404
