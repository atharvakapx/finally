"""Chat endpoint — bridges the user, the LLM, and the trading engine.

The LLM module (`app.llm`) handles prompt assembly, history/context
loading, and model invocation. This router is responsible for:

  - calling ``LLMChat.chat()`` (or its mock equivalent),
  - validating + executing any trades or watchlist changes the LLM
    requested (using the same code paths as the manual endpoints),
  - persisting the user and assistant messages.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app import errors
from app.api.portfolio import TradeRequest, _execute_trade_atomic
from app.api.watchlist import (
    WatchlistAddRequest,
    add_to_watchlist,
    remove_ticker,
)
from app.db import get_db
from app.db.crud import insert_chat_message
from app.state import DEFAULT_USER_ID, AppState, get_state
from app.validation import is_valid_ticker, normalize_ticker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


async def _call_llm(state: AppState, message: str) -> Any:
    """Invoke the LLM client. Isolated so tests can monkeypatch it."""
    try:
        from app.llm import LLMChat
    except ImportError as exc:
        logger.warning("LLM module not yet available: %s", exc)
        raise errors.APIError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "llm_unavailable",
            "Chat service is initializing. Please retry shortly.",
        ) from exc

    chat = LLMChat(price_cache=state.price_cache, db_path=state.db_path)
    return await chat.chat(user_id=DEFAULT_USER_ID, user_message=message)


async def _execute_trade_action(state: AppState, trade: Any) -> dict[str, Any]:
    """Apply one LLM-issued trade. Returns an action receipt."""
    payload = {
        "ticker": getattr(trade, "ticker", None) or "",
        "side": getattr(trade, "side", None) or "",
        "quantity": getattr(trade, "quantity", 0),
    }
    try:
        req = TradeRequest(**payload)
    except Exception as exc:
        return {"status": "rejected", "reason": "invalid_payload", "message": str(exc)}

    ticker = normalize_ticker(req.ticker)
    if not ticker or not is_valid_ticker(ticker):
        return {"status": "rejected", "reason": "invalid_ticker", "ticker": req.ticker}

    side = (req.side or "").strip().lower()
    if side not in {"buy", "sell"}:
        return {"status": "rejected", "reason": "invalid_side", "side": req.side}

    if req.quantity <= 0:
        return {"status": "rejected", "reason": "invalid_quantity"}

    price = state.price_cache.get_price(ticker)
    if price is None:
        return {
            "status": "rejected",
            "reason": "market_data_unavailable",
            "ticker": ticker,
        }

    try:
        result = _execute_trade_atomic(
            state, ticker, side, round(float(req.quantity), 4), float(price)
        )
    except errors.APIError as exc:
        return {
            "status": "rejected",
            "ticker": ticker,
            "side": side,
            "reason": exc.code,
            "message": exc.message,
        }

    if result["position"] is not None:
        await state.market_source.add_ticker(ticker)

    return {
        "status": "executed",
        "trade": result["trade"],
        "position": result["position"],
        "cash_balance": result["cash_balance"],
    }


async def _apply_watchlist_change(state: AppState, change: Any) -> dict[str, Any]:
    """Apply one LLM-issued watchlist add/remove."""
    action = (getattr(change, "action", "") or "").strip().lower()
    raw_ticker = getattr(change, "ticker", "") or ""
    normalized = normalize_ticker(raw_ticker)
    if not normalized or not is_valid_ticker(normalized):
        return {"status": "rejected", "reason": "invalid_ticker", "ticker": raw_ticker}

    try:
        if action == "add":
            entry = await add_to_watchlist(
                WatchlistAddRequest(ticker=normalized), state=state
            )
            return {"status": "added", "ticker": normalized, "entry": entry}
        if action == "remove":
            await remove_ticker(normalized, state=state)
            return {"status": "removed", "ticker": normalized}
    except errors.APIError as exc:
        return {
            "status": "rejected",
            "ticker": normalized,
            "action": action,
            "reason": exc.code,
            "message": exc.message,
        }

    return {"status": "rejected", "reason": "invalid_action", "action": action}


@router.post("")
async def chat(
    payload: ChatRequest,
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    """Send a message, run the LLM, auto-execute any actions, return everything."""
    message_text = payload.message.strip()
    if not message_text:
        raise errors.APIError(
            status.HTTP_400_BAD_REQUEST,
            "invalid_message",
            "Message text must be non-empty.",
        )

    # Persist the user message before calling the LLM. If the model fails the
    # transcript still shows the question the user asked.
    with get_db(state.db_path) as conn:
        insert_chat_message(conn, DEFAULT_USER_ID, "user", message_text, None)

    llm_response = await _call_llm(state, message_text)

    assistant_text = (getattr(llm_response, "message", "") or "").strip() or "(no response)"
    trades = list(getattr(llm_response, "trades", []) or [])
    watchlist_changes = list(getattr(llm_response, "watchlist_changes", []) or [])

    executed_actions: dict[str, list[dict[str, Any]]] = {
        "trades": [],
        "watchlist_changes": [],
    }
    for trade in trades:
        executed_actions["trades"].append(await _execute_trade_action(state, trade))
    for change in watchlist_changes:
        executed_actions["watchlist_changes"].append(
            await _apply_watchlist_change(state, change)
        )

    with get_db(state.db_path) as conn:
        insert_chat_message(
            conn,
            DEFAULT_USER_ID,
            "assistant",
            assistant_text,
            executed_actions if any(executed_actions.values()) else None,
        )

    return {
        "message": assistant_text,
        "actions": executed_actions,
    }
