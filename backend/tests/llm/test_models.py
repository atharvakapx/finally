"""Tests for the structured-output Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.llm.models import LLMResponse, TradeAction, WatchlistChange


class TestLLMResponse:
    def test_minimal_message_only(self):
        resp = LLMResponse.model_validate_json('{"message": "Hello"}')
        assert resp.message == "Hello"
        assert resp.trades == []
        assert resp.watchlist_changes == []

    def test_with_trades_and_watchlist(self):
        payload = {
            "message": "Bought NVDA and added PYPL",
            "trades": [{"ticker": "NVDA", "side": "buy", "quantity": 5}],
            "watchlist_changes": [{"ticker": "PYPL", "action": "add"}],
        }
        resp = LLMResponse.model_validate(payload)
        assert resp.trades[0].ticker == "NVDA"
        assert resp.trades[0].side == "buy"
        assert resp.trades[0].quantity == 5
        assert resp.watchlist_changes[0].action == "add"

    def test_fractional_quantity_allowed(self):
        resp = LLMResponse.model_validate(
            {
                "message": "ok",
                "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 0.25}],
            }
        )
        assert resp.trades[0].quantity == 0.25

    def test_rejects_unknown_side(self):
        with pytest.raises(ValidationError):
            TradeAction.model_validate({"ticker": "AAPL", "side": "short", "quantity": 1})

    def test_rejects_unknown_watchlist_action(self):
        with pytest.raises(ValidationError):
            WatchlistChange.model_validate({"ticker": "AAPL", "action": "delete"})

    def test_missing_message_fails(self):
        with pytest.raises(ValidationError):
            LLMResponse.model_validate({"trades": []})

    def test_round_trip_json(self):
        original = LLMResponse(
            message="ok",
            trades=[TradeAction(ticker="TSLA", side="sell", quantity=2.5)],
        )
        clone = LLMResponse.model_validate_json(original.model_dump_json())
        assert clone == original
