"""Watchlist router for FinAlly backend."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.market import PriceCache
from app.services.watchlist import (
    get_watchlist_items,
    add_ticker_to_watchlist,
    remove_ticker_from_watchlist,
)

logger = logging.getLogger(__name__)


def create_watchlist_router(price_cache: PriceCache) -> APIRouter:
    """Router factory. Receives shared objects; no module-level globals."""
    router = APIRouter(prefix="/watchlist", tags=["watchlist"])

    @router.get("")
    async def get_watchlist(request: Request) -> JSONResponse:
        """Return all watchlist items with live prices and session Δ%.

        get_watchlist_items is a plain (sync) function — called directly, no await.
        """
        items = get_watchlist_items(
            request.app.state.price_cache,
            request.app.state.session_baselines,
        )
        return JSONResponse(items, status_code=200)

    @router.post("")
    async def add_ticker(request: Request) -> JSONResponse:
        """Add a ticker to the watchlist (validate, persist, seed market source).

        Async handler: awaits add_ticker_to_watchlist which awaits market_source.add_ticker.
        Body parsed via request.json() (works in async handlers).
        """
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"error": "invalid_ticker", "message": "Request body must be valid JSON"},
                status_code=400,
            )
        ticker = (body.get("ticker") or "")
        result = await add_ticker_to_watchlist(ticker, request.app.state.market_source)
        if isinstance(result, tuple):
            code, msg, status = result
            return JSONResponse({"error": code, "message": msg}, status_code=status)
        return JSONResponse(result, status_code=200)

    @router.delete("/{ticker}")
    async def remove_ticker(ticker: str, request: Request) -> JSONResponse:
        """Remove a ticker from the watchlist (blocked if position held).

        Async handler: awaits remove_ticker_from_watchlist which awaits market_source.remove_ticker.
        """
        result = await remove_ticker_from_watchlist(ticker, request.app.state.market_source)
        if isinstance(result, tuple):
            code, msg, status = result
            return JSONResponse({"error": code, "message": msg}, status_code=status)
        return JSONResponse(result, status_code=200)

    return router
