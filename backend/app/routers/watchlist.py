"""Watchlist router for FinAlly backend (stub — implemented in Phase 2)."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.market import PriceCache

logger = logging.getLogger(__name__)


def create_watchlist_router(price_cache: PriceCache) -> APIRouter:
    """Router factory. Receives shared objects; no module-level globals."""
    router = APIRouter(prefix="/watchlist", tags=["watchlist"])

    @router.get("")
    async def get_watchlist() -> JSONResponse:
        return JSONResponse({"error": "not_implemented", "message": "Coming in Phase 2"}, status_code=501)

    @router.post("")
    async def add_ticker() -> JSONResponse:
        return JSONResponse({"error": "not_implemented", "message": "Coming in Phase 2"}, status_code=501)

    @router.delete("/{ticker}")
    async def remove_ticker(ticker: str) -> JSONResponse:
        return JSONResponse({"error": "not_implemented", "message": "Coming in Phase 2"}, status_code=501)

    return router
