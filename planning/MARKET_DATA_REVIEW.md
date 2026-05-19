# Market Data Backend — Code Review

**Date:** 2026-05-19  
**Reviewer:** Claude Code  
**Scope:** `backend/app/market/` (8 source files, ~500 LOC) and `backend/tests/market/` (6 test files, 73 tests)  
**Branch reviewed:** `main` (commit `a4de896`)

---

## 1. Test Results

**73 tests, 73 passing. 0 failures.**

```
tests/market/test_cache.py          13 passed
tests/market/test_factory.py         7 passed
tests/market/test_massive.py        13 passed
tests/market/test_models.py         11 passed
tests/market/test_simulator.py      17 passed
tests/market/test_simulator_source.py 10 passed
```

Runtime: 2.1 seconds. `pytest-asyncio` in `auto` mode handles all async tests correctly.

**Lint (ruff):** Clean. All checks pass with no warnings.

---

## 2. Coverage

```
Name                           Stmts   Miss  Cover
----------------------------------------------------
app/market/__init__.py             6      0   100%
app/market/cache.py               39      0   100%
app/market/factory.py             15      0   100%
app/market/interface.py           13      0   100%
app/market/massive_client.py      67      4    94%
app/market/models.py              26      0   100%
app/market/seed_prices.py          8      0   100%
app/market/simulator.py          139      3    98%
app/market/stream.py              44     30    32%
----------------------------------------------------
TOTAL                            357     37    90%
```

Overall: **90%**. Six modules are at 94-100%. The outlier is `stream.py` at 32%.

### Coverage gaps

| Module | Uncovered lines | Reason |
|--------|-----------------|--------|
| `stream.py` | 29–51, 65–98 | SSE endpoint body and `_generate_events` generator — no ASGI test client used in this suite |
| `simulator.py` | 149, 268–269 | Duplicate-guard in `_add_ticker_internal`; exception branch in `_run_loop` |
| `massive_client.py` | 85–87, 125 | `_poll_loop` sleep/poll cycle; `_fetch_snapshots` body — always mocked via `patch.object` |

The `massive_client.py` and `simulator.py` gaps are acceptable and expected. The `stream.py` gap is the only meaningful risk (detailed below).

---

## 3. Previous Review — Resolved Issues

A prior review (2026-02-10, archived at `planning/archive/MARKET_DATA_REVIEW.md`) identified 7 issues. All have been resolved in the current codebase:

| # | Issue | Status |
|---|-------|--------|
| 1 | Missing `[tool.hatch.build.targets.wheel]` in `pyproject.toml` | Fixed |
| 2 | Lazy `massive` import caused test failures when package absent | Fixed — import moved to module top level |
| 3 | `_generate_events` annotated `-> None` instead of `-> AsyncGenerator[str, None]` | Fixed |
| 4 | `SimulatorDataSource.get_tickers()` reached into `GBMSimulator._tickers` | Fixed — `GBMSimulator.get_tickers()` public method added |
| 5 | Unused `DEFAULT_CORR` constant alongside `CROSS_GROUP_CORR` | Fixed — deduplicated |
| 6 | Unused imports in 4 test files (pytest, math, asyncio) | Fixed — ruff passes clean |
| 7 | Massive test mocks targeted wrong names, 5 tests failing | Fixed — all 73 pass |

---

## 4. Architecture Assessment

The subsystem correctly implements the strategy described in `PLAN.md` and `planning/MARKET_INTERFACE.md`.

```
MarketDataSource (ABC)
├── SimulatorDataSource   ← GBM engine, asyncio task, no external deps
└── MassiveDataSource     ← REST poller, asyncio.to_thread for sync SDK
          │
          ▼
    PriceCache (thread-safe, version-stamped)
          │
  ┌───────┼────────┐
  ▼       ▼        ▼
SSE   Portfolio  Trade
```

**What is done well:**

- **Strategy pattern is clean.** `MarketDataSource` ABC requires five methods; both implementations satisfy it fully. Downstream code is genuinely source-agnostic.
- **PriceCache as single point of truth.** Producers write; consumers read. No direct coupling across the boundary. Thread-safety via `threading.Lock` is the right choice given the Massive client runs via `asyncio.to_thread`.
- **GBM math is correct.** The Itô-corrected formula `S(t+dt) = S(t) * exp((mu - sigma²/2)*dt + sigma*sqrt(dt)*Z)` ensures log-normal prices and guarantees positivity. `DEFAULT_DT` is correctly computed for 500ms ticks over a 252-day, 6.5h trading year.
- **Cholesky decomposition for correlated moves** is mathematically sound. The sector-based correlation structure (tech: 0.6, finance: 0.5, cross/TSLA: 0.3) is realistic. The matrix is always positive definite given these values.
- **Immediate cache seeding.** Both `start()` methods seed the cache before the background loop begins. The SSE endpoint and watchlist API never see an empty cache on the first request.
- **Exception resilience in hot paths.** Both `_run_loop` (simulator) and `_poll_once` (Massive) catch and log exceptions without crashing the background task.
- **SSE implementation follows the spec.** Version-based change detection avoids redundant no-op events. `retry: 1000` gives browser auto-reconnect. `X-Accel-Buffering: no` prevents nginx buffering. Heartbeat fires at 15s to prevent proxy timeout.
- **Factory is the sole `MASSIVE_API_KEY` reader.** No other module touches this env var — easy to test and reason about.

---

## 5. Issues Found

### 5.1 `timestamp or time.time()` treats zero as missing (Severity: Low)

**File:** `cache.py:30`

```python
ts = timestamp or time.time()
```

If `timestamp=0.0` is passed (valid Unix epoch), it evaluates as falsy and is silently replaced with the current time. This is unlikely to matter in practice (no real trade price timestamps are from 1970), but it is a semantic error. The Massive client converts millisecond timestamps to seconds (`snap.last_trade.timestamp / 1000.0`), so the exposure is limited. Regardless, the pattern is fragile.

**Fix:**
```python
ts = timestamp if timestamp is not None else time.time()
```

---

### 5.2 Module-level SSE router singleton (Severity: Low)

**File:** `stream.py:20–28`

```python
router = APIRouter(prefix="/api/stream", tags=["streaming"])  # module-level

def create_stream_router(price_cache: PriceCache) -> APIRouter:
    @router.get("/prices")
    async def stream_prices(request: Request) -> StreamingResponse:
        ...
    return router
```

`router` is created once at import time. Each call to `create_stream_router()` registers an additional `/prices` route on the same `APIRouter` object. If called twice (e.g., in two different tests or if accidentally called twice in app startup), the second call would register a duplicate route. FastAPI typically ignores duplicate routes silently, returning whichever was registered first — so the second cache injection would be lost without any error.

In normal app usage this is a single call and causes no problem. For testing the SSE endpoint with different cache instances it would silently fail.

**Fix:** Move `router` instantiation inside `create_stream_router()`:
```python
def create_stream_router(price_cache: PriceCache) -> APIRouter:
    router = APIRouter(prefix="/api/stream", tags=["streaming"])

    @router.get("/prices")
    async def stream_prices(request: Request) -> StreamingResponse:
        ...
    return router
```

---

### 5.3 `add_ticker` normalization inconsistency (Severity: Low)

**Files:** `massive_client.py:67–68`, `simulator.py:120–125`

`MassiveDataSource.add_ticker()` normalizes its input:
```python
ticker = ticker.upper().strip()
```

`SimulatorDataSource.add_ticker()` does not:
```python
async def add_ticker(self, ticker: str) -> None:
    if self._sim:
        self._sim.add_ticker(ticker)
```

In practice the watchlist API validates format with `^[A-Z]{1,5}$` before calling `add_ticker`, so lowercase input never reaches here. But the two implementations behave differently at their own interface boundary, which violates the Liskov Substitution Principle expectation that both sources behave identically.

**Fix:** Add normalization to `SimulatorDataSource.add_ticker()` and `remove_ticker()`, matching Massive's behavior, or remove normalization from Massive and rely entirely on the API layer.

---

### 5.4 `version` property reads without lock (Severity: Trivial)

**File:** `cache.py:64–66`

```python
@property
def version(self) -> int:
    return self._version
```

All other `PriceCache` methods acquire `self._lock` before reading `self._prices` or `self._version`. This one does not. On CPython, reading a single `int` is atomic due to the GIL. On Python 3.13+ with the experimental no-GIL build (PEP 703), this could be a race condition.

This is a trivial concern for 2026, but the inconsistency is a code smell — readers of the class expect the lock discipline to be uniform.

**Fix:** Either acquire the lock here, or add a comment explaining why it's intentionally exempt.

---

### 5.5 SSE streaming is untested (Severity: Medium)

**File:** `stream.py` (32% coverage)

`_generate_events()` — the core SSE generator — is not tested. It contains non-trivial logic: version-based change detection, heartbeat timing, disconnect detection, and event formatting. The untested paths include:

- The `retry: 1000\n\n` initial event
- Version change detection and price payload formatting
- The 15-second heartbeat branch
- Client disconnect detection and graceful loop exit
- `asyncio.CancelledError` handling

The SSE stream is the primary data channel to the frontend. A regression here would break the entire real-time UI with no test catching it.

**Recommendation:** Add at least two tests using `httpx.AsyncClient` with `asgi_transport`:

1. **Happy path:** Start a `SimulatorDataSource`, create a `FastAPI` app that mounts the stream router, make an SSE request, assert at least one `data:` event is received with the correct JSON structure.
2. **Heartbeat:** Mock the cache's version to never change, assert a `: keep-alive` comment is emitted within the heartbeat window.

```python
# Example pattern
from httpx import AsyncClient, ASGITransport

async def test_sse_emits_price_events():
    cache = PriceCache()
    cache.update("AAPL", 190.50)
    app = FastAPI()
    app.include_router(create_stream_router(cache), prefix="/api")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        async with client.stream("GET", "/api/stream/prices") as response:
            assert response.status_code == 200
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    payload = json.loads(line[5:])
                    assert "AAPL" in payload
                    break
```

---

## 6. Design Observations

### 6.1 SSE emits all prices on every version bump, not only changed tickers

The PLAN.md spec says:

> "The server emits events on price change, not on a fixed timer. … the SSE handler holds the last version it sent per client and pushes the diff whenever the counter advances."

The word **"diff"** implies only changed tickers. The implementation sends all prices whenever any version change is detected:

```python
if current_version != last_version:
    prices = price_cache.get_all()  # all tickers
    data = {ticker: update.to_dict() for ticker, update in prices.items()}
```

With the GBM simulator running at 500ms intervals, all tickers update every tick, so all prices change together — making "diff" and "all" equivalent in practice. With the Massive poller, it similarly fetches all watched tickers per poll.

This is not a bug for the current design, but if the architecture ever moves toward per-ticker update granularity (e.g., WebSocket feed), the SSE layer would need revisiting. The comment in the spec is slightly misleading about the current behavior.

### 6.2 GBM parameter choices are well-calibrated

The per-ticker sigma values (TSLA: 0.50, V: 0.17) approximate real-world annualized volatility. The shock event rate (0.1% per tick × 10 tickers × 2 ticks/sec ≈ 1 event per 50s) is tuned well — visible but not chaotic. TSLA's correlation override (0.3 against all tickers) is a nice realistic touch.

### 6.3 No cap on PriceCache memory

The `PriceCache` holds one `PriceUpdate` per ticker. At a 50-ticker watchlist cap, each `PriceUpdate` costs roughly 200 bytes. Total memory usage is bounded at ~10KB regardless of session length — there is no memory leak risk.

### 6.4 Massive client ticker list is not thread-safe

`MassiveDataSource._tickers` is a plain `list[str]`. `add_ticker()` and `remove_ticker()` mutate it from the async event loop, while `_fetch_snapshots()` reads it from a thread via `asyncio.to_thread`. On CPython, list reads/writes are effectively atomic due to the GIL, but this is not guaranteed.

In practice: a `_fetch_snapshots` call reading `self._tickers` while `remove_ticker` filters it would see either the old or new list (not a corrupted intermediate state). This is safe on CPython today, but worth noting if no-GIL Python becomes a target.

---

## 7. Spec Compliance Checklist

| Requirement (PLAN.md) | Status |
|-----------------------|--------|
| Two implementations behind one ABC | ✅ |
| GBM with configurable drift and volatility | ✅ |
| ~500ms update interval | ✅ |
| Correlated moves (Cholesky) | ✅ |
| Occasional 2–5% shock events | ✅ |
| Starts from realistic seed prices | ✅ |
| Massive REST polling (not WebSocket) | ✅ |
| Free tier: 15-second poll interval (default) | ✅ |
| Single in-memory price cache | ✅ |
| SSE endpoint `GET /api/stream/prices` | ✅ |
| Events on price change (version-based) | ✅ |
| Heartbeat every 15s | ✅ |
| `retry:` directive for auto-reconnect | ✅ |
| New tickers seed at $100.00 (simulator) | ✅ |
| Massive mode validates ticker via API call | ✅ (`validate_ticker` pattern in doc, not yet wired to watchlist API — but that's the API layer's job) |
| 50-ticker watchlist cap | N/A — enforced at API layer, not market module |
| `ticker_held` delete guard | N/A — API layer concern |
| `session_change` baseline (first cache price) | Partial — cache records first price as `previous_price == price` (flat); session delta tracking is the frontend's responsibility |

---

## 8. Verdict

The market data backend is well-built. The GBM math is correct, the architecture is clean, the strategy pattern is properly applied, and all 73 tests pass with clean linting. The previous review's 7 issues have all been resolved.

**Must fix before shipping:**

None. The implementation is production-ready for its scope.

**Should fix before the next component integrates against this:**

1. **`timestamp or time.time()` → `timestamp if timestamp is not None else time.time()`** (`cache.py:30`) — avoids a silent semantic bug that would be hard to debug if it ever surfaced.
2. **SSE streaming tests** (`stream.py`) — 32% coverage on the primary data channel is the most significant risk. Add at least one ASGI integration test using `httpx`.
3. **Module-level `router` singleton** (`stream.py:20`) — move inside `create_stream_router()` to make the function idempotent and testable.

**Nice to have:**

4. `add_ticker` normalization symmetry between `SimulatorDataSource` and `MassiveDataSource`.
5. Lock discipline consistency for `PriceCache.version`.
