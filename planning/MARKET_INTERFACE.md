# Market Data Interface — Design Document

## Overview

The market data subsystem uses a **strategy pattern** with a single abstract interface (`MarketDataSource`) implemented by two concrete classes: a GBM simulator (default) and a Massive REST poller (when `MASSIVE_API_KEY` is set). All downstream code — SSE streaming, portfolio valuation, trade execution — reads from a shared `PriceCache` and never touches the data source directly.

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  Environment                                         │
│  MASSIVE_API_KEY set? ─── No ──→ SimulatorDataSource │
│                    └──── Yes ──→ MassiveDataSource   │
└──────────────────────────────────────────────────────┘
                      │
                      ▼ writes to
              ┌───────────────┐
              │  PriceCache   │  (thread-safe, in-memory)
              └───────────────┘
                      │
         ┌────────────┼────────────┐
         ▼            ▼            ▼
    SSE stream    Portfolio    Trade
    endpoint      valuation    execution
```

The `PriceCache` is the single point of truth. Producers write; consumers read. Neither side knows anything about the other.

---

## Module Layout

```
backend/app/market/
├── __init__.py          # Public re-exports
├── models.py            # PriceUpdate dataclass
├── cache.py             # PriceCache
├── interface.py         # MarketDataSource ABC
├── seed_prices.py       # Default tickers, seed prices, GBM params
├── simulator.py         # GBMSimulator + SimulatorDataSource
├── massive_client.py    # MassiveDataSource (Polygon.io REST poller)
├── factory.py           # create_market_data_source() factory function
└── stream.py            # FastAPI SSE router factory
```

---

## Core Types

### `PriceUpdate` — `models.py`

Immutable frozen dataclass representing a single price event.

```python
@dataclass(frozen=True, slots=True)
class PriceUpdate:
    ticker: str
    price: float
    previous_price: float
    timestamp: float          # Unix seconds

    @property
    def change(self) -> float: ...          # absolute delta
    @property
    def change_percent(self) -> float: ...  # percentage delta
    @property
    def direction(self) -> str: ...         # "up" | "down" | "flat"

    def to_dict(self) -> dict: ...          # JSON-serializable
```

`PriceUpdate` is always created by `PriceCache.update()`, never directly. It carries everything the SSE stream and frontend need in one object.

---

### `PriceCache` — `cache.py`

Thread-safe in-memory store. One instance per application, shared by the data source and all consumers.

```python
class PriceCache:
    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate
    def get(self, ticker: str) -> PriceUpdate | None
    def get_price(self, ticker: str) -> float | None
    def get_all(self) -> dict[str, PriceUpdate]     # snapshot copy
    def remove(self, ticker: str) -> None

    @property
    def version(self) -> int   # monotonic counter, bumped on every update
```

The `version` counter enables **change-based SSE**: the SSE handler stores the last version it sent per client and wakes up only when the counter advances, emitting only changed tickers. This avoids no-op events on a stable market.

Internal synchronization uses `threading.Lock` because the Massive client runs its sync SDK in `asyncio.to_thread()`, which means writes may come from a thread pool worker rather than the event loop.

---

### `MarketDataSource` — `interface.py`

Abstract base class. Every implementation must provide these five methods:

```python
class MarketDataSource(ABC):
    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """Begin producing updates. Called once at app startup."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the background task. Safe to call multiple times."""

    @abstractmethod
    async def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the active set. No-op if already present."""

    @abstractmethod
    async def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker. Also removes it from the PriceCache."""

    @abstractmethod
    def get_tickers(self) -> list[str]:
        """Current list of tracked tickers."""
```

Note that `get_tickers` is synchronous — it is safe to call from FastAPI route handlers without `await`.

---

### `create_market_data_source()` — `factory.py`

The only place in the codebase where `MASSIVE_API_KEY` is read. Returns a fully configured `MarketDataSource` without the caller needing to know which implementation it got.

```python
from app.market import PriceCache, create_market_data_source

cache = PriceCache()
source = create_market_data_source(cache)
# Returns SimulatorDataSource if MASSIVE_API_KEY is absent/empty
# Returns MassiveDataSource(poll_interval=15.0) if key is present
```

The factory reads `MASSIVE_API_KEY` from `os.environ` (or the `.env` file loaded at startup). Downstream code never reads this env var directly.

---

## Lifecycle

```python
# FastAPI lifespan handler (startup/shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    cache = PriceCache()
    source = create_market_data_source(cache)

    default_tickers = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
                       "NVDA", "META", "JPM", "V", "NFLX"]
    await source.start(default_tickers)

    app.state.price_cache = cache
    app.state.market_source = source

    yield  # App runs here

    await source.stop()
```

During the app's lifetime, the watchlist API endpoints call `add_ticker` / `remove_ticker` to keep the active set in sync with the database.

---

## Active Ticker Set

The active set is the union of all watchlist tickers and all tickers with a non-zero position. This is enforced at the watchlist API layer:

- `POST /api/watchlist` → calls `source.add_ticker(ticker)` after validating
- `DELETE /api/watchlist/{ticker}` → returns `400 ticker_held` if `quantity > 0`; otherwise calls `source.remove_ticker(ticker)`
- Opening a position on a ticker not in the watchlist → not needed (positions come from buying watchlist tickers)

The `PriceCache` passively mirrors the active set: `remove_ticker` calls `cache.remove(ticker)` before removing from the source.

---

## SSE Streaming — `stream.py`

The SSE router is created by a factory function that closes over the shared `PriceCache`:

```python
from app.market import create_stream_router

router = create_stream_router(price_cache)
# Mounts GET /api/stream/prices
app.include_router(router, prefix="/api")
```

The handler uses version-based change detection to avoid redundant events:

```python
async def generate_events(request: Request) -> AsyncGenerator[str, None]:
    last_version = 0
    while not await request.is_disconnected():
        current_version = price_cache.version
        if current_version > last_version:
            all_prices = price_cache.get_all()
            for update in all_prices.values():
                yield f"data: {json.dumps(update.to_dict())}\n\n"
            last_version = current_version
        else:
            # No change — send heartbeat every 15s to keep connection alive
            yield ": keep-alive\n\n"
        await asyncio.sleep(0.1)
```

---

## Public API Surface (`__init__.py`)

```python
from app.market import (
    PriceUpdate,              # Data type
    PriceCache,               # Shared cache
    MarketDataSource,         # ABC (for type hints)
    create_market_data_source, # Factory
    create_stream_router,     # SSE endpoint factory
)
```

Downstream modules import from `app.market` only — never from the submodules directly. This keeps the internal module boundaries flexible.

---

## Design Decisions

### Why a shared cache rather than direct reads?

The data source runs on its own cadence (500ms for simulator, 15s for Massive). If consumers read directly from the source, they'd be blocked waiting for the next poll. The cache decouples producer cadence from consumer reads: the SSE handler can sample at any rate and always gets the freshest available price.

### Why threading.Lock rather than asyncio.Lock?

The Massive client SDK is synchronous. `asyncio.to_thread()` runs it in a thread pool worker, which means `cache.update()` may be called from outside the event loop. `threading.Lock` is safe from both threads and the event loop (it doesn't require `await`).

### Why synchronous `get_tickers()`?

FastAPI route handlers call `get_tickers()` to check whether a ticker is already tracked. Making it synchronous avoids `await` ceremony in handlers and is safe because the tickers list is guarded by the GIL (simulator) or is a plain Python list mutation (Massive).

### Why not WebSockets?

SSE is one-way server→client push, which is all the market data stream needs. It's simpler, requires no handshake protocol, works through HTTP/2 multiplexing, and has universal browser support via the native `EventSource` API. WebSockets would add bidirectional complexity with no benefit.
