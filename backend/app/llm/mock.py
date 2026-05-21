"""Deterministic mock LLM responses for tests, CI, and key-less demos.

Activated when ``OPENAI_API_KEY`` is absent/empty or ``LLM_MOCK=true``. The
goal is *not* to imitate the real model; it's to keep the chat flow alive
with predictable outputs so callers can exercise trade execution, watchlist
mutation, and message persistence without an API key.
"""

from __future__ import annotations

from .models import LLMResponse, TradeAction, WatchlistChange

# Common English tokens that look like tickers but never are. The mock skips
# them when scanning a user message so phrases like "buy AAPL" pick the
# obvious symbol instead of the verb.
_TICKER_STOPWORDS = frozenset(
    {
        "A", "AN", "THE", "TO", "OF", "IN", "ON", "AT", "FOR", "AND", "OR", "BUT",
        "IS", "ARE", "WAS", "BE", "MY", "ME", "I", "YOU", "WE", "IT", "ITS",
        "BUY", "SELL", "ADD", "REMOVE", "GET", "SHOW", "TELL", "FROM", "WITH",
        "PLEASE", "NOW", "SOME", "ANY", "ALL", "HOW", "WHAT", "WHEN", "WHERE",
        "WHY", "DO", "DOES", "CAN", "WILL", "WOULD", "SHOULD", "LIST", "TODAY",
    }
)


def _detect_ticker(user_message: str) -> str:
    """Pick a plausible ticker from the message; fall back to ``AAPL``."""
    for token in user_message.replace(",", " ").split():
        stripped = token.strip(".!?:;'\"$()").upper()
        if (
            1 <= len(stripped) <= 5
            and stripped.isalpha()
            and stripped not in _TICKER_STOPWORDS
        ):
            return stripped
    return "AAPL"


def mock_chat_response(user_message: str) -> LLMResponse:
    """Return a deterministic ``LLMResponse`` for the given user message.

    The body of ``message`` echoes the user's intent in a recognizable way so
    tests can assert on it. Trade and watchlist actions are added only when
    the input clearly asks for them.
    """
    lower = user_message.lower()
    trades: list[TradeAction] = []
    watchlist_changes: list[WatchlistChange] = []

    if "sell" in lower:
        trades.append(TradeAction(ticker=_detect_ticker(user_message), side="sell", quantity=1))
    elif "buy" in lower:
        trades.append(TradeAction(ticker=_detect_ticker(user_message), side="buy", quantity=1))

    if "remove" in lower:
        watchlist_changes.append(
            WatchlistChange(ticker=_detect_ticker(user_message), action="remove")
        )
    elif "add" in lower:
        watchlist_changes.append(
            WatchlistChange(ticker=_detect_ticker(user_message), action="add")
        )

    message = (
        "[mock] I received your message and prepared a deterministic response. "
        "Set OPENAI_API_KEY and unset LLM_MOCK to use the live model."
    )
    return LLMResponse(message=message, trades=trades, watchlist_changes=watchlist_changes)
