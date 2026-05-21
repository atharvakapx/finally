"""Chat service for FinAlly backend.

Provides:
  - is_mock_mode: returns True when OPENAI_API_KEY is absent/empty or LLM_MOCK=true
  - build_chat_context: reads DB + price cache + session baselines for LLM context
  - call_llm: calls gpt-4.1-mini via LiteLLM (or returns deterministic mock)
  - execute_chat_actions: auto-executes trades and watchlist changes from LLM response
  - save_messages: persists user + assistant messages to chat_messages table
"""

from __future__ import annotations

import json
import logging
import os
import uuid

from app.db import DEFAULT_USER_ID, _now_iso, get_db
from app.market import PriceCache, MarketDataSource
from app.services.portfolio import execute_trade
from app.services.watchlist import add_ticker_to_watchlist, remove_ticker_from_watchlist

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt template
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TEMPLATE = """\
You are FinAlly, an AI trading assistant for a simulated portfolio.
You have access to the user's current portfolio state below.

Portfolio Context:
{context_json}

Instructions:
- Respond with valid JSON matching: {{"message": "...", "trades": [...], "watchlist_changes": [...]}}
- trades: [{{"ticker": "AAPL", "side": "buy"|"sell", "quantity": <number>}}]
- watchlist_changes: [{{"ticker": "AAPL", "action": "add"|"remove"}}]
- For dollar amounts ("buy $500 of NVDA"), convert to shares using the live price in context
- Be concise and data-driven. Always respond with valid JSON.\
"""

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_mock_mode() -> bool:
    """Return True if OPENAI_API_KEY is absent/empty OR LLM_MOCK env var is 'true'."""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    llm_mock = os.environ.get("LLM_MOCK", "").strip().lower()
    return not api_key or llm_mock == "true"


def build_chat_context(price_cache: PriceCache, session_baselines: dict) -> dict:
    """Read DB and price cache to build full portfolio context for the LLM.

    Parameters
    ----------
    price_cache:
        In-memory cache of latest prices from market data source.
    session_baselines:
        Dict of ticker -> first-observed price this process session.
        Used to compute session change % for watchlist items.

    Returns a dict with: cash, positions, watchlist, total_portfolio_value, recent_messages.
    """
    with get_db() as conn:
        # Cash balance
        row = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id=?", (DEFAULT_USER_ID,)
        ).fetchone()
        cash = row["cash_balance"] if row else 0.0

        # All positions with quantity > 0
        pos_rows = conn.execute(
            "SELECT ticker, quantity, avg_cost FROM positions WHERE user_id=? AND quantity > 0",
            (DEFAULT_USER_ID,),
        ).fetchall()

        # All watchlist items
        wl_rows = conn.execute(
            "SELECT ticker FROM watchlist WHERE user_id=? ORDER BY added_at ASC",
            (DEFAULT_USER_ID,),
        ).fetchall()

        # Last 20 messages (oldest first)
        msg_rows = conn.execute(
            "SELECT role, content FROM chat_messages WHERE user_id=? "
            "ORDER BY created_at DESC LIMIT 20",
            (DEFAULT_USER_ID,),
        ).fetchall()

    # Build positions list with live P&L
    positions = []
    total_value = cash
    for r in pos_rows:
        ticker = r["ticker"]
        price = price_cache.get_price(ticker)
        cur = price if price is not None else r["avg_cost"]
        market_value = r["quantity"] * cur
        cost_basis = r["quantity"] * r["avg_cost"]
        unrealized_pnl = market_value - cost_basis
        pct_change = (unrealized_pnl / cost_basis * 100) if cost_basis else 0.0
        positions.append(
            {
                "ticker": ticker,
                "quantity": r["quantity"],
                "avg_cost": r["avg_cost"],
                "current_price": cur,
                "unrealized_pnl": unrealized_pnl,
                "pct_change": pct_change,
            }
        )
        total_value += market_value

    # Build watchlist list with live prices and session change %
    watchlist = []
    for r in wl_rows:
        ticker = r["ticker"]
        price = price_cache.get_price(ticker)
        baseline = session_baselines.get(ticker)
        if price is not None and baseline is None:
            session_baselines[ticker] = price
            baseline = price
        session_change_pct = (
            (price - baseline) / baseline * 100
            if price is not None and baseline
            else 0.0
        )
        watchlist.append(
            {
                "ticker": ticker,
                "current_price": price,
                "session_change_pct": session_change_pct,
            }
        )

    # Messages list reversed so oldest first
    recent_messages = [
        {"role": r["role"], "content": r["content"]} for r in reversed(msg_rows)
    ]

    return {
        "cash": cash,
        "positions": positions,
        "watchlist": watchlist,
        "total_portfolio_value": total_value,
        "recent_messages": recent_messages,
    }


def call_llm(user_message: str, context: dict) -> dict:
    """Call gpt-4.1-mini via LiteLLM with portfolio context, or return mock response.

    Mock mode activates when is_mock_mode() is True (no API key or LLM_MOCK=true).
    """
    if is_mock_mode():
        return {
            "message": "I'm FinAlly, your AI trading assistant. How can I help you today?",
            "trades": [],
            "watchlist_changes": [],
        }

    import litellm  # deferred import — only needed in live mode

    context_json = json.dumps(
        {k: v for k, v in context.items() if k != "recent_messages"}, indent=2
    )
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context_json=context_json)

    messages = [
        {"role": "system", "content": system_prompt},
        *[{"role": m["role"], "content": m["content"]} for m in context["recent_messages"]],
        {"role": "user", "content": user_message},
    ]

    try:
        response = litellm.completion(
            model="gpt-4.1-mini",
            messages=messages,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except json.JSONDecodeError:
        return {"message": content, "trades": [], "watchlist_changes": []}
    except Exception as exc:
        logger.error("LiteLLM call failed: %s", exc)
        return {
            "message": "Sorry, I encountered an error processing your request.",
            "trades": [],
            "watchlist_changes": [],
        }


async def execute_chat_actions(
    price_cache: PriceCache,
    market_source: MarketDataSource,
    trades: list[dict],
    watchlist_changes: list[dict],
) -> list[str]:
    """Execute trades and watchlist changes from the LLM response.

    Errors are collected as result strings rather than raised, so a single
    failed trade doesn't abort the rest of the actions.

    Returns a list of human-readable result strings for inclusion in the response.
    """
    results: list[str] = []

    for trade in trades:
        ticker = (trade.get("ticker") or "").upper()
        side = trade.get("side", "")
        quantity = trade.get("quantity")

        if not ticker or not side or quantity is None:
            results.append(f"Skipped malformed trade: {trade}")
            continue

        result = execute_trade(price_cache, ticker, side, quantity)
        if isinstance(result, tuple):
            error_code, message, _status = result
            results.append(f"Trade failed ({ticker} {side} {quantity}): {error_code} — {message}")
        else:
            results.append(
                f"Executed {side} {result['trade']['quantity']} {ticker} "
                f"@ ${result['trade']['price']:.2f}"
            )

    for change in watchlist_changes:
        ticker = (change.get("ticker") or "").upper()
        action = change.get("action", "")

        if not ticker or action not in ("add", "remove"):
            results.append(f"Skipped malformed watchlist change: {change}")
            continue

        if action == "add":
            result = await add_ticker_to_watchlist(ticker, market_source)
        else:
            result = await remove_ticker_from_watchlist(ticker, market_source)

        if isinstance(result, tuple):
            error_code, message, _status = result
            results.append(
                f"Watchlist {action} failed ({ticker}): {error_code} — {message}"
            )
        else:
            results.append(f"Watchlist: {action}ed {ticker}")

    return results


def save_messages(user_message: str, response: dict, actions: list[str]) -> None:
    """Persist user and assistant messages to the chat_messages table."""
    now_user = _now_iso()
    # Small sleep not needed; timestamps are unique enough with UUID primary keys
    now_assistant = _now_iso()

    actions_json = json.dumps(
        {
            "trades": response.get("trades", []),
            "watchlist_changes": response.get("watchlist_changes", []),
            "results": actions,
        }
    )

    with get_db() as conn:
        conn.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), DEFAULT_USER_ID, "user", user_message, None, now_user),
        )
        conn.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                DEFAULT_USER_ID,
                "assistant",
                response.get("message", ""),
                actions_json,
                now_assistant,
            ),
        )
