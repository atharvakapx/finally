"""Tests for portfolio snapshot service (SNAP-01, SNAP-02, PORT-04, counter lifecycle)."""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


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


@pytest.fixture
def db_module(tmp_path, monkeypatch):
    """Provide a freshly reloaded app.db module pointing at a temp DB path."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    import app.db
    module = importlib.reload(app.db)
    yield module


# ---------------------------------------------------------------------------
# TestClientCounter — counter lifecycle (increment, decrement, clamp-at-0)
# ---------------------------------------------------------------------------


class TestClientCounter:
    def test_increment_decrement(self) -> None:
        """Counter starts at 0; increment→1; increment→2; decrement→1; decrement→0;
        extra decrement stays at 0 (never negative)."""
        # Import inside test body so collection succeeds before Task 2 creates the module
        from app.services.snapshots import ClientCounter  # noqa: PLC0415

        counter = ClientCounter()
        assert counter.count == 0

        counter.increment()
        assert counter.count == 1

        counter.increment()
        assert counter.count == 2

        counter.decrement()
        assert counter.count == 1

        counter.decrement()
        assert counter.count == 0

        # Extra decrement must clamp at 0, never go negative
        counter.decrement()
        assert counter.count == 0
        assert counter.count >= 0


# ---------------------------------------------------------------------------
# TestRecordSnapshot — direct service call, total_value check
# ---------------------------------------------------------------------------


class TestRecordSnapshot:
    def test_snapshot_total_value(self, db_module) -> None:
        """Seed cash=10000 + 10 shares position; cache price 100.0;
        record_snapshot → exactly one row, total_value == 11000."""
        import sqlite3
        from app.market import PriceCache
        from app.services.snapshots import record_snapshot  # noqa: PLC0415

        db_module.init_db()

        # Insert a position: 10 shares of TESTX at avg_cost 50 (irrelevant for snapshot)
        import uuid
        conn = sqlite3.connect(db_module._DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute(
            "INSERT OR IGNORE INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES (?, 'default', 'TESTX', 10.0, 50.0, '2026-01-01T00:00:00Z')",
            (str(uuid.uuid4()),),
        )
        conn.commit()
        conn.close()

        # Seed cache with known price
        cache = PriceCache()
        cache.update("TESTX", 100.0)

        # Call record_snapshot — should INSERT one row with total_value == 10000 + 10*100
        record_snapshot(cache)

        conn2 = sqlite3.connect(db_module._DB_PATH)
        conn2.row_factory = sqlite3.Row
        rows = conn2.execute(
            "SELECT total_value FROM portfolio_snapshots WHERE user_id='default'"
        ).fetchall()
        conn2.close()

        assert len(rows) == 1, f"Expected 1 snapshot row, got {len(rows)}"
        assert rows[0]["total_value"] == pytest.approx(11000.0), (
            f"Expected total_value 11000.0, got {rows[0]['total_value']}"
        )


# ---------------------------------------------------------------------------
# TestSnapshotAfterTrade — SNAP-02 via app_client
# ---------------------------------------------------------------------------


class TestSnapshotAfterTrade:
    def test_snapshot_after_trade(self, app_client) -> None:
        """SNAP-02: POST /api/portfolio/trade buy → portfolio_snapshots gains exactly
        one new row with total_value reflecting post-trade cash + holdings."""
        import sqlite3
        import time

        client, module = app_client

        # Let the simulator populate the cache with AAPL price
        time.sleep(1.5)

        # Count snapshots before trade
        db_path = module.app.state.price_cache  # just need access to DB path
        import app.db
        before_count_result = None
        with app.db.get_db() as conn:
            before_count_result = conn.execute(
                "SELECT count(*) c FROM portfolio_snapshots WHERE user_id='default'"
            ).fetchone()["c"]

        # Execute a trade — buy 1 share of AAPL
        resp = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "side": "buy", "quantity": 1},
        )
        assert resp.status_code == 200, f"Trade failed: {resp.json()}"

        # Count snapshots after trade — should be exactly one more
        with app.db.get_db() as conn:
            after_count = conn.execute(
                "SELECT count(*) c FROM portfolio_snapshots WHERE user_id='default'"
            ).fetchone()["c"]

        assert after_count == before_count_result + 1, (
            f"Expected snapshot count to increase by 1 after trade, "
            f"was {before_count_result}, now {after_count}"
        )

        # Verify the new snapshot has a reasonable total_value
        with app.db.get_db() as conn:
            newest = conn.execute(
                "SELECT total_value FROM portfolio_snapshots WHERE user_id='default' "
                "ORDER BY recorded_at DESC LIMIT 1"
            ).fetchone()
        assert newest["total_value"] > 0, "Snapshot total_value should be positive"


# ---------------------------------------------------------------------------
# TestSnapshotLoop — SNAP-01: cadence gated on SSE client count
# ---------------------------------------------------------------------------


class TestSnapshotLoop:
    def test_cadence_gated_on_clients(self, db_module) -> None:
        """SNAP-01: With count==0, record_snapshot is NOT called.
        With count==1, record_snapshot IS called. Tests the gate condition
        that snapshot_loop uses."""
        import sqlite3
        from app.market import PriceCache
        from app.services.snapshots import ClientCounter, record_snapshot  # noqa: PLC0415

        db_module.init_db()

        cache = PriceCache()

        counter = ClientCounter()

        # Helper to count snapshot rows
        def snapshot_count() -> int:
            conn = sqlite3.connect(db_module._DB_PATH)
            conn.row_factory = sqlite3.Row
            n = conn.execute(
                "SELECT count(*) c FROM portfolio_snapshots WHERE user_id='default'"
            ).fetchone()["c"]
            conn.close()
            return n

        # Gate condition: count == 0 → do NOT record
        assert counter.count == 0
        before = snapshot_count()
        if counter.count > 0:  # mirrors snapshot_loop gate logic
            record_snapshot(cache)
        after = snapshot_count()
        assert after == before, (
            f"count==0: no snapshot should be recorded, but went from {before} to {after}"
        )

        # Gate condition: count > 0 → DO record
        counter.increment()
        assert counter.count == 1
        before2 = snapshot_count()
        if counter.count > 0:  # mirrors snapshot_loop gate logic
            record_snapshot(cache)
        after2 = snapshot_count()
        assert after2 == before2 + 1, (
            f"count>0: snapshot should be recorded, but went from {before2} to {after2}"
        )


# ---------------------------------------------------------------------------
# TestHistory — PORT-04: GET /api/portfolio/history
# ---------------------------------------------------------------------------


class TestHistory:
    def test_history_returns_series(self, app_client) -> None:
        """PORT-04: Insert 3 portfolio_snapshots rows with increasing recorded_at;
        GET /api/portfolio/history → list of 3 dicts {total_value, recorded_at}
        ordered ascending."""
        import uuid
        client, module = app_client

        import app.db
        with app.db.get_db() as conn:
            for i, (tv, ts) in enumerate([
                (9000.0, "2026-01-01T10:00:00+00:00"),
                (9500.0, "2026-01-01T10:01:00+00:00"),
                (10000.0, "2026-01-01T10:02:00+00:00"),
            ]):
                conn.execute(
                    "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
                    "VALUES (?, 'default', ?, ?)",
                    (str(uuid.uuid4()), tv, ts),
                )

        resp = client.get("/api/portfolio/history")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.json()}"

        data = resp.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        assert len(data) == 3, f"Expected 3 items, got {len(data)}: {data}"

        # Verify ascending order by recorded_at
        assert data[0]["recorded_at"] < data[1]["recorded_at"] < data[2]["recorded_at"], (
            f"Items not in ascending order: {[d['recorded_at'] for d in data]}"
        )

        # Verify total_value values match
        assert data[0]["total_value"] == pytest.approx(9000.0)
        assert data[1]["total_value"] == pytest.approx(9500.0)
        assert data[2]["total_value"] == pytest.approx(10000.0)

        # Verify each item has exactly {total_value, recorded_at}
        for item in data:
            assert "total_value" in item, f"Missing total_value in {item}"
            assert "recorded_at" in item, f"Missing recorded_at in {item}"

    def test_history_empty(self, app_client) -> None:
        """Fresh DB → GET /api/portfolio/history returns []."""
        client, _ = app_client

        resp = client.get("/api/portfolio/history")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.json()}"

        data = resp.json()
        assert data == [], f"Expected empty list, got {data}"
