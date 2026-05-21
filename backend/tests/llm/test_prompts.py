"""Tests for the portfolio context builder."""

from __future__ import annotations

from app.llm.prompts import SYSTEM_PROMPT, build_portfolio_context


class TestSystemPrompt:
    def test_system_prompt_mentions_dollar_to_share_conversion(self):
        assert "dollar" in SYSTEM_PROMPT.lower() or "$" in SYSTEM_PROMPT
        assert "JSON" in SYSTEM_PROMPT


class TestBuildPortfolioContext:
    def test_empty_portfolio_renders_safely(self):
        out = build_portfolio_context(
            {"cash_balance": 10000.0, "total_value": 10000.0, "positions": [], "watchlist": []}
        )
        assert "$10,000.00" in out
        assert "Positions: none" in out
        assert "Watchlist: empty" in out

    def test_position_with_current_price_shows_pnl(self):
        out = build_portfolio_context(
            {
                "cash_balance": 5000.0,
                "total_value": 6000.0,
                "positions": [
                    {
                        "ticker": "AAPL",
                        "quantity": 5.0,
                        "avg_cost": 190.00,
                        "current_price": 200.00,
                        "unrealized_pnl": 50.00,
                        "unrealized_pnl_pct": 5.26,
                    }
                ],
                "watchlist": [],
            }
        )
        assert "AAPL" in out
        assert "$200.00" in out
        assert "+5.26%" in out
        assert "Positions (1)" in out

    def test_position_without_current_price_renders_na(self):
        out = build_portfolio_context(
            {
                "cash_balance": 100.0,
                "total_value": 100.0,
                "positions": [{"ticker": "AAPL", "quantity": 1.0, "avg_cost": 100.0}],
                "watchlist": [],
            }
        )
        assert "AAPL" in out
        assert "n/a" in out

    def test_watchlist_renders_live_prices_for_dollar_conversion(self):
        """LLM needs live prices visible to convert '$500 of NVDA' to share count."""
        out = build_portfolio_context(
            {
                "cash_balance": 5000.0,
                "total_value": 5000.0,
                "positions": [],
                "watchlist": [
                    {"ticker": "NVDA", "current_price": 450.50, "session_change_pct": 1.23},
                    {"ticker": "PYPL", "current_price": 64.00, "session_change_pct": -0.50},
                ],
            }
        )
        assert "NVDA" in out
        assert "$450.50" in out
        assert "+1.23%" in out
        assert "-0.50%" in out

    def test_missing_fields_default_safely(self):
        # No keys whatsoever — function shouldn't raise.
        out = build_portfolio_context({})
        assert "$0.00" in out
        assert "Positions: none" in out
