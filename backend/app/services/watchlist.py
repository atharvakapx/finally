"""Watchlist service for FinAlly backend.

Provides:
  - get_watchlist_items: sync function to read watchlist with live prices + session Δ%
  - add_ticker_to_watchlist: async function with format validation, cap enforcement, source sync
  - remove_ticker_from_watchlist: async function with held-ticker guard, source sync

WATCH-01..05 requirements implemented here.
"""

from __future__ import annotations

import logging
import re
import uuid

from app.db import get_db, _now_iso, DEFAULT_USER_ID
from app.market import PriceCache, MarketDataSource

logger = logging.getLogger(__name__)

TICKER_RE = re.compile(r"^[A-Z]{1,5}$")
WATCHLIST_CAP = 50


def get_watchlist_items(price_cache: PriceCache, session_baselines: dict) -> list[dict]:
    """Return all watchlist items with live prices and session change %.

    Session Δ%: baseline = the FIRST price observed for a ticker this process
    (lazy first-observed, stored in session_baselines). NOT tick-over-tick.

    This is a plain def (not async) — only synchronous operations (DB + cache reads).
    The async router handler calls it directly without await.
    """
    with get_db() as conn:
        rows = conn.execute(
            "SELECT ticker, added_at FROM watchlist WHERE user_id=? ORDER BY added_at ASC",
            (DEFAULT_USER_ID,),
        ).fetchall()

    result = []
    for r in rows:
        ticker = r["ticker"]
        price = price_cache.get_price(ticker)
        baseline = session_baselines.get(ticker)

        # Lazy first-observed baseline: set on first GET after server start
        if price is not None and baseline is None:
            session_baselines[ticker] = price
            baseline = price

        session_change_pct = (
            (price - baseline) / baseline * 100
            if price is not None and baseline
            else 0.0
        )
        result.append(
            {
                "ticker": ticker,
                "price": price,
                "session_change_pct": session_change_pct,
                "added_at": r["added_at"],
            }
        )
    return result


async def add_ticker_to_watchlist(
    ticker: str, market_source: MarketDataSource
) -> tuple | dict:
    """Validate, persist, and seed the ticker into the market source.

    Returns a dict on success, or a (error_code, message, status_code) tuple on failure.
    The market_source.add_ticker coroutine is awaited AFTER the DB write (WATCH-05).
    """
    ticker = ticker.upper()

    # T-02-W2: format validation — must be 1-5 uppercase letters
    if not TICKER_RE.fullmatch(ticker):
        return ("invalid_ticker", "Ticker must be 1-5 uppercase letters", 400)

    with get_db() as conn:
        # T-02-W3: watchlist cap check (WATCH-04)
        count = conn.execute(
            "SELECT count(*) c FROM watchlist WHERE user_id=?",
            (DEFAULT_USER_ID,),
        ).fetchone()["c"]
        if count >= WATCHLIST_CAP:
            return ("watchlist_full", "Watchlist at 50-ticker cap", 400)

        # T-02-W1: parameterized INSERT only — ticker already upper-cased + validated
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), DEFAULT_USER_ID, ticker, _now_iso()),
        )

    # WATCH-05: await AFTER the DB block, not inside it
    await market_source.add_ticker(ticker)
    logger.info("Added ticker %s to watchlist and seeded market source", ticker)
    return {"ticker": ticker, "added_at": _now_iso()}


async def remove_ticker_from_watchlist(
    ticker: str, market_source: MarketDataSource
) -> tuple | dict:
    """Guard against removing a held ticker, then remove from DB and market source.

    Returns a dict on success, or a (error_code, message, status_code) tuple on failure.
    The market_source.remove_ticker coroutine is awaited AFTER the DB write.
    """
    ticker = ticker.upper()

    with get_db() as conn:
        # T-02-W4: ticker_held guard — check positions.quantity > 0
        pos = conn.execute(
            "SELECT quantity FROM positions WHERE user_id=? AND ticker=?",
            (DEFAULT_USER_ID, ticker),
        ).fetchone()
        if pos and pos["quantity"] > 0:
            return ("ticker_held", "Cannot remove a ticker you hold a position in", 400)

        # Safe to delete — no held position
        conn.execute(
            "DELETE FROM watchlist WHERE user_id=? AND ticker=?",
            (DEFAULT_USER_ID, ticker),
        )

    # Await AFTER the DB block — remove_ticker is async (interface.py line 49)
    await market_source.remove_ticker(ticker)
    logger.info("Removed ticker %s from watchlist and market source", ticker)
    return {"status": "removed", "ticker": ticker}
