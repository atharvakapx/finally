# Phase 1: Backend Foundation - Pattern Map

**Mapped:** 2026-05-21
**Files analyzed:** 7
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/main.py` | config/entrypoint | event-driven (lifespan) | `backend/market_data_demo.py` | role-match (startup/shutdown wiring) |
| `backend/app/db.py` | utility | CRUD | `backend/app/market/cache.py` | partial (in-process resource, init on startup) |
| `backend/app/routers/health.py` | route | request-response | `backend/app/market/stream.py` | role-match (FastAPI APIRouter module) |
| `backend/app/routers/portfolio.py` | route | CRUD | `backend/app/market/stream.py` | role-match (router factory pattern) |
| `backend/app/routers/watchlist.py` | route | CRUD | `backend/app/market/stream.py` | role-match (router factory pattern) |
| `backend/app/routers/chat.py` | route | request-response | `backend/app/market/stream.py` | role-match (router factory pattern) |
| `backend/static/index.html` | static asset | — | none | no analog |

---

## Pattern Assignments

### `backend/app/main.py` (config/entrypoint, event-driven lifespan)

**Analog:** `backend/market_data_demo.py` (startup/shutdown wiring) + `backend/app/market/simulator.py` (asyncio task lifecycle)

**Imports pattern** — follow `from __future__ import annotations`, `logging.getLogger(__name__)`, dotenv load before env reads:
```python
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.market import PriceCache, create_market_data_source, create_stream_router
from app.db import init_db
from app.routers import health, portfolio, watchlist, chat

load_dotenv()  # Must be first — before any os.environ reads

logger = logging.getLogger(__name__)
```

**Lifespan pattern** — `@asynccontextmanager` with `yield`; store shared objects on `app.state`; cancel task on shutdown. Source: `backend/app/market/simulator.py` lines 219-239 (start/stop) + `backend/market_data_demo.py` lines 207-266 (run():
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    init_db()

    cache = PriceCache()
    source = create_market_data_source(cache)

    default_tickers = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
                       "NVDA", "META", "JPM", "V", "NFLX"]
    await source.start(default_tickers)

    app.state.price_cache = cache
    app.state.market_source = source

    logger.info("FinAlly backend started")
    yield

    # --- shutdown ---
    await source.stop()
    logger.info("FinAlly backend stopped")


app = FastAPI(title="FinAlly", lifespan=lifespan)
```

**Router registration pattern** — include_router with prefix, stream router via factory; StaticFiles AFTER all /api routes:
```python
app.include_router(health.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(watchlist.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(create_stream_router(app.state.price_cache), prefix="/api")

# StaticFiles mount LAST so /api/* routes take priority
app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

Note: `create_stream_router` needs the cache at registration time. Because `app.state` is populated in lifespan before the first request, pass it via a lambda or register the stream router inside the lifespan after setting `app.state`. Alternatively, call `create_stream_router` inside lifespan and store the router, then register it. The CONTEXT.md decision D-06 says no module-level globals — the cleanest approach is to include the stream router at app construction time by passing the cache to it inside lifespan via `app.include_router`.

---

### `backend/app/db.py` (utility, CRUD)

**Analog:** `backend/app/market/cache.py` (in-process resource initialized once, no module-level state) + `backend/app/market/factory.py` (reads env/config, returns configured object)

**Module-level pattern** — No module-level DB connection. All state is local to functions or context managers. Source: `backend/app/market/cache.py` lines 18-21 (constructor, no globals):
```python
from __future__ import annotations

import logging
import os
import sqlite3
import uuid
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger(__name__)

# DB path resolved once from env/default; not a live connection
_DB_PATH = os.environ.get("DB_PATH", "/app/db/finally.db")
```

**Schema strings pattern** — Pure Python string constants, `CREATE TABLE IF NOT EXISTS`. All 6 tables. The CONTEXT.md decision D-07 specifies co-located schema strings, not SQL files:
```python
_SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users_profile (
        id TEXT PRIMARY KEY,
        cash_balance REAL NOT NULL DEFAULT 10000.0,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS watchlist (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL DEFAULT 'default',
        ticker TEXT NOT NULL,
        added_at TEXT NOT NULL,
        UNIQUE(user_id, ticker)
    )
    """,
    # ... remaining 4 tables follow the same pattern
]

_SEED_STATEMENTS = [
    (
        "INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
        ("default", 10000.0, "<iso_timestamp>"),
    ),
    # One row per default ticker: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX
]
```

**`init_db()` pattern** — idempotent, called once during lifespan startup:
```python
def init_db() -> None:
    """Create tables and seed default data if missing. Safe to call on every startup."""
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    with sqlite3.connect(_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        for stmt in _SCHEMA_STATEMENTS:
            conn.execute(stmt)
        for sql, params in _SEED_STATEMENTS:
            conn.execute(sql, params)
        conn.commit()
    logger.info("Database initialized: %s", _DB_PATH)
```

**`get_db()` context manager pattern** — yields a connection, commits on success, rolls back on exception. No module-level connection:
```python
@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite connections. Commits on success, rolls back on error."""
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

---

### `backend/app/routers/health.py` (route, request-response)

**Analog:** `backend/app/market/stream.py` — simple APIRouter module with a single endpoint. Health is the simplest form: no factory needed (no external dependencies), just a module-level router.

**Imports and router definition** — Source: `backend/app/market/stream.py` lines 1-20:
```python
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["system"])


@router.get("/health")
async def health_check() -> JSONResponse:
    return JSONResponse({"status": "ok"})
```

Note: Health needs no injected dependencies (no cache, no DB), so a plain module-level `router` is fine — no factory closure needed (unlike portfolio/watchlist/chat).

---

### `backend/app/routers/portfolio.py` (route, CRUD — stub in Phase 1)

**Analog:** `backend/app/market/stream.py` lines 23-51 — router factory pattern with injected dependency.

**Factory + stub pattern** — Phase 1 returns 501 from all endpoints; the factory shape is established so Phase 2 fills in the bodies:
```python
from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.market import PriceCache

logger = logging.getLogger(__name__)


def create_portfolio_router(price_cache: PriceCache) -> APIRouter:
    """Router factory. Receives shared objects; no module-level globals."""
    router = APIRouter(prefix="/portfolio", tags=["portfolio"])

    @router.get("")
    async def get_portfolio() -> JSONResponse:
        return JSONResponse({"error": "not_implemented"}, status_code=501)

    @router.post("/trade")
    async def execute_trade() -> JSONResponse:
        return JSONResponse({"error": "not_implemented"}, status_code=501)

    @router.get("/history")
    async def get_history() -> JSONResponse:
        return JSONResponse({"error": "not_implemented"}, status_code=501)

    return router
```

Note: CONTEXT.md decision D-04 specifies the full router structure is scaffolded in Phase 1. The factory receives `price_cache` (and in Phase 2 also a DB path/connection factory) as explicit parameters — no `app.state` access inside routers.

---

### `backend/app/routers/watchlist.py` (route, CRUD — stub in Phase 1)

**Analog:** `backend/app/market/stream.py` lines 23-51 — same factory pattern.

**Factory + stub pattern** — same shape as portfolio.py stub:
```python
from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.market import PriceCache

logger = logging.getLogger(__name__)


def create_watchlist_router(price_cache: PriceCache) -> APIRouter:
    """Router factory. Receives shared objects; no module-level globals."""
    router = APIRouter(prefix="/watchlist", tags=["watchlist"])

    @router.get("")
    async def get_watchlist() -> JSONResponse:
        return JSONResponse({"error": "not_implemented"}, status_code=501)

    @router.post("")
    async def add_ticker() -> JSONResponse:
        return JSONResponse({"error": "not_implemented"}, status_code=501)

    @router.delete("/{ticker}")
    async def remove_ticker(ticker: str) -> JSONResponse:
        return JSONResponse({"error": "not_implemented"}, status_code=501)

    return router
```

---

### `backend/app/routers/chat.py` (route, request-response — stub in Phase 1)

**Analog:** `backend/app/market/stream.py` lines 23-51 — same factory pattern.

**Factory + stub pattern**:
```python
from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def create_chat_router() -> APIRouter:
    """Router factory. Phase 3 adds LLM client and DB injection."""
    router = APIRouter(prefix="/chat", tags=["chat"])

    @router.post("")
    async def send_message() -> JSONResponse:
        return JSONResponse({"error": "not_implemented"}, status_code=501)

    return router
```

---

### `backend/static/index.html` (static asset)

**Analog:** None — no HTML files exist in the codebase.

**Pattern from spec:** CONTEXT.md decision D-08 specifies a minimal dark-themed placeholder. Required elements: dark background matching `#0d1117`, text "FinAlly — Frontend coming in Phase 4", no JavaScript needed. This is a pure HTML/CSS file with inline styles to avoid any external dependency.

---

## Shared Patterns

### Module Header Convention
**Source:** Every file in `backend/app/market/` (e.g., `stream.py` line 1, `factory.py` line 1, `cache.py` line 1)
**Apply to:** All new Python modules
```python
"""<One-line docstring describing the module.>"""

from __future__ import annotations
```

### Logger Initialization
**Source:** `backend/app/market/stream.py` line 16, `backend/app/market/factory.py` line 13, `backend/app/market/simulator.py` line 25
**Apply to:** All new Python modules that log
```python
logger = logging.getLogger(__name__)
```

### Background Task Error Handling
**Source:** `backend/app/market/simulator.py` lines 260-269
**Apply to:** Any background loop added in Phase 1 or later (snapshot cadence in Phase 2)
```python
async def _run_loop(self) -> None:
    while True:
        try:
            # ... work ...
        except Exception:
            logger.exception("Loop step failed")
        await asyncio.sleep(self._interval)
```

### Asyncio Task Lifecycle (start/stop)
**Source:** `backend/app/market/simulator.py` lines 219-239
**Apply to:** `main.py` lifespan (wraps `source.start` / `source.stop`)
```python
# start:
self._task = asyncio.create_task(self._run_loop(), name="task-name")

# stop:
if self._task and not self._task.done():
    self._task.cancel()
    try:
        await self._task
    except asyncio.CancelledError:
        pass
self._task = None
```

### Test Class Structure
**Source:** `backend/tests/market/test_factory.py` lines 1-79 and `backend/tests/market/test_simulator_source.py` lines 1-38
**Apply to:** `backend/tests/test_db.py`, `backend/tests/test_health.py` (new test files in Phase 1)
```python
# Sync tests (no async needed for DB init, factory behavior)
class TestClassName:
    def test_<scenario>(self):
        ...

# Async tests (for route handlers, background tasks)
@pytest.mark.asyncio
class TestClassName:
    async def test_<scenario>(self):
        ...
```

### Error Response Shape
**Source:** `planning/PLAN.md` §8 (Error Contract) — no existing code analog yet
**Apply to:** All router stubs and future implementations
```python
# All non-2xx responses:
{"error": "<machine_code>", "message": "<human readable>"}
# e.g.:
JSONResponse({"error": "not_implemented", "message": "Coming in Phase 2"}, status_code=501)
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `backend/static/index.html` | static asset | — | No HTML/frontend files exist yet; use plain HTML with inline dark styles |

---

## Metadata

**Analog search scope:** `backend/app/market/`, `backend/tests/market/`, `backend/market_data_demo.py`, `backend/pyproject.toml`
**Files scanned:** 12
**Pattern extraction date:** 2026-05-21
