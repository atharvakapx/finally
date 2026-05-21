# Phase 1: Backend Foundation - Context

**Gathered:** 2026-05-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the existing `backend/app/market/` subsystem into a running FastAPI application: lifespan startup/shutdown, SQLite lazy initialization (run at startup, idempotent), health check endpoint, and static file serving with a placeholder page. No portfolio, watchlist, or chat endpoints — those are Phase 2/3.

</domain>

<decisions>
## Implementation Decisions

### DB Initialization
- **D-01:** DB initializes during **lifespan startup** (not lazy per-request). The health check is reliable from the first request with no per-request init checks needed.
- **D-02:** Init is **idempotent**: `CREATE TABLE IF NOT EXISTS` for all 6 tables + `INSERT OR IGNORE` for seed data. Safe to run on every startup — preserves existing data, seeds only if missing.
- **D-03:** DB module lives at **`backend/app/db.py`** — single flat file with `init_db()`, `get_db()` context manager, and all schema strings. No SQL files, no package structure.

### App Module Structure
- **D-04:** Scaffold the **full router structure in Phase 1**: `backend/app/routers/health.py`, `portfolio.py`, `watchlist.py`, `chat.py`. Phase 2/3 fill in portfolio/watchlist/chat; Phase 1 only implements health. Sets the code pattern for the whole project.
- **D-05:** Use **`@asynccontextmanager` lifespan** (modern FastAPI pattern). Single function with `yield` separating startup from shutdown. Phase 2's snapshot cadence task plugs in naturally here.
- **D-06:** **`app.state`** holds shared objects: `PriceCache`, `MarketDataSource`. Router factories (like the existing `create_stream_router`) receive them explicitly. No module-level globals — consistent with the existing market subsystem pattern.

### Schema Approach
- **D-07:** Schema defined as **pure Python `CREATE TABLE IF NOT EXISTS` strings** in `backend/app/db.py`. No SQL files to load from disk. All DB logic co-located in one module.

### Static File Serving
- **D-08:** Phase 1 creates **`backend/static/`** with a minimal placeholder `index.html` ("Frontend coming soon"). FastAPI mounts `StaticFiles` at `/*` from this directory.
- **D-09:** Phase 4's Dockerfile copies the Next.js export output into `backend/static/`, replacing the placeholder. The FastAPI mount path and directory name stay unchanged across phases.

### Claude's Discretion
- Health check response shape: `{"status": "ok"}` as specified in ROADMAP.md — no variation needed.
- DB connection management: standard `sqlite3` from stdlib with a context manager in `get_db()`. No ORM, no third-party DB library.
- Logging: `logging.getLogger(__name__)` per module, INFO level, matching the existing market subsystem pattern.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Market Data Subsystem (existing, complete — do not reimplement)
- `backend/app/market/__init__.py` — Public exports: `PriceUpdate`, `PriceCache`, `MarketDataSource`, `create_market_data_source`, `create_stream_router`
- `backend/app/market/factory.py` — `create_market_data_source(price_cache)` factory; reads `MASSIVE_API_KEY` from env
- `backend/app/market/stream.py` — `create_stream_router(price_cache)` router factory; the SSE endpoint is already implemented here
- `backend/app/market/cache.py` — `PriceCache` — the thread-safe in-memory store all downstream code reads from
- `backend/market_data_demo.py` — Reference example of how to wire PriceCache + SimulatorDataSource together in a standalone script

### Project Spec
- `planning/PLAN.md` §3 (Architecture), §7 (Database), §8 (API Endpoints), §5 (Environment Variables) — canonical contract for all backend behavior
- `.planning/REQUIREMENTS.md` — CORE-01 through CORE-05, DB-01 through DB-05 are Phase 1's requirement set
- `.planning/ROADMAP.md` — Phase 1 success criteria (5 items)

### Config / Environment
- `.env.example` (to be created in Phase 5, but documented in `planning/PLAN.md` §5) — `OPENAI_API_KEY`, `MASSIVE_API_KEY`, `LLM_MOCK`
- `backend/pyproject.toml` — Python project config, existing deps (fastapi, uvicorn, pydantic, python-dotenv, numpy, massive)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `create_market_data_source(price_cache: PriceCache) -> MarketDataSource` — factory that reads `MASSIVE_API_KEY` and returns either `SimulatorDataSource` or `MassiveDataSource`. Phase 1 calls this in lifespan startup.
- `create_stream_router(price_cache: PriceCache) -> APIRouter` — ready-to-include SSE router. Register it in `main.py` with `app.include_router(create_stream_router(cache), prefix="/api")`.
- `backend/app/market/seed_prices.py` — `SEED_PRICES` dict with realistic prices for the 10 default tickers. Reference this (or the same ticker list) when seeding the watchlist table.

### Established Patterns
- **Router factory pattern**: `create_stream_router(price_cache)` — Phase 1's `backend/app/routers/health.py` can be a simple module (no closure needed), but portfolio/watchlist/chat routers should follow the factory pattern once they need DB/cache access.
- **No module-level globals**: `PriceCache` and `MarketDataSource` are created in lifespan and stored on `app.state`. Match this in the new `db.py` — no module-level DB connection.
- **Error handling in background loops**: `try/except Exception` with `logger.exception()` — simulator and Massive client both do this. Follow the same pattern in any background tasks added in Phase 1.
- **Asyncio tasks**: `SimulatorDataSource._run_loop()` runs as an asyncio `Task`. Store the task handle in `app.state` or as a local in the lifespan function so it can be cancelled on shutdown.

### Integration Points
- `app.include_router(create_stream_router(app.state.price_cache), prefix="/api")` — wire the SSE router in `main.py` after creating the cache in lifespan
- `StaticFiles` mount at `"/"` with `backend/static/` as the directory — must be registered AFTER all `/api/*` routes so API routes take priority
- `python-dotenv` (`load_dotenv()`) — call at the top of `main.py` before reading any env vars

</code_context>

<specifics>
## Specific Ideas

- Default tickers for DB seed: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX (from `planning/PLAN.md` §7 and consistent with `backend/app/market/seed_prices.py`)
- Placeholder `index.html` at `backend/static/index.html` — simple dark-themed page saying "FinAlly — Frontend coming in Phase 4"
- `backend/app/routers/` stub files for portfolio, watchlist, chat should return `{"status": "not implemented"}` or a `501` so the app starts cleanly without broken imports

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 1-Backend Foundation*
*Context gathered: 2026-05-21*
