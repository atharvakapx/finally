---
phase: 2
slug: portfolio-watchlist-apis
status: active
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-21
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3+ with pytest-asyncio 0.24+ (`asyncio_mode = auto`) |
| **Config file** | `backend/pyproject.toml` → `[tool.pytest.ini_options]` (`testpaths=["tests"]`) |
| **Quick run command** | `export PATH="$HOME/.local/bin:$PATH"; cd backend && uv run --extra dev pytest tests/test_portfolio.py tests/test_watchlist.py tests/test_snapshots.py -q` |
| **Full suite command** | `export PATH="$HOME/.local/bin:$PATH"; cd backend && uv run --extra dev pytest -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command above
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-T1 | 02-01 | 1 | PORT-02, PORT-03, PORT-05 | N/A (test scaffolding) | unit (RED) | `cd backend && uv run --extra dev pytest tests/test_portfolio.py --collect-only -q 2>&1 | grep -cE '^tests/test_portfolio\.py::'` >= 13 | ❌ W0 | ⬜ pending |
| 02-01-T2 | 02-01 | 1 | PORT-01, PORT-02, PORT-03, PORT-05 | BEGIN IMMEDIATE prevents concurrent double-spend | unit | `cd backend && uv run --extra dev pytest tests/test_portfolio.py -q` | ❌ W0 | ⬜ pending |
| 02-01-T3 | 02-01 | 1 | PORT-01, PORT-02, PORT-03, PORT-05 | JSON error envelope uses JSONResponse never HTTPException | integration | `cd backend && uv run --extra dev pytest tests/test_portfolio.py tests/test_main_integration.py -q` | ❌ W0 | ⬜ pending |
| 02-02-T1 | 02-02 | 1 | WATCH-01..05 | N/A (test scaffolding) | unit (RED) | `cd backend && uv run --extra dev pytest tests/test_watchlist.py --collect-only -q 2>&1 | grep -cE '^tests/test_watchlist\.py::'` >= 10 | ❌ W0 | ⬜ pending |
| 02-02-T2 | 02-02 | 1 | WATCH-01..05 | 50-cap enforced; ticker_held guard; format check | unit | `cd backend && uv run --extra dev pytest tests/test_watchlist.py -q` | ❌ W0 | ⬜ pending |
| 02-02-T3 | 02-02 | 1 | WATCH-01..05 | add_ticker called on market_source after DB insert | integration | `cd backend && uv run --extra dev pytest tests/test_watchlist.py tests/test_main_integration.py -q` | ❌ W0 | ⬜ pending |
| 02-03-T1 | 02-03 | 2 | SNAP-01, SNAP-02, PORT-04 | N/A (test scaffolding) | unit (RED) | `cd backend && uv run --extra dev pytest tests/test_snapshots.py --collect-only -q 2>&1 | grep -cE '^tests/test_snapshots\.py::'` >= 5 | ❌ W0 | ⬜ pending |
| 02-03-T2 | 02-03 | 2 | SNAP-02, PORT-04 | Snapshot written after every trade | unit | `cd backend && uv run --extra dev pytest tests/test_snapshots.py -q` | ❌ W0 | ⬜ pending |
| 02-03-T3 | 02-03 | 2 | SNAP-01 | Counter increments on SSE connect, decrements on disconnect | integration | `cd backend && uv run --extra dev pytest tests/test_snapshots.py tests/test_main_integration.py -q` | ❌ W0 | ⬜ pending |
| 02-03-T4 | 02-03 | 2 | PORT-04 | /api/portfolio/history returns ordered snapshot series | integration | `cd backend && uv run --extra dev pytest tests/test_portfolio.py tests/test_snapshots.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_portfolio.py` — covers PORT-01..05 (incl. concurrency test using raw `threading.Thread` against `execute_trade` directly, proven pattern from `test_db.py`)
- [ ] `backend/tests/test_watchlist.py` — covers WATCH-01..05 (use a mock/spy `market_source` to assert `add_ticker`/`remove_ticker` calls)
- [ ] `backend/tests/test_snapshots.py` — covers SNAP-01/02 (inject small interval or mock `asyncio.sleep`; assert no snapshot when counter==0; assert counter lifecycle in `_generate_events`)
- [ ] Shared fixtures in `backend/tests/conftest.py`: per-test temp DB (`tmp_path` + `importlib.reload(app.db)` pattern from `test_db.py`/`test_main_integration.py`) and pre-warmed `PriceCache` fixture

*Existing infrastructure covers framework — pytest/pytest-asyncio/httpx already installed.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-21
