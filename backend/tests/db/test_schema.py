"""Tests for app.db.schema — initialization, seeding, idempotency."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.db import get_db, init_db
from app.db.schema import (
    DEFAULT_CASH_BALANCE,
    DEFAULT_USER_ID,
    DEFAULT_WATCHLIST,
)

EXPECTED_TABLES = {
    "users_profile",
    "watchlist",
    "positions",
    "trades",
    "portfolio_snapshots",
    "chat_messages",
}


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row[0] for row in rows}


def test_init_db_creates_file(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "missing" / "finally.db"
    assert not db_path.exists()
    init_db(db_path)
    assert db_path.exists()


def test_init_db_creates_all_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "finally.db"
    init_db(db_path)
    with get_db(db_path) as conn:
        assert _table_names(conn) >= EXPECTED_TABLES


def test_init_db_seeds_default_user(tmp_path: Path) -> None:
    db_path = tmp_path / "finally.db"
    init_db(db_path)
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT id, cash_balance FROM users_profile WHERE id = ?",
            (DEFAULT_USER_ID,),
        ).fetchone()
    assert row is not None
    assert row["id"] == DEFAULT_USER_ID
    assert row["cash_balance"] == pytest.approx(DEFAULT_CASH_BALANCE)


def test_init_db_seeds_default_watchlist(tmp_path: Path) -> None:
    db_path = tmp_path / "finally.db"
    init_db(db_path)
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT ticker FROM watchlist WHERE user_id = ?",
            (DEFAULT_USER_ID,),
        ).fetchall()
    seeded = {row["ticker"] for row in rows}
    assert seeded == set(DEFAULT_WATCHLIST)


def test_init_db_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "finally.db"
    init_db(db_path)
    init_db(db_path)
    init_db(db_path)

    with get_db(db_path) as conn:
        user_count = conn.execute("SELECT COUNT(*) FROM users_profile").fetchone()[0]
        watchlist_count = conn.execute(
            "SELECT COUNT(*) FROM watchlist WHERE user_id = ?", (DEFAULT_USER_ID,)
        ).fetchone()[0]

    assert user_count == 1
    assert watchlist_count == len(DEFAULT_WATCHLIST)


def test_init_db_preserves_existing_data(tmp_path: Path) -> None:
    db_path = tmp_path / "finally.db"
    init_db(db_path)

    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
            (4242.0, DEFAULT_USER_ID),
        )

    init_db(db_path)

    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = ?", (DEFAULT_USER_ID,)
        ).fetchone()
    assert row["cash_balance"] == pytest.approx(4242.0)


def test_watchlist_unique_constraint(tmp_path: Path) -> None:
    db_path = tmp_path / "finally.db"
    init_db(db_path)
    with get_db(db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) "
                "VALUES (?, ?, ?, ?)",
                ("x", DEFAULT_USER_ID, "AAPL", "2026-01-01T00:00:00Z"),
            )


def test_positions_unique_constraint(tmp_path: Path) -> None:
    db_path = tmp_path / "finally.db"
    init_db(db_path)
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("p1", DEFAULT_USER_ID, "AAPL", 10.0, 190.0, "2026-01-01T00:00:00Z"),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("p2", DEFAULT_USER_ID, "AAPL", 5.0, 195.0, "2026-01-01T00:00:01Z"),
            )


def test_wal_journal_mode_active(tmp_path: Path) -> None:
    db_path = tmp_path / "finally.db"
    init_db(db_path)
    with get_db(db_path) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
