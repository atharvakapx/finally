"""Phase 1 integration test — full lifespan happy path."""

from __future__ import annotations

import importlib
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    """Function-scoped fixture: fresh DB, no external keys, full lifespan via TestClient."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "finally.db"))
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    import app.db
    import app.main
    importlib.reload(app.db)
    importlib.reload(app.main)

    with TestClient(app.main.app) as client:
        yield client, app.main

    # Confirm DB file was created
    assert (tmp_path / "finally.db").exists()


class TestPhase1Integration:
    """End-to-end integration tests for the Phase 1 walking skeleton."""

    def test_health_endpoint_returns_ok(self, app_client) -> None:
        """GET /api/health returns 200 with {"status": "ok"}."""
        client, _ = app_client
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_portfolio_history_endpoint_live(self, app_client) -> None:
        """GET /api/portfolio/history returns 200 with a list (plan 02-03 implemented it).

        Returns an empty list on a fresh DB (no snapshots yet), or a list of
        {total_value, recorded_at} dicts if snapshots exist.
        """
        client, _ = app_client
        resp = client.get("/api/portfolio/history")
        assert resp.status_code == 200, f"GET /api/portfolio/history returned {resp.status_code}: {resp.json()}"
        data = resp.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}: {data}"

    def test_watchlist_endpoints_live(self, app_client) -> None:
        """Watchlist endpoints are live (Phase 2 implemented); GET returns 200 with items."""
        client, _ = app_client
        # GET should now return 200 with the seeded watchlist (not 501 stub)
        resp = client.get("/api/watchlist")
        assert resp.status_code == 200, f"GET /api/watchlist returned {resp.status_code}: {resp.json()}"
        items = resp.json()
        assert isinstance(items, list)
        assert len(items) == 10, f"Expected 10 default tickers, got {len(items)}"

    def test_chat_returns_200(self, app_client) -> None:
        """POST /api/chat returns 200 (Phase 3 implemented; 501 stub replaced)."""
        client, _ = app_client
        resp = client.post("/api/chat", json={"message": "hi"})
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data

    def test_market_source_is_simulator_when_no_massive_key(self, app_client) -> None:
        """When MASSIVE_API_KEY is absent, SimulatorDataSource is used."""
        client, module = app_client
        source = module.app.state.market_source
        assert type(source).__name__ == "SimulatorDataSource", (
            f"Expected SimulatorDataSource, got {type(source).__name__}"
        )

    def test_price_cache_populated_within_3_seconds(self, app_client) -> None:
        """PriceCache holds prices for all 10 default tickers within 3 seconds of startup."""
        client, module = app_client
        # Simulator runs at ~500ms cadence; 2 second wait is sufficient
        time.sleep(2.0)
        cache = module.app.state.price_cache
        prices = cache.get_all()
        from app.db import DEFAULT_TICKERS
        for ticker in DEFAULT_TICKERS:
            assert ticker in prices, f"Ticker {ticker} not in cache after 2s; have: {sorted(prices.keys())}"
            assert prices[ticker].price > 0, f"Price for {ticker} is {prices[ticker].price}"

    def test_sse_stream_emits_event_within_3_seconds(self, app_client) -> None:
        """GET /api/stream/prices returns text/event-stream and emits a data event."""
        client, _ = app_client
        deadline = time.monotonic() + 3.0
        found_data = False
        accumulated = b""
        with client.stream("GET", "/api/stream/prices") as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream"), (
                f"Unexpected content-type: {response.headers['content-type']}"
            )
            # Read raw bytes in chunks; stop as soon as we see a "data:" line
            # or the deadline expires. iter_bytes() yields chunks as they arrive.
            for chunk in response.iter_bytes(chunk_size=256):
                accumulated += chunk
                if b"data:" in accumulated:
                    found_data = True
                    break
                if time.monotonic() > deadline:
                    break
        assert found_data, (
            f"No data event received from SSE stream within 3 seconds. "
            f"Got: {accumulated[:200]!r}"
        )

    def test_static_root_served(self, app_client) -> None:
        """GET / returns 200 with FinAlly branding in the HTML."""
        client, _ = app_client
        resp = client.get("/")
        assert resp.status_code == 200
        assert "FinAlly" in resp.text
