"""Chat router for FinAlly backend — POST /api/chat."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.market import PriceCache
from app.services.chat import build_chat_context, call_llm, execute_chat_actions, save_messages

logger = logging.getLogger(__name__)


def create_chat_router(price_cache: PriceCache) -> APIRouter:
    """Router factory. Accepts price_cache for parity with other routers (unused directly;
    the request's app.state.price_cache is used inside the handler)."""
    router = APIRouter(prefix="/chat", tags=["chat"])

    @router.post("")
    async def send_message(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"error": "invalid_request", "message": "Body must be valid JSON"},
                status_code=400,
            )

        user_message = (body.get("message") or "").strip()
        if not user_message:
            return JSONResponse(
                {"error": "invalid_request", "message": "message field required"},
                status_code=400,
            )

        context = build_chat_context(
            request.app.state.price_cache,
            request.app.state.session_baselines,
        )
        response = call_llm(user_message, context)
        actions = await execute_chat_actions(
            request.app.state.price_cache,
            request.app.state.market_source,
            response.get("trades", []),
            response.get("watchlist_changes", []),
        )
        save_messages(user_message, response, actions)
        return JSONResponse(
            {
                "message": response.get("message", ""),
                "trades": response.get("trades", []),
                "watchlist_changes": response.get("watchlist_changes", []),
                "actions": actions,
            },
            status_code=200,
        )

    return router
