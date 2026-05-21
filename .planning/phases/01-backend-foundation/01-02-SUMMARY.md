---
phase: 01-backend-foundation
plan: 02
subsystem: database
tags: [sqlite, schema, seed, init_db, get_db, walking-skeleton]

# Dependency graph
requires:
  - 01-01 (FastAPI app with lifespan; routers package)
provides:
  - backend/app/db.py: init_db, get_db, get_db_immediate, DEFAULT_USER_ID, DEFAULT_CASH_BALANCE, DEFAULT_TICKERS
  - init_db() wired into lifespan startup in backend/app/main.py
  - 9-test suite covering schema creation, seed data, idempotence, commit/rollback, BEGIN IMMEDIATE serialization
affects:
  - 01-backend-foundation/plan-03 (market source plugs into same lifespan; test_health requires DB_PATH fixture)
  - 02-portfolio-watchlist (get_db and get_db_immediate are the canonical DB helpers for all write paths)
  - 03-ai-chat (chat_messages table consumed by Phase 3)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "init_db() idempotent via CREATE TABLE IF NOT EXISTS + INSERT OR IGNORE"
    - "get_db() context manager: commit on success, rollback on exception, always close"
    - "get_db_immediate() with isolation_level=None + explicit BEGIN IMMEDIATE for write-path serialization (DB-05)"
    - "Module-level _DB_PATH resolved once at import; tests override via monkeypatch.setenv + importlib.reload"
    - "conftest.py sets DB_PATH via os.environ.setdefault at module scope before any app import"

key-files:
  created:
    - backend/app/db.py
    - backend/tests/test_db.py
  modified:
    - backend/app/main.py
    - backend/tests/conftest.py

key-decisions:
  - "isolation_level=None on get_db_immediate() connection so Python autocommit layer does not interfere with explicit BEGIN IMMEDIATE / COMMIT / ROLLBACK"
  - "conftest.py uses os.environ.setdefault at module scope (not a fixture) so DB_PATH is set before app.db is first imported by test_health.py's module-level from app.main import app"
  - "test_db.py db_module fixture uses importlib.reload(app.db) after monkeypatch.setenv so each test gets a fresh _DB_PATH pointing to its own tmp file"

requirements-completed:
  - DB-01
  - DB-02
  - DB-03
  - DB-04
  - DB-05

# Metrics
duration: 8min
completed: 2026-05-21
---

# Phase 1 Plan 02: SQLite Layer Summary

**6-table SQLite schema with idempotent init_db(), commit/rollback get_db(), BEGIN IMMEDIATE get_db_immediate() for write serialization, wired into FastAPI lifespan, with 9-test coverage suite**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-21T11:21:00Z
- **Completed:** 2026-05-21T11:29:20Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `backend/app/db.py` created with all 6 tables, idempotent `init_db()`, `get_db()` context manager, and `get_db_immediate()` with BEGIN IMMEDIATE for write-path serialization
- `init_db()` wired as first statement in lifespan startup in `backend/app/main.py`
- 9 tests passing in `backend/tests/test_db.py`: table creation, seed data, idempotence, commit on success, rollback on exception, BEGIN IMMEDIATE in_transaction assertion, and concurrent writers serialization
- All Plan 01 health tests (3) still passing after DB integration
- `conftest.py` updated with module-scope `DB_PATH` default so health tests work outside Docker

## Task Commits

1. **Task 1: Create backend/app/db.py** — `df812c1` (feat)
2. **Task 2: Wire init_db into lifespan and add test suite** — `a31c444` (feat)

## Files Created/Modified

- `backend/app/db.py` — 194 lines; schema for 6 tables, _seed helper, init_db, get_db, get_db_immediate, module constants
- `backend/app/main.py` — Added `from app.db import init_db`; `init_db()` as first lifespan startup call
- `backend/tests/test_db.py` — 9 tests in 3 classes (TestInitDb, TestGetDb, TestGetDbImmediate)
- `backend/tests/conftest.py` — Added module-scope DB_PATH default pointing to tmpdir

## Decisions Made

- `isolation_level=None` on `get_db_immediate()` connections so Python's implicit transaction management does not interfere with the explicit `BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK` sequence
- `conftest.py` sets `DB_PATH` at module scope via `os.environ.setdefault` (not via a pytest fixture) because `test_health.py` imports `app.main` at module load time — a fixture would run too late to influence `_DB_PATH` in `app.db`
- `test_db.py` per-test isolation uses `monkeypatch.setenv` + `importlib.reload(app.db)` so each test gets its own fresh `_DB_PATH`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_health.py PermissionError when lifespan calls init_db()**
- **Found during:** Task 2 (running existing smoke tests after wiring init_db into lifespan)
- **Issue:** `test_health.py` creates a `TestClient(app)` which runs the lifespan; `init_db()` now fires during startup with `_DB_PATH=/app/db/finally.db`; `/app` does not exist outside Docker, causing `PermissionError: [Errno 13] Permission denied: '/app'`
- **Fix:** Added module-scope `os.environ.setdefault("DB_PATH", ...)` to `tests/conftest.py` pointing to a `tempfile.mkdtemp()` location. `setdefault` is used (not `os.environ[...] = ...`) so tests that supply their own `DB_PATH` via `monkeypatch` take precedence
- **Files modified:** `backend/tests/conftest.py`
- **Verification:** All 12 tests (3 health + 9 db) pass
- **Committed in:** `a31c444` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (bug)
**Impact on plan:** Necessary for test_health.py to remain green after init_db() was added to lifespan. No scope creep.

## Known Stubs

None — all exported symbols are fully implemented.

## Issues Encountered

None beyond the one auto-fixed deviation above.

## Next Phase Readiness

- `get_db()` and `get_db_immediate()` are ready for Phase 2 portfolio/watchlist routers
- `chat_messages` table is ready for Phase 3 LLM chat
- `portfolio_snapshots` table is ready for Phase 2 snapshot background task
- All 12 backend tests pass; codebase is in a clean, bootable state

---
*Phase: 01-backend-foundation*
*Completed: 2026-05-21*
