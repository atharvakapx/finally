"""Portfolio router for FinAlly backend (stub — implemented in Phase 2)."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.market import PriceCache

logger = logging.getLogger(__name__)


def create_portfolio_router(price_cache: PriceCache) -> APIRouter:
    """Router factory. Receives shared objects; no module-level globals."""
    router = APIRouter(prefix="/portfolio", tags=["portfolio"])

    @router.get("")
    async def get_portfolio() -> JSONResponse:
        return JSONResponse({"error": "not_implemented", "message": "Coming in Phase 2"}, status_code=501)

    @router.post("/trade")
    async def execute_trade() -> JSONResponse:
        return JSONResponse({"error": "not_implemented", "message": "Coming in Phase 2"}, status_code=501)

    @router.get("/history")
    async def get_history() -> JSONResponse:
        return JSONResponse({"error": "not_implemented", "message": "Coming in Phase 2"}, status_code=501)

    return router
