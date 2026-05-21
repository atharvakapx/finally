"""Portfolio API tests — PORT-01, PORT-02, PORT-03, PORT-05.

Covers: GET /api/portfolio, POST /api/portfolio/trade (buy/sell validations,
weighted-average cost, fill price, concurrency protection).
"""

from __future__ import annotations

import importlib
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app.market import PriceCache


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


def seed_cache(module, ticker: str, price: float) -> None:
    """Helper: seed a deterministic price into the app's price cache."""
    module.app.state.price_cache.update(ticker, price)


# ---------------------------------------------------------------------------
# GET /api/portfolio tests
# ---------------------------------------------------------------------------


class TestGetPortfolio:
    def test_get_portfolio_empty(self, app_client) -> None:
        """Fresh DB (no positions) → positions == [], total_value == 10000.0, cash == 10000.0."""
        client, module = app_client
        resp = client.get("/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cash"] == 10000.0
        assert data["positions"] == []
        assert data["total_value"] == 10000.0

    def test_get_portfolio_total_matches_cache(self, app_client) -> None:
        """Seed cash + a position, set cache price → total_value == cash + quantity*price."""
        client, module = app_client

        # Seed AAPL into cache at $150
        seed_cache(module, "AAPL", 150.0)

        # Buy 10 shares of AAPL at 150 → cash 8500, position qty=10 avg_cost=150
        resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10})
        assert resp.status_code == 200

        # Now re-seed cache at new price $200 to test valuation
        seed_cache(module, "AAPL", 200.0)

        resp = client.get("/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()

        # total_value = cash(8500) + 10 * 200 = 10500
        assert abs(data["total_value"] - 10500.0) < 0.01
        assert abs(data["cash"] - 8500.0) < 0.01

        assert len(data["positions"]) == 1
        pos = data["positions"][0]
        assert pos["ticker"] == "AAPL"
        assert pos["quantity"] == 10
        assert abs(pos["avg_cost"] - 150.0) < 0.01
        assert abs(pos["current_price"] - 200.0) < 0.01
        # unrealized_pnl = 10 * (200 - 150) = 500
        assert abs(pos["unrealized_pnl"] - 500.0) < 0.01
        # pnl_pct = 500 / (10*150) * 100 = 33.33%
        assert abs(pos["pnl_pct"] - 33.333) < 0.01
        # Verify all expected keys are present
        for key in ("ticker", "quantity", "avg_cost", "current_price", "unrealized_pnl", "pnl_pct"):
            assert key in pos, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# POST /api/portfolio/trade tests
# ---------------------------------------------------------------------------


class TestExecuteTrade:
    def test_buy_debits_cash_and_sets_avg_cost(self, app_client) -> None:
        """Buy 10 AAPL @100 → cash 10000→9000, position avg_cost 100.0, quantity 10."""
        client, module = app_client
        seed_cache(module, "AAPL", 100.0)

        resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10})
        assert resp.status_code == 200
        data = resp.json()

        assert abs(data["cash_balance"] - 9000.0) < 0.01
        assert data["position"]["ticker"] == "AAPL"
        assert data["position"]["quantity"] == 10
        assert abs(data["position"]["avg_cost"] - 100.0) < 0.01

    def test_buy_weighted_average_cost(self, app_client) -> None:
        """Buy 10 @100 then buy 10 @200 → quantity 20, avg_cost 150.0."""
        client, module = app_client
        seed_cache(module, "AAPL", 100.0)
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10})

        seed_cache(module, "AAPL", 200.0)
        resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10})
        assert resp.status_code == 200
        data = resp.json()

        assert data["position"]["quantity"] == 20
        assert abs(data["position"]["avg_cost"] - 150.0) < 0.01

    def test_buy_insufficient_cash(self, app_client) -> None:
        """Buy a quantity whose cost > cash → 400 {"error":"insufficient_cash"}, cash unchanged."""
        client, module = app_client
        # AAPL at $2000, buy 10 = $20000 → exceeds $10000 cash
        seed_cache(module, "AAPL", 2000.0)
        resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10})
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"] == "insufficient_cash"
        assert "message" in data

        # Cash must be unchanged
        portfolio = client.get("/api/portfolio").json()
        assert portfolio["cash"] == 10000.0

    def test_sell_credits_cash_and_reduces(self, app_client) -> None:
        """Hold 10 @100, sell 4 @120 → cash += 480, quantity 6, avg_cost stays 100.0."""
        client, module = app_client
        seed_cache(module, "AAPL", 100.0)
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10})

        seed_cache(module, "AAPL", 120.0)
        resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "sell", "quantity": 4})
        assert resp.status_code == 200
        data = resp.json()

        # cash after buy: 10000 - 1000 = 9000; sell 4@120 = +480 → 9480
        assert abs(data["cash_balance"] - 9480.0) < 0.01
        assert data["position"]["quantity"] == 6
        # avg_cost must NOT change on sell
        assert abs(data["position"]["avg_cost"] - 100.0) < 0.01

    def test_full_sell_deletes_position(self, app_client) -> None:
        """Hold 10, sell 10 → GET /api/portfolio shows no position row for that ticker."""
        client, module = app_client
        seed_cache(module, "AAPL", 100.0)
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10})

        resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "sell", "quantity": 10})
        assert resp.status_code == 200

        portfolio = client.get("/api/portfolio").json()
        tickers_in_positions = [p["ticker"] for p in portfolio["positions"]]
        assert "AAPL" not in tickers_in_positions

    def test_sell_oversold(self, app_client) -> None:
        """Hold 5, sell 10 → 400 {"error":"insufficient_shares"}, position unchanged."""
        client, module = app_client
        seed_cache(module, "AAPL", 100.0)
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 5})

        resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "sell", "quantity": 10})
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"] == "insufficient_shares"
        assert "message" in data

        # Position must be unchanged
        portfolio = client.get("/api/portfolio").json()
        pos = next((p for p in portfolio["positions"] if p["ticker"] == "AAPL"), None)
        assert pos is not None
        assert pos["quantity"] == 5

    def test_invalid_side(self, app_client) -> None:
        """side='hold' → 400 {"error":"invalid_side"}."""
        client, module = app_client
        seed_cache(module, "AAPL", 100.0)
        resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "hold", "quantity": 1})
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"] == "invalid_side"

    def test_invalid_quantity_zero(self, app_client) -> None:
        """quantity=0 → 400 {"error":"invalid_quantity"}."""
        client, module = app_client
        seed_cache(module, "AAPL", 100.0)
        resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 0})
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"] == "invalid_quantity"

    def test_invalid_quantity_negative(self, app_client) -> None:
        """quantity=-5 → 400 {"error":"invalid_quantity"}."""
        client, module = app_client
        seed_cache(module, "AAPL", 100.0)
        resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": -5})
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"] == "invalid_quantity"

    def test_trade_fills_at_cache_price(self, app_client) -> None:
        """Cache MSFT=321.0; buy 1 → response trade.price == 321.0."""
        client, module = app_client
        seed_cache(module, "MSFT", 321.0)
        resp = client.post("/api/portfolio/trade", json={"ticker": "MSFT", "side": "buy", "quantity": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert abs(data["trade"]["price"] - 321.0) < 0.01

    def test_no_cache_price_503(self, app_client) -> None:
        """Ticker with no cache entry → 503 {"error":"market_data_unavailable"}."""
        client, module = app_client
        # Use a ticker that doesn't exist in cache
        resp = client.post("/api/portfolio/trade", json={"ticker": "ZZZZ", "side": "buy", "quantity": 1})
        assert resp.status_code == 503
        data = resp.json()
        assert data["error"] == "market_data_unavailable"

    def test_concurrent_buys_serialize(self, app_client) -> None:
        """Concurrent buys: exactly one succeeds when cash is only enough for one.

        Calls execute_trade() directly from two threads using the test_db.py stagger
        pattern so BEGIN IMMEDIATE serialization is actually tested (TestClient
        serializes HTTP requests and cannot prove concurrency).
        """
        client, module = app_client

        # Seed cache with AAPL at $5000
        seed_cache(module, "AAPL", 5000.0)

        # Cash is $10000; each buy costs $5000 — exactly one should succeed
        results: list = []
        errors: list = []

        def buy_shares():
            try:
                # Import inside the test body — NOT at module scope — so
                # collection succeeds before Task 2 creates the module
                from app.services.portfolio import execute_trade  # noqa: PLC0415
                import app.db as db_mod  # noqa: PLC0415
                import app.main as main_mod  # noqa: PLC0415

                cache = main_mod.app.state.price_cache
                time.sleep(0.05)  # open contention window
                result = execute_trade(cache, "AAPL", "buy", 2.0)
                results.append(result)
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=buy_shares)
        t2 = threading.Thread(target=buy_shares)

        t1.start()
        time.sleep(0.005)  # tiny stagger so t1 gets BEGIN IMMEDIATE first
        t2.start()

        t1.join(timeout=10)
        t2.join(timeout=10)

        assert not errors, f"Thread errors: {errors}"

        # Exactly one buy should succeed (return a dict), one should fail (return a tuple)
        successes = [r for r in results if isinstance(r, dict)]
        failures = [r for r in results if isinstance(r, tuple)]

        assert len(successes) == 1, f"Expected 1 success, got {len(successes)}: {results}"
        assert len(failures) == 1, f"Expected 1 failure, got {len(failures)}: {results}"
        assert failures[0][0] == "insufficient_cash", f"Expected insufficient_cash, got: {failures[0]}"

        # Final cash must be non-negative: 10000 - (2 * 5000) = 0 if both succeeded (bad)
        # or 10000 - (2 * 5000) = 0 if only one succeeded at price seeded into cache
        portfolio = client.get("/api/portfolio").json()
        assert portfolio["cash"] >= 0, f"Cash went negative: {portfolio['cash']}"
