"""Tests for backend/app/db.py — schema, seed, idempotence, transaction helpers."""

from __future__ import annotations

import importlib
import os
import sqlite3
import threading
import time

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_module(tmp_path, monkeypatch):
    """Provide a freshly reloaded app.db module pointing at a temp DB path.

    Each test gets a clean SQLite file so tests never interfere with each
    other or write to /app/db/finally.db.
    """
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    import app.db

    module = importlib.reload(app.db)
    yield module


# ---------------------------------------------------------------------------
# TestInitDb
# ---------------------------------------------------------------------------


class TestInitDb:
    def test_init_db_creates_all_six_tables(self, db_module):
        """init_db() must create exactly the 6 expected tables."""
        db_module.init_db()

        conn = sqlite3.connect(db_module._DB_PATH)
        try:
            tables = sorted(
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            )
        finally:
            conn.close()

        assert tables == [
            "chat_messages",
            "portfolio_snapshots",
            "positions",
            "trades",
            "users_profile",
            "watchlist",
        ]

    def test_init_db_seeds_default_user(self, db_module):
        """init_db() must create exactly one user profile row with $10k."""
        db_module.init_db()

        conn = sqlite3.connect(db_module._DB_PATH)
        try:
            rows = conn.execute("SELECT id, cash_balance FROM users_profile").fetchall()
        finally:
            conn.close()

        assert len(rows) == 1
        assert rows[0][0] == "default"
        assert rows[0][1] == 10000.0

    def test_init_db_seeds_ten_default_tickers(self, db_module):
        """init_db() must seed all 10 default tickers into the watchlist."""
        db_module.init_db()

        conn = sqlite3.connect(db_module._DB_PATH)
        try:
            rows = conn.execute(
                "SELECT ticker FROM watchlist WHERE user_id='default'"
            ).fetchall()
        finally:
            conn.close()

        seeded = {row[0] for row in rows}
        assert len(rows) == 10
        assert seeded == set(db_module.DEFAULT_TICKERS)

    def test_init_db_is_idempotent(self, db_module):
        """Calling init_db() twice must not produce duplicate rows."""
        db_module.init_db()
        db_module.init_db()  # second call — must be a no-op for existing rows

        conn = sqlite3.connect(db_module._DB_PATH)
        try:
            user_count = conn.execute(
                "SELECT count(*) FROM users_profile"
            ).fetchone()[0]
            ticker_count = conn.execute(
                "SELECT count(*) FROM watchlist WHERE user_id='default'"
            ).fetchone()[0]
        finally:
            conn.close()

        assert user_count == 1
        assert ticker_count == 10

    def test_init_db_creates_parent_directory(self, tmp_path, monkeypatch):
        """init_db() must create the parent directory if it does not exist."""
        nested_path = str(tmp_path / "nested" / "subdir" / "test.db")
        monkeypatch.setenv("DB_PATH", nested_path)
        import app.db

        module = importlib.reload(app.db)

        module.init_db()

        assert os.path.isfile(nested_path)


# ---------------------------------------------------------------------------
# TestGetDb
# ---------------------------------------------------------------------------


class TestGetDb:
    def test_get_db_commits_on_success(self, db_module):
        """Changes made inside get_db() block must persist after the block exits."""
        db_module.init_db()

        with db_module.get_db() as conn:
            conn.execute(
                "UPDATE users_profile SET cash_balance=9999 WHERE id='default'"
            )

        # Read back using a raw connection to confirm the commit
        verify_conn = sqlite3.connect(db_module._DB_PATH)
        try:
            row = verify_conn.execute(
                "SELECT cash_balance FROM users_profile WHERE id='default'"
            ).fetchone()
        finally:
            verify_conn.close()

        assert row[0] == 9999.0

    def test_get_db_rolls_back_on_exception(self, db_module):
        """An exception inside get_db() must roll back the transaction."""
        db_module.init_db()

        try:
            with db_module.get_db() as conn:
                conn.execute(
                    "UPDATE users_profile SET cash_balance=42 WHERE id='default'"
                )
                raise RuntimeError("boom")
        except RuntimeError:
            pass

        # The update must have been rolled back
        verify_conn = sqlite3.connect(db_module._DB_PATH)
        try:
            row = verify_conn.execute(
                "SELECT cash_balance FROM users_profile WHERE id='default'"
            ).fetchone()
        finally:
            verify_conn.close()

        assert row[0] == 10000.0


# ---------------------------------------------------------------------------
# TestGetDbImmediate
# ---------------------------------------------------------------------------


class TestGetDbImmediate:
    def test_get_db_immediate_issues_begin_immediate(self, db_module):
        """Connection yielded by get_db_immediate() must be inside a transaction."""
        db_module.init_db()

        with db_module.get_db_immediate() as conn:
            # sqlite3.Connection.in_transaction is True while a transaction is open
            assert conn.in_transaction is True

    def test_get_db_immediate_serializes_writers(self, db_module):
        """Two concurrent get_db_immediate() writers must serialize, not lose updates."""
        db_module.init_db()

        errors: list[Exception] = []

        def increment_balance() -> None:
            try:
                with db_module.get_db_immediate() as conn:
                    # Simulate work to increase contention window
                    time.sleep(0.05)
                    conn.execute(
                        "UPDATE users_profile "
                        "SET cash_balance = cash_balance + 1 "
                        "WHERE id = 'default'"
                    )
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=increment_balance)
        t2 = threading.Thread(target=increment_balance)

        # Start both threads nearly simultaneously so they contend for the lock
        t1.start()
        # Tiny sleep ensures t1 has issued BEGIN IMMEDIATE before t2 tries
        time.sleep(0.005)
        t2.start()

        t1.join(timeout=5)
        t2.join(timeout=5)

        assert not errors, f"Thread errors: {errors}"

        verify_conn = sqlite3.connect(db_module._DB_PATH)
        try:
            row = verify_conn.execute(
                "SELECT cash_balance FROM users_profile WHERE id='default'"
            ).fetchone()
        finally:
            verify_conn.close()

        # Both increments must have been applied — no lost update
        assert row[0] == 10002.0
