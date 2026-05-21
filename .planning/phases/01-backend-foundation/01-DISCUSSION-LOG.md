# Phase 1: Backend Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-21
**Phase:** 1-Backend Foundation
**Areas discussed:** DB init mechanism, App module scaffold, Schema approach, Static placeholder

---

## DB Init Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| On lifespan startup | DB init runs when the FastAPI app starts. Health check always works. Predictable — no per-request checks needed. | ✓ |
| Lazy on first data request | Matches the spec's 'lazy init' language. Health check works without touching DB. Middleware fires init on first /api/* call that needs DB. | |
| Lazy on any first request | First request (including health check) triggers init. Most literal reading of spec. | |

**User's choice:** On lifespan startup

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — check tables and seed if empty | CREATE TABLE IF NOT EXISTS + INSERT OR IGNORE. Safe to run every startup, idempotent. | ✓ |
| Only if DB file doesn't exist | Skip init entirely if finally.db already exists. Could leave a partially-initialized DB in a bad state. | |
| You decide | Claude picks the safer option (idempotent seed check). | |

**User's choice:** Yes — idempotent seed check on every startup

---

## App Module Scaffold

| Option | Description | Selected |
|--------|-------------|----------|
| Full router structure now | Create backend/app/routers/ with portfolio.py, watchlist.py, chat.py as stubs + health.py. Establishes the pattern once. | ✓ |
| Minimal — only what Phase 1 needs | Just backend/app/main.py with health check inline. Phase 2 creates routers/ when it needs it. | |
| Single routers.py | All routes in one file. Simpler for now, refactor later. | |

**User's choice:** Full router structure now

---

| Option | Description | Selected |
|--------|-------------|----------|
| asynccontextmanager lifespan | Modern FastAPI pattern. Single function, yield separates startup from shutdown. Best for adding Phase 2 snapshot cadence task. | ✓ |
| on_event handlers (deprecated) | Still works but deprecated in FastAPI 0.93+. | |
| You decide | Claude picks asynccontextmanager. | |

**User's choice:** asynccontextmanager lifespan

---

| Option | Description | Selected |
|--------|-------------|----------|
| app.state for shared objects | Store PriceCache + MarketDataSource on app.state during lifespan. Clean, testable, no globals. | ✓ |
| Module-level globals | Global singletons. Simpler code but harder to test and at odds with existing no-globals pattern. | |
| Full FastAPI Depends() everywhere | Most idiomatic but more boilerplate for Phase 1. | |

**User's choice:** app.state for shared objects (PriceCache, MarketDataSource)

---

## Schema Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Pure Python CREATE TABLE IF NOT EXISTS | Schema defined as Python strings in backend/app/db.py. No separate SQL files. Everything in one place. | ✓ |
| SQL file(s) loaded at runtime | backend/db/schema.sql loaded and executed at startup. Spec mentions this pattern. Clearer separation but adds file I/O. | |
| Both — SQL files + Python runner | schema.sql for readability, Python reads and executes it. More complex, two things to keep in sync. | |

**User's choice:** Pure Python CREATE TABLE IF NOT EXISTS

---

| Option | Description | Selected |
|--------|-------------|----------|
| backend/app/db.py — single flat file | All DB logic in one module: init_db(), get_db() context manager, schema strings. Simple, co-located with app. | ✓ |
| backend/app/db/ package | More structure upfront. Might be premature for 6 tables. | |
| backend/db/ — outside app/ | Matches spec's mention of backend/db/. Separates concerns but adds import distance. | |

**User's choice:** backend/app/db.py — single flat file

---

## Static Placeholder

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal placeholder HTML | A backend/static/ dir with a single index.html. Phase 4 replaces it with the real Next.js export. | ✓ |
| Empty static dir — mount but serve nothing | Non-API routes return 404. Clean but / would fail a curl test. | |
| Skip static serving in Phase 1 | Don't mount StaticFiles yet. Phase 4 adds the mount. But success criterion 4 requires serving /*. | |

**User's choice:** Minimal placeholder HTML

---

| Option | Description | Selected |
|--------|-------------|----------|
| backend/static/ — FastAPI serves from there | Phase 1 puts placeholder here. Phase 4's Dockerfile copies Next.js export into this directory. Mount path stays the same. | ✓ |
| frontend/out/ — where next export outputs | Works in production but doesn't exist during Phase 1. | |
| A configurable path via env var | STATIC_DIR env var. Flexible but adds complexity Phase 1 doesn't need. | |

**User's choice:** backend/static/ — consistent across all phases

---

## Claude's Discretion

- Health check response shape: `{"status": "ok"}` as specified (no variation)
- DB connection management: stdlib `sqlite3` with context manager — no ORM
- Logging: `logging.getLogger(__name__)` per module, INFO level (matches existing market subsystem)

## Deferred Ideas

None — discussion stayed within phase scope.
