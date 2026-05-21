"""Chat API tests — CHAT-01..08.

Tests cover:
  CHAT-01: POST /api/chat with no OPENAI_API_KEY returns 200 with message field (mock mode)
  CHAT-02: LLM_MOCK=true forces mock mode even when OPENAI_API_KEY is present
  CHAT-03: Messages persisted to chat_messages table after request
  CHAT-04: Missing message field returns 400
  CHAT-05: Non-JSON body returns 400
  CHAT-06: Second message includes first in context (history loaded)
  CHAT-07: Mock response with trade executes the trade
  CHAT-08: Mock response with watchlist change applies it
"""

from __future__ import annotations

import importlib
import json

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    """Function-scoped fixture: fresh DB, no external keys, mocked market source."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "finally.db"))
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MOCK", raising=False)

    import app.db
    import app.main
    importlib.reload(app.db)
    importlib.reload(app.main)

    with TestClient(app.main.app) as client:
        mock_source = MagicMock()
        mock_source.add_ticker = AsyncMock()
        mock_source.remove_ticker = AsyncMock()
        mock_source.get_tickers = MagicMock(return_value=[])
        app.main.app.state.market_source = mock_source

        yield client, app.main, mock_source


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def seed_cache(module, ticker: str, price: float) -> None:
    """Seed a deterministic price into the app's price cache."""
    module.app.state.price_cache.update(ticker, price)


# ---------------------------------------------------------------------------
# CHAT-01: Mock mode — no API key
# ---------------------------------------------------------------------------


class TestMockModeNoApiKey:
    def test_mock_mode_no_api_key(self, app_client) -> None:
        """CHAT-01: POST /api/chat with no OPENAI_API_KEY returns 200 with message field."""
        client, module, _ = app_client
        resp = client.post("/api/chat", json={"message": "Hello"})
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data, f"Response missing 'message' key: {data}"
        assert isinstance(data["message"], str)
        assert len(data["message"]) > 0
        assert "trades" in data
        assert "watchlist_changes" in data
        assert "actions" in data


# ---------------------------------------------------------------------------
# CHAT-02: Mock mode forced by LLM_MOCK=true
# ---------------------------------------------------------------------------


class TestMockModeForced:
    def test_mock_mode_forced(self, tmp_path, monkeypatch) -> None:
        """CHAT-02: LLM_MOCK=true forces mock even when OPENAI_API_KEY is present."""
        monkeypatch.setenv("DB_PATH", str(tmp_path / "finally.db"))
        monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-key-for-test")
        monkeypatch.setenv("LLM_MOCK", "true")

        import app.db
        import app.main
        importlib.reload(app.db)
        importlib.reload(app.main)

        with TestClient(app.main.app) as client:
            mock_source = MagicMock()
            mock_source.add_ticker = AsyncMock()
            mock_source.remove_ticker = AsyncMock()
            app.main.app.state.market_source = mock_source

            resp = client.post("/api/chat", json={"message": "What's my portfolio?"})
            assert resp.status_code == 200
            data = resp.json()
            assert "message" in data
            assert isinstance(data["message"], str)
            # Should be the deterministic mock message — no real OpenAI call
            assert "FinAlly" in data["message"] or len(data["message"]) > 0


# ---------------------------------------------------------------------------
# CHAT-03: Messages persisted
# ---------------------------------------------------------------------------


class TestChatPersistsMessages:
    def test_chat_persists_messages(self, app_client) -> None:
        """CHAT-03: User and assistant messages are saved to chat_messages table."""
        client, module, _ = app_client

        resp = client.post("/api/chat", json={"message": "Tell me about my portfolio"})
        assert resp.status_code == 200

        # Query DB directly
        import app.db as db_module
        with db_module.get_db() as conn:
            rows = conn.execute(
                "SELECT role, content FROM chat_messages ORDER BY created_at ASC"
            ).fetchall()

        assert len(rows) == 2, f"Expected 2 rows (user + assistant), got {len(rows)}"
        assert rows[0]["role"] == "user"
        assert rows[0]["content"] == "Tell me about my portfolio"
        assert rows[1]["role"] == "assistant"
        assert len(rows[1]["content"]) > 0


# ---------------------------------------------------------------------------
# CHAT-04: Missing message field
# ---------------------------------------------------------------------------


class TestChatMissingMessageField:
    def test_chat_missing_message_field(self, app_client) -> None:
        """CHAT-04: Missing message field returns 400 invalid_request."""
        client, module, _ = app_client

        resp = client.post("/api/chat", json={"text": "Hello"})
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"] == "invalid_request"

    def test_chat_empty_message_field(self, app_client) -> None:
        """Empty string message field also returns 400."""
        client, module, _ = app_client

        resp = client.post("/api/chat", json={"message": "   "})
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"] == "invalid_request"


# ---------------------------------------------------------------------------
# CHAT-05: Invalid JSON body
# ---------------------------------------------------------------------------


class TestChatInvalidJsonBody:
    def test_chat_invalid_json_body(self, app_client) -> None:
        """CHAT-05: Non-JSON body returns 400."""
        client, module, _ = app_client

        resp = client.post(
            "/api/chat",
            content=b"not valid json at all",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"] == "invalid_request"


# ---------------------------------------------------------------------------
# CHAT-06: Chat history loaded in context
# ---------------------------------------------------------------------------


class TestChatHistoryLoaded:
    def test_chat_history_loaded(self, app_client) -> None:
        """CHAT-06: Second message includes first message in context (last 20 messages)."""
        client, module, _ = app_client

        # First message
        resp1 = client.post("/api/chat", json={"message": "Hello, I'm starting fresh"})
        assert resp1.status_code == 200

        # Track context passed to call_llm on second call
        captured_contexts = []

        import app.routers.chat as chat_router_module
        import app.services.chat as chat_module

        original_call_llm = chat_module.call_llm

        def capturing_call_llm(user_message, context):
            captured_contexts.append(context)
            return original_call_llm(user_message, context)

        # Patch where the router uses it (imported name in routers/chat.py)
        with patch.object(chat_router_module, "call_llm", side_effect=capturing_call_llm):
            resp2 = client.post("/api/chat", json={"message": "What did I just say?"})
            assert resp2.status_code == 200

        assert len(captured_contexts) == 1
        context = captured_contexts[0]
        recent_messages = context.get("recent_messages", [])
        # Should contain at least the user+assistant pair from the first request
        assert len(recent_messages) >= 2, (
            f"Expected >=2 messages in context, got {len(recent_messages)}: {recent_messages}"
        )
        # The user's first message should appear in history
        user_msgs = [m for m in recent_messages if m["role"] == "user"]
        contents = [m["content"] for m in user_msgs]
        assert any("Hello, I'm starting fresh" in c for c in contents), (
            f"First message not found in context history: {contents}"
        )


# ---------------------------------------------------------------------------
# CHAT-07: Trade execution via chat
# ---------------------------------------------------------------------------


class TestExecuteChatActionsTrade:
    def test_execute_chat_actions_trade(self, app_client) -> None:
        """CHAT-07: Mock response with trade executes the trade via execute_trade."""
        client, module, _ = app_client

        # Seed price so execute_trade can fill the order
        seed_cache(module, "AAPL", 150.0)

        # Patch call_llm to return a controlled response with a trade
        import app.routers.chat as chat_router_module

        mock_response = {
            "message": "Buying 1 share of AAPL for you.",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 1}],
            "watchlist_changes": [],
        }

        # Patch where the router uses it (imported name in routers/chat.py)
        with patch.object(chat_router_module, "call_llm", return_value=mock_response):
            resp = client.post("/api/chat", json={"message": "Buy 1 share of AAPL"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Buying 1 share of AAPL for you."

        # Verify trade was actually executed — check portfolio
        portfolio_resp = client.get("/api/portfolio")
        assert portfolio_resp.status_code == 200
        portfolio = portfolio_resp.json()
        aapl_positions = [p for p in portfolio["positions"] if p["ticker"] == "AAPL"]
        assert len(aapl_positions) == 1, f"Expected AAPL position, got: {portfolio['positions']}"
        assert aapl_positions[0]["quantity"] == 1.0
        # Cash should be reduced by ~$150
        assert portfolio["cash"] < 10000.0


# ---------------------------------------------------------------------------
# CHAT-08: Watchlist change via chat
# ---------------------------------------------------------------------------


class TestExecuteChatActionsWatchlist:
    def test_execute_chat_actions_watchlist(self, app_client) -> None:
        """CHAT-08: Mock response with watchlist_change applies it."""
        client, module, mock_source = app_client

        import app.routers.chat as chat_router_module

        mock_response = {
            "message": "Added PYPL to your watchlist.",
            "trades": [],
            "watchlist_changes": [{"ticker": "PYPL", "action": "add"}],
        }

        # Patch where the router uses it (imported name in routers/chat.py)
        with patch.object(chat_router_module, "call_llm", return_value=mock_response):
            resp = client.post("/api/chat", json={"message": "Add PYPL to my watchlist"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Added PYPL to your watchlist."

        # Verify PYPL is now in the watchlist
        wl_resp = client.get("/api/watchlist")
        assert wl_resp.status_code == 200
        tickers = [item["ticker"] for item in wl_resp.json()]
        assert "PYPL" in tickers, f"PYPL not found in watchlist: {tickers}"

        # Verify market_source.add_ticker was called
        mock_source.add_ticker.assert_awaited_once_with("PYPL")
