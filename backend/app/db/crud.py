"""CRUD helpers for FinAlly database tables.

All functions take an open `sqlite3.Connection` and operate on the row
representation defined by `app.db.schema`. Functions that write do not call
`commit()` — the surrounding `get_db()` context manager (or a caller's
explicit transaction) owns commit semantics. Reads return plain `dict`s so
results are easy to JSON-serialize.

Trade execution pattern
-----------------------
The trade endpoint MUST wrap its work in a `BEGIN IMMEDIATE` transaction:

    with get_db(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        profile = get_user_profile(conn, user_id)
        position = get_position(conn, user_id, ticker)
        # ... validate cash / shares ...
        insert_trade(conn, ...)
        update_cash_balance(conn, ...)
        upsert_position(conn, ...)

`BEGIN IMMEDIATE` acquires a write lock up front, so two concurrent buys
cannot both read the same `cash_balance` and double-spend it.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

DEFAULT_USER_ID = "default"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


# ---------------------------------------------------------------------------
# users_profile
# ---------------------------------------------------------------------------


def get_user_profile(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
    """Return the user profile row. Raises KeyError if the user does not exist."""
    row = conn.execute(
        "SELECT id, cash_balance, created_at FROM users_profile WHERE id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"user_profile not found: {user_id!r}")
    return _row_to_dict(row)  # type: ignore[return-value]


def update_cash_balance(
    conn: sqlite3.Connection, user_id: str, new_balance: float
) -> dict[str, Any]:
    """Set the cash balance to ``new_balance`` and return the updated profile."""
    cursor = conn.execute(
        "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
        (float(new_balance), user_id),
    )
    if cursor.rowcount == 0:
        raise KeyError(f"user_profile not found: {user_id!r}")
    return get_user_profile(conn, user_id)


# ---------------------------------------------------------------------------
# watchlist
# ---------------------------------------------------------------------------


def get_watchlist(
    conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID
) -> list[dict[str, Any]]:
    """Return the user's watchlist ordered by `added_at` ascending."""
    rows = conn.execute(
        "SELECT id, user_id, ticker, added_at "
        "FROM watchlist WHERE user_id = ? ORDER BY added_at ASC, ticker ASC",
        (user_id,),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]  # type: ignore[misc]


def add_to_watchlist(conn: sqlite3.Connection, user_id: str, ticker: str) -> dict[str, Any]:
    """Add a ticker to the watchlist.

    Raises ``sqlite3.IntegrityError`` if the ticker is already present.
    Format validation, watchlist-size caps, and unknown-symbol checks all
    happen one layer up in the API; this function only enforces the DB
    UNIQUE constraint.
    """
    row_id = str(uuid.uuid4())
    added_at = _utc_now_iso()
    conn.execute(
        "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
        (row_id, user_id, ticker, added_at),
    )
    return {"id": row_id, "user_id": user_id, "ticker": ticker, "added_at": added_at}


def remove_from_watchlist(conn: sqlite3.Connection, user_id: str, ticker: str) -> bool:
    """Remove a ticker from the watchlist. Returns True if a row was deleted."""
    cursor = conn.execute(
        "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    )
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# positions
# ---------------------------------------------------------------------------


def get_positions(
    conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID
) -> list[dict[str, Any]]:
    """Return all positions for the user, ordered by ticker."""
    rows = conn.execute(
        "SELECT id, user_id, ticker, quantity, avg_cost, updated_at "
        "FROM positions WHERE user_id = ? ORDER BY ticker ASC",
        (user_id,),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]  # type: ignore[misc]


def get_position(
    conn: sqlite3.Connection, user_id: str, ticker: str
) -> dict[str, Any] | None:
    """Return a single position row or None."""
    row = conn.execute(
        "SELECT id, user_id, ticker, quantity, avg_cost, updated_at "
        "FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ).fetchone()
    return _row_to_dict(row)


def upsert_position(
    conn: sqlite3.Connection,
    user_id: str,
    ticker: str,
    quantity: float,
    avg_cost: float,
) -> dict[str, Any]:
    """Insert or update a position row. Returns the resulting row.

    Note: this function does not interpret zero-quantity specially. Callers
    that want zero-quantity positions removed should invoke
    :func:`delete_position` instead.
    """
    existing = get_position(conn, user_id, ticker)
    updated_at = _utc_now_iso()
    if existing is None:
        row_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (row_id, user_id, ticker, float(quantity), float(avg_cost), updated_at),
        )
    else:
        conn.execute(
            "UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ? "
            "WHERE user_id = ? AND ticker = ?",
            (float(quantity), float(avg_cost), updated_at, user_id, ticker),
        )
    return get_position(conn, user_id, ticker)  # type: ignore[return-value]


def delete_position(conn: sqlite3.Connection, user_id: str, ticker: str) -> bool:
    """Delete a position row. Returns True if a row was deleted."""
    cursor = conn.execute(
        "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    )
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# trades
# ---------------------------------------------------------------------------


def insert_trade(
    conn: sqlite3.Connection,
    user_id: str,
    ticker: str,
    side: str,
    quantity: float,
    price: float,
) -> dict[str, Any]:
    """Append a trade row. Does not touch cash or positions — caller's job."""
    row_id = str(uuid.uuid4())
    executed_at = _utc_now_iso()
    conn.execute(
        "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (row_id, user_id, ticker, side, float(quantity), float(price), executed_at),
    )
    return {
        "id": row_id,
        "user_id": user_id,
        "ticker": ticker,
        "side": side,
        "quantity": float(quantity),
        "price": float(price),
        "executed_at": executed_at,
    }


def get_trades(
    conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID
) -> list[dict[str, Any]]:
    """Return all trades for the user, newest first."""
    rows = conn.execute(
        "SELECT id, user_id, ticker, side, quantity, price, executed_at "
        "FROM trades WHERE user_id = ? ORDER BY executed_at DESC, rowid DESC",
        (user_id,),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]  # type: ignore[misc]


# ---------------------------------------------------------------------------
# portfolio_snapshots
# ---------------------------------------------------------------------------


def insert_portfolio_snapshot(
    conn: sqlite3.Connection, user_id: str, total_value: float
) -> dict[str, Any]:
    """Append a portfolio-value snapshot."""
    row_id = str(uuid.uuid4())
    recorded_at = _utc_now_iso()
    conn.execute(
        "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
        "VALUES (?, ?, ?, ?)",
        (row_id, user_id, float(total_value), recorded_at),
    )
    return {
        "id": row_id,
        "user_id": user_id,
        "total_value": float(total_value),
        "recorded_at": recorded_at,
    }


def get_portfolio_snapshots(
    conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID
) -> list[dict[str, Any]]:
    """Return all snapshots for the user, oldest first (suitable for plotting)."""
    rows = conn.execute(
        "SELECT id, user_id, total_value, recorded_at "
        "FROM portfolio_snapshots WHERE user_id = ? ORDER BY recorded_at ASC, rowid ASC",
        (user_id,),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]  # type: ignore[misc]


# ---------------------------------------------------------------------------
# chat_messages
# ---------------------------------------------------------------------------


def insert_chat_message(
    conn: sqlite3.Connection,
    user_id: str,
    role: str,
    content: str,
    actions: dict[str, Any] | list[Any] | None = None,
) -> dict[str, Any]:
    """Append a chat message. ``actions`` is JSON-serialized when present."""
    row_id = str(uuid.uuid4())
    created_at = _utc_now_iso()
    actions_json = json.dumps(actions) if actions is not None else None
    conn.execute(
        "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (row_id, user_id, role, content, actions_json, created_at),
    )
    return {
        "id": row_id,
        "user_id": user_id,
        "role": role,
        "content": content,
        "actions": actions,
        "created_at": created_at,
    }


def get_chat_messages(
    conn: sqlite3.Connection,
    user_id: str = DEFAULT_USER_ID,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return the last ``limit`` messages ordered oldest → newest.

    The LLM context window expects messages in chronological order, so we
    select the most recent ``limit`` by insertion order and reverse them
    before returning. We tiebreak on the implicit `rowid` so messages
    inserted within the same second still order deterministically by the
    sequence they were written.
    """
    rows = conn.execute(
        "SELECT id, user_id, role, content, actions, created_at "
        "FROM chat_messages WHERE user_id = ? "
        "ORDER BY created_at DESC, rowid DESC LIMIT ?",
        (user_id, int(limit)),
    ).fetchall()
    messages: list[dict[str, Any]] = []
    for row in reversed(rows):
        record = _row_to_dict(row)
        assert record is not None
        if record["actions"] is not None:
            record["actions"] = json.loads(record["actions"])
        messages.append(record)
    return messages
