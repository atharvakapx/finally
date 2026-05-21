"""``LLMChat`` — entrypoint that drives a single chat turn.

Responsibilities (mirrors PLAN.md §9):

1. Load portfolio context (cash, positions+P&L, watchlist with live prices).
2. Load the last 20 ``chat_messages`` rows as conversation history.
3. Call ``gpt-4.1-mini`` via LiteLLM with structured outputs — or mock mode.
4. Return a ``ChatResponse`` for the API layer to act on.

The API layer is responsible for auto-executing trades/watchlist changes and
persisting messages. That separation lets the chat module stay focused on
prompt assembly and model invocation, and lets the API layer reuse the same
validation paths as ``POST /api/portfolio/trade``.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.market import PriceCache

from .models import LLMResponse, TradeAction, WatchlistChange
from .prompts import SYSTEM_PROMPT, build_portfolio_context

logger = logging.getLogger(__name__)

MODEL = "gpt-4.1-mini"
CHAT_HISTORY_LIMIT = 20
ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
_ENV_LOADED = False


def _ensure_env_loaded() -> None:
    """Load ``.env`` at the project root exactly once per process."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH, override=False)
    _ENV_LOADED = True


def is_mock_mode() -> bool:
    """Mock mode if ``OPENAI_API_KEY`` is empty or ``LLM_MOCK=true``."""
    _ensure_env_loaded()
    if os.getenv("LLM_MOCK", "").strip().lower() == "true":
        return True
    return os.getenv("OPENAI_API_KEY", "").strip() == ""


@dataclass
class ChatResponse:
    """Result of a single chat turn.

    ``message``, ``trades``, ``watchlist_changes`` come straight from the LLM
    (or the mock). The API layer fills ``executed_trades`` with the trades it
    successfully executed and ``errors`` with human-readable strings for any
    actions that failed validation.
    """

    message: str
    trades: list[TradeAction] = field(default_factory=list)
    watchlist_changes: list[WatchlistChange] = field(default_factory=list)
    executed_trades: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @classmethod
    def from_llm(cls, parsed: LLMResponse) -> ChatResponse:
        return cls(
            message=parsed.message,
            trades=list(parsed.trades),
            watchlist_changes=list(parsed.watchlist_changes),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.message,
            "trades": [t.model_dump() for t in self.trades],
            "watchlist_changes": [w.model_dump() for w in self.watchlist_changes],
            "executed_trades": list(self.executed_trades),
            "errors": list(self.errors),
        }


class LLMChat:
    """Build prompts, call the model, and hand the parsed response back."""

    def __init__(self, price_cache: PriceCache, db_path: str | os.PathLike[str]) -> None:
        self._cache = price_cache
        self._db_path = str(db_path)
        _ensure_env_loaded()

    async def chat(self, user_id: str, user_message: str) -> ChatResponse:
        """Run one chat turn for ``user_id`` against ``user_message``."""
        portfolio = self._load_portfolio(user_id)
        history = self._load_history(user_id, CHAT_HISTORY_LIMIT)
        context_block = build_portfolio_context(portfolio)

        if is_mock_mode():
            from .mock import mock_chat_response

            parsed = mock_chat_response(user_message)
            return ChatResponse.from_llm(parsed)

        messages = self._build_messages(context_block, history, user_message)
        parsed = self._call_llm(messages)
        return ChatResponse.from_llm(parsed)

    def _build_messages(
        self,
        context_block: str,
        history: list[dict[str, str]],
        user_message: str,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Current portfolio context (refreshed each turn):\n\n"
                    f"{context_block}"
                ),
            },
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        return messages

    def _call_llm(self, messages: list[dict[str, str]]) -> LLMResponse:
        from litellm import completion

        response = completion(
            model=MODEL,
            messages=messages,
            response_format=LLMResponse,
        )
        raw = response.choices[0].message.content or ""
        try:
            return LLMResponse.model_validate_json(raw)
        except Exception as exc:  # malformed JSON from the model
            logger.warning("LLM returned unparseable JSON, returning fallback: %s", exc)
            return LLMResponse(
                message=(
                    "I had trouble formatting my last response. Could you "
                    "rephrase your question?"
                )
            )

    def _load_portfolio(self, user_id: str) -> dict[str, Any]:
        """Read portfolio + watchlist from SQLite, enrich with live prices."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            cash_row = conn.execute(
                "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
            ).fetchone()
            cash = float(cash_row["cash_balance"]) if cash_row else 0.0

            position_rows = conn.execute(
                "SELECT ticker, quantity, avg_cost FROM positions "
                "WHERE user_id = ? AND quantity > 0 ORDER BY ticker",
                (user_id,),
            ).fetchall()

            watchlist_rows = conn.execute(
                "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY ticker",
                (user_id,),
            ).fetchall()
        finally:
            conn.close()

        positions: list[dict[str, Any]] = []
        positions_value = 0.0
        for row in position_rows:
            ticker = row["ticker"]
            qty = float(row["quantity"])
            avg_cost = float(row["avg_cost"])
            current = self._cache.get_price(ticker)
            entry: dict[str, Any] = {
                "ticker": ticker,
                "quantity": qty,
                "avg_cost": avg_cost,
            }
            if current is not None:
                entry["current_price"] = current
                entry["unrealized_pnl"] = (current - avg_cost) * qty
                entry["unrealized_pnl_pct"] = (
                    ((current - avg_cost) / avg_cost * 100.0) if avg_cost else 0.0
                )
                positions_value += current * qty
            positions.append(entry)

        watchlist: list[dict[str, Any]] = []
        for row in watchlist_rows:
            ticker = row["ticker"]
            update = self._cache.get(ticker)
            entry = {"ticker": ticker}
            if update is not None:
                entry["current_price"] = update.price
                if update.previous_price:
                    entry["session_change_pct"] = (
                        (update.price - update.previous_price)
                        / update.previous_price
                        * 100.0
                    )
            watchlist.append(entry)

        return {
            "cash_balance": cash,
            "total_value": cash + positions_value,
            "positions": positions,
            "watchlist": watchlist,
        }

    def _load_history(self, user_id: str, limit: int) -> list[dict[str, str]]:
        """Return the last ``limit`` chat messages in chronological order."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT role, content FROM chat_messages WHERE user_id = ? "
                "ORDER BY created_at DESC, id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        finally:
            conn.close()

        history: list[dict[str, str]] = []
        for row in reversed(rows):
            role = row["role"]
            if role not in ("user", "assistant"):
                continue
            content = row["content"]
            # Assistant rows store the full JSON action payload. The LLM only
            # needs the conversational text from prior turns; strip the rest.
            if role == "assistant":
                content = _extract_assistant_text(content)
            history.append({"role": role, "content": content})
        return history


def _extract_assistant_text(stored_content: str) -> str:
    """Pull the user-visible ``message`` out of a stored assistant row.

    Assistant messages may be stored as plain text or as a JSON ``LLMResponse``
    blob (the chat API may persist either form). Try JSON first; fall back to
    the raw string.
    """
    try:
        decoded = json.loads(stored_content)
    except (TypeError, ValueError, json.JSONDecodeError):
        return stored_content
    if isinstance(decoded, dict) and isinstance(decoded.get("message"), str):
        return decoded["message"]
    return stored_content
