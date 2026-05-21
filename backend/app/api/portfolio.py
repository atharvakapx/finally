"""Portfolio endpoints — positions, trade execution, history."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app import errors
from app.db import get_db
from app.db.crud import (
    delete_position,
    get_portfolio_snapshots,
    get_position,
    get_positions,
    get_user_profile,
    get_watchlist,
    insert_portfolio_snapshot,
    insert_trade,
    update_cash_balance,
    upsert_position,
)
from app.state import DEFAULT_USER_ID, AppState, get_state
from app.validation import is_valid_ticker, normalize_ticker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

VALID_SIDES = {"buy", "sell"}


class TradeRequest(BaseModel):
    ticker: str = Field(..., description="Uppercase ticker symbol, 1-5 letters")
    side: str = Field(..., description="'buy' or 'sell'")
    quantity: float = Field(..., gt=0, description="Positive share count (fractional OK)")


def _position_value(position: dict[str, Any], price: float | None) -> dict[str, Any]:
    """Enrich a position row with live price and unrealized P&L."""
    qty = float(position["quantity"])
    avg_cost = float(position["avg_cost"])
    current_price = float(price) if price is not None else avg_cost
    market_value = round(qty * current_price, 4)
    cost_basis = round(qty * avg_cost, 4)
    unrealized_pnl = round(market_value - cost_basis, 4)
    pct_change = (
        round((current_price - avg_cost) / avg_cost * 100, 4) if avg_cost > 0 else 0.0
    )
    return {
        "ticker": position["ticker"],
        "quantity": qty,
        "avg_cost": avg_cost,
        "current_price": current_price,
        "market_value": market_value,
        "cost_basis": cost_basis,
        "unrealized_pnl": unrealized_pnl,
        "unrealized_pnl_pct": pct_change,
        "has_live_price": price is not None,
        "updated_at": position["updated_at"],
    }


def _portfolio_total(cash: float, positions: list[dict[str, Any]]) -> float:
    return round(cash + sum(float(p["market_value"]) for p in positions), 4)


@router.get("")
def get_portfolio(state: AppState = Depends(get_state)) -> dict[str, Any]:
    """Return cash, positions enriched with live prices, and the running total."""
    with get_db(state.db_path) as conn:
        profile = get_user_profile(conn, DEFAULT_USER_ID)
        raw_positions = get_positions(conn, DEFAULT_USER_ID)

    enriched = [
        _position_value(pos, state.price_cache.get_price(pos["ticker"]))
        for pos in raw_positions
    ]
    cash_balance = float(profile["cash_balance"])
    total_value = _portfolio_total(cash_balance, enriched)
    total_cost_basis = round(sum(float(p["cost_basis"]) for p in enriched), 4)
    total_market_value = round(sum(float(p["market_value"]) for p in enriched), 4)
    total_unrealized_pnl = round(total_market_value - total_cost_basis, 4)

    return {
        "user_id": profile["id"],
        "cash_balance": round(cash_balance, 4),
        "positions": enriched,
        "total_market_value": total_market_value,
        "total_cost_basis": total_cost_basis,
        "total_unrealized_pnl": total_unrealized_pnl,
        "total_value": total_value,
    }


@router.get("/history")
def get_portfolio_history(state: AppState = Depends(get_state)) -> dict[str, Any]:
    """Return all portfolio snapshots ordered oldest -> newest."""
    with get_db(state.db_path) as conn:
        snapshots = get_portfolio_snapshots(conn, DEFAULT_USER_ID)
    return {"snapshots": snapshots}


def _execute_trade_atomic(
    state: AppState,
    ticker: str,
    side: str,
    quantity: float,
    price: float,
) -> dict[str, Any]:
    """Run the cash + position + trade-log write inside BEGIN IMMEDIATE.

    Returns the trade record, the updated cash balance, and the resulting
    position (or None if the sell zeroed it out).
    """
    with get_db(state.db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")

        profile = get_user_profile(conn, DEFAULT_USER_ID)
        existing = get_position(conn, DEFAULT_USER_ID, ticker)
        cash = float(profile["cash_balance"])
        existing_qty = float(existing["quantity"]) if existing else 0.0
        existing_avg_cost = float(existing["avg_cost"]) if existing else 0.0

        cost = round(quantity * price, 4)

        if side == "buy":
            if cost > cash + 1e-9:
                raise errors.insufficient_cash(needed=cost, have=cash)
            new_cash = round(cash - cost, 4)
            # Weighted-average cost basis update.
            new_qty = existing_qty + quantity
            if existing_qty > 0:
                new_avg_cost = round(
                    (existing_qty * existing_avg_cost + quantity * price) / new_qty,
                    6,
                )
            else:
                new_avg_cost = round(price, 6)
            updated_position = upsert_position(
                conn, DEFAULT_USER_ID, ticker, new_qty, new_avg_cost
            )
        else:  # sell
            if quantity > existing_qty + 1e-9:
                raise errors.insufficient_shares(
                    needed=quantity, have=existing_qty, ticker=ticker
                )
            new_qty = round(existing_qty - quantity, 8)
            new_cash = round(cash + cost, 4)
            if new_qty <= 1e-9:
                delete_position(conn, DEFAULT_USER_ID, ticker)
                updated_position = None
            else:
                # Avg cost unchanged on a sell.
                updated_position = upsert_position(
                    conn, DEFAULT_USER_ID, ticker, new_qty, existing_avg_cost
                )

        update_cash_balance(conn, DEFAULT_USER_ID, new_cash)
        trade = insert_trade(conn, DEFAULT_USER_ID, ticker, side, quantity, price)

        # Immediately record a snapshot reflecting the new portfolio value.
        # Live prices for non-traded positions come from the cache.
        other_positions = [
            p
            for p in get_positions(conn, DEFAULT_USER_ID)
            if p["ticker"] != ticker
        ]
        total = new_cash
        for pos in other_positions:
            live = state.price_cache.get_price(pos["ticker"])
            total += float(pos["quantity"]) * float(live if live is not None else pos["avg_cost"])
        if updated_position is not None:
            live = state.price_cache.get_price(ticker)
            total += float(updated_position["quantity"]) * float(
                live if live is not None else price
            )
        total = round(total, 4)
        insert_portfolio_snapshot(conn, DEFAULT_USER_ID, total)

    return {
        "trade": trade,
        "cash_balance": new_cash,
        "position": updated_position,
        "total_value": total,
    }


@router.post("/trade")
async def execute_trade(
    payload: TradeRequest,
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    """Execute a market order. Instant fill at the cached live price."""
    ticker = normalize_ticker(payload.ticker)
    if not ticker or not is_valid_ticker(ticker):
        raise errors.invalid_ticker(payload.ticker)

    side = (payload.side or "").strip().lower()
    if side not in VALID_SIDES:
        raise errors.invalid_side(payload.side)

    if payload.quantity <= 0:
        raise errors.invalid_quantity()

    # Trades are only allowed on tickers in the active set (watchlist ∪ positions).
    with get_db(state.db_path) as conn:
        in_watchlist = any(
            row["ticker"] == ticker for row in get_watchlist(conn, DEFAULT_USER_ID)
        )
        existing_position = get_position(conn, DEFAULT_USER_ID, ticker)
    if not in_watchlist and existing_position is None:
        raise errors.unknown_ticker(ticker)

    price = state.price_cache.get_price(ticker)
    if price is None:
        raise errors.market_data_unavailable(ticker)

    quantity = round(float(payload.quantity), 4)
    if quantity <= 0:
        raise errors.invalid_quantity()

    result = _execute_trade_atomic(state, ticker, side, quantity, float(price))

    # Ensure the ticker is in the active market data set (it should be, but
    # this is cheap insurance for sells that don't zero out and buys on
    # held-but-unwatched tickers).
    if result["position"] is not None:
        await state.market_source.add_ticker(ticker)

    return result
