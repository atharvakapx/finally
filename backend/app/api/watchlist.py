"""Watchlist endpoints — add, remove, list."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app import errors
from app.db import get_db
from app.db.crud import (
    get_position,
    get_watchlist,
    remove_from_watchlist,
)
from app.db.crud import add_to_watchlist as crud_add_to_watchlist
from app.state import DEFAULT_USER_ID, AppState, get_state
from app.validation import WATCHLIST_CAP, is_valid_ticker, normalize_ticker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class WatchlistAddRequest(BaseModel):
    ticker: str = Field(..., description="Ticker symbol to add")


def _enrich_with_price(entry: dict[str, Any], state: AppState) -> dict[str, Any]:
    """Attach live price + session change pct to a watchlist row."""
    ticker = entry["ticker"]
    update = state.price_cache.get(ticker)
    if update is None:
        return {
            **entry,
            "price": None,
            "previous_price": None,
            "change": None,
            "change_percent": None,
            "direction": "flat",
            "timestamp": None,
        }
    return {
        **entry,
        "price": update.price,
        "previous_price": update.previous_price,
        "change": update.change,
        "change_percent": update.change_percent,
        "direction": update.direction,
        "timestamp": update.timestamp,
    }


@router.get("")
def list_watchlist(state: AppState = Depends(get_state)) -> dict[str, Any]:
    """List the current watchlist with live price data attached."""
    with get_db(state.db_path) as conn:
        rows = get_watchlist(conn, DEFAULT_USER_ID)
    enriched = [_enrich_with_price(row, state) for row in rows]
    return {"watchlist": enriched, "count": len(enriched), "cap": WATCHLIST_CAP}


@router.post("", status_code=201)
async def add_to_watchlist(
    payload: WatchlistAddRequest,
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    """Add a ticker to the watchlist.

    Validates format, enforces the size cap, and (in Massive mode) probes the
    symbol against the upstream API before persisting.
    """
    ticker = normalize_ticker(payload.ticker)
    if not ticker or not is_valid_ticker(ticker):
        raise errors.invalid_ticker(payload.ticker)

    with get_db(state.db_path) as conn:
        current = get_watchlist(conn, DEFAULT_USER_ID)

    if any(row["ticker"] == ticker for row in current):
        # Idempotent: already present, return the existing entry.
        existing = next(row for row in current if row["ticker"] == ticker)
        return _enrich_with_price(existing, state)

    if len(current) >= WATCHLIST_CAP:
        raise errors.watchlist_full(WATCHLIST_CAP)

    # Hand-off to the market data source. The simulator seeds new tickers at
    # $100; the Massive client probes the symbol and raises on unknown
    # tickers (translated to 404 below).
    try:
        await state.market_source.add_ticker(ticker)
    except ValueError as exc:
        raise errors.unknown_ticker(ticker) from exc

    try:
        with get_db(state.db_path) as conn:
            entry = crud_add_to_watchlist(conn, DEFAULT_USER_ID, ticker)
    except sqlite3.IntegrityError:
        # Race condition: another writer beat us to it. Still success-ish.
        with get_db(state.db_path) as conn:
            rows = get_watchlist(conn, DEFAULT_USER_ID)
        entry = next(row for row in rows if row["ticker"] == ticker)

    return _enrich_with_price(entry, state)


@router.delete("/{ticker}")
async def remove_ticker(
    ticker: str,
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    """Remove a ticker from the watchlist.

    Refuses when the user still holds shares — preventing the active ticker
    set from being smaller than the union of watchlist and positions.
    """
    normalized = normalize_ticker(ticker)
    if not normalized or not is_valid_ticker(normalized):
        raise errors.invalid_ticker(ticker)

    with get_db(state.db_path) as conn:
        position = get_position(conn, DEFAULT_USER_ID, normalized)
        if position is not None and float(position["quantity"]) > 0:
            raise errors.ticker_held(normalized)

        removed = remove_from_watchlist(conn, DEFAULT_USER_ID, normalized)

    if not removed:
        raise errors.not_found(f"Watchlist entry for {normalized}")

    # If the user no longer holds the ticker, drop it from the active set.
    if position is None or float(position["quantity"]) <= 0:
        await state.market_source.remove_ticker(normalized)

    return {"ticker": normalized, "removed": True}
