"""Tests for mock-mode LLM responses and the mock-mode detector."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from app.db.schema import init_db
from app.llm import LLMChat
from app.llm.client import is_mock_mode
from app.llm.mock import mock_chat_response
from app.llm.models import LLMResponse
from app.market import PriceCache


class TestMockResponse:
    def test_returns_valid_llm_response(self):
        resp = mock_chat_response("Hello, what's my portfolio?")
        assert isinstance(resp, LLMResponse)
        assert resp.message  # non-empty
        assert resp.trades == []
        assert resp.watchlist_changes == []

    def test_buy_intent_includes_trade(self):
        resp = mock_chat_response("Please buy AAPL")
        assert len(resp.trades) == 1
        assert resp.trades[0].side == "buy"
        assert resp.trades[0].ticker == "AAPL"

    def test_sell_intent_includes_trade(self):
        resp = mock_chat_response("sell TSLA now")
        assert len(resp.trades) == 1
        assert resp.trades[0].side == "sell"
        assert resp.trades[0].ticker == "TSLA"

    def test_add_intent_includes_watchlist_change(self):
        resp = mock_chat_response("add PYPL to my watchlist")
        assert len(resp.watchlist_changes) == 1
        assert resp.watchlist_changes[0].action == "add"
        assert resp.watchlist_changes[0].ticker == "PYPL"

    def test_remove_intent_includes_watchlist_change(self):
        resp = mock_chat_response("remove META from watchlist")
        assert len(resp.watchlist_changes) == 1
        assert resp.watchlist_changes[0].action == "remove"

    def test_deterministic_for_same_input(self):
        a = mock_chat_response("Tell me about my portfolio")
        b = mock_chat_response("Tell me about my portfolio")
        assert a == b


class TestMockModeDetection:
    def test_no_api_key_triggers_mock(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "LLM_MOCK": ""}, clear=False):
            # Bypass the .env cache so we read the patched env values.
            import app.llm.client as client_mod

            client_mod._ENV_LOADED = True
            assert is_mock_mode() is True

    def test_empty_api_key_triggers_mock(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "   ", "LLM_MOCK": ""}, clear=False):
            import app.llm.client as client_mod

            client_mod._ENV_LOADED = True
            assert is_mock_mode() is True

    def test_llm_mock_true_overrides_present_key(self):
        with patch.dict(
            os.environ, {"OPENAI_API_KEY": "sk-real-key", "LLM_MOCK": "true"}, clear=False
        ):
            import app.llm.client as client_mod

            client_mod._ENV_LOADED = True
            assert is_mock_mode() is True

    def test_key_present_and_llm_mock_false_uses_live(self):
        with patch.dict(
            os.environ, {"OPENAI_API_KEY": "sk-real-key", "LLM_MOCK": "false"}, clear=False
        ):
            import app.llm.client as client_mod

            client_mod._ENV_LOADED = True
            assert is_mock_mode() is False


@pytest.fixture
def chat_setup(tmp_path: Path):
    """Build a real SQLite DB + cache so the chat path exercises the DB queries."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    cache = PriceCache()
    cache.update("AAPL", 200.00)
    cache.update("NVDA", 450.00)
    yield cache, db_path


class TestMockChatIntegration:
    @pytest.mark.asyncio
    async def test_chat_in_mock_mode_makes_no_api_call(self, chat_setup, monkeypatch):
        cache, db_path = chat_setup
        monkeypatch.setenv("OPENAI_API_KEY", "")
        monkeypatch.setenv("LLM_MOCK", "true")
        import app.llm.client as client_mod

        client_mod._ENV_LOADED = True

        # If anything tries to import litellm.completion, fail the test loudly.
        def fail_completion(*_args, **_kwargs):  # pragma: no cover
            raise AssertionError("litellm.completion called in mock mode")

        monkeypatch.setattr("litellm.completion", fail_completion)

        chat = LLMChat(price_cache=cache, db_path=db_path)
        result = await chat.chat(user_id="default", user_message="buy AAPL")

        assert result.message
        assert any(t.ticker == "AAPL" and t.side == "buy" for t in result.trades)

    @pytest.mark.asyncio
    async def test_chat_loads_history_from_db(self, chat_setup, monkeypatch):
        cache, db_path = chat_setup
        monkeypatch.setenv("OPENAI_API_KEY", "")
        monkeypatch.setenv("LLM_MOCK", "true")
        import app.llm.client as client_mod

        client_mod._ENV_LOADED = True

        conn = sqlite3.connect(db_path)
        with conn:
            conn.execute(
                "INSERT INTO chat_messages (id, user_id, role, content, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("m1", "default", "user", "earlier question", "2026-05-21T10:00:00Z"),
            )
            conn.execute(
                "INSERT INTO chat_messages (id, user_id, role, content, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("m2", "default", "assistant", '{"message": "earlier reply"}',
                 "2026-05-21T10:00:01Z"),
            )
        conn.close()

        chat = LLMChat(price_cache=cache, db_path=db_path)
        history = chat._load_history("default", 20)

        assert history == [
            {"role": "user", "content": "earlier question"},
            {"role": "assistant", "content": "earlier reply"},
        ]

    def test_portfolio_loader_includes_live_prices_and_pnl(self, chat_setup):
        cache, db_path = chat_setup

        # Seed a position so the loader has something to compute P&L on.
        conn = sqlite3.connect(db_path)
        with conn:
            conn.execute(
                "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("p1", "default", "AAPL", 10.0, 180.00, "2026-05-21T10:00:00Z"),
            )
        conn.close()

        chat = LLMChat(price_cache=cache, db_path=db_path)
        data = chat._load_portfolio("default")

        assert data["cash_balance"] == 10000.0
        assert any(
            p["ticker"] == "AAPL" and p["current_price"] == 200.00 for p in data["positions"]
        )
        aapl = next(p for p in data["positions"] if p["ticker"] == "AAPL")
        assert aapl["unrealized_pnl"] == pytest.approx(200.0)  # (200-180)*10
        # Watchlist defaults include AAPL — verify live price is attached.
        watch_aapl = next(w for w in data["watchlist"] if w["ticker"] == "AAPL")
        assert watch_aapl["current_price"] == 200.00
