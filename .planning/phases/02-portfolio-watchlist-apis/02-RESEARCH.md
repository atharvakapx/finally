# Phase 2: Portfolio & Watchlist APIs - Research

**Researched:** 2026-05-21
**Domain:** FastAPI REST endpoints over SQLite + an existing thread-safe in-memory PriceCache; financial trade math (weighted-average cost, P&L); a periodic asyncio background task
**Confidence:** HIGH

## Summary

Phase 2 wires the already-built market-data subsystem and SQLite layer (both completed in Phase 1) into the four user-facing endpoint groups: portfolio read, trade execution, watchlist CRUD, and portfolio-value history. There is **no new external dependency** — every tool needed (`fastapi`, `starlette`, `pydantic`, stdlib `sqlite3` and `asyncio`) is already installed and verified in the project venv. The work is almost entirely "glue + correct financial arithmetic + correct error contract," not new technology adoption.

The two genuinely subtle pieces are (1) the concurrent-buy safety guarantee, which the codebase already solves at the data layer via `get_db_immediate()` issuing `BEGIN IMMEDIATE` — the trade endpoint must read cash/position **inside** that transaction, validate, then write, all before commit; and (2) the snapshot cadence task (SNAP-01), which must run every 30 s **only while at least one SSE client is connected** — but the SSE endpoint lives in `app/market/stream.py`, which CLAUDE.md marks "complete — do not reimplement." The cleanest reconciliation is a small **additive** client-counter (increment on connect, decrement on disconnect) rather than a rewrite, plus a shared counter object on `app.state` that the snapshot task polls.

**Primary recommendation:** Implement the trade endpoint as a plain `def` (sync) handler so FastAPI runs it in its threadpool and the blocking `get_db_immediate()` context manager works naturally; read-then-validate-then-write all inside the single `BEGIN IMMEDIATE` transaction; pull all live prices from `app.state.price_cache` (never the DB); return the flat `{"error", "message"}` envelope via `JSONResponse(..., status_code=...)` (NOT `HTTPException`, which wraps in `{"detail": ...}`); and add the snapshot task to the existing `lifespan` in `main.py` driven by an SSE client counter.

## User Constraints

> No CONTEXT.md exists for this phase (standalone `--research-phase 2` run). The binding constraints below are extracted from CLAUDE.md, planning/PLAN.md, and the phase brief. The planner MUST honor them as locked.

### Locked Decisions (from CLAUDE.md + PLAN.md + phase brief)
- SQLite only — use existing `get_db()` and `get_db_immediate()` from `app.db`. No Postgres, no Redis, no ORM. `[CITED: CLAUDE.md]`
- `POST /api/portfolio/trade` MUST use the `BEGIN IMMEDIATE` transaction (`get_db_immediate()`) for write serialization / concurrent-buy protection (DB-05). `[CITED: phase brief + PLAN.md §8 Concurrency]`
- `uv` for Python package management — `uv add` / `uv run` only. `[CITED: CLAUDE.md]`
- The price cache (`app.state.price_cache`) is the source of truth for live prices — **no DB reads for current prices**. `[CITED: phase brief]`
- Watchlist additions must call `market_source.add_ticker()` via `app.state.market_source` (WATCH-05). `[CITED: phase brief]`
- Watchlist deletions must respect the `ticker_held` guard; only drop from the data source when no position exists (WATCH-03). `[CITED: phase brief + PLAN.md §6 Held-but-Unwatched]`
- Session change % baseline = first price observed in the cache for a ticker, **not** from DB (WATCH-01). `[CITED: phase brief + PLAN.md §6 Session Change %]`
- All error responses use `{"error": "<code>", "message": "<human>"}` (flat shape). `[CITED: PLAN.md §8 Error Contract]`
- User ID is always `"default"` (single-user). `[CITED: PLAN.md §7]`
- Market data subsystem (`backend/app/market/`) is **complete — do not reimplement**. Consume `PriceCache` / `MarketDataSource`. `[CITED: CLAUDE.md]`
- Money is SQLite `REAL` (IEEE-754 double) — fake money, no Decimal ledger reconciliation required. `[CITED: PLAN.md §7 Money Representation]`
- Watchlist cap = 50 tickers → `400 watchlist_full` (WATCH-04). `[CITED: PLAN.md §6 + §8]`
- Ticker format regex `^[A-Z]{1,5}$` → `400 invalid_ticker` (WATCH-02). `[CITED: PLAN.md §8]`
- Snapshot recorded after every trade (SNAP-02) and every 30 s while ≥1 SSE client connected; cadence task pauses when no client connected (SNAP-01). `[CITED: phase brief + PLAN.md §7 portfolio_snapshots]`

### Claude's Discretion
- Internal module layout of the routers (helper functions, a shared `errors.py`, a `trades.py` service module, etc.).
- Pydantic request/response model definitions vs. raw dict handling.
- Whether the snapshot client-counter lives in a tiny additive edit to `stream.py` or a wrapper.
- Test file organization under `backend/tests/`.

### Deferred Ideas (OUT OF SCOPE)
- Limit orders, order book, partial fills (v2 TRADE-01). Market orders only.
- Trade confirmation dialog (v2 TRADE-02) — this is also explicitly auto-execute for the LLM in Phase 3.
- Per-user isolation / auth (v2 AUTH-*). `user_id="default"` hardcoded.
- Massive-mode `unknown_ticker` probe is in scope **only** if Massive mode is active; default sim mode does format check only (see Pitfall 6).
- LLM auto-execution wiring (Phase 3) — but the trade/watchlist functions should be written so Phase 3 can call them directly (see Architecture Pattern 5).

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PORT-01 | `GET /api/portfolio` returns cash, positions w/ live P&L, total value | Read `users_profile.cash_balance` + all `positions` rows via `get_db()`; for each, look up `price_cache.get_price(ticker)`; compute `unrealized_pnl` and `pnl_pct`; `total_value = cash + Σ(qty×price)` (Pattern 1, Code Example 1) |
| PORT-02 | `POST /trade` `side=buy` validates sufficient cash | Inside `get_db_immediate()`: re-read cash, compute `cost = qty×cache_price`, reject `insufficient_cash` if `cost > cash` (Pattern 2, Code Example 2) |
| PORT-03 | `POST /trade` `side=sell` validates sufficient shares | Inside same txn: re-read position qty, reject `insufficient_shares` if `qty > held` (Pattern 2) |
| PORT-04 | `GET /portfolio/history` returns snapshot time series | `SELECT total_value, recorded_at FROM portfolio_snapshots WHERE user_id='default' ORDER BY recorded_at` (Code Example 5) |
| PORT-05 | Trades fill at current cache price, instant, no spread | `price_cache.get_price(ticker)`; if `None` → `503 market_data_unavailable` (Pattern 2, Pitfall 3) |
| WATCH-01 | `GET /watchlist` returns tickers + latest price + session Δ% | Join watchlist rows with cache; session baseline = first-observed price (needs a baseline map — Pattern 4, Pitfall 5) |
| WATCH-02 | `POST /watchlist` format-validates `^[A-Z]{1,5}$` → `400 invalid_ticker` | `re.fullmatch` before any DB write (Pattern 3, Code Example 3) |
| WATCH-03 | `DELETE /watchlist/{ticker}` → `400 ticker_held` if position held | Check `positions.quantity > 0` before delete (Pattern 3) |
| WATCH-04 | Cap 50 → `400 watchlist_full` | `SELECT count(*)` before insert (Pattern 3) |
| WATCH-05 | Add seeds ticker into active data source immediately | `await app.state.market_source.add_ticker(ticker)` after DB insert (Pattern 3, Pitfall 7) |
| SNAP-01 | Snapshot every 30 s while ≥1 SSE client connected; pauses otherwise | asyncio task in lifespan polling an SSE client counter (Pattern 6, Pitfall 2) |
| SNAP-02 | Snapshot immediately after each trade | Call a shared `record_snapshot()` at the end of a successful trade (Pattern 2 + 6) |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Portfolio read & valuation | API / Backend | In-memory PriceCache | Live prices come from the cache; positions/cash from DB; valuation is pure server-side arithmetic |
| Trade execution + cash/position mutation | API / Backend (write txn) | Database (SQLite `BEGIN IMMEDIATE`) | Money correctness + concurrency safety must live behind the serialized write lock |
| Trade fill price | In-memory PriceCache | — | Source of truth for "current price"; never the DB (Locked Decision) |
| Watchlist CRUD | API / Backend | Database + MarketDataSource | DB holds membership; the data source must learn about adds/removes to stream prices |
| Session Δ% baseline | In-memory (process state) | — | "First observed price since server start" is runtime state, not persisted (Pitfall 5) |
| Snapshot cadence (every 30 s) | API / Backend (asyncio task) | Database | Background writer; gated on SSE connection count |
| SSE connection counting | In-memory (process state) | — | A live counter incremented/decremented by the stream generator |

## Standard Stack

### Core
| Library | Version (installed/verified) | Purpose | Why Standard |
|---------|------------------------------|---------|--------------|
| fastapi | 0.128.7 | Routing, request validation, dependency injection | Already the app framework; routers wired in `main.py` `[VERIFIED: uv run import]` |
| starlette | 0.52.1 | Underlying ASGI, `JSONResponse`, threadpool for `def` handlers, `run_in_threadpool` | Ships with FastAPI; provides the threadpool that makes sync sqlite safe `[VERIFIED: uv run import]` |
| pydantic | 2.12.5 | Optional request/response models (e.g. trade body) | Already installed; v2 API `[VERIFIED: uv run import]` |
| sqlite3 (stdlib) | Python 3.12 stdlib | All persistence via `get_db()` / `get_db_immediate()` | Locked decision; helpers already exist in `app/db.py` `[VERIFIED: read app/db.py]` |
| asyncio (stdlib) | Python 3.12 stdlib | The 30 s snapshot cadence task in `lifespan` | Same pattern the simulator already uses (`asyncio.create_task`) `[VERIFIED: read simulator.py]` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| re (stdlib) | stdlib | Ticker format validation `^[A-Z]{1,5}$` | WATCH-02 / trade ticker validation |
| uuid (stdlib) | stdlib | PK generation for `trades`, `positions`, `portfolio_snapshots` rows | Matches existing `_seed()` in `db.py` (`str(uuid.uuid4())`) |
| datetime (stdlib) | stdlib | ISO 8601 timestamps | Reuse the `_now_iso()` pattern from `db.py` |
| httpx | 0.28.1 (dev) | Async test client for true-concurrency trade tests | Tests only; already a dev dep `[VERIFIED: pyproject.toml + uv import]` |
| pytest / pytest-asyncio | 8.3+/0.24+ | Test framework (already configured, `asyncio_mode=auto`) | All Phase 2 tests `[VERIFIED: pyproject.toml]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `JSONResponse({"error",...}, status_code=...)` | `HTTPException(detail={...})` | `HTTPException` wraps the body in `{"detail": {...}}`, **breaking** the flat error contract. Existing stubs already use `JSONResponse` directly — keep that. (Pitfall 1) |
| Plain `def` sync handlers | `async def` + `run_in_threadpool(...)` wrapping every DB call | Both work. Plain `def` is simpler and idiomatic for blocking sqlite; FastAPI auto-runs it in the 40-thread AnyIO pool. The existing stubs are `async def` but do no I/O — converting the real handlers to `def` is cleaner. (Pattern 2) |
| Raw dict responses | Pydantic response models | Pydantic adds validation/schema but more boilerplate; dicts are fine and match existing handlers. Discretionary. |

**Installation:**
```bash
# No new packages required for Phase 2 — everything is already installed.
# If a Pydantic model file is added, no install needed (pydantic 2.12.5 present).
```

**Version verification:** Performed live in this session via `uv run python -c "import fastapi, starlette, pydantic, httpx; ..."` → fastapi 0.128.7, starlette 0.52.1, pydantic 2.12.5, httpx 0.28.1. `uv 0.11.15`, Python venv targets `>=3.12`. `[VERIFIED: uv run]`

## Package Legitimacy Audit

> Phase 2 installs **no external packages**. All dependencies are pre-installed stdlib or already-present project deps verified in Phase 1.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| fastapi | PyPI | mature | very high | github.com/fastapi/fastapi | n/a (pre-installed) | Approved — already in lockfile |
| starlette | PyPI | mature | very high | github.com/encode/starlette | n/a (pre-installed) | Approved — transitive of fastapi |
| pydantic | PyPI | mature | very high | github.com/pydantic/pydantic | n/a (pre-installed) | Approved — already in lockfile |
| sqlite3 / asyncio / re / uuid / datetime | stdlib | stdlib | n/a | CPython | n/a | Approved — Python standard library |

**Packages removed due to slopcheck [SLOP] verdict:** none — no new packages introduced.
**Packages flagged as suspicious [SUS]:** none.

*slopcheck and ctx7 CLIs were not installable in this environment; this is moot because Phase 2 introduces zero new dependencies. If the planner later decides to add a package, it must run the Package Legitimacy Gate first.*

## Architecture Patterns

### System Architecture Diagram

```
                         HTTP request (same-origin /api/*)
                                     │
                                     ▼
        ┌──────────────────────────────────────────────────────┐
        │                FastAPI app (main.py)                   │
        │  app.state.price_cache   app.state.market_source      │
        │  app.state.<sse_counter> app.state.<session_baselines>│
        └───┬───────────────┬───────────────┬──────────────┬────┘
            │               │               │              │
   GET /portfolio   POST /portfolio/trade   GET/POST/DEL    GET /portfolio/history
   GET .../history  (def, BEGIN IMMEDIATE)  /watchlist      │
            │               │               │              │
            ▼               ▼               ▼              ▼
     ┌────────────┐  ┌──────────────┐  ┌───────────┐  ┌──────────┐
     │ read cash, │  │ 1.read price │  │ validate  │  │  SELECT  │
     │ positions  │  │   from cache │  │  regex/cap│  │ snapshots│
     │ + cache    │  │ 2.BEGIN IMM  │  │ /held     │  │ ORDER BY │
     │  prices    │  │ 3.re-read    │  │           │  │ recorded │
     │ → compute  │  │   cash/pos   │  │ DB write  │  └──────────┘
     │   P&L      │  │ 4.validate   │  │ +source   │
     └─────┬──────┘  │ 5.write rows │  │ add/remove│
           │         │ 6.COMMIT     │  └─────┬─────┘
           │         │ 7.snapshot   │        │
           ▼         └──────┬───────┘        ▼
    ┌──────────────┐        │        ┌────────────────────┐
    │  PriceCache  │◄───────┘        │ market_source      │
    │ (in-memory,  │   reads         │ .add_ticker/.remove│
    │  thread-safe)│                 └────────────────────┘
    └──────▲───────┘
           │ writes (every 500ms)
    ┌──────┴────────────┐        ┌──────────────────────────────┐
    │ SimulatorDataSource│       │ Snapshot cadence task (async) │
    │ / MassiveDataSource│       │ every 30s IF sse_count > 0:   │
    └────────────────────┘       │  total_value = portfolio calc │
                                 │  INSERT portfolio_snapshots   │
    SSE /api/stream/prices ──────┤  (also called after each trade)│
    (increments/decrements ──────┘                               │
     sse_counter on connect/disconnect) ─────────────────────────┘

    All persistence → SQLite db/finally.db via get_db() / get_db_immediate()
```

### Recommended Project Structure
```
backend/app/
├── routers/
│   ├── portfolio.py     # REPLACE stub: GET /portfolio, POST /trade, GET /history
│   ├── watchlist.py     # REPLACE stub: GET, POST, DELETE
│   └── errors.py        # NEW (discretionary): error_response() helper + code constants
├── services/            # NEW (discretionary): pure logic, callable by Phase 3 LLM
│   ├── trades.py        # execute_trade(...) → result | error; weighted-avg-cost math
│   ├── portfolio.py     # build_portfolio_view(...), compute_total_value(...)
│   └── snapshots.py     # record_snapshot(...), snapshot_loop()
├── db.py                # UNCHANGED (get_db, get_db_immediate, helpers)
├── main.py              # EDIT: add snapshot task + sse counter to lifespan/app.state
└── market/
    └── stream.py        # EDIT (additive only): inc/dec sse counter on connect/disconnect
```
> Splitting trade/portfolio/snapshot logic into `services/` (callable functions, not HTTP-coupled) is **strongly recommended** because Phase 3's LLM auto-execution (CHAT-03/CHAT-04) must run trades and watchlist edits through the *same* validation without re-issuing HTTP requests.

### Pattern 1: Portfolio valuation (cache is price source of truth)
**What:** Read cash + positions from DB, overlay live prices from the cache, compute P&L.
**When to use:** `GET /api/portfolio`, and inside snapshot recording (`total_value`).
**Example:**
```python
# Source: derived from app/db.py + app/market/cache.py (this repo)
def build_portfolio_view(price_cache) -> dict:
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
        price = price_cache.get_price(r["ticker"])   # None if cache has no price
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

### Pattern 2: Trade execution under BEGIN IMMEDIATE (read-validate-write atomically)
**What:** All cash/position reads, validation, and writes happen inside one `get_db_immediate()` block so two concurrent buys cannot double-spend.
**When to use:** `POST /api/portfolio/trade` and Phase 3 LLM trades.
**Example:**
```python
# Source: derived from app/db.py get_db_immediate() + PLAN.md §8 Concurrency (this repo)
def execute_trade(price_cache, ticker: str, side: str, quantity: float):
    # --- pre-txn cheap validation (cache + format) ---
    if side not in ("buy", "sell"):
        return ("invalid_side", "side must be 'buy' or 'sell'", 400)
    if not isinstance(quantity, (int, float)) or quantity <= 0:
        return ("invalid_quantity", "quantity must be positive", 400)
    price = price_cache.get_price(ticker)
    if price is None:
        return ("market_data_unavailable", f"No price for {ticker}", 503)

    with get_db_immediate() as conn:                 # BEGIN IMMEDIATE acquires write lock
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
            # weighted-average cost
            new_avg = (held_qty * held_cost + quantity * price) / new_qty
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
            if new_qty <= 0:                          # remove position at zero
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
    # commit happened on context exit; snapshot AFTER commit (SNAP-02)
    record_snapshot(price_cache)
    return {"trade": {...}, "cash_balance": new_cash, "position": {...}}  # shape per PLAN §8
```
> Key correctness rules: **avg_cost only changes on buys** (weighted average); on a sell it stays put and a full sell deletes the row. Validate `cost > cash` (strict) — equality is allowed (cash can hit exactly 0). `record_snapshot()` runs *after* the transaction commits, not inside it.

### Pattern 3: Watchlist mutation with all guards + data-source sync
**What:** Validate format → cap → uniqueness; on add, persist then `await market_source.add_ticker`; on delete, enforce `ticker_held` then persist then `await market_source.remove_ticker` (only if no position).
**When to use:** `POST` / `DELETE /api/watchlist`.
**Example:**
```python
# Source: derived from PLAN.md §6/§8 + app/market interface (this repo)
import re
TICKER_RE = re.compile(r"^[A-Z]{1,5}$")
WATCHLIST_CAP = 50

async def add_to_watchlist(request, ticker: str):
    ticker = ticker.upper()
    if not TICKER_RE.fullmatch(ticker):
        return error_response("invalid_ticker", "Ticker must be 1-5 uppercase letters", 400)
    with get_db() as conn:
        count = conn.execute(
            "SELECT count(*) c FROM watchlist WHERE user_id='default'").fetchone()["c"]
        if count >= WATCHLIST_CAP:
            return error_response("watchlist_full", "Watchlist at 50-ticker cap", 400)
        exists = conn.execute(
            "SELECT 1 FROM watchlist WHERE user_id='default' AND ticker=?", (ticker,)
        ).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO watchlist (id,user_id,ticker,added_at) VALUES (?,?,?,?)",
                (str(uuid.uuid4()), "default", ticker, _now_iso()))
    # WATCH-05: seed into the live source so it starts streaming (idempotent)
    await request.app.state.market_source.add_ticker(ticker)
    return {"ticker": ticker, ...}

async def remove_from_watchlist(request, ticker: str):
    ticker = ticker.upper()
    with get_db() as conn:
        pos = conn.execute(
            "SELECT quantity FROM positions WHERE user_id='default' AND ticker=?", (ticker,)
        ).fetchone()
        if pos and pos["quantity"] > 0:
            return error_response("ticker_held",
                                  "Cannot remove a ticker you hold a position in", 400)
        conn.execute("DELETE FROM watchlist WHERE user_id='default' AND ticker=?", (ticker,))
    # active ticker set = watchlist ∪ positions; only drop from source when no position
    await request.app.state.market_source.remove_ticker(ticker)
    return JSONResponse({"status": "removed", "ticker": ticker})
```
> Note: this handler is `async def` *because* `market_source.add_ticker/remove_ticker` are coroutines. The DB work is blocking — acceptable for short single-row ops, but if strictness is wanted, wrap the `get_db()` block in `run_in_threadpool`. Mixed-mode is the realistic tradeoff here (Pitfall 8).

### Pattern 4: Watchlist GET with session Δ%
**What:** Join watchlist tickers with cache prices; session Δ% = `(current - baseline)/baseline*100` where baseline is the **first price the cache produced for that ticker this process** (Pitfall 5).
**When to use:** `GET /api/watchlist`.

### Pattern 5: HTTP handler is a thin shell over a service function (Phase 3 reuse)
**What:** The route function parses the body and maps the service result to status code; the service function is pure Python and returns either a success dict or `(error_code, message, status)`.
**Why:** Phase 3 CHAT-03/04 must auto-execute trades & watchlist edits through the *same* validation. If logic lives only inside the HTTP handler, Phase 3 has to either duplicate it or make internal HTTP calls. A `services/` layer prevents both.

### Pattern 6: Snapshot cadence task gated on SSE client count
**What:** An asyncio task created in `lifespan` loops `await asyncio.sleep(30)`; each wake, if `sse_counter > 0`, compute `total_value` and INSERT a `portfolio_snapshots` row. `record_snapshot()` is also called directly after each trade (SNAP-02).
**When to use:** Added to `main.py` lifespan; counter incremented/decremented by `stream.py`.
**Example:**
```python
# Source: derived from FastAPI lifespan docs [CITED: fastapi.tiangolo.com/advanced/events]
#         + existing simulator asyncio.create_task pattern (this repo)
async def snapshot_loop(app):
    try:
        while True:
            await asyncio.sleep(30)
            if app.state.sse_clients.count > 0:        # gate: pause when nobody connected
                record_snapshot(app.state.price_cache)
    except asyncio.CancelledError:
        pass

@asynccontextmanager
async def lifespan(app):
    init_db()
    source = create_market_data_source(price_cache)
    await source.start(list(DEFAULT_TICKERS))
    app.state.price_cache = price_cache
    app.state.market_source = source
    app.state.sse_clients = ClientCounter()            # NEW shared counter
    task = asyncio.create_task(snapshot_loop(app), name="snapshot-loop")  # NEW
    yield
    task.cancel()
    try: await task
    except asyncio.CancelledError: pass
    await source.stop()
```

### Anti-Patterns to Avoid
- **Reading "current price" from the DB.** There is no current-price column; the cache is the only source (Locked Decision). The `trades` table stores the *fill* price, not a live price.
- **Using `HTTPException(detail={...})`** for the error contract — it nests under `{"detail": ...}` and breaks the documented flat shape (Pitfall 1).
- **Validating cash/shares *outside* the `BEGIN IMMEDIATE` block** then writing inside — that reintroduces the TOCTOU race the transaction exists to prevent. Re-read inside (Pitfall 4).
- **Recording the snapshot inside the trade transaction** — keep the write transaction minimal; snapshot after commit.
- **Changing `avg_cost` on a sell** — weighted-average cost only moves on buys.
- **Reseeding session baselines from the DB** — baseline is in-memory, per process start (Pitfall 5).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Concurrent-write serialization | A Python `threading.Lock` / asyncio lock around trades | `get_db_immediate()` (`BEGIN IMMEDIATE`) — already built & tested | A process-level lock doesn't survive multiple workers; SQLite's write lock is the correct boundary and is already proven in `test_db.py` |
| Connection lifecycle / commit / rollback | Manual `conn.commit()` / `try/except rollback` everywhere | `get_db()` / `get_db_immediate()` context managers | They already handle commit-on-success, rollback-on-error, WAL, and BEGIN IMMEDIATE |
| Live price source | Polling the market source or re-deriving prices | `app.state.price_cache.get_price()` / `.get_all()` | Thread-safe, version-tracked, the single source of truth |
| Ticker price streaming on add | Manually pushing prices for a new ticker | `await market_source.add_ticker()` (seeds cache immediately) | The simulator seeds the new ticker price into the cache on add; reimplementing risks divergence |
| Background scheduling | A separate scheduler lib (APScheduler, celery) | A single `asyncio.create_task` in lifespan | One periodic in-process task; no external scheduler is justified for a single-container app |
| Money rounding | A Decimal-based ledger | `REAL` + `toFixed` on display | Locked decision: fake money, no reconciliation; Decimal would be over-engineering here |

**Key insight:** Phase 2 is almost entirely *assembly* of components Phase 1 already built and tested. The dangerous temptation is to re-solve concurrency or price-sourcing in the router; the right move is to lean on `get_db_immediate()` and `price_cache`.

## Runtime State Inventory

> Phase 2 is **greenfield endpoint implementation**, not a rename/refactor/migration. This section is included only to record one piece of genuine *new* runtime state the design introduces, since the planner must allocate where it lives.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | New rows written to existing tables: `trades`, `positions`, `portfolio_snapshots`, `watchlist`. Schema already exists (Phase 1) — no migration. | Code writes only; no schema change |
| Live service config | None — no external service config changes | None — verified by reading factory.py/simulator.py |
| OS-registered state | None | None |
| Secrets/env vars | None new. Massive/OpenAI keys unchanged; trade/watchlist don't read secrets | None |
| Build artifacts | None — no `pyproject.toml` dependency change, so no reinstall needed | None |
| **New in-process runtime state (not persisted)** | (a) Session Δ% baseline map: first-observed price per ticker; (b) SSE client counter for snapshot gating | Both must live on `app.state`, reset on process restart (by design) |

**Nothing found in categories Live service config / OS-registered / Secrets / Build artifacts** — verified by reading `factory.py`, `simulator.py`, `db.py`, and `pyproject.toml`; Phase 2 adds no dependency and touches no external system config.

## Common Pitfalls

### Pitfall 1: Error envelope shape gets nested under `detail`
**What goes wrong:** Using `raise HTTPException(status_code=400, detail={"error":..., "message":...})` produces `{"detail": {"error":..., "message":...}}`, not the contracted flat `{"error":..., "message":...}`. Existing Phase 1 integration tests assert `data["error"]` at top level.
**Why it happens:** `HTTPException` is the "obvious" FastAPI idiom and most tutorials show it.
**How to avoid:** Return `JSONResponse({"error": code, "message": msg}, status_code=...)` directly (exactly as the current stub routers do). A shared `error_response(code, msg, status)` helper keeps it consistent.
**Warning signs:** Tests asserting `resp.json()["error"]` fail with `KeyError: 'error'` (it's under `detail`).

### Pitfall 2: Snapshot task records forever (or never)
**What goes wrong:** A naive `while True: sleep(30); record()` snapshots even when no client is connected (violates SNAP-01 "pauses when no client connected"), bloating the DB on idle deployments. The inverse bug: gating on a counter that's never incremented → never snapshots.
**Why it happens:** The SSE endpoint (`stream.py`) currently has **no client counter** (verified via grep — none exists). The cadence requirement implicitly demands one.
**How to avoid:** Introduce a tiny shared counter (`app.state.sse_clients`) that the SSE generator increments on connect and decrements in its `finally`/`CancelledError` path. The cadence loop checks `count > 0` each wake. This is an **additive** change to `stream.py`, not a reimplementation.
**Warning signs:** Idle test run accumulates snapshots; or `portfolio_snapshots` stays empty even with a connected client.

### Pitfall 3: Trade on a ticker with no cache price
**What goes wrong:** `price_cache.get_price(ticker)` returns `None` (cache not yet warm, or ticker just added) and `None * quantity` raises `TypeError`, surfacing as `500` instead of the contracted `503 market_data_unavailable`.
**Why it happens:** The cache warms ~500 ms after a ticker is added; a trade can arrive in that window.
**How to avoid:** Check `price is None` *before* arithmetic and return `503 market_data_unavailable`. Note the simulator's `add_ticker` seeds the price synchronously, so newly-added watchlist tickers usually have a price immediately — but defend anyway.
**Warning signs:** `500 internal_error` on trades for valid but freshly-added tickers.

### Pitfall 4: TOCTOU race — validate outside the transaction
**What goes wrong:** Reading cash with `get_db()`, validating, then writing with a separate `get_db_immediate()` lets two concurrent buys both pass the check and double-spend. Success criterion 2 explicitly requires this be prevented.
**Why it happens:** Splitting read and write across connections feels natural.
**How to avoid:** Do the cash/position read, the validation, AND the writes all inside the **same** `get_db_immediate()` block. `BEGIN IMMEDIATE` serializes the second writer until the first commits.
**Warning signs:** A concurrent-buy test ends with cash < 0 or total spent > starting cash.

### Pitfall 5: Session Δ% baseline persisted or recomputed from change_percent
**What goes wrong:** Using `PriceUpdate.change_percent` (tick-over-tick) as "session change," or persisting the baseline, gives the wrong number. PLAN §6 defines session Δ% baseline as the *first price observed after server start / after the ticker was added*.
**Why it happens:** `change_percent` already exists on `PriceUpdate` and looks tempting; and DB persistence feels "more correct."
**How to avoid:** Maintain an in-memory `{ticker: first_seen_price}` map on `app.state`, populated lazily the first time the cache has a price for a ticker. Session Δ% = `(current - baseline)/baseline*100`. Reset on restart (intended). Label the column "Session Δ%".
**Warning signs:** Δ% shows tiny per-tick values instead of cumulative drift since load.

### Pitfall 6: Massive-mode `unknown_ticker` probe applied in simulator mode
**What goes wrong:** Returning `404 unknown_ticker` for tickers the simulator would happily accept. PLAN §6: simulator mode does **format check only** and seeds unknown tickers at $100; Massive mode additionally probes via one REST call.
**Why it happens:** Reading the error table and applying every code unconditionally.
**How to avoid:** Only probe (and only possibly emit `unknown_ticker`) when the active source is `MassiveDataSource`. In sim mode, format check is the entire check. The MVP can defer the Massive probe entirely if Massive mode is out of test scope — but document the deferral. (Default test path is simulator.)
**Warning signs:** Adding a valid uncommon symbol fails in sim mode.

### Pitfall 7: `add_ticker`/`remove_ticker` are coroutines — must be awaited
**What goes wrong:** Calling `market_source.add_ticker(ticker)` without `await` returns a coroutine that never runs; the ticker is in the watchlist DB but never streams.
**Why it happens:** They look like plain methods.
**How to avoid:** The interface is `async`; the watchlist handlers must be `async def` and `await` them (verified in `interface.py`).
**Warning signs:** Added ticker shows in `GET /watchlist` but never gets a price / never appears in SSE.

### Pitfall 8: Blocking sqlite inside an `async def` handler stalls the event loop
**What goes wrong:** Doing `with get_db() as conn: ...` directly in an `async def` runs blocking sqlite on the event loop thread, stalling SSE streaming and other requests under load.
**Why it happens:** Mixing async (needed for `await add_ticker`) with blocking DB calls.
**How to avoid:** Prefer plain `def` handlers for pure-DB endpoints (`GET /portfolio`, `POST /trade`, `GET /history`) — FastAPI runs them in the AnyIO threadpool (default 40 threads). For the watchlist handlers that must `await` the source, either keep DB ops tiny (single-row, fast) or wrap the DB block in `starlette.concurrency.run_in_threadpool`. Document the chosen tradeoff.
**Warning signs:** SSE event latency spikes during heavy trade activity.

## Code Examples

### Example 1: GET /api/portfolio response assembly
See Pattern 1. Response shape per PLAN §8:
`{"cash": float, "positions": [{"ticker","quantity","avg_cost","current_price","unrealized_pnl","pnl_pct"}], "total_value": float}`.

### Example 2: Trade endpoint (HTTP shell over service)
```python
# Source: derived from existing stub portfolio.py + Pattern 2/5 (this repo)
@router.post("/trade")
def execute_trade_route(body: dict, request: Request) -> JSONResponse:   # plain def → threadpool
    ticker = (body.get("ticker") or "").upper()
    result = execute_trade(request.app.state.price_cache,
                           ticker, body.get("side"), body.get("quantity"))
    if isinstance(result, tuple):                 # (code, message, status)
        code, msg, status = result
        return JSONResponse({"error": code, "message": msg}, status_code=status)
    return JSONResponse(result, status_code=200)
```
> The `price_cache` is reachable both as the closure arg passed to `create_portfolio_router(price_cache)` (current wiring) and via `request.app.state.price_cache`. Either works; the closure form matches the existing factory signature.

### Example 3: Ticker validation
```python
# Source: PLAN.md §8 error contract (this repo)
import re
TICKER_RE = re.compile(r"^[A-Z]{1,5}$")
if not TICKER_RE.fullmatch(ticker):
    return JSONResponse({"error": "invalid_ticker",
                         "message": "Ticker must be 1-5 uppercase letters"}, status_code=400)
```

### Example 4: SSE client counter (additive edit to stream.py)
```python
# Source: derived from existing stream.py _generate_events (this repo)
# In _generate_events, accept a counter and inc/dec around the loop:
async def _generate_events(price_cache, request, counter, interval=0.5):
    counter.increment()
    try:
        yield "retry: 1000\n\n"
        ...  # existing loop unchanged
    finally:
        counter.decrement()        # runs on disconnect AND on CancelledError
```
> The `finally` guarantees decrement on both clean disconnect and `asyncio.CancelledError`. `ClientCounter` is a 5-line class with a `Lock` and an int, living outside the market package (e.g. `app/services/snapshots.py` or `app/state.py`).

### Example 5: GET /api/portfolio/history
```python
# Source: PLAN.md §7 portfolio_snapshots + §8 (this repo)
@router.get("/history")
def get_history() -> JSONResponse:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT total_value, recorded_at FROM portfolio_snapshots "
            "WHERE user_id='default' ORDER BY recorded_at ASC").fetchall()
    return JSONResponse([{"total_value": r["total_value"],
                          "recorded_at": r["recorded_at"]} for r in rows])
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pydantic v1 `.dict()` / `Config` class | Pydantic v2 `.model_dump()` / `model_config` | Pydantic 2.0 (2023) | If the planner adds request models, use v2 API (installed 2.12.5) |
| FastAPI `@app.on_event("startup")` | `lifespan=` async context manager | FastAPI 0.93+ (deprecated on_event since) | Phase 1 already uses `lifespan`; add the snapshot task there, not `on_event` |
| `loop.run_in_executor` boilerplate | `starlette.concurrency.run_in_threadpool` / plain `def` handlers | Starlette/FastAPI current | Use `def` handlers or `run_in_threadpool`, not raw executors |

**Deprecated/outdated:**
- `asyncio.DefaultEventLoopPolicy` (used in `tests/conftest.py`) emits a DeprecationWarning on 3.12+ and is slated for removal in 3.16. Not a Phase 2 blocker, but the planner may note it; existing tests still pass with the warning.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Adding an SSE client counter to `stream.py` is an acceptable *additive* edit (not a forbidden "reimplementation" of the complete market package) | Pattern 6 / Pitfall 2 / Example 4 | If forbidden, the snapshot gating (SNAP-01) needs an alternative (e.g. an ASGI middleware wrapping `/api/stream/prices`, or a route override). Low risk — the edit is ~6 lines and additive. **Flag for discuss-phase.** |
| A2 | Massive-mode `unknown_ticker` probe may be deferred for the MVP since default/test path is the simulator | Pitfall 6 / Deferred | If real Massive validation is required in this phase, an extra REST probe + `404` path is needed. Default test env has no `MASSIVE_API_KEY`, so sim path is exercised. |
| A3 | Session Δ% baseline lives in-memory and resets on restart (per PLAN §6) and is acceptable to not persist | Pitfall 5 / Pattern 4 | If product wants baseline to survive restarts, needs a persisted baseline. PLAN §6 explicitly says "after the server starts," so risk is low. |
| A4 | `def` (sync) handlers for the DB-only endpoints are acceptable even though the existing stubs are `async def` | Pattern 2 / Pitfall 8 | If a convention mandates `async def` everywhere, wrap DB calls in `run_in_threadpool` instead. Functionally equivalent. |
| A5 | A `services/` layer is desirable so Phase 3 can reuse trade/watchlist logic | Pattern 5 / structure | If the planner prefers logic in routers, Phase 3 must import the route functions or duplicate logic. Recommended but discretionary. |
| A6 | On a sell, `avg_cost` is unchanged and a full sell deletes the position row | Pattern 2 | Standard weighted-average accounting; PLAN doesn't contradict. If realized-P&L tracking were required it'd differ — but `trades` log already captures realized history. |

## Open Questions

1. **How should the snapshot task observe SSE connection count given the market package is "complete"?**
   - What we know: `stream.py` has no counter today (verified); SNAP-01 requires gating on connection presence.
   - What's unclear: whether editing `stream.py` additively is within the "do not reimplement" rule.
   - Recommendation: Treat a ~6-line additive counter hook as allowed (it's not a reimplementation). If discuss-phase rejects this, fall back to an ASGI middleware that counts `/api/stream/prices` connections without touching the market module. (A1)

2. **Is Massive-mode `unknown_ticker` validation in scope for Phase 2?**
   - What we know: Default + E2E paths use the simulator (no key). PLAN documents the Massive probe.
   - What's unclear: whether the phase must implement the live REST probe now or defer to when Massive is exercised.
   - Recommendation: Implement the simulator path fully; gate the Massive probe behind `isinstance(source, MassiveDataSource)` and ship it if cheap, else defer with a noted TODO. (A2)

3. **Response shape for `POST /watchlist` success** — PLAN §8 says "the new entry"; the exact fields aren't enumerated.
   - Recommendation: Return `{"ticker", "added_at"}` (and optionally current `price`/`session_change_pct`) to match the `GET /watchlist` item shape so the frontend can append without a refetch.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python (uv venv, >=3.12) | All backend code | ✓ | uv 0.11.15, venv targets >=3.12 | — |
| uv | Package mgmt / `uv run` test exec | ✓ | 0.11.15 (at `~/.local/bin/uv`) | — |
| fastapi | Routing | ✓ | 0.128.7 | — |
| starlette | JSONResponse, threadpool | ✓ | 0.52.1 | — |
| pydantic | Optional models | ✓ | 2.12.5 | — |
| pytest / pytest-asyncio | Tests | ✓ | configured (`asyncio_mode=auto`) | — |
| httpx | Async test client (concurrency tests) | ✓ | 0.28.1 (dev) | TestClient (serializes) or raw threads |
| sqlite3 / asyncio / re / uuid (stdlib) | Persistence, scheduling, validation | ✓ | Python stdlib | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none required; for *true*-concurrency trade tests, `httpx.AsyncClient` + `ASGITransport` or raw `threading.Thread` (the proven `test_db.py` approach) substitute for the serializing sync `TestClient`.

> Note: `uv` is at `~/.local/bin/uv`, not on the default non-login PATH. Test/run commands must `export PATH="$HOME/.local/bin:$PATH"` first (or use the absolute path). The full suite's SSE/simulator-timing integration tests are slow under sandbox load (can exceed 2 min); `tests/test_db.py` runs in <1 s and is the fast feedback loop. `[VERIFIED: this session]`

## Validation Architecture

> `nyquist_validation` is `true` in `.planning/config.json` → this section is included.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3+ with pytest-asyncio 0.24+ (`asyncio_mode = auto`) |
| Config file | `backend/pyproject.toml` → `[tool.pytest.ini_options]` (`testpaths=["tests"]`) |
| Quick run command | `export PATH="$HOME/.local/bin:$PATH"; cd backend && uv run --extra dev pytest tests/test_portfolio.py tests/test_watchlist.py -q` |
| Full suite command | `export PATH="$HOME/.local/bin:$PATH"; cd backend && uv run --extra dev pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PORT-01 | portfolio total = cash + Σ(qty×price); P&L per position | unit/integration | `pytest tests/test_portfolio.py::test_get_portfolio_total_matches_cache -x` | ❌ Wave 0 |
| PORT-02 | buy debits cash, weighted-avg cost; `400 insufficient_cash` | unit | `pytest tests/test_portfolio.py::test_buy_insufficient_cash -x` | ❌ Wave 0 |
| PORT-02 | concurrent buys cannot double-spend (BEGIN IMMEDIATE) | concurrency | `pytest tests/test_portfolio.py::test_concurrent_buys_serialize -x` | ❌ Wave 0 |
| PORT-03 | sell credits cash, removes position at 0; `400 insufficient_shares` | unit | `pytest tests/test_portfolio.py::test_sell_oversold -x` | ❌ Wave 0 |
| PORT-04 | history returns ordered snapshot series | unit | `pytest tests/test_portfolio.py::test_history_returns_series -x` | ❌ Wave 0 |
| PORT-05 | fill price = cache price; `503` when cache empty | unit | `pytest tests/test_portfolio.py::test_trade_fills_at_cache_price -x` | ❌ Wave 0 |
| WATCH-01 | GET watchlist returns price + session Δ% (first-observed baseline) | unit | `pytest tests/test_watchlist.py::test_session_change_baseline -x` | ❌ Wave 0 |
| WATCH-02 | format validation → `400 invalid_ticker` | unit | `pytest tests/test_watchlist.py::test_invalid_ticker_format -x` | ❌ Wave 0 |
| WATCH-03 | held-position guard → `400 ticker_held` | unit | `pytest tests/test_watchlist.py::test_remove_held_ticker -x` | ❌ Wave 0 |
| WATCH-04 | 50-cap → `400 watchlist_full` | unit | `pytest tests/test_watchlist.py::test_watchlist_cap -x` | ❌ Wave 0 |
| WATCH-05 | add calls `market_source.add_ticker` | integration | `pytest tests/test_watchlist.py::test_add_seeds_source -x` | ❌ Wave 0 |
| SNAP-01 | snapshot every 30s only while SSE client connected; pauses idle | integration (time-mocked) | `pytest tests/test_snapshots.py::test_cadence_gated_on_clients -x` | ❌ Wave 0 |
| SNAP-02 | snapshot recorded immediately after a trade | unit | `pytest tests/test_snapshots.py::test_snapshot_after_trade -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run --extra dev pytest tests/test_portfolio.py tests/test_watchlist.py tests/test_snapshots.py -q`
- **Per wave merge:** `uv run --extra dev pytest -q` (full suite)
- **Phase gate:** Full suite green before `/gsd:verify-work` (note: SSE-timing tests are slow; allow generous timeout).

### Wave 0 Gaps
- [ ] `backend/tests/test_portfolio.py` — covers PORT-01..05 (incl. concurrency test using `httpx.AsyncClient`+`ASGITransport` or raw threads against `execute_trade`)
- [ ] `backend/tests/test_watchlist.py` — covers WATCH-01..05 (use a mock/spy `market_source` to assert `add_ticker`/`remove_ticker` calls)
- [ ] `backend/tests/test_snapshots.py` — covers SNAP-01/02 (inject a small interval or mock `asyncio.sleep`; assert no snapshot when counter==0)
- [ ] Shared fixtures: a per-test temp DB (reuse the `tmp_path`+`importlib.reload(app.db)` pattern from `test_db.py`/`test_main_integration.py`) and a pre-warmed `PriceCache` fixture seeded with known prices for deterministic P&L assertions.
- [ ] Framework install: none — pytest/pytest-asyncio/httpx already present.

> Concurrency-test note: the synchronous `TestClient` serializes requests, so it CANNOT prove the `BEGIN IMMEDIATE` guarantee. Use either (a) the `test_db.py` raw-`threading.Thread` pattern calling `execute_trade` directly, or (b) `httpx.AsyncClient(transport=ASGITransport(app))` firing two `asyncio.gather`'d POSTs. Option (a) is already proven in this repo.

## Security Domain

> `security_enforcement` is absent from config (treat as enabled). This is a backend write API, so the section applies.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Single-user app, `user_id="default"` hardcoded; no auth layer by design (out of scope AUTH-*) |
| V3 Session Management | no | No sessions/cookies; same-origin SPA |
| V4 Access Control | no | No multi-user; everything operates on the `"default"` user |
| V5 Input Validation | **yes** | Ticker regex `^[A-Z]{1,5}$`; `side ∈ {buy,sell}`; `quantity` positive numeric; reject otherwise with documented `400` codes |
| V6 Cryptography | no | No secrets handled in these endpoints; API keys read elsewhere, never logged |
| V7/V5 Injection | **yes** | **Parameterized SQL only** — all queries use `?` placeholders (never f-string/`%`-format SQL). Verified existing code uses parameter binding |

### Known Threat Patterns for FastAPI + SQLite

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via `ticker` path/body param | Tampering | Parameterized queries (`?` binding) — already the codebase norm; never interpolate `ticker` into SQL |
| Double-spend / race on concurrent buys | Tampering / EoP | `BEGIN IMMEDIATE` read-validate-write inside one transaction (Pattern 2, Pitfall 4) |
| Negative / non-numeric quantity to mint cash or shares | Tampering | `invalid_quantity` guard: `quantity > 0` and numeric, before any write |
| Unbounded watchlist growth (resource exhaustion) | DoS | 50-ticker cap → `watchlist_full` (WATCH-04) — also protects cache/SSE payload |
| Information leak in error messages | Info Disclosure | Error messages are user-facing but contain only dollar amounts/quantities the user already owns; no stack traces (`500 internal_error` is generic) |
| Snapshot table growth on idle | DoS (disk) | Cadence task pauses when no SSE client connected (SNAP-01) — built-in mitigation |

## Sources

### Primary (HIGH confidence)
- This repository (read directly this session): `backend/app/db.py`, `backend/app/main.py`, `backend/app/market/{__init__,cache,interface,stream,models,factory,simulator,seed_prices}.py`, `backend/app/routers/{portfolio,watchlist,chat,health}.py`, `backend/tests/{conftest,test_db,test_main_integration}.py`, `backend/pyproject.toml`, `backend/CLAUDE.md`, `CLAUDE.md`, `planning/PLAN.md`, `planning/MARKET_DATA_SUMMARY.md` — the authoritative contract for shapes, helpers, and constraints.
- Live version verification: `uv run python -c "import fastapi, starlette, pydantic, httpx"` → fastapi 0.128.7 / starlette 0.52.1 / pydantic 2.12.5 / httpx 0.28.1; `uv --version` 0.11.15.
- Live test run: `pytest tests/test_db.py` → 9 passed in 0.44s (confirms `get_db_immediate` BEGIN IMMEDIATE serialization is testable & green).
- FastAPI official docs — lifespan / background tasks: https://fastapi.tiangolo.com/advanced/events/

### Secondary (MEDIUM confidence)
- FastAPI official docs — error handling (HTTPException vs JSONResponse): https://fastapi.tiangolo.com/tutorial/handling-errors/
- FastAPI official docs — concurrency / `def` threadpool behavior: https://fastapi.tiangolo.com/async/

### Tertiary (LOW confidence)
- WebSearch on blocking-sqlite-in-async best practice (cross-referenced with the official `/async/` page above; the official page is the authority): https://fastapi.tiangolo.com/async/ , https://sentry.io/answers/fastapi-difference-between-run-in-executor-and-run-in-threadpool/

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every version verified live via `uv run`; no new packages introduced.
- Architecture: HIGH — patterns derive directly from the repo's own `get_db_immediate`, `price_cache`, and `lifespan`; financial math is standard weighted-average accounting. The one MEDIUM area is *where* the SSE counter lives (A1, depends on interpreting "do not reimplement").
- Pitfalls: HIGH — derived from reading the actual stubs, the error contract, and PLAN's explicit clarifications (session Δ%, held-but-unwatched, Massive vs sim).

**Research date:** 2026-05-21
**Valid until:** 2026-06-20 (stable — local codebase + mature framework; re-verify only if FastAPI/Pydantic are upgraded)
