---
phase: 02-portfolio-watchlist-apis
plan: "02"
subsystem: backend-watchlist
tags: [watchlist, api, tdd, sqlite, session-baseline]
dependency_graph:
  requires:
    - 02-01  # DB schema, main.py lifespan, PriceCache wired in app.state
  provides:
    - GET /api/watchlist (prices + session Δ%)
    - POST /api/watchlist (validated, capped, streamed)
    - DELETE /api/watchlist/{ticker} (held-ticker guard)
    - app.state.session_baselines dict (process-local baseline map)
  affects:
    - 02-03  # snapshot service reads watchlist; uses same app.state.market_source
    - Phase 3  # LLM (CHAT-04) calls these same endpoints for watchlist management
    - Phase 4  # Frontend watchlist panel calls GET/POST/DELETE /api/watchlist
tech_stack:
  added: []
  patterns:
    - TDD red-green cycle (test → service → router)
    - Router factory pattern (create_watchlist_router keeps stub signature)
    - Flat JSONResponse error envelope (no HTTPException)
    - Lazy session-baseline map (process-local, first-observed price)
    - Async service functions await market_source AFTER DB write (WATCH-05)
key_files:
  created:
    - backend/app/services/__init__.py
    - backend/app/services/watchlist.py
    - backend/tests/test_watchlist.py
  modified:
    - backend/app/routers/watchlist.py
    - backend/app/main.py
    - backend/tests/test_main_integration.py
decisions:
  - "get_watchlist_items is plain def (not async): only sync DB reads + cache lookups; router calls it without await"
  - "await market_source.add_ticker/remove_ticker placed AFTER the DB block, not inside the with get_db() context, to avoid holding a DB connection during an async coroutine call"
  - "Session Δ% baseline stored in app.state.session_baselines (plain dict); never persisted — resets on server restart by design (PLAN.md §6)"
  - "Updated test_main_integration.py test_watchlist_stubs_return_501 → test_watchlist_endpoints_live since stubs are now replaced by real implementations"
metrics:
  duration: "7 minutes"
  completed_date: "2026-05-21T16:27:35Z"
  tasks_completed: 3
  files_changed: 6
---

# Phase 2 Plan 02: Watchlist API Summary

**One-liner:** Full watchlist CRUD (GET/POST/DELETE) with live prices, session Δ% baseline tracking, format + cap validation, and async market source synchronization via TDD red-green cycle.

## What Was Built

Three tasks delivering WATCH-01..05:

1. **Task 1 (RED):** `backend/tests/test_watchlist.py` — 8 failing tests with AsyncMock market source spy covering all success + rejection paths for GET/POST/DELETE watchlist endpoints.

2. **Task 2 (GREEN - service):** `backend/app/services/watchlist.py` — pure-Python service layer:
   - `get_watchlist_items(price_cache, session_baselines)` — sync; lazy first-observed baseline
   - `add_ticker_to_watchlist(ticker, market_source)` — async; format validation + cap + await add_ticker
   - `remove_ticker_from_watchlist(ticker, market_source)` — async; held-ticker guard + await remove_ticker
   - `backend/app/main.py` — `app.state.session_baselines = {}` added before `yield` in lifespan

3. **Task 3 (GREEN - router):** `backend/app/routers/watchlist.py` — live routes wired to service:
   - GET: calls `get_watchlist_items` synchronously
   - POST: async handler awaits `add_ticker_to_watchlist`
   - DELETE: async handler awaits `remove_ticker_from_watchlist`
   - All errors via flat `JSONResponse({"error": ..., "message": ...})` — no HTTPException

## Test Results

```
8 passed, 8 warnings in 1.15s
```

All WATCH-01..05 requirements verified by the test suite.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Obsolete 501-stub watchlist assertion in test_main_integration.py**
- **Found during:** Task 3 verification
- **Issue:** `test_watchlist_stubs_return_501` asserted watchlist endpoints return 501 — correct for Phase 1 stubs, but broken once real implementation landed. The plan output section explicitly noted this would become obsolete.
- **Fix:** Renamed test to `test_watchlist_endpoints_live`; updated assertion to verify GET /api/watchlist returns 200 with 10 seeded items.
- **Files modified:** `backend/tests/test_main_integration.py`
- **Commit:** f4e6af4 (included in Task 3 commit)

## TDD Gate Compliance

| Gate | Commit | Type |
|------|--------|------|
| RED  | b973ab7 | `test(02-02): add failing watchlist test suite (RED)` |
| GREEN (service) | f58d2fc | `feat(02-02): implement watchlist service + wire session_baselines in main.py` |
| GREEN (router) | f4e6af4 | `feat(02-02): wire GET/POST/DELETE watchlist routes to service (GREEN)` |

## Known Stubs

None. All watchlist endpoints return live data backed by SQLite and the PriceCache.

## Threat Surface Scan

No new network endpoints or auth paths beyond those declared in the plan's threat model. All threats mitigated:

| Threat | Mitigation | Status |
|--------|-----------|--------|
| T-02-W1 Tampering (SQL injection) | Parameterized `?` SQL, ticker uppercased + regex-validated | Mitigated |
| T-02-W2 Invalid ticker format | `^[A-Z]{1,5}$` fullmatch → `invalid_ticker` 400 | Mitigated |
| T-02-W3 Unbounded watchlist (DoS) | WATCHLIST_CAP=50 → `watchlist_full` 400 | Mitigated |
| T-02-W4 Removing held ticker | `positions.quantity > 0` guard → `ticker_held` 400 | Mitigated |
| T-02-SC Package installs | No new packages required | N/A |

## Self-Check
