"""Portfolio service — pure-Python business logic for portfolio valuation and trade execution.

Callable by HTTP handlers (Phase 2) and the LLM chat layer (Phase 3).
"""

from __future__ import annotations

import logging
import uuid

from app.db import DEFAULT_USER_ID, _now_iso, get_db, get_db_immediate
from app.market import PriceCache

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _upsert_position(conn, ticker: str, quantity: float, avg_cost: float) -> None:
    """INSERT OR REPLACE the position row for (user_id, ticker).

    Uses a new UUID for 'id' on every upsert — SQLite will replace the existing
    row due to the UNIQUE(user_id, ticker) constraint.
    """
    conn.execute(
        "INSERT OR REPLACE INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), DEFAULT_USER_ID, ticker, quantity, avg_cost, _now_iso()),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_portfolio_view(price_cache: PriceCache) -> dict:
    """Return cash, positions with live P&L, and total portfolio value.

    Live prices come from the in-memory price_cache (never from the DB).
    Falls back to avg_cost for valuation if no cache price exists yet.
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id=?", (DEFAULT_USER_ID,)
        ).fetchone()
        cash = row["cash_balance"] if row else 0.0

        rows = conn.execute(
            "SELECT ticker, quantity, avg_cost FROM positions "
            "WHERE user_id=? AND quantity > 0",
            (DEFAULT_USER_ID,),
        ).fetchall()

    positions = []
    total = cash
    for r in rows:
        ticker = r["ticker"]
        price = price_cache.get_price(ticker)
        cur = price if price is not None else r["avg_cost"]  # fallback when cache is cold
        market_value = r["quantity"] * cur
        cost_basis = r["quantity"] * r["avg_cost"]
        unrealized_pnl = market_value - cost_basis
        pnl_pct = (unrealized_pnl / cost_basis * 100) if cost_basis else 0.0
        positions.append(
            {
                "ticker": ticker,
                "quantity": r["quantity"],
                "avg_cost": r["avg_cost"],
                "current_price": cur,
                "unrealized_pnl": unrealized_pnl,
                "pnl_pct": pnl_pct,
            }
        )
        total += market_value

    return {"cash": cash, "positions": positions, "total_value": total}


def execute_trade(
    price_cache: PriceCache, ticker: str, side: str, quantity
) -> dict | tuple[str, str, int]:
    """Execute a market order (buy or sell).

    Pre-transaction cheap validation is done before acquiring the DB write lock.
    All cash/position reads, validation, and writes happen inside a single
    BEGIN IMMEDIATE transaction to prevent concurrent double-spend.

    Returns a success dict on success, or a (error_code, message, status_code)
    tuple on validation failure.
    """
    # --- pre-transaction cheap validation (no DB needed) ---
    if side not in ("buy", "sell"):
        return ("invalid_side", "side must be 'buy' or 'sell'", 400)

    if not isinstance(quantity, (int, float)) or isinstance(quantity, bool) or quantity <= 0:
        return ("invalid_quantity", "quantity must be positive", 400)

    price = price_cache.get_price(ticker)
    if price is None:
        return ("market_data_unavailable", f"No price for {ticker}", 503)

    # --- BEGIN IMMEDIATE: serializes concurrent writers ---
    with get_db_immediate() as conn:
        # Re-read cash inside the transaction (prevent TOCTOU race)
        cash_row = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id=?", (DEFAULT_USER_ID,)
        ).fetchone()
        cash = cash_row["cash_balance"] if cash_row else 0.0

        pos_row = conn.execute(
            "SELECT quantity, avg_cost FROM positions WHERE user_id=? AND ticker=?",
            (DEFAULT_USER_ID, ticker),
        ).fetchone()
        held_qty = pos_row["quantity"] if pos_row else 0.0
        held_cost = pos_row["avg_cost"] if pos_row else 0.0

        if side == "buy":
            cost = quantity * price
            if cost > cash:
                return (
                    "insufficient_cash",
                    f"Need ${cost:.2f}, have ${cash:.2f}",
                    400,
                )
            new_qty = held_qty + quantity
            new_avg = (held_qty * held_cost + quantity * price) / new_qty  # weighted avg
            conn.execute(
                "UPDATE users_profile SET cash_balance=? WHERE id=?",
                (cash - cost, DEFAULT_USER_ID),
            )
            _upsert_position(conn, ticker, new_qty, new_avg)
            new_cash = cash - cost

        else:  # sell
            if quantity > held_qty:
                return (
                    "insufficient_shares",
                    f"Have {held_qty}, tried to sell {quantity}",
                    400,
                )
            proceeds = quantity * price
            new_qty = held_qty - quantity
            conn.execute(
                "UPDATE users_profile SET cash_balance=? WHERE id=?",
                (cash + proceeds, DEFAULT_USER_ID),
            )
            if new_qty <= 0:
                # Delete the position row on a full sell
                conn.execute(
                    "DELETE FROM positions WHERE user_id=? AND ticker=?",
                    (DEFAULT_USER_ID, ticker),
                )
                new_avg = held_cost  # avg_cost MUST NOT change on sell
            else:
                _upsert_position(conn, ticker, new_qty, held_cost)  # avg_cost unchanged
                new_avg = held_cost
            new_cash = cash + proceeds

        # Record the trade (append-only log)
        trade_id = str(uuid.uuid4())
        executed_at = _now_iso()
        conn.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (trade_id, DEFAULT_USER_ID, ticker, side, quantity, price, executed_at),
        )
    # SNAP-02: snapshot recorded AFTER commit (in plan 02-03); not inside the transaction

    return {
        "trade": {
            "id": trade_id,
            "ticker": ticker,
            "side": side,
            "quantity": quantity,
            "price": price,
            "executed_at": executed_at,
        },
        "cash_balance": new_cash,
        "position": {
            "ticker": ticker,
            "quantity": new_qty,
            "avg_cost": new_avg,
        },
    }
