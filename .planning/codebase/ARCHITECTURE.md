<!-- refreshed: 2026-05-21 -->
# Architecture

**Analysis Date:** 2026-05-21

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│              Browser (EventSource + REST fetch)              │
│              frontend/ — Next.js static export               │
│              [NOT YET BUILT — directory is empty]            │
└───────────────────────────┬─────────────────────────────────┘
                            │  HTTP / SSE (port 8000, same origin)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI (uvicorn, port 8000)                    │
│  ├── /api/stream/prices      SSE streaming                   │
│  ├── /api/portfolio/*        Portfolio & trades              │
│  ├── /api/watchlist/*        Watchlist management            │
│  ├── /api/chat               LLM chat (planned)              │
│  ├── /api/health             Health check                    │
│  └── /*                      Static file serving (Next.js)  │
│                              backend/app/                    │
└───────────┬─────────────────────┬────────────────────────────┘
            │                     │
            ▼                     ▼
┌───────────────────┐   ┌─────────────────────────────────────┐
│  SQLite           │   │  Market Data Subsystem               │
│  db/finally.db    │   │  backend/app/market/                 │
│  (volume-mounted) │   │                                      │
│  [PLANNED]        │   │  MarketDataSource (ABC)              │
└───────────────────┘   │  ├── SimulatorDataSource (GBM)      │
                        │  └── MassiveDataSource (Polygon.io)  │
                        │           │                          │
                        │           ▼                          │
                        │       PriceCache                     │
                        │           │                          │
                        │           ▼                          │
                        │  SSE stream /api/stream/prices       │
                        └─────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `PriceUpdate` | Immutable price snapshot — ticker, price, previous_price, timestamp, change, direction | `backend/app/market/models.py` |
| `PriceCache` | Thread-safe in-memory store of latest price per ticker; version counter for SSE diffing | `backend/app/market/cache.py` |
| `MarketDataSource` | Abstract interface: `start/stop/add_ticker/remove_ticker/get_tickers` | `backend/app/market/interface.py` |
| `SimulatorDataSource` | GBM-based simulator running as an asyncio background task; writes to PriceCache every 500ms | `backend/app/market/simulator.py` |
| `GBMSimulator` | Core GBM math with Cholesky-correlated sector moves and random shock events | `backend/app/market/simulator.py` |
| `MassiveDataSource` | REST polling client for Polygon.io via `massive` package; writes to PriceCache on poll interval | `backend/app/market/massive_client.py` |
| `create_market_data_source` | Factory — selects `SimulatorDataSource` or `MassiveDataSource` based on `MASSIVE_API_KEY` env var | `backend/app/market/factory.py` |
| `create_stream_router` | FastAPI router factory for SSE endpoint; injects `PriceCache` dependency without globals | `backend/app/market/stream.py` |
| Seed data | Realistic seed prices ($190 AAPL etc.), per-ticker GBM params, sector correlation groups | `backend/app/market/seed_prices.py` |
| `market_data_demo.py` | Standalone Rich terminal dashboard demonstrating the market subsystem in isolation | `backend/market_data_demo.py` |

## Pattern Overview

**Overall:** Strategy pattern + Producer-Consumer with a shared cache

**Key Characteristics:**
- Data producers (`SimulatorDataSource` / `MassiveDataSource`) are interchangeable via the `MarketDataSource` ABC — downstream code never imports a concrete source directly
- `PriceCache` decouples producers from consumers; SSE streaming, portfolio valuation, and trade execution all read from the cache
- Factory function (`create_market_data_source`) encapsulates environment-variable selection logic in one place
- Router factories (`create_stream_router`) inject dependencies (PriceCache) without module-level globals
- All FastAPI app code lives under `backend/app/`; the `backend/app/market/` subpackage is the only implemented subsystem so far

## Layers

**Data Model Layer:**
- Purpose: Immutable value objects representing domain concepts
- Location: `backend/app/market/models.py`
- Contains: `PriceUpdate` frozen dataclass with computed properties
- Depends on: Nothing (pure Python)
- Used by: PriceCache, SSE stream, all consumers

**Cache Layer:**
- Purpose: Thread-safe shared mutable state bridging async producers and consumers
- Location: `backend/app/market/cache.py`
- Contains: `PriceCache` with `threading.Lock`, monotonic version counter
- Depends on: `models.py`
- Used by: `SimulatorDataSource`, `MassiveDataSource`, SSE stream generator

**Data Source Layer:**
- Purpose: Price generation/fetching background tasks writing to PriceCache
- Location: `backend/app/market/simulator.py`, `backend/app/market/massive_client.py`
- Contains: `GBMSimulator`, `SimulatorDataSource`, `MassiveDataSource`
- Depends on: `cache.py`, `interface.py`, `seed_prices.py`
- Used by: FastAPI startup lifecycle (not yet wired — startup code is planned)

**Configuration/Seed Layer:**
- Purpose: Externalize per-ticker constants and correlation parameters
- Location: `backend/app/market/seed_prices.py`
- Contains: `SEED_PRICES`, `TICKER_PARAMS`, `CORRELATION_GROUPS`, correlation constants
- Depends on: Nothing
- Used by: `GBMSimulator`

**Interface/Contract Layer:**
- Purpose: Abstract base class enforcing the data source contract
- Location: `backend/app/market/interface.py`
- Contains: `MarketDataSource` ABC
- Depends on: Nothing
- Used by: `SimulatorDataSource`, `MassiveDataSource`, `create_market_data_source`

**Factory Layer:**
- Purpose: Environment-variable-driven selection of concrete implementations
- Location: `backend/app/market/factory.py`
- Contains: `create_market_data_source(price_cache) -> MarketDataSource`
- Depends on: `cache.py`, `interface.py`, `simulator.py`, `massive_client.py`
- Used by: FastAPI app startup (planned)

**SSE Transport Layer:**
- Purpose: Long-lived HTTP streaming of price updates to browser clients
- Location: `backend/app/market/stream.py`
- Contains: `create_stream_router(price_cache)` factory, `_generate_events` async generator
- Depends on: `cache.py`, FastAPI
- Used by: FastAPI app router registration (planned)

**Public API (Package `__init__`):**
- Purpose: Controlled public surface of the `app.market` package
- Location: `backend/app/market/__init__.py`
- Exports: `PriceUpdate`, `PriceCache`, `MarketDataSource`, `create_market_data_source`, `create_stream_router`

## Data Flow

### Price Generation → SSE Client

1. `SimulatorDataSource._run_loop()` fires every 500ms (`backend/app/market/simulator.py:260`)
2. `GBMSimulator.step()` produces `{ticker: new_price}` using GBM with Cholesky-correlated draws (`simulator.py:74`)
3. `PriceCache.update(ticker, price)` stores the new `PriceUpdate` and bumps `_version` (`cache.py:23`)
4. `_generate_events()` wakes every 500ms, compares `cache.version` to `last_version` (`stream.py:54`)
5. On version change, serializes all prices to JSON and yields `data: {...}\n\n` as SSE event (`stream.py:87`)
6. Browser `EventSource` receives event; frontend updates watchlist/sparklines (frontend not yet built)

### Heartbeat (No Price Change)

1. If no version change for 15 seconds, `_generate_events` yields `": keep-alive\n\n"` (`stream.py:92`)
2. Prevents proxy/browser from closing idle SSE connection

### Ticker Lifecycle (Add/Remove)

1. Caller invokes `await source.add_ticker("TSLA")` on the active `MarketDataSource`
2. `SimulatorDataSource.add_ticker()` delegates to `GBMSimulator.add_ticker()`, which rebuilds the Cholesky correlation matrix (`simulator.py:120`)
3. Cache is immediately seeded with the new ticker's initial price (`simulator.py:244`)
4. Conversely, `remove_ticker()` drops the ticker from both simulator and cache (`simulator.py:251`)

### Massive API Polling

1. `MassiveDataSource._poll_loop()` sleeps `poll_interval` seconds (default 15s for free tier) (`massive_client.py:83`)
2. `_poll_once()` calls `asyncio.to_thread(self._fetch_snapshots)` to avoid blocking the event loop (`massive_client.py:97`)
3. `RESTClient.get_snapshot_all()` fetches all active tickers in one API call (`massive_client.py:125`)
4. Each snapshot's `last_trade.price` and `last_trade.timestamp / 1000` are written to `PriceCache` (`massive_client.py:102`)

**State Management:**
- Prices: `PriceCache` holds the single source of truth for current prices; thread-safe via `threading.Lock`
- Simulator internal state: `GBMSimulator._prices` holds the running simulation prices (separate from cache)
- SSE client state: per-connection `last_version` integer tracked inside the async generator closure
- All other state (portfolio, watchlist, trades, chat): SQLite database — not yet implemented

## Key Abstractions

**`MarketDataSource` (ABC):**
- Purpose: Uniform lifecycle interface for any price data provider
- Examples: `backend/app/market/simulator.py` (`SimulatorDataSource`), `backend/app/market/massive_client.py` (`MassiveDataSource`)
- Pattern: Strategy; callers only reference the ABC, never the concrete class

**`PriceCache` (thread-safe store):**
- Purpose: Decouple async producers (background tasks) from sync/async consumers (SSE, API handlers)
- Examples: `backend/app/market/cache.py`
- Pattern: Shared mutable state with explicit locking; version counter enables change detection without polling

**`PriceUpdate` (frozen dataclass):**
- Purpose: Immutable value object for one price tick; computed properties for direction/change/percent
- Examples: `backend/app/market/models.py`
- Pattern: Frozen dataclass with `__slots__`; `to_dict()` for JSON serialization

**Router Factories:**
- Purpose: Inject dependencies (PriceCache) into FastAPI router closures without module globals
- Examples: `create_stream_router(price_cache)` in `backend/app/market/stream.py`
- Pattern: Factory function returning `APIRouter`; the `PriceCache` instance is captured in closure scope

## Entry Points

**`market_data_demo.py`:**
- Location: `backend/market_data_demo.py`
- Triggers: `uv run market_data_demo.py` from `backend/`
- Responsibilities: Standalone demonstration — creates `PriceCache`, starts `SimulatorDataSource`, renders a Rich terminal dashboard for 60 seconds

**FastAPI Application (planned):**
- Location: Not yet created; will live at `backend/app/main.py` per convention
- Triggers: `uvicorn app.main:app` (run by Docker CMD)
- Responsibilities: Register SSE router (`create_stream_router`), start market data source on lifespan startup, serve Next.js static export, handle portfolio/watchlist/chat REST routes

## Architectural Constraints

- **Threading:** Python asyncio event loop for the FastAPI/uvicorn server. Background price tasks (`SimulatorDataSource._run_loop`, `MassiveDataSource._poll_loop`) are asyncio `Task`s on the same loop. `PriceCache` uses `threading.Lock` to be safe if ever accessed from threads (e.g., the Massive REST client runs in `asyncio.to_thread`).
- **Global state:** No module-level singletons in the market subsystem. `PriceCache` and `MarketDataSource` instances are intended to be created at app startup and passed via dependency injection. Demo script (`market_data_demo.py`) creates its own local instances.
- **Circular imports:** None detected. Import graph is strictly layered: `models` ← `cache` ← `simulator`/`massive_client` ← `factory`; `stream` depends only on `cache`.
- **Single user:** Database schema includes `user_id` columns defaulting to `"default"` — hardcoded single-user for now.
- **SSE, not WebSockets:** One-way server→client push only. The browser sends commands via normal REST POST endpoints, not over the SSE channel.
- **Static export:** Frontend is a Next.js static export served by FastAPI; no separate Next.js server process.

## Anti-Patterns

### Accessing private simulator state in tests

**What happens:** `test_simulator.py` accesses `sim._tickers` and `sim._cholesky` directly to assert internal state (e.g., `assert sim._cholesky is None`).
**Why it's wrong:** Tests coupled to private implementation details break when internals are refactored.
**Do this instead:** Use `sim.get_tickers()` for the ticker list; expose a `has_correlation_matrix()` boolean if needed, or test behavior rather than state.

### Synchronous Massive REST client on asyncio loop

**What happens:** `massive.RESTClient` is synchronous; `MassiveDataSource._fetch_snapshots` wraps it in `asyncio.to_thread()` (`massive_client.py:97`).
**Why it's wrong:** Not truly an anti-pattern here — `to_thread` is the correct pattern — but the thread-pool size is the default, which could queue under high load.
**Do this instead:** The current approach is correct. For higher throughput, consider an async HTTP client (e.g., `httpx`) if the `massive` package is replaced.

## Error Handling

**Strategy:** Errors are caught and logged at the boundary; background loops continue running.

**Patterns:**
- `SimulatorDataSource._run_loop()` wraps `self._sim.step()` in `try/except Exception` with `logger.exception()` — loop never crashes (`simulator.py:263`)
- `MassiveDataSource._poll_once()` wraps the entire poll in `try/except Exception` with `logger.error()` — poller retries on next interval (`massive_client.py:118`)
- `MassiveDataSource._poll_once()` inner loop has a narrower `try/except (AttributeError, TypeError)` to skip malformed snapshots without aborting the batch (`massive_client.py:107`)
- `_generate_events()` catches `asyncio.CancelledError` and logs disconnection cleanly (`stream.py:97`)
- REST error contract (planned): all non-2xx responses use `{"error": "<code>", "message": "<human>"}` shape

## Cross-Cutting Concerns

**Logging:** `logging.getLogger(__name__)` in every module. Uses uvicorn's default stdout formatter at `INFO` level. `DEBUG` used for high-frequency events (simulator random shocks, Massive poll counts). No log files.

**Validation:** Ticker format validation (`^[A-Z]{1,5}$`) is a planned REST layer concern (watchlist endpoint). The market subsystem itself accepts any string ticker.

**Authentication:** None. Single-user, no auth layer. `user_id = "default"` hardcoded in all DB operations.

---

*Architecture analysis: 2026-05-21*
