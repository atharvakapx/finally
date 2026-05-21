---
plan: 01-03
phase: 01-backend-foundation
status: complete
completed_at: 2026-05-21

requires:
  - 01-01 (FastAPI app + stub routers)
  - 01-02 (SQLite DB layer + init_db in lifespan)
provides:
  - PriceCache module-scope instance wired into all router factories
  - SimulatorDataSource lifecycle managed in lifespan (start on boot, stop on shutdown)
  - GET /api/stream/prices SSE endpoint live and streaming
  - Stub routers (portfolio, watchlist, chat) registered at module scope
  - Full Phase 1 integration test suite (8 tests)

requirements-completed:
  - CORE-02
  - CORE-05
---

# Plan 01-03: Market Data + Router Scaffold — Summary

**PriceCache wired at module scope, SimulatorDataSource started in lifespan, SSE stream live, stub routers registered, integration test suite passing**

## Accomplishments

- `backend/app/main.py` fully rewritten to Phase 1 final state:
  - Module-scope `price_cache = PriceCache()` (no lifecycle; passed to router factories)
  - Lifespan startup: `init_db()` → `create_market_data_source(cache)` → `source.start()` → `app.state` assignments
  - Lifespan shutdown: `await source.stop()`
  - Router registration order: health → portfolio → watchlist → chat → stream (no extra `/api` prefix) → static mount LAST
- `backend/app/routers/portfolio.py`, `watchlist.py`, `chat.py` — factory-pattern stub routers returning 501
- `backend/tests/test_main_integration.py` — `TestPhase1Integration` with 8 tests:
  - health 200, portfolio/watchlist 501, chat 501
  - `SimulatorDataSource` used when no `MASSIVE_API_KEY`
  - PriceCache populated within 3 seconds
  - SSE stream emits `data:` lines with `text/event-stream` content-type
  - Static root served

## Test Results

- 93 total tests passing: 60 market + 9 db + 3 health + 8 integration + 13 other

## Key Files

- `backend/app/main.py` — Modified: full Phase 1 wiring
- `backend/app/routers/portfolio.py` — Stub router
- `backend/app/routers/watchlist.py` — Stub router
- `backend/app/routers/chat.py` — Stub router
- `backend/tests/test_main_integration.py` — New integration test suite

## Self-Check: PASSED

All must_haves verified:
- ✓ Lifespan constructs PriceCache, calls create_market_data_source(cache), awaits source.start()
- ✓ PriceCache and MarketDataSource stored on app.state
- ✓ PriceCache populated for all 10 default tickers within 3 seconds
- ✓ GET /api/stream/prices reachable, returns text/event-stream, emits events within 3s
- ✓ Lifespan shutdown awaits source.stop()
- ✓ Stub routers exist for portfolio, watchlist, chat — all return 501 with correct error shape
- ✓ MASSIVE_API_KEY absent → SimulatorDataSource used
