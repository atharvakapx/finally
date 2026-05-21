---
phase: 02-portfolio-watchlist-apis
verified: 2026-05-21T16:59:24Z
status: passed
score: 12/12
overrides_applied: 0
---

# Phase 2: Portfolio & Watchlist APIs — Verification Report

**Phase Goal:** A user (or a future LLM caller) can manage their watchlist and execute trades against live prices, with cash, positions, and portfolio snapshots updating consistently.
**Verified:** 2026-05-21T16:59:24Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `GET /api/portfolio` returns cash, every position with live price and unrealized P&L, and a total portfolio value that matches `cash + Σ(qty × price)` | VERIFIED | `build_portfolio_view` in `services/portfolio.py:40-80` computes exact formula; `test_get_portfolio_total_matches_cache` passes with cash+qty*price assertion |
| 2 | Buying via `POST /api/portfolio/trade` debits cash at the cache's current price, creates/updates position with weighted-average cost, refuses `400 insufficient_cash` when cash would go negative, concurrent buys protected by `BEGIN IMMEDIATE` | VERIFIED | `execute_trade` uses `get_db_immediate()` at line 107; concurrent test `test_concurrent_buys_serialize` PASSED — exactly 1 success, 1 `insufficient_cash` |
| 3 | Selling debits shares, credits cash, removes position when quantity hits zero, refuses `400 insufficient_shares` when oversold | VERIFIED | `execute_trade` sell path lines 138-161; full-sell DELETE at line 153; `test_full_sell_deletes_position` and `test_sell_oversold` PASSED |
| 4 | `POST /api/watchlist` and `DELETE /api/watchlist/{ticker}` enforce regex format, 50-ticker cap, held-position guard with documented `400` codes; adds immediately seed the ticker into the active data source | VERIFIED | `TICKER_RE = re.compile(r"^[A-Z]{1,5}$")`, `WATCHLIST_CAP = 50` in `services/watchlist.py`; `await market_source.add_ticker(ticker)` at line 98 after DB write; all 6 watchlist tests PASSED |
| 5 | `GET /api/portfolio/history` returns a time series of snapshots; snapshot recorded after every trade and every 30s while at least one SSE client is connected; cadence task pauses when no client connected | VERIFIED | `record_snapshot` called in `routers/portfolio.py:60` post-commit; `snapshot_loop` gated on `sse_clients.count > 0` in `services/snapshots.py:97`; `ClientCounter` increments in `stream.py:72` and decrements in `finally` at line 111; `test_snapshot_after_trade`, `test_cadence_gated_on_clients`, `test_history_returns_series` all PASSED |

**Score: 5/5 roadmap truths verified**

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/services/portfolio.py` | `build_portfolio_view(price_cache)` and `execute_trade(price_cache, ticker, side, quantity)` | VERIFIED | Both functions defined; `execute_trade` uses `get_db_immediate`; all SQL parameterized with `?` |
| `backend/app/routers/portfolio.py` | `GET /api/portfolio`, `POST /api/portfolio/trade`, `GET /api/portfolio/history` routes | VERIFIED | `create_portfolio_router` factory; all 3 routes implemented; no `HTTPException` |
| `backend/app/services/watchlist.py` | `get_watchlist_items`, `add_ticker_to_watchlist`, `remove_ticker_from_watchlist` + `TICKER_RE` + `WATCHLIST_CAP = 50` | VERIFIED | All 3 service functions present; `TICKER_RE` and `WATCHLIST_CAP = 50` at module scope |
| `backend/app/routers/watchlist.py` | `create_watchlist_router` with GET/POST/DELETE routes, async handlers | VERIFIED | All 3 routes present; POST and DELETE are `async def`; no `HTTPException` |
| `backend/app/services/snapshots.py` | `ClientCounter`, `record_snapshot(price_cache)`, `snapshot_loop(app)` | VERIFIED | All 3 defined; `ClientCounter` uses `threading.Lock` with `max(0, ...)` clamp |
| `backend/app/market/stream.py` | Additive SSE counter increment/decrement — loop body unchanged | VERIFIED | `counter` param added to `_generate_events`; `counter.increment()` before first yield; `counter.decrement()` in `finally` block; `HEARTBEAT_INTERVAL` and version-diff loop unchanged |
| `backend/tests/test_portfolio.py` | 14 PORT-01/02/03/05 tests including concurrency | VERIFIED | 14/14 PASSED; `test_concurrent_buys_serialize` with `threading.Thread`; `execute_trade` imported inside test body |
| `backend/tests/test_watchlist.py` | 8 WATCH-01..05 tests with AsyncMock market source spy | VERIFIED | 8/8 PASSED; `mock_source.add_ticker = AsyncMock()` confirmed |
| `backend/tests/test_snapshots.py` | SNAP-01/02 + PORT-04 + counter lifecycle tests | VERIFIED | 6/6 PASSED; `TestClientCounter`, `TestRecordSnapshot`, `TestSnapshotAfterTrade`, `TestSnapshotLoop`, `TestHistory` |

**Score: 9/9 artifacts — all VERIFIED**

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `routers/portfolio.py` | `services/portfolio.py` | `from app.services.portfolio import build_portfolio_view, execute_trade` | WIRED | Line 13 of `routers/portfolio.py` |
| `services/portfolio.py` | `app.db.get_db_immediate` | `BEGIN IMMEDIATE` write transaction in `execute_trade` | WIRED | Lines 11 + 107 — imported and used |
| `services/portfolio.py` | `price_cache.get_price` | Fill price + valuation from in-memory cache | WIRED | `price_cache.get_price(ticker)` at lines 44 and 102 |
| `routers/watchlist.py` | `services/watchlist.py` | `from app.services.watchlist import get_watchlist_items, add_ticker_to_watchlist, remove_ticker_from_watchlist` | WIRED | Lines 11-15 of `routers/watchlist.py` |
| `services/watchlist.py` | `market_source.add_ticker` / `remove_ticker` | Awaited coroutine after DB write | WIRED | Lines 98 and 129 — `await market_source.add_ticker(ticker)` / `await market_source.remove_ticker(ticker)` |
| `app/main.py` | `app.state.session_baselines` | Shared in-memory baseline map created in lifespan | WIRED | `app.state.session_baselines = {}` at line 39 of `main.py` |
| `app/main.py` | `services/snapshots.py` | `ClientCounter` on `app.state.sse_clients` + `asyncio.create_task(snapshot_loop(app))` | WIRED | Lines 19-41 of `main.py` |
| `app/market/stream.py` | `app.state.sse_clients` | `counter.increment` on connect / `counter.decrement` in `finally` | WIRED | Lines 41-43 (get from `app.state`), 72 (increment), 110-111 (finally decrement) |
| `routers/portfolio.py` | `services/snapshots.record_snapshot` | Called after successful trade (SNAP-02) | WIRED | Line 60 of `routers/portfolio.py` — inside success branch only |

**Score: 9/9 key links — all WIRED**

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `GET /api/portfolio` | `cash`, `positions`, `total_value` | `build_portfolio_view` → `users_profile` + `positions` tables + `PriceCache.get_price()` | Yes — real DB query + live cache prices | FLOWING |
| `POST /api/portfolio/trade` | `cash_balance`, `position`, `trade` | `execute_trade` → `BEGIN IMMEDIATE` transaction reading and writing `users_profile` + `positions` + `trades` tables | Yes — real atomic DB read-write | FLOWING |
| `GET /api/portfolio/history` | `[{total_value, recorded_at}]` | `portfolio_snapshots` table, `ORDER BY recorded_at ASC` | Yes — real DB query ordered ascending | FLOWING |
| `GET /api/watchlist` | `[{ticker, price, session_change_pct, added_at}]` | `watchlist` table + `PriceCache.get_price()` + `session_baselines` dict | Yes — live prices + lazy baseline tracking | FLOWING |
| `POST /api/watchlist` | persisted ticker | `watchlist` table INSERT + `await market_source.add_ticker(ticker)` | Yes — real DB insert + market source wired | FLOWING |
| `record_snapshot` | `total_value` | `users_profile` cash + `positions` quantities × `PriceCache` prices | Yes — real computation from DB + cache | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 28 phase 2 tests pass | `uv run pytest tests/test_portfolio.py tests/test_watchlist.py tests/test_snapshots.py -v` | 28/28 PASSED, 0 failures | PASS |
| No SQL injection in service files | `grep -n "f\".*WHERE\|f\".*INSERT"` across all service files | No matches | PASS |
| No HTTPException used | `grep -rn "HTTPException"` across routers and services | No matches | PASS |
| No 501 stubs remaining in routers | `grep -rn "501"` in portfolio/watchlist routers | No matches | PASS |
| `execute_trade` uses `get_db_immediate` | `grep -n "get_db_immediate" backend/app/services/portfolio.py` | Imported line 11, used line 107 | PASS |
| `record_snapshot` called in success branch only | `grep -n "record_snapshot" backend/app/routers/portfolio.py` | Line 60, inside `else` (non-tuple) branch only | PASS |
| `counter.increment/decrement` in stream.py | `grep -n "counter" backend/app/market/stream.py` | Increment line 72, decrement in `finally` lines 110-111 | PASS |

---

### Probe Execution

Step 7c: No probe scripts declared in plan files for this phase. No `scripts/*/tests/probe-*.sh` found. SKIPPED.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| PORT-01 | 02-01 | `GET /api/portfolio` returns cash, positions with live P&L, total value | SATISFIED | `build_portfolio_view` returns `{cash, positions[], total_value}`; test_get_portfolio_total_matches_cache PASSED |
| PORT-02 | 02-01 | `POST /api/portfolio/trade` with buy validates sufficient cash | SATISFIED | `execute_trade` checks `cost > cash`, returns `insufficient_cash` 400; test_buy_insufficient_cash PASSED |
| PORT-03 | 02-01 | `POST /api/portfolio/trade` with sell validates sufficient shares | SATISFIED | `execute_trade` checks `quantity > held_qty`, returns `insufficient_shares` 400; test_sell_oversold PASSED |
| PORT-04 | 02-03 | `GET /api/portfolio/history` returns snapshot time series | SATISFIED | `get_history` queries `portfolio_snapshots ORDER BY recorded_at ASC`; test_history_returns_series PASSED |
| PORT-05 | 02-01 | Trades fill at current `PriceCache` price | SATISFIED | `execute_trade` reads `price_cache.get_price(ticker)` before transaction; test_trade_fills_at_cache_price PASSED |
| WATCH-01 | 02-02 | `GET /api/watchlist` returns tickers with latest prices and session Δ% | SATISFIED | `get_watchlist_items` returns `{ticker, price, session_change_pct, added_at}`; test_session_change_baseline PASSED |
| WATCH-02 | 02-02 | `POST /api/watchlist` validates format `^[A-Z]{1,5}$`, returns `400 invalid_ticker` | SATISFIED | `TICKER_RE = re.compile(r"^[A-Z]{1,5}$")`; test_invalid_ticker_format PASSED |
| WATCH-03 | 02-02 | `DELETE /api/watchlist/{ticker}` returns `400 ticker_held` if position held | SATISFIED | `remove_ticker_from_watchlist` checks `positions.quantity > 0`; test_remove_held_ticker_blocked PASSED |
| WATCH-04 | 02-02 | Watchlist capped at 50 tickers; `POST` returns `400 watchlist_full` | SATISFIED | `WATCHLIST_CAP = 50`; test_watchlist_cap PASSED |
| WATCH-05 | 02-02 | Adding ticker seeds it in active data source immediately | SATISFIED | `await market_source.add_ticker(ticker)` after DB write; test_add_seeds_source PASSED via AsyncMock spy |
| SNAP-01 | 02-03 | Snapshot recorded every 30s while at least one SSE client connected; pauses when idle | SATISFIED | `snapshot_loop` gated on `sse_clients.count > 0`; `TestSnapshotLoop.test_cadence_gated_on_clients` proves 0-row delta at count==0 and +1 row at count>0 |
| SNAP-02 | 02-03 | Snapshot recorded immediately after each trade execution | SATISFIED | `record_snapshot` called at `routers/portfolio.py:60` in success branch after `execute_trade`; test_snapshot_after_trade PASSED |

**All 12 requirements: SATISFIED**

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | — |

No TBD, FIXME, XXX, or placeholder patterns found in any phase 2 files. No SQL injection patterns (f-string SQL). No HTTPException usage. No stub returns remaining.

---

### Human Verification Required

None. All phase 2 behaviors are programmably verifiable via the test suite and static analysis. The phase delivers only backend REST APIs — no UI, no visual output, no external service integrations requiring live keys.

---

## Gaps Summary

No gaps. All 12 requirements (PORT-01–05, WATCH-01–05, SNAP-01–02) are satisfied by substantive, wired, data-flowing implementations. The full test suite of 28 tests passes with 0 failures.

**Phase 2 goal is fully achieved.**

---

_Verified: 2026-05-21T16:59:24Z_
_Verifier: Claude (gsd-verifier)_
