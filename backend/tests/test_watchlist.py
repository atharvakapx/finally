"""Watchlist API tests — Phase 2 Plan 02.

Tests cover WATCH-01..05:
  WATCH-01: GET /api/watchlist returns tickers with price and session_change_pct
  WATCH-02: POST validates ticker format (invalid_ticker 400)
  WATCH-03: DELETE blocked while position held (ticker_held 400)
  WATCH-04: POST rejects when watchlist is at 50-ticker cap (watchlist_full 400)
  WATCH-05: POST awaits market_source.add_ticker after DB write; DELETE awaits remove_ticker

This is RED — tests FAIL until Tasks 2-3 implement the service + router.
"""

from __future__ import annotations

import importlib
import uuid

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from app.market import PriceCache


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    """Function-scoped fixture: fresh DB, no external keys, mocked market source."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "finally.db"))
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    import app.db
    import app.main
    importlib.reload(app.db)
    importlib.reload(app.main)

    with TestClient(app.main.app) as client:
        # Replace the real market source with an AsyncMock spy so tests
        # can verify add_ticker / remove_ticker are awaited without running
        # the actual simulator's async methods.
        mock_source = MagicMock()
        mock_source.add_ticker = AsyncMock()
        mock_source.remove_ticker = AsyncMock()
        mock_source.get_tickers = MagicMock(return_value=[])
        app.main.app.state.market_source = mock_source

        yield client, app.main, mock_source


# ---------------------------------------------------------------------------
# TestGetWatchlist
# ---------------------------------------------------------------------------


class TestGetWatchlist:
    """Tests for GET /api/watchlist."""

    def test_returns_default_tickers(self, app_client) -> None:
        """Fresh DB: GET /api/watchlist returns 10 seeded tickers with required keys."""
        client, module, mock_source = app_client
        resp = client.get("/api/watchlist")
        assert resp.status_code == 200
        items = resp.json()
        assert isinstance(items, list)
        assert len(items) == 10, f"Expected 10 default tickers, got {len(items)}: {[i['ticker'] for i in items]}"
        for item in items:
            assert "ticker" in item, f"Missing 'ticker' key in item: {item}"
            assert "price" in item, f"Missing 'price' key in item: {item}"
            assert "session_change_pct" in item, f"Missing 'session_change_pct' key in item: {item}"
            assert "added_at" in item, f"Missing 'added_at' key in item: {item}"

    def test_session_change_baseline(self, app_client) -> None:
        """Session Δ%: baseline = first observed price; NOT tick-over-tick."""
        client, module, mock_source = app_client

        # Pre-warm cache with AAPL at 100.0
        cache: PriceCache = module.app.state.price_cache
        cache.update("AAPL", 100.0)

        # First GET: baseline for AAPL should be set to 100.0
        resp = client.get("/api/watchlist")
        assert resp.status_code == 200

        # Update price to 110.0 — 10% gain from baseline
        cache.update("AAPL", 110.0)

        # Second GET: session_change_pct should be 10.0 (not tick-over-tick)
        resp2 = client.get("/api/watchlist")
        assert resp2.status_code == 200
        items = resp2.json()
        aapl_item = next((i for i in items if i["ticker"] == "AAPL"), None)
        assert aapl_item is not None, "AAPL not found in watchlist"
        assert abs(aapl_item["session_change_pct"] - 10.0) < 0.01, (
            f"Expected session_change_pct=10.0, got {aapl_item['session_change_pct']}"
        )


# ---------------------------------------------------------------------------
# TestAddWatchlist
# ---------------------------------------------------------------------------


class TestAddWatchlist:
    """Tests for POST /api/watchlist."""

    def test_add_valid_ticker_persists_and_seeds(self, app_client) -> None:
        """POST valid ticker → 200, appears in GET, market_source.add_ticker awaited."""
        client, module, mock_source = app_client

        resp = client.post("/api/watchlist", json={"ticker": "PYPL"})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.json()}"
        data = resp.json()
        assert data["ticker"] == "PYPL"
        assert "added_at" in data

        # Ticker should appear in GET
        get_resp = client.get("/api/watchlist")
        assert get_resp.status_code == 200
        tickers = [i["ticker"] for i in get_resp.json()]
        assert "PYPL" in tickers, f"PYPL not found in watchlist: {tickers}"

        # add_ticker was awaited once with "PYPL"
        mock_source.add_ticker.assert_awaited_once_with("PYPL")

    def test_invalid_ticker_format(self, app_client) -> None:
        """POST invalid ticker format → 400 {error: invalid_ticker}; add_ticker NOT called."""
        client, module, mock_source = app_client

        for bad_ticker in ["invalid!!", "TOOLONG1"]:
            resp = client.post("/api/watchlist", json={"ticker": bad_ticker})
            assert resp.status_code == 400, (
                f"Expected 400 for '{bad_ticker}', got {resp.status_code}: {resp.json()}"
            )
            data = resp.json()
            assert data["error"] == "invalid_ticker", (
                f"Expected error='invalid_ticker', got {data}"
            )
            assert "message" in data

        # add_ticker must NOT have been called for any invalid ticker
        mock_source.add_ticker.assert_not_awaited()

    def test_lowercase_normalized(self, app_client) -> None:
        """POST lowercase ticker → stored and seeded as uppercase."""
        client, module, mock_source = app_client

        resp = client.post("/api/watchlist", json={"ticker": "pypl"})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.json()}"
        data = resp.json()
        assert data["ticker"] == "PYPL", f"Expected PYPL, got {data['ticker']}"

        # add_ticker was called with the uppercase version
        mock_source.add_ticker.assert_awaited_once_with("PYPL")

    def test_watchlist_cap(self, app_client) -> None:
        """POST when watchlist already at 50 tickers → 400 {error: watchlist_full}."""
        client, module, mock_source = app_client

        # 10 default tickers already seeded; insert 40 more to hit cap
        import app.db
        with app.db.get_db() as conn:
            for i in range(40):
                ticker = f"T{i:03d}"  # T000..T039 — 4-char tickers
                conn.execute(
                    "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) "
                    "VALUES (?, ?, ?, ?)",
                    (str(uuid.uuid4()), "default", ticker, "2026-01-01T00:00:00+00:00"),
                )

        # Verify we're at cap
        with app.db.get_db() as conn:
            count = conn.execute(
                "SELECT count(*) c FROM watchlist WHERE user_id='default'"
            ).fetchone()["c"]
        assert count == 50, f"Expected 50 watchlist entries, got {count}"

        # POST should now return watchlist_full
        resp = client.post("/api/watchlist", json={"ticker": "NEWT"})
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.json()}"
        data = resp.json()
        assert data["error"] == "watchlist_full", f"Expected error='watchlist_full', got {data}"
        assert "message" in data

        # add_ticker must NOT have been called
        mock_source.add_ticker.assert_not_awaited()


# ---------------------------------------------------------------------------
# TestRemoveWatchlist
# ---------------------------------------------------------------------------


class TestRemoveWatchlist:
    """Tests for DELETE /api/watchlist/{ticker}."""

    def test_remove_held_ticker_blocked(self, app_client) -> None:
        """DELETE ticker with non-zero position → 400 {error: ticker_held}; still in watchlist."""
        client, module, mock_source = app_client

        # Insert a position for AAPL with qty > 0
        import app.db
        with app.db.get_db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), "default", "AAPL", 10.0, 150.0, "2026-01-01T00:00:00+00:00"),
            )

        resp = client.delete("/api/watchlist/AAPL")
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.json()}"
        data = resp.json()
        assert data["error"] == "ticker_held", f"Expected error='ticker_held', got {data}"
        assert "message" in data

        # AAPL should still be in the watchlist
        get_resp = client.get("/api/watchlist")
        tickers = [i["ticker"] for i in get_resp.json()]
        assert "AAPL" in tickers, f"AAPL should still be in watchlist after held-block, got: {tickers}"

        # remove_ticker must NOT have been called
        mock_source.remove_ticker.assert_not_awaited()

    def test_remove_unheld_ticker(self, app_client) -> None:
        """DELETE ticker with no position → 200, gone from GET, remove_ticker awaited."""
        client, module, mock_source = app_client

        # First add PYPL to the watchlist
        add_resp = client.post("/api/watchlist", json={"ticker": "PYPL"})
        assert add_resp.status_code == 200, f"Setup POST failed: {add_resp.json()}"

        # Reset mock counts after setup
        mock_source.add_ticker.reset_mock()
        mock_source.remove_ticker.reset_mock()

        # Delete PYPL (no position)
        resp = client.delete("/api/watchlist/PYPL")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.json()}"

        # PYPL should not be in the watchlist
        get_resp = client.get("/api/watchlist")
        tickers = [i["ticker"] for i in get_resp.json()]
        assert "PYPL" not in tickers, f"PYPL should be removed, but found in: {tickers}"

        # remove_ticker was awaited once with "PYPL"
        mock_source.remove_ticker.assert_awaited_once_with("PYPL")
