"""Tests for app.db.crud helpers."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from app.db import get_db
from app.db.crud import (
    add_to_watchlist,
    delete_position,
    get_chat_messages,
    get_portfolio_snapshots,
    get_position,
    get_positions,
    get_trades,
    get_user_profile,
    get_watchlist,
    insert_chat_message,
    insert_portfolio_snapshot,
    insert_trade,
    remove_from_watchlist,
    update_cash_balance,
    upsert_position,
)
from app.db.schema import DEFAULT_USER_ID

# ---------------------------------------------------------------------------
# users_profile
# ---------------------------------------------------------------------------


def test_get_user_profile_returns_seeded_user(conn: sqlite3.Connection) -> None:
    profile = get_user_profile(conn)
    assert profile["id"] == DEFAULT_USER_ID
    assert profile["cash_balance"] == pytest.approx(10000.0)
    assert "created_at" in profile


def test_get_user_profile_missing_raises(conn: sqlite3.Connection) -> None:
    with pytest.raises(KeyError):
        get_user_profile(conn, user_id="nobody")


def test_update_cash_balance(conn: sqlite3.Connection) -> None:
    profile = update_cash_balance(conn, DEFAULT_USER_ID, 5000.5)
    assert profile["cash_balance"] == pytest.approx(5000.5)

    refetched = get_user_profile(conn)
    assert refetched["cash_balance"] == pytest.approx(5000.5)


def test_update_cash_balance_missing_user_raises(conn: sqlite3.Connection) -> None:
    with pytest.raises(KeyError):
        update_cash_balance(conn, "nobody", 100.0)


# ---------------------------------------------------------------------------
# watchlist
# ---------------------------------------------------------------------------


def test_get_watchlist_returns_seed(conn: sqlite3.Connection) -> None:
    rows = get_watchlist(conn)
    tickers = {row["ticker"] for row in rows}
    assert {"AAPL", "GOOGL", "MSFT", "NFLX"} <= tickers
    assert len(rows) == 10


def test_add_to_watchlist(conn: sqlite3.Connection) -> None:
    row = add_to_watchlist(conn, DEFAULT_USER_ID, "PYPL")
    assert row["ticker"] == "PYPL"
    tickers = {entry["ticker"] for entry in get_watchlist(conn)}
    assert "PYPL" in tickers


def test_add_to_watchlist_duplicate_raises(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add_to_watchlist(conn, DEFAULT_USER_ID, "AAPL")


def test_remove_from_watchlist(conn: sqlite3.Connection) -> None:
    assert remove_from_watchlist(conn, DEFAULT_USER_ID, "AAPL") is True
    tickers = {entry["ticker"] for entry in get_watchlist(conn)}
    assert "AAPL" not in tickers


def test_remove_from_watchlist_missing_returns_false(conn: sqlite3.Connection) -> None:
    assert remove_from_watchlist(conn, DEFAULT_USER_ID, "NOTHERE") is False


# ---------------------------------------------------------------------------
# positions
# ---------------------------------------------------------------------------


def test_positions_empty_initially(conn: sqlite3.Connection) -> None:
    assert get_positions(conn) == []
    assert get_position(conn, DEFAULT_USER_ID, "AAPL") is None


def test_upsert_position_inserts(conn: sqlite3.Connection) -> None:
    row = upsert_position(conn, DEFAULT_USER_ID, "AAPL", quantity=10.0, avg_cost=190.0)
    assert row["quantity"] == pytest.approx(10.0)
    assert row["avg_cost"] == pytest.approx(190.0)

    fetched = get_position(conn, DEFAULT_USER_ID, "AAPL")
    assert fetched is not None
    assert fetched["quantity"] == pytest.approx(10.0)


def test_upsert_position_updates(conn: sqlite3.Connection) -> None:
    upsert_position(conn, DEFAULT_USER_ID, "AAPL", quantity=10.0, avg_cost=190.0)
    upsert_position(conn, DEFAULT_USER_ID, "AAPL", quantity=15.0, avg_cost=192.0)

    fetched = get_position(conn, DEFAULT_USER_ID, "AAPL")
    assert fetched is not None
    assert fetched["quantity"] == pytest.approx(15.0)
    assert fetched["avg_cost"] == pytest.approx(192.0)


def test_delete_position(conn: sqlite3.Connection) -> None:
    upsert_position(conn, DEFAULT_USER_ID, "AAPL", quantity=10.0, avg_cost=190.0)
    assert delete_position(conn, DEFAULT_USER_ID, "AAPL") is True
    assert get_position(conn, DEFAULT_USER_ID, "AAPL") is None


def test_delete_position_missing_returns_false(conn: sqlite3.Connection) -> None:
    assert delete_position(conn, DEFAULT_USER_ID, "AAPL") is False


# ---------------------------------------------------------------------------
# trades
# ---------------------------------------------------------------------------


def test_insert_trade_round_trip(conn: sqlite3.Connection) -> None:
    trade = insert_trade(
        conn, DEFAULT_USER_ID, "AAPL", side="buy", quantity=5.0, price=190.25
    )
    assert trade["side"] == "buy"
    assert trade["quantity"] == pytest.approx(5.0)
    assert trade["price"] == pytest.approx(190.25)

    rows = get_trades(conn)
    assert len(rows) == 1
    assert rows[0]["ticker"] == "AAPL"


def test_get_trades_newest_first(conn: sqlite3.Connection) -> None:
    insert_trade(conn, DEFAULT_USER_ID, "AAPL", "buy", 5.0, 190.0)
    insert_trade(conn, DEFAULT_USER_ID, "GOOGL", "buy", 2.0, 175.0)
    insert_trade(conn, DEFAULT_USER_ID, "AAPL", "sell", 1.0, 195.0)

    rows = get_trades(conn)
    assert len(rows) == 3
    timestamps = [row["executed_at"] for row in rows]
    assert timestamps == sorted(timestamps, reverse=True)


# ---------------------------------------------------------------------------
# portfolio_snapshots
# ---------------------------------------------------------------------------


def test_insert_portfolio_snapshot(conn: sqlite3.Connection) -> None:
    snap = insert_portfolio_snapshot(conn, DEFAULT_USER_ID, 10250.5)
    assert snap["total_value"] == pytest.approx(10250.5)

    rows = get_portfolio_snapshots(conn)
    assert len(rows) == 1
    assert rows[0]["total_value"] == pytest.approx(10250.5)


def test_portfolio_snapshots_oldest_first(conn: sqlite3.Connection) -> None:
    insert_portfolio_snapshot(conn, DEFAULT_USER_ID, 10000.0)
    insert_portfolio_snapshot(conn, DEFAULT_USER_ID, 10100.0)
    insert_portfolio_snapshot(conn, DEFAULT_USER_ID, 10050.0)

    rows = get_portfolio_snapshots(conn)
    assert len(rows) == 3
    timestamps = [row["recorded_at"] for row in rows]
    assert timestamps == sorted(timestamps)


# ---------------------------------------------------------------------------
# chat_messages
# ---------------------------------------------------------------------------


def test_insert_chat_message_user(conn: sqlite3.Connection) -> None:
    msg = insert_chat_message(conn, DEFAULT_USER_ID, "user", "Buy 5 AAPL")
    assert msg["role"] == "user"
    assert msg["actions"] is None

    rows = get_chat_messages(conn)
    assert len(rows) == 1
    assert rows[0]["content"] == "Buy 5 AAPL"
    assert rows[0]["actions"] is None


def test_insert_chat_message_assistant_with_actions(conn: sqlite3.Connection) -> None:
    actions = {"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 5}]}
    msg = insert_chat_message(
        conn, DEFAULT_USER_ID, "assistant", "Bought 5 AAPL.", actions=actions
    )
    assert msg["actions"] == actions

    rows = get_chat_messages(conn)
    assert len(rows) == 1
    assert rows[0]["actions"] == actions


def test_get_chat_messages_returns_oldest_first_within_limit(
    conn: sqlite3.Connection,
) -> None:
    for i in range(25):
        insert_chat_message(conn, DEFAULT_USER_ID, "user", f"msg-{i:02d}")

    rows = get_chat_messages(conn, limit=20)
    assert len(rows) == 20
    contents = [row["content"] for row in rows]

    assert contents[-1] == "msg-24"
    assert contents[0] == "msg-05"
    timestamps = [row["created_at"] for row in rows]
    assert timestamps == sorted(timestamps)


# ---------------------------------------------------------------------------
# trade transaction isolation
# ---------------------------------------------------------------------------


def test_begin_immediate_serializes_writers(db_path: Path) -> None:
    """Two writers that both BEGIN IMMEDIATE must not both modify cash from
    the same starting balance.

    The second writer is forced to wait for the first to release its lock,
    so when the second writer re-reads cash inside its transaction it sees
    the first writer's committed value. This is exactly the guarantee the
    trade endpoint relies on to prevent double-spend.
    """
    started = threading.Event()
    proceed = threading.Event()
    second_observed: dict[str, float] = {}

    def first_writer() -> None:
        with get_db(db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            profile = get_user_profile(conn)
            started.set()
            proceed.wait(timeout=2)
            update_cash_balance(conn, DEFAULT_USER_ID, profile["cash_balance"] - 1000.0)

    def second_writer() -> None:
        started.wait(timeout=2)
        with get_db(db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            profile = get_user_profile(conn)
            second_observed["cash_balance"] = profile["cash_balance"]
            update_cash_balance(conn, DEFAULT_USER_ID, profile["cash_balance"] - 500.0)

    t1 = threading.Thread(target=first_writer)
    t2 = threading.Thread(target=second_writer)
    t1.start()
    t2.start()

    proceed.set()
    t1.join(timeout=5)
    t2.join(timeout=5)
    assert not t1.is_alive()
    assert not t2.is_alive()

    assert second_observed["cash_balance"] == pytest.approx(9000.0)

    with get_db(db_path) as conn:
        final = get_user_profile(conn)
    assert final["cash_balance"] == pytest.approx(8500.0)


def test_rollback_on_exception(db_path: Path) -> None:
    """get_db should roll back any work when the block raises."""
    with pytest.raises(RuntimeError):
        with get_db(db_path) as conn:
            update_cash_balance(conn, DEFAULT_USER_ID, 1.0)
            raise RuntimeError("boom")

    with get_db(db_path) as conn:
        profile = get_user_profile(conn)
    assert profile["cash_balance"] == pytest.approx(10000.0)
