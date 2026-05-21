---
phase: 02-portfolio-watchlist-apis
plan: "03"
subsystem: backend-snapshots
tags: [portfolio-snapshots, sse-counter, asyncio, tdd, sqlite, background-task]
dependency_graph:
  requires:
    - 02-01  # execute_trade, GET /portfolio, DB schema (portfolio_snapshots table)
    - 02-02  # app.state.session_baselines, lifespan pattern established
  provides:
    - GET /api/portfolio/history (PORT-04) — ordered portfolio_snapshots time series
    - record_snapshot(price_cache) — computes cash + live positions, INSERTs snapshot row
    - ClientCounter — thread-safe SSE client counter (increment/decrement/clamp-at-0)
    - snapshot_loop(app) — 30s cadence task gated on sse_clients.count > 0 (SNAP-01)
    - SNAP-02: snapshot recorded immediately after every successful trade
  affects:
    - Phase 4 frontend — P&L chart uses GET /api/portfolio/history data
    - Phase 3 AI chat — trade execution now triggers snapshot via same route handler
tech_stack:
  added: []
  patterns:
    - TDD red-green cycle (test file first, service second, wiring third/fourth)
    - Thread-safe counter with threading.Lock (clamp-at-0 via max(0, ...))
    - asyncio background task with CancelledError guard (snapshot_loop)
    - Additive SSE hook (counter param, finally block — loop body unchanged)
    - Post-commit snapshot (record_snapshot called after execute_trade returns, not inside txn)
key_files:
  created:
    - backend/app/services/snapshots.py
    - backend/tests/test_snapshots.py
  modified:
    - backend/app/market/stream.py
    - backend/app/main.py
    - backend/app/routers/portfolio.py
    - backend/tests/test_main_integration.py
decisions:
  - "counter.increment() placed before first yield (before the try/except/finally loop) — counter tracks live connections from the moment the generator starts, not after retry line"
  - "record_snapshot uses two separate get_db() calls (read then write) — keeps post-commit semantics; the trade's BEGIN IMMEDIATE block has already committed before snapshot runs"
  - "snapshot_loop gates on sse_clients.count > 0 after asyncio.sleep(30), not before — first interval always waits 30s to avoid burst writes on startup"
  - "SSE test_sse_stream_emits_event_within_3_seconds hangs in this worktree environment regardless of plan changes (pre-existing env issue); all other integration tests pass"
metrics:
  duration: "~15 min"
  completed_date: "2026-05-21T16:55:25Z"
  tasks_completed: 4
  files_changed: 6
---

# Phase 2 Plan 03: Portfolio Snapshots + History Summary

**One-liner:** Thread-safe SSE client counter, 30s cadence snapshot task gated on active clients (SNAP-01), trade-triggered snapshot (SNAP-02), and live GET /api/portfolio/history endpoint (PORT-04) — all via TDD red-green cycle.

## What Was Built

Four tasks delivering SNAP-01, SNAP-02, PORT-04, and counter lifecycle:

1. **Task 1 (RED):** `backend/tests/test_snapshots.py` — 6 failing tests covering counter lifecycle, record_snapshot total_value math, SNAP-02 trade trigger, SNAP-01 cadence gate (count==0 vs count>0 row deltas), and PORT-04 ordered history + empty list.

2. **Task 2 (GREEN - service):** `backend/app/services/snapshots.py`:
   - `ClientCounter`: threading.Lock + `_count`; increment/decrement/count property; decrement clamps at 0 via `max(0, ...)`
   - `record_snapshot(price_cache)`: reads cash + positions with `get_db()`, computes total = cash + Σ(qty × live_price), INSERTs snapshot with second `get_db()`; skips positions with no cache price
   - `snapshot_loop(app)`: `await asyncio.sleep(30)` → `if sse_clients.count > 0: record_snapshot(...)` → `except asyncio.CancelledError: pass`

3. **Task 3 (wiring):** Additive edits to `stream.py` and `main.py`:
   - `_generate_events` accepts `counter=None`; calls `counter.increment()` before first yield; `finally:` calls `counter.decrement()` (existing HEARTBEAT_INTERVAL + version-diff loop body UNCHANGED)
   - `stream_prices` passes `getattr(request.app.state, "sse_clients", None)` as counter
   - `main.py` lifespan: creates `app.state.sse_clients = ClientCounter()` and `asyncio.create_task(snapshot_loop(app), name="snapshot-loop")`; cancels+awaits task on shutdown before `source.stop()`

4. **Task 4 (GREEN - router):** `backend/app/routers/portfolio.py`:
   - `execute_trade_route`: calls `record_snapshot(request.app.state.price_cache)` after successful trade (not on tuple/error results) — SNAP-02
   - `get_history`: replaces 501 stub with `SELECT total_value, recorded_at ... ORDER BY recorded_at ASC`; returns list of `{total_value, recorded_at}` dicts

## Test Results

```
120 passed, 1 deselected (SSE stream hang — pre-existing env issue)
```

- `tests/test_snapshots.py`: 6/6 — counter lifecycle, record_snapshot math, SNAP-02 after trade, SNAP-01 gate, PORT-04 ordered series + empty list
- `tests/test_portfolio.py`: 14/14 — unchanged from 02-01
- `tests/test_main_integration.py`: 7/8 — SSE stream test hangs pre-existing (confirmed by reverting changes and retesting)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Obsolete 501-stub history assertion in test_main_integration.py**
- **Found during:** Task 4 verification
- **Issue:** `test_portfolio_history_stub_returns_501` asserted `/api/portfolio/history` returns 501 — correct before Task 4, broken once the real implementation landed. The plan output section explicitly noted this would become obsolete.
- **Fix:** Renamed test to `test_portfolio_history_endpoint_live`; updated assertion to verify GET /api/portfolio/history returns 200 with a list.
- **Files modified:** `backend/tests/test_main_integration.py`
- **Commit:** `0a81934` (included in Task 4 commit)

### Environment Notes

The `test_sse_stream_emits_event_within_3_seconds` test hangs (no output, runs indefinitely) in this worktree environment. This was confirmed to be pre-existing: reverting `stream.py` to the unmodified version and running the same test still hangs. All 120 other tests pass. The SSE counter logic is confirmed correct by `TestClientCounter` (counter lifecycle) and `TestSnapshotLoop` (gate condition).

## TDD Gate Compliance

| Gate | Commit | Type |
|------|--------|------|
| RED  | c11ade4 | `test(02-03): add failing snapshot + history + counter test suite (RED)` |
| GREEN (service) | 2f0ef11 | `feat(02-03): implement snapshots service (ClientCounter, record_snapshot, snapshot_loop)` |
| GREEN (wiring) | 3603eca | `feat(02-03): wire SSE counter into stream.py + snapshot cadence task in lifespan` |
| GREEN (router) | 0a81934 | `feat(02-03): wire SNAP-02 into trade route + implement GET /portfolio/history (GREEN)` |

## Known Stubs

None. All snapshot-related endpoints return live data:
- `GET /api/portfolio/history` — real query, real data
- `record_snapshot` — real DB INSERT with live PriceCache values

## Threat Surface Scan

No new network endpoints beyond those in the plan's threat model. All mitigations applied:

| Threat | Mitigation | Status |
|--------|-----------|--------|
| T-02-S1 DoS (disk exhaustion) | snapshot_loop gates on `sse_clients.count > 0` (SNAP-01) | Mitigated |
| T-02-S2 Tampering (counter underflow) | `decrement()` clamps at 0 via `max(0, ...)` under Lock | Mitigated |
| T-02-S3 Tampering (SQL injection) | Parameterized `?` SQL only in record_snapshot + get_history | Mitigated |
| T-02-S4 DoS (trade lock contention) | record_snapshot runs AFTER trade commit, not inside BEGIN IMMEDIATE | Mitigated |

## Self-Check
