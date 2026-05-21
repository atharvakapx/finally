# Phase 2: Portfolio & Watchlist APIs - Pattern Map

**Mapped:** 2026-05-21
**Files analyzed:** 7 new/modified files
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/routers/portfolio.py` | router | request-response (CRUD + write txn) | `backend/app/routers/portfolio.py` (stub) + `backend/app/routers/health.py` | exact (same file, stub → full) |
| `backend/app/routers/watchlist.py` | router | request-response (CRUD) | `backend/app/routers/watchlist.py` (stub) + `backend/app/routers/chat.py` | exact (same file, stub → full) |
| `backend/app/services/portfolio.py` | service | CRUD + request-response | `backend/app/db.py` (query patterns) + RESEARCH.md Pattern 1 | role-match (DB helpers + arithmetic) |
| `backend/app/services/watchlist.py` | service | CRUD | `backend/app/db.py` (context managers) + `backend/app/market/interface.py` | role-match |
| `backend/app/services/snapshots.py` | service + background task | event-driven (asyncio cadence) | `backend/app/market/simulator.py` (asyncio.create_task pattern) + `backend/app/main.py` (lifespan) | role-match |
| `backend/tests/test_portfolio.py` | test | CRUD + concurrency | `backend/tests/test_db.py` | exact (same test style, threading pattern) |
| `backend/tests/test_watchlist.py` | test | CRUD | `backend/tests/test_db.py` + `backend/tests/test_main_integration.py` | exact (same fixtures + TestClient style) |

---

## Pattern Assignments

### `backend/app/routers/portfolio.py` (router, request-response + write txn)

**Analog:** `backend/app/routers/portfolio.py` (stub, lines 1-32) — replace body, keep skeleton; secondary: `backend/app/routers/health.py`

**Imports pattern** (`portfolio.py` lines 1-13, `health.py` lines 1-12):
```python
from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.market import PriceCache
from app.db import get_db, get_db_immediate, _now_iso
from app.services.portfolio import build_portfolio_view, execute_trade
from app.services.snapshots import record_snapshot

logger = logging.getLogger(__name__)
```

**Router factory pattern** (`portfolio.py` lines 15-31 — keep this factory signature exactly):
```python
def create_portfolio_router(price_cache: PriceCache) -> APIRouter:
    """Router factory. Receives shared objects; no module-level globals."""
    router = APIRouter(prefix="/portfolio", tags=["portfolio"])

    @router.get("")
    def get_portfolio(request: Request) -> JSONResponse:  # plain def → threadpool
        ...

    @router.post("/trade")
    def execute_trade_route(request: Request) -> JSONResponse:  # plain def → threadpool
        ...

    @router.get("/history")
    def get_history() -> JSONResponse:  # plain def → threadpool
        ...

    return router
```

**Error response pattern** (from RESEARCH.md Code Example 2; matches existing stub usage at `portfolio.py` line 21):
```python
# Use JSONResponse directly — NOT HTTPException (which nests under {"detail": ...})
return JSONResponse({"error": "insufficient_cash", "message": f"Need ${cost:.2f}, have ${cash:.2f}"}, status_code=400)
```

**Trade route shell pattern** (RESEARCH.md Code Example 2):
```python
@router.post("/trade")
def execute_trade_route(request: Request) -> JSONResponse:
    import json
    body = ...  # parse via request body in sync handler: use Body() or Pydantic model
    ticker = (body.get("ticker") or "").upper()
    result = execute_trade(request.app.state.price_cache,
                           ticker, body.get("side"), body.get("quantity"))
    if isinstance(result, tuple):           # (error_code, message, status_code)
        code, msg, status = result
        return JSONResponse({"error": code, "message": msg}, status_code=status)
    return JSONResponse(result, status_code=200)
```

**History route pattern** (RESEARCH.md Code Example 5):
```python
@router.get("/history")
def get_history() -> JSONResponse:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT total_value, recorded_at FROM portfolio_snapshots "
            "WHERE user_id='default' ORDER BY recorded_at ASC"
        ).fetchall()
    return JSONResponse([{"total_value": r["total_value"], "recorded_at": r["recorded_at"]} for r in rows])
```

---

### `backend/app/routers/watchlist.py` (router, request-response + CRUD)

**Analog:** `backend/app/routers/watchlist.py` (stub, lines 1-32) — replace body; secondary `backend/app/routers/chat.py` (factory pattern lines 1-20)

**Imports pattern** (`watchlist.py` lines 1-12):
```python
from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.market import PriceCache
from app.services.watchlist import get_watchlist_items, add_ticker_to_watchlist, remove_ticker_from_watchlist

logger = logging.getLogger(__name__)
```

**Router factory skeleton** (mirrors `watchlist.py` stub lines 15-31 and `chat.py` lines 13-20):
```python
def create_watchlist_router(price_cache: PriceCache) -> APIRouter:
    """Router factory. Receives shared objects; no module-level globals."""
    router = APIRouter(prefix="/watchlist", tags=["watchlist"])

    @router.get("")
    async def get_watchlist(request: Request) -> JSONResponse:  # async: reads app.state
        ...

    @router.post("")
    async def add_ticker(request: Request) -> JSONResponse:     # async: awaits market_source
        ...

    @router.delete("/{ticker}")
    async def remove_ticker(ticker: str, request: Request) -> JSONResponse:  # async: awaits
        ...

    return router
```

**Ticker validation pattern** (RESEARCH.md Code Example 3):
```python
import re
TICKER_RE = re.compile(r"^[A-Z]{1,5}$")

if not TICKER_RE.fullmatch(ticker):
    return JSONResponse({"error": "invalid_ticker",
                         "message": "Ticker must be 1-5 uppercase letters"}, status_code=400)
```

---

### `backend/app/services/portfolio.py` (service, CRUD + P&L arithmetic)

**Analog:** `backend/app/db.py` (lines 105-179, context manager patterns) + RESEARCH.md Patterns 1 & 2

**Imports pattern** (matches `db.py` lines 1-12 style):
```python
from __future__ import annotations

import logging
import uuid

from app.db import get_db, get_db_immediate, _now_iso, DEFAULT_USER_ID
from app.market import PriceCache

logger = logging.getLogger(__name__)
```

**Portfolio valuation function** (RESEARCH.md Pattern 1 — copy exactly):
```python
def build_portfolio_view(price_cache: PriceCache) -> dict:
    with get_db() as conn:
        cash = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id='default'"
        ).fetchone()["cash_balance"]
        rows = conn.execute(
            "SELECT ticker, quantity, avg_cost FROM positions "
            "WHERE user_id='default' AND quantity > 0"
        ).fetchall()
    positions, total = [], cash
    for r in rows:
        price = price_cache.get_price(r["ticker"])      # None if cache has no price
        cur = price if price is not None else r["avg_cost"]   # fallback for valuation
        market_value = r["quantity"] * cur
        cost_basis = r["quantity"] * r["avg_cost"]
        pnl = market_value - cost_basis
        pnl_pct = (pnl / cost_basis * 100) if cost_basis else 0.0
        positions.append({
            "ticker": r["ticker"], "quantity": r["quantity"],
            "avg_cost": r["avg_cost"], "current_price": cur,
            "unrealized_pnl": pnl, "pnl_pct": pnl_pct,
        })
        total += market_value
    return {"cash": cash, "positions": positions, "total_value": total}
```

**Trade execution function — BEGIN IMMEDIATE pattern** (RESEARCH.md Pattern 2 — copy exactly, includes `get_db_immediate()` from `db.py` lines 159-179):
```python
def execute_trade(price_cache: PriceCache, ticker: str, side: str, quantity):
    # --- pre-txn cheap validation (no DB needed) ---
    if side not in ("buy", "sell"):
        return ("invalid_side", "side must be 'buy' or 'sell'", 400)
    if not isinstance(quantity, (int, float)) or quantity <= 0:
        return ("invalid_quantity", "quantity must be positive", 400)
    price = price_cache.get_price(ticker)
    if price is None:
        return ("market_data_unavailable", f"No price for {ticker}", 503)

    with get_db_immediate() as conn:         # BEGIN IMMEDIATE — serializes concurrent buys
        cash = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id='default'"
        ).fetchone()["cash_balance"]
        pos = conn.execute(
            "SELECT quantity, avg_cost FROM positions "
            "WHERE user_id='default' AND ticker=?", (ticker,)
        ).fetchone()
        held_qty = pos["quantity"] if pos else 0.0
        held_cost = pos["avg_cost"] if pos else 0.0

        if side == "buy":
            cost = quantity * price
            if cost > cash:
                return ("insufficient_cash",
                        f"Need ${cost:.2f}, have ${cash:.2f}", 400)
            new_qty = held_qty + quantity
            new_avg = (held_qty * held_cost + quantity * price) / new_qty  # weighted avg
            conn.execute("UPDATE users_profile SET cash_balance=? WHERE id='default'",
                         (cash - cost,))
            _upsert_position(conn, ticker, new_qty, new_avg)
            new_cash = cash - cost
        else:  # sell
            if quantity > held_qty:
                return ("insufficient_shares",
                        f"Have {held_qty}, tried to sell {quantity}", 400)
            proceeds = quantity * price
            new_qty = held_qty - quantity
            conn.execute("UPDATE users_profile SET cash_balance=? WHERE id='default'",
                         (cash + proceeds,))
            if new_qty <= 0:
                conn.execute("DELETE FROM positions WHERE user_id='default' AND ticker=?",
                             (ticker,))
                new_avg = held_cost
            else:
                _upsert_position(conn, ticker, new_qty, held_cost)  # avg_cost unchanged on sell
                new_avg = held_cost
            new_cash = cash + proceeds

        trade_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO trades (id,user_id,ticker,side,quantity,price,executed_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (trade_id, "default", ticker, side, quantity, price, _now_iso()))
    # SNAP-02: snapshot AFTER commit, not inside the transaction
    return {"trade": {"id": trade_id, "ticker": ticker, "side": side,
                      "quantity": quantity, "price": price, "executed_at": ...},
            "cash_balance": new_cash,
            "position": {"ticker": ticker, "quantity": new_qty, "avg_cost": new_avg}}
```

**UUID + timestamp helper usage** (from `db.py` lines 105-119 — reuse exactly):
```python
import uuid
from app.db import _now_iso   # datetime.now(timezone.utc).isoformat()

trade_id = str(uuid.uuid4())
now = _now_iso()
```

**Parameterized SQL pattern** (from `db.py` lines 112-120 — always use `?` placeholders):
```python
conn.execute(
    "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
    (str(uuid.uuid4()), DEFAULT_USER_ID, ticker, _now_iso()),
)
```

---

### `backend/app/services/watchlist.py` (service, CRUD + async market source integration)

**Analog:** `backend/app/db.py` (context managers) + `backend/app/market/interface.py` (lines 1-57, async method signatures) + RESEARCH.md Pattern 3

**Imports pattern**:
```python
from __future__ import annotations

import logging
import re
import uuid

from app.db import get_db, _now_iso
from app.market import PriceCache, MarketDataSource

logger = logging.getLogger(__name__)

TICKER_RE = re.compile(r"^[A-Z]{1,5}$")
WATCHLIST_CAP = 50
```

**GET watchlist with session Δ% pattern** (RESEARCH.md Pattern 4 — session baseline from `app.state`):
```python
async def get_watchlist_items(price_cache: PriceCache, session_baselines: dict) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT ticker, added_at FROM watchlist WHERE user_id='default' ORDER BY added_at ASC"
        ).fetchall()
    result = []
    for r in rows:
        ticker = r["ticker"]
        price = price_cache.get_price(ticker)
        baseline = session_baselines.get(ticker)
        if price is not None and baseline is None:
            session_baselines[ticker] = price      # lazy: first observed price this session
            baseline = price
        session_change_pct = ((price - baseline) / baseline * 100
                              if price is not None and baseline else 0.0)
        result.append({
            "ticker": ticker,
            "price": price,
            "session_change_pct": session_change_pct,
            "added_at": r["added_at"],
        })
    return result
```

**ADD with guards + market source sync** (RESEARCH.md Pattern 3; note `add_ticker` from `interface.py` line 42 is `async`):
```python
async def add_ticker_to_watchlist(ticker: str, market_source: MarketDataSource) -> tuple | dict:
    ticker = ticker.upper()
    if not TICKER_RE.fullmatch(ticker):
        return ("invalid_ticker", "Ticker must be 1-5 uppercase letters", 400)
    with get_db() as conn:
        count = conn.execute(
            "SELECT count(*) c FROM watchlist WHERE user_id='default'"
        ).fetchone()["c"]
        if count >= WATCHLIST_CAP:
            return ("watchlist_full", "Watchlist at 50-ticker cap", 400)
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), "default", ticker, _now_iso()))
    # WATCH-05: must await — add_ticker is async (see interface.py line 42)
    await market_source.add_ticker(ticker)
    return {"ticker": ticker, "added_at": _now_iso()}
```

**DELETE with ticker_held guard** (RESEARCH.md Pattern 3):
```python
async def remove_ticker_from_watchlist(ticker: str, market_source: MarketDataSource) -> tuple | dict:
    ticker = ticker.upper()
    with get_db() as conn:
        pos = conn.execute(
            "SELECT quantity FROM positions WHERE user_id='default' AND ticker=?", (ticker,)
        ).fetchone()
        if pos and pos["quantity"] > 0:
            return ("ticker_held", "Cannot remove a ticker you hold a position in", 400)
        conn.execute(
            "DELETE FROM watchlist WHERE user_id='default' AND ticker=?", (ticker,))
    await market_source.remove_ticker(ticker)
    return {"status": "removed", "ticker": ticker}
```

---

### `backend/app/services/snapshots.py` (service + background task, event-driven asyncio)

**Analog:** `backend/app/main.py` (lines 28-41, asyncio lifespan pattern) + `backend/app/market/stream.py` (lines 54-98, CancelledError + finally pattern) + RESEARCH.md Pattern 6

**Imports pattern**:
```python
from __future__ import annotations

import asyncio
import logging
import uuid
from threading import Lock

from app.db import get_db, _now_iso
from app.market import PriceCache

logger = logging.getLogger(__name__)
```

**ClientCounter class** (RESEARCH.md Code Example 4 — 5-line class):
```python
class ClientCounter:
    """Thread-safe SSE client connection counter."""
    def __init__(self) -> None:
        self._lock = Lock()
        self._count = 0

    def increment(self) -> None:
        with self._lock:
            self._count += 1

    def decrement(self) -> None:
        with self._lock:
            self._count = max(0, self._count - 1)

    @property
    def count(self) -> int:
        with self._lock:
            return self._count
```

**record_snapshot function** (called after each trade — SNAP-02):
```python
def record_snapshot(price_cache: PriceCache) -> None:
    """Compute total portfolio value and INSERT a portfolio_snapshots row."""
    with get_db() as conn:
        cash = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id='default'"
        ).fetchone()["cash_balance"]
        rows = conn.execute(
            "SELECT ticker, quantity FROM positions WHERE user_id='default' AND quantity > 0"
        ).fetchall()
    total = cash
    for r in rows:
        price = price_cache.get_price(r["ticker"])
        if price is not None:
            total += r["quantity"] * price
    with get_db() as conn:
        conn.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
            "VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), "default", total, _now_iso()))
```

**snapshot_loop asyncio task** (RESEARCH.md Pattern 6 — mirrors lifespan in `main.py` lines 29-41 and CancelledError pattern in `stream.py` lines 97-98):
```python
async def snapshot_loop(app) -> None:
    """Background task: record portfolio snapshot every 30s, gated on SSE clients."""
    try:
        while True:
            await asyncio.sleep(30)
            if app.state.sse_clients.count > 0:
                record_snapshot(app.state.price_cache)
    except asyncio.CancelledError:
        pass
```

**lifespan edit in `main.py`** (additive — lines 29-41 in `main.py`, add 3 lines):
```python
# In lifespan, after existing startup lines (app.state.market_source = source):
from app.services.snapshots import ClientCounter, snapshot_loop
app.state.sse_clients = ClientCounter()
task = asyncio.create_task(snapshot_loop(app), name="snapshot-loop")
yield
# In shutdown section, before source.stop():
task.cancel()
try:
    await task
except asyncio.CancelledError:
    pass
```

**stream.py additive edit** (increment/decrement in `_generate_events`, lines 54-98 — wrap the existing `try` block):
```python
# At top of _generate_events, before yield "retry: 1000\n\n":
#   accept a counter parameter and call counter.increment()
# In the existing except asyncio.CancelledError block and add finally:
async def _generate_events(price_cache, request, counter=None, interval=0.5):
    if counter:
        counter.increment()
    try:
        yield "retry: 1000\n\n"
        # ... existing loop unchanged ...
    except asyncio.CancelledError:
        logger.info("SSE stream cancelled for: %s", client_ip)
    finally:
        if counter:
            counter.decrement()    # runs on disconnect AND CancelledError
```

---

### `backend/tests/test_portfolio.py` (test, CRUD + concurrency)

**Analog:** `backend/tests/test_db.py` (lines 1-234) — closest match for structure, fixtures, and the threading concurrency pattern

**Test file imports pattern** (`test_db.py` lines 1-12):
```python
from __future__ import annotations

import importlib
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app.market import PriceCache
```

**Isolated DB fixture pattern** (`test_db.py` lines 19-31 — copy exactly, adjust module names):
```python
@pytest.fixture
def db_module(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    import app.db
    module = importlib.reload(app.db)
    yield module
```

**App client fixture with fresh DB** (`test_main_integration.py` lines 13-28 — use for API-level tests):
```python
@pytest.fixture
def app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "finally.db"))
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import app.db
    import app.main
    importlib.reload(app.db)
    importlib.reload(app.main)
    with TestClient(app.main.app) as client:
        yield client, app.main
```

**Concurrency test pattern — threading** (`test_db.py` lines 191-233 — copy threading approach for concurrent buy test):
```python
def test_concurrent_buys_serialize(self, ...):
    errors = []

    def buy_shares():
        try:
            # call execute_trade() directly or via raw threading.Thread
            time.sleep(0.05)  # open contention window
            ...
        except Exception as exc:
            errors.append(exc)

    t1 = threading.Thread(target=buy_shares)
    t2 = threading.Thread(target=buy_shares)
    t1.start()
    time.sleep(0.005)
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)

    assert not errors
    # assert total cash debited = exactly one purchase, not two double-spends
```

**Class-based test organization** (`test_db.py` lines 39-53 style):
```python
class TestGetPortfolio:
    def test_...(self, app_client): ...

class TestExecuteTrade:
    def test_buy_insufficient_cash(self, ...): ...
    def test_sell_oversold(self, ...): ...
    def test_concurrent_buys_serialize(self, ...): ...

class TestPortfolioHistory:
    def test_history_returns_series(self, ...): ...
```

---

### `backend/tests/test_watchlist.py` (test, CRUD with mock market source)

**Analog:** `backend/tests/test_main_integration.py` (lines 13-76) — TestClient + `app_client` fixture; `test_db.py` for class structure

**Mock market source pattern** (no existing analog — use `unittest.mock.AsyncMock`):
```python
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_market_source():
    source = MagicMock()
    source.add_ticker = AsyncMock()
    source.remove_ticker = AsyncMock()
    source.get_tickers = MagicMock(return_value=[])
    return source
```

**Session Δ% baseline fixture** (in-memory dict on `app.state` — set via fixture):
```python
@pytest.fixture
def app_with_cache(tmp_path, monkeypatch):
    # Override app.state.session_baselines and price_cache with known values
    cache = PriceCache()
    cache.update("AAPL", 150.0)
    # ... inject into app.state after reload ...
```

**Class-based test organization** (`test_db.py` lines 39-53 style):
```python
class TestGetWatchlist:
    def test_session_change_baseline(self, ...): ...

class TestAddWatchlist:
    def test_invalid_ticker_format(self, ...): ...
    def test_watchlist_cap(self, ...): ...
    def test_add_seeds_source(self, ...): ...

class TestRemoveWatchlist:
    def test_remove_held_ticker(self, ...): ...
    def test_remove_calls_source(self, ...): ...
```

**Assert API error contract** (from `test_main_integration.py` lines 43-56 — `data["error"]` at top level, not under `detail`):
```python
resp = client.post("/api/watchlist", json={"ticker": "INVALID!!"})
assert resp.status_code == 400
data = resp.json()
assert data["error"] == "invalid_ticker"   # top-level, not data["detail"]["error"]
assert "message" in data
```

---

## Shared Patterns

### Error Response (flat envelope)
**Source:** `backend/app/routers/portfolio.py` (stub, line 21); RESEARCH.md Pitfall 1
**Apply to:** All router files — every non-2xx response
```python
# CORRECT: flat {"error": ..., "message": ...}
return JSONResponse({"error": "insufficient_cash", "message": "Need $X, have $Y"}, status_code=400)

# WRONG — produces {"detail": {"error": ...}} — breaks the contract:
# raise HTTPException(status_code=400, detail={"error": ..., "message": ...})
```

### Router Factory Pattern
**Source:** `backend/app/routers/portfolio.py` lines 15-31; `backend/app/routers/watchlist.py` lines 15-31; `backend/app/routers/chat.py` lines 13-20
**Apply to:** `portfolio.py`, `watchlist.py` routers
```python
def create_portfolio_router(price_cache: PriceCache) -> APIRouter:
    """Router factory. Receives shared objects; no module-level globals."""
    router = APIRouter(prefix="/portfolio", tags=["portfolio"])
    # ... route definitions as closures ...
    return router
```

### Database Context Managers
**Source:** `backend/app/db.py` lines 142-179
**Apply to:** All service files that touch the DB
- Read-only or non-critical writes: `with get_db() as conn:` (commits on success, rolls back on error)
- Trade write path: `with get_db_immediate() as conn:` (issues `BEGIN IMMEDIATE` — serializes concurrent writers)
- Never use `conn.commit()` manually; the context manager handles it
- Always use `?` placeholders — never f-string/%-format SQL

### `from __future__ import annotations` + logging
**Source:** `backend/app/db.py` lines 1-13; `backend/app/routers/portfolio.py` lines 1-12
**Apply to:** Every new `.py` file
```python
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)
```

### UUID + Timestamp helpers
**Source:** `backend/app/db.py` lines 105-120
**Apply to:** All service files inserting new rows
```python
import uuid
from app.db import _now_iso

row_id = str(uuid.uuid4())   # matches db.py _seed() pattern
timestamp = _now_iso()        # datetime.now(timezone.utc).isoformat()
```

### Parameterized SQL
**Source:** `backend/app/db.py` lines 112-120
**Apply to:** All service files — every SQL query with user-controlled values
```python
conn.execute(
    "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
    (str(uuid.uuid4()), DEFAULT_USER_ID, ticker, _now_iso()),
)
# Never: f"... WHERE ticker='{ticker}'"
```

### asyncio.CancelledError + finally guard
**Source:** `backend/app/market/stream.py` lines 72-98
**Apply to:** `snapshot_loop` in `services/snapshots.py`; the counter decrement in `stream.py`
```python
try:
    while True:
        await asyncio.sleep(30)
        ...
except asyncio.CancelledError:
    pass   # clean exit on task.cancel()
```

### asyncio.create_task in lifespan
**Source:** `backend/app/main.py` lines 28-41 (lifespan pattern)
**Apply to:** `main.py` edit adding snapshot task
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    ...
    task = asyncio.create_task(snapshot_loop(app), name="snapshot-loop")
    yield
    # shutdown
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await source.stop()
```

### Test DB Isolation Fixture
**Source:** `backend/tests/test_db.py` lines 19-31; `backend/tests/test_main_integration.py` lines 13-28; `backend/tests/conftest.py` lines 1-22
**Apply to:** `test_portfolio.py`, `test_watchlist.py`, `test_snapshots.py`
```python
@pytest.fixture
def app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "finally.db"))
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import app.db, app.main
    importlib.reload(app.db)
    importlib.reload(app.main)
    with TestClient(app.main.app) as client:
        yield client, app.main
```

### PriceCache seeding in tests
**Source:** `backend/app/market/cache.py` lines 23-41 (`.update()` method)
**Apply to:** `test_portfolio.py`, `test_watchlist.py` — pre-warm cache with known prices for deterministic P&L
```python
cache = PriceCache()
cache.update("AAPL", 150.00)   # known price → deterministic P&L assertions
cache.update("GOOGL", 175.00)
```

---

## No Analog Found

All files have analogs in the codebase. No entries.

---

## Metadata

**Analog search scope:** `backend/app/routers/`, `backend/app/market/`, `backend/app/db.py`, `backend/app/main.py`, `backend/tests/`
**Files scanned:** 14 source files read directly; directory listing confirmed no `services/` or `tasks/` directory exists yet (all new)
**Pattern extraction date:** 2026-05-21
