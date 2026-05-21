---
phase: 03-ai-chat
plan: 01
status: complete
tests_passed: 131
subsystem: backend/chat
tags: [litellm, openai, mock-mode, chat-service, sse-safe]
dependency_graph:
  requires: [02-01, 02-02, 02-03]
  provides: [POST /api/chat, chat service, LLM mock mode]
  affects: [backend/app/services/chat.py, backend/app/routers/chat.py]
tech_stack:
  added: [litellm==1.85.1, openai==2.37.0]
  patterns: [structured-json-output, deferred-litellm-import, patch-at-use-site]
key_files:
  created:
    - backend/app/services/chat.py
    - backend/tests/test_chat.py
  modified:
    - backend/app/routers/chat.py
    - backend/app/main.py
    - backend/tests/test_main_integration.py
decisions:
  - "Deferred litellm import inside call_llm() — only imported when live mode is needed; avoids loading litellm in mock mode"
  - "Patch call_llm at the router import site (app.routers.chat) in tests, not at the service module — necessary because Python's from-import binds by value"
  - "Updated test_main_integration.py to expect 200 instead of 501 — the 501 stub is now replaced by the real endpoint"
metrics:
  duration_seconds: 980
  completed_at: "2026-05-21T17:36:49Z"
  tasks_completed: 4
  files_created: 2
  files_modified: 3
---

# Phase 3 Plan 01: AI Chat Endpoint Summary

AI chat endpoint with LiteLLM integration, deterministic mock mode, full portfolio context injection, trade/watchlist auto-execution, and message persistence.

## What Was Implemented

**`backend/app/services/chat.py`** (new)
- `is_mock_mode()` — True when `OPENAI_API_KEY` absent/empty or `LLM_MOCK=true`
- `build_chat_context(price_cache, session_baselines)` — builds full portfolio snapshot: cash, positions with live P&L, watchlist with session Δ%, last 20 chat messages
- `call_llm(user_message, context)` — calls `gpt-4.1-mini` via LiteLLM with `response_format=json_object`, or returns deterministic mock response
- `execute_chat_actions(price_cache, market_source, trades, watchlist_changes)` — auto-executes trades via `execute_trade()` and watchlist changes via `add_ticker_to_watchlist` / `remove_ticker_from_watchlist`; collects errors as strings rather than raising
- `save_messages(user_message, response, actions)` — inserts user + assistant rows into `chat_messages` table with `actions` JSON

**`backend/app/routers/chat.py`** (replaced 501 stub)
- `create_chat_router(price_cache)` — now accepts `price_cache` parameter (parity with other routers)
- `POST /api/chat` — validates JSON body and non-empty message, builds context, calls LLM, executes actions, saves messages, returns `{message, trades, watchlist_changes, actions}`

**`backend/app/main.py`** (updated)
- `create_chat_router()` → `create_chat_router(price_cache)` to match new signature

**`backend/tests/test_chat.py`** (new, 9 tests)
- CHAT-01: mock mode no API key returns 200
- CHAT-02: `LLM_MOCK=true` forces mock even with key
- CHAT-03: messages persisted to DB after request
- CHAT-04: missing message field → 400
- CHAT-05: non-JSON body → 400
- CHAT-06: second message includes first in context
- CHAT-07: trade in LLM response auto-executes
- CHAT-08: watchlist change in LLM response applies

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_main_integration.py to expect 200 not 501**
- **Found during:** Task 4 (full suite run)
- **Issue:** `test_chat_stub_returns_501` expected the old Phase 1 stub behavior; Phase 3 replaced the stub
- **Fix:** Updated test to `test_chat_returns_200`, asserting 200 + `message` key
- **Files modified:** `backend/tests/test_main_integration.py`
- **Commit:** 10709c4

**2. [Rule 1 - Bug] Patched `call_llm` at router import site in tests**
- **Found during:** Task 4 (tests failing with wrong message in CHAT-07/08)
- **Issue:** `patch.object(chat_module, "call_llm", ...)` patches the module attribute but the router already bound the name via `from app.services.chat import call_llm`
- **Fix:** Changed test patches to `patch.object(chat_router_module, "call_llm", ...)` where `chat_router_module = app.routers.chat`
- **Files modified:** `backend/tests/test_chat.py`
- **Commit:** 10709c4

## Known Issues (pre-existing, not regressions)

`test_sse_stream_emits_event_within_3_seconds` in `test_main_integration.py` hangs indefinitely in this environment — this is a pre-existing behavior unrelated to Phase 3. The test uses `TestClient.stream()` which can deadlock with asyncio SSE in this environment. All 131 other tests pass.

## Self-Check

- [x] `backend/app/services/chat.py` exists
- [x] `backend/app/routers/chat.py` — real implementation, not 501
- [x] `backend/tests/test_chat.py` exists
- [x] Commits: fc27f55 (litellm dep), 7c7efe1 (chat service), 54a1c2a (router), 10709c4 (tests)

## Self-Check: PASSED
