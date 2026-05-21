"""System prompt and portfolio context formatting for the LLM."""

from __future__ import annotations

from typing import Any

SYSTEM_PROMPT = (
    "You are FinAlly, an AI trading assistant for a simulated portfolio. "
    "Analyze portfolio composition, risk concentration, and P&L. Suggest "
    "trades with reasoning and execute them when the user asks or agrees. "
    "Manage the watchlist proactively when it helps the user. Be concise "
    "and data-driven; numbers beat adjectives. "
    "When the user requests a dollar amount (e.g. 'buy $500 of NVDA'), "
    "convert it to a share count using the live prices in the portfolio "
    "context — the trade schema accepts share quantities only. "
    "Always respond with valid JSON matching the required schema: "
    '{"message": str, "trades": [...], "watchlist_changes": [...]}. '
    "Set trades or watchlist_changes to an empty list when no action is needed."
)


def _fmt_money(value: float) -> str:
    return f"${value:,.2f}"


def _fmt_pct(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def build_portfolio_context(portfolio_data: dict[str, Any]) -> str:
    """Format portfolio state into a compact, LLM-friendly context block.

    Expected ``portfolio_data`` shape::

        {
            "cash_balance": 8234.10,
            "total_value": 11234.56,
            "positions": [
                {
                    "ticker": "AAPL",
                    "quantity": 5.0,
                    "avg_cost": 192.43,
                    "current_price": 198.10,
                    "unrealized_pnl": 28.35,
                    "unrealized_pnl_pct": 2.94,
                },
                ...
            ],
            "watchlist": [
                {"ticker": "PYPL", "current_price": 64.32, "session_change_pct": -1.20},
                ...
            ],
        }

    Missing optional fields render as ``"n/a"`` rather than raising — the goal
    is a robust prompt, not strict validation.
    """
    cash = float(portfolio_data.get("cash_balance", 0.0))
    total = float(portfolio_data.get("total_value", cash))
    positions = portfolio_data.get("positions") or []
    watchlist = portfolio_data.get("watchlist") or []

    lines: list[str] = ["=== Portfolio Snapshot ==="]
    lines.append(f"Cash: {_fmt_money(cash)}")
    lines.append(f"Total portfolio value: {_fmt_money(total)}")

    lines.append("")
    if positions:
        lines.append(f"Positions ({len(positions)}):")
        lines.append("  ticker | qty | avg_cost | current | unrealized P&L")
        for pos in positions:
            ticker = pos.get("ticker", "?")
            qty = float(pos.get("quantity", 0.0))
            avg_cost = float(pos.get("avg_cost", 0.0))
            current = pos.get("current_price")
            pnl = pos.get("unrealized_pnl")
            pnl_pct = pos.get("unrealized_pnl_pct")
            current_str = _fmt_money(float(current)) if current is not None else "n/a"
            if pnl is not None and pnl_pct is not None:
                pnl_str = f"{_fmt_money(float(pnl))} ({_fmt_pct(float(pnl_pct))})"
            else:
                pnl_str = "n/a"
            lines.append(
                f"  {ticker} | {qty:.4f} | {_fmt_money(avg_cost)} | "
                f"{current_str} | {pnl_str}"
            )
    else:
        lines.append("Positions: none")

    lines.append("")
    if watchlist:
        lines.append(f"Watchlist ({len(watchlist)}) — live prices:")
        for entry in watchlist:
            ticker = entry.get("ticker", "?")
            price = entry.get("current_price")
            session = entry.get("session_change_pct")
            price_str = _fmt_money(float(price)) if price is not None else "n/a"
            session_str = _fmt_pct(float(session)) if session is not None else "n/a"
            lines.append(f"  {ticker}: {price_str} ({session_str} session)")
    else:
        lines.append("Watchlist: empty")

    return "\n".join(lines)
