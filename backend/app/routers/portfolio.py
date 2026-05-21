"""Portfolio router for FinAlly backend."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.market import PriceCache
from app.services.portfolio import build_portfolio_view, execute_trade

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------


class TradeBody(BaseModel):
    """Trade request body. Fields are optional so malformed bodies still reach
    the service layer, which returns documented 400 codes rather than FastAPI 422."""

    ticker: str | None = None
    side: str | None = None
    quantity: float | None = None


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------


def create_portfolio_router(price_cache: PriceCache) -> APIRouter:
    """Router factory. Receives shared objects; no module-level globals."""
    router = APIRouter(prefix="/portfolio", tags=["portfolio"])

    @router.get("")
    def get_portfolio(request: Request) -> JSONResponse:  # plain def → threadpool
        """Return current portfolio: cash, positions with live P&L, total value."""
        return JSONResponse(
            build_portfolio_view(request.app.state.price_cache), status_code=200
        )

    @router.post("/trade")
    def execute_trade_route(body: TradeBody, request: Request) -> JSONResponse:  # plain def → threadpool
        """Execute a market buy or sell order."""
        ticker = (body.ticker or "").upper()
        result = execute_trade(
            request.app.state.price_cache, ticker, body.side, body.quantity
        )
        if isinstance(result, tuple):
            code, msg, status = result
            return JSONResponse({"error": code, "message": msg}, status_code=status)
        return JSONResponse(result, status_code=200)

    @router.get("/history")
    def get_history() -> JSONResponse:  # plain def → threadpool
        """Return portfolio value snapshots over time. Implemented in plan 02-03."""
        return JSONResponse(
            {"error": "not_implemented", "message": "Coming in Phase 2"},
            status_code=501,
        )

    return router
