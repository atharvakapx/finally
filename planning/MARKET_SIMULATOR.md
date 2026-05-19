# Market Simulator — Design Document

## Overview

The simulator generates realistic-looking stock price movements without any external API dependency. It uses **Geometric Brownian Motion (GBM)** with **Cholesky-correlated moves** across tickers and occasional random shock events. It runs as an `asyncio` background task at 500ms intervals.

---

## Why GBM?

GBM is the standard model underlying the Black-Scholes options pricing formula. It has two properties that make simulated prices look plausible:

1. **Log-normal distribution** — prices can only go positive (a stock can never go below zero)
2. **Proportional moves** — a 1% move on a $10 stock and a $1000 stock are equally likely; the absolute dollar move scales with price

The discrete-time GBM formula:

```
S(t + dt) = S(t) * exp((mu - 0.5 * sigma^2) * dt + sigma * sqrt(dt) * Z)
```

Where:
- `S(t)` — current price
- `mu` — annualized drift (expected return, e.g. 0.05 = 5%/year)
- `sigma` — annualized volatility (e.g. 0.25 = 25%/year)
- `dt` — time step as a fraction of a trading year
- `Z` — standard normal random variable (correlated across tickers)

At 500ms tick cadence with a 252-day, 6.5h trading year:

```
dt = 0.5 / (252 * 6.5 * 3600) ≈ 8.48e-8
```

This dt is tiny, so per-tick moves are sub-cent. They accumulate naturally over time to produce realistic-looking drift and volatility without extreme jumps on every tick.

---

## Correlated Moves (Cholesky Decomposition)

Real stocks don't move independently — tech stocks tend to move together, financials tend to move together, and sectors have some cross-correlation. The simulator models this with a correlation matrix and Cholesky decomposition.

### Algorithm

1. Build an n×n correlation matrix `C` where `C[i][j]` is the pairwise correlation between ticker i and ticker j.
2. Compute the Cholesky factor `L` such that `L @ L.T == C`.
3. Each tick: generate `n` independent standard normal draws `z_independent`, then compute `z_correlated = L @ z_independent`.
4. Use the correlated draws in the GBM formula — correlated tickers will tend to move in the same direction on any given tick.

```python
# Rebuild Cholesky whenever tickers are added/removed
corr = np.eye(n)
for i, j in itertools.combinations(range(n), 2):
    rho = pairwise_correlation(tickers[i], tickers[j])
    corr[i, j] = corr[j, i] = rho

L = np.linalg.cholesky(corr)

# Each tick
z_independent = np.random.standard_normal(n)
z_correlated = L @ z_independent
```

This is O(n²) to rebuild and O(n) per tick. At n < 50 tickers, both are negligible.

---

## Correlation Structure

Defined in `seed_prices.py`:

| Relationship | Correlation | Rationale |
|---|---|---|
| Tech–tech (AAPL, GOOGL, MSFT, AMZN, META, NVDA, NFLX) | 0.6 | Same sector, shared macro drivers |
| Finance–finance (JPM, V) | 0.5 | Interest rate sensitivity |
| TSLA with anything | 0.3 | Notoriously idiosyncratic, does its own thing |
| Cross-sector | 0.3 | Broad market correlation (SPY effect) |
| Unknown/new tickers | 0.3 | Conservative default |

The correlation matrix is always positive definite because:
- Diagonal is 1.0
- All off-diagonal values are < 1.0 and positive
- The values are consistent (no logical contradictions)

---

## Shock Events

To add visual drama and simulate earnings / news events, the simulator applies occasional random price shocks:

```python
if random.random() < event_probability:  # default: 0.001 per tick
    shock_magnitude = random.uniform(0.02, 0.05)   # 2-5% move
    shock_sign = random.choice([-1, 1])
    price *= 1 + shock_magnitude * shock_sign
```

At `event_probability=0.001` with 10 tickers at 2 ticks/second, the expected rate is one shock event every ~50 seconds across the whole watchlist. This is frequent enough to be visible and entertaining without dominating the price action.

---

## Seed Prices and Per-Ticker Parameters

Defined in `seed_prices.py`. New tickers added dynamically use `DEFAULT_PARAMS` and seed at $100.00.

```python
SEED_PRICES = {
    "AAPL": 190.00,
    "GOOGL": 175.00,
    "MSFT": 420.00,
    "AMZN": 185.00,
    "TSLA": 250.00,
    "NVDA": 800.00,
    "META": 500.00,
    "JPM": 195.00,
    "V":   280.00,
    "NFLX": 600.00,
}

TICKER_PARAMS = {
    "AAPL":  {"sigma": 0.22, "mu": 0.05},  # Moderate volatility
    "GOOGL": {"sigma": 0.25, "mu": 0.05},
    "MSFT":  {"sigma": 0.20, "mu": 0.05},  # Lowest of big tech
    "AMZN":  {"sigma": 0.28, "mu": 0.05},
    "TSLA":  {"sigma": 0.50, "mu": 0.03},  # High vol, lower drift
    "NVDA":  {"sigma": 0.40, "mu": 0.08},  # High vol, strong drift
    "META":  {"sigma": 0.30, "mu": 0.05},
    "JPM":   {"sigma": 0.18, "mu": 0.04},  # Low vol bank stock
    "V":     {"sigma": 0.17, "mu": 0.04},  # Lowest vol in set
    "NFLX":  {"sigma": 0.35, "mu": 0.05},
}

DEFAULT_PARAMS = {"sigma": 0.25, "mu": 0.05}  # Unknown tickers
```

---

## Code Structure

### `GBMSimulator` — pure math, no I/O

```python
class GBMSimulator:
    def __init__(self, tickers: list[str], dt: float = DEFAULT_DT,
                 event_probability: float = 0.001): ...

    def step(self) -> dict[str, float]:
        """Advance all tickers by one time step. Returns {ticker: new_price}.
        Hot path — called every 500ms."""

    def add_ticker(self, ticker: str) -> None:
        """Add ticker, seed price, and rebuild Cholesky."""

    def remove_ticker(self, ticker: str) -> None:
        """Remove ticker and rebuild Cholesky."""

    def get_price(self, ticker: str) -> float | None: ...
    def get_tickers(self) -> list[str]: ...
```

`GBMSimulator` is a pure math engine with no async code and no external dependencies beyond `numpy`. It's independently testable.

### `SimulatorDataSource` — async wrapper

```python
class SimulatorDataSource(MarketDataSource):
    def __init__(self, price_cache: PriceCache, update_interval: float = 0.5,
                 event_probability: float = 0.001): ...

    async def start(self, tickers: list[str]) -> None:
        """Create GBMSimulator, seed cache, start _run_loop task."""

    async def stop(self) -> None:
        """Cancel the loop task."""

    async def add_ticker(self, ticker: str) -> None:
        """Delegate to sim.add_ticker(); seed cache immediately."""

    async def remove_ticker(self, ticker: str) -> None:
        """Delegate to sim.remove_ticker(); remove from cache."""

    def get_tickers(self) -> list[str]: ...
```

`SimulatorDataSource` bridges the async `MarketDataSource` interface with the synchronous `GBMSimulator`. The run loop is a plain `asyncio` task:

```python
async def _run_loop(self) -> None:
    while True:
        try:
            prices = self._sim.step()
            for ticker, price in prices.items():
                self._cache.update(ticker=ticker, price=price)
        except Exception:
            logger.exception("Simulator step failed")
        await asyncio.sleep(self._interval)
```

The `asyncio.sleep(0.5)` yields control back to the event loop between steps, so the simulator never starves request handling.

---

## Startup Seeding

On `start()`, the simulator immediately seeds the `PriceCache` with initial prices before the loop begins. This ensures the SSE stream and watchlist API have data on the very first request, with no "empty cache" window:

```python
async def start(self, tickers: list[str]) -> None:
    self._sim = GBMSimulator(tickers=tickers, ...)
    # Seed immediately
    for ticker in tickers:
        price = self._sim.get_price(ticker)
        if price is not None:
            self._cache.update(ticker=ticker, price=price)
    # Then start the loop
    self._task = asyncio.create_task(self._run_loop(), name="simulator-loop")
```

For dynamically added tickers (`add_ticker`), the same immediate seed applies — the ticker is available in the cache before the method returns.

---

## Dynamic Ticker Addition

When a user adds a new ticker to the watchlist:

1. `add_ticker(ticker)` is called on the `SimulatorDataSource`
2. `GBMSimulator.add_ticker()` initializes the ticker:
   - Seeds price from `SEED_PRICES` if known, otherwise `$100.00`
   - Assigns params from `TICKER_PARAMS` if known, otherwise `DEFAULT_PARAMS`
   - Rebuilds the Cholesky decomposition to include the new ticker
3. The cache is immediately seeded with the new price
4. The ticker appears in the next SSE broadcast

Unknown tickers (not in `SEED_PRICES`) seed at `$100.00` with `sigma=0.25, mu=0.05`. This is documented in the plan so the watchlist API's `400 invalid_ticker` vs simulator acceptance behavior is understood.

---

## Testing Approach

The two-layer structure (`GBMSimulator` + `SimulatorDataSource`) enables targeted tests:

**GBMSimulator tests** (`test_simulator.py`):
- `step()` returns prices for all tracked tickers
- Prices remain positive after many steps (log-normal property)
- Adding/removing tickers updates the active set correctly
- Cholesky is rebuilt on ticker changes
- Shock events fire within expected probability bounds

**SimulatorDataSource tests** (`test_simulator_source.py`):
- `start()` seeds the cache before the loop runs
- `add_ticker()` makes the ticker available in the cache immediately
- `remove_ticker()` removes the ticker from both simulator and cache
- `stop()` cancels the background task cleanly

**Factory tests** (`test_factory.py`):
- Returns `SimulatorDataSource` when `MASSIVE_API_KEY` is absent
- Returns `MassiveDataSource` when key is present

---

## Performance Characteristics

| Property | Value |
|---|---|
| Tick interval | 500ms |
| Per-tick CPU (10 tickers) | < 1ms (NumPy matrix multiply + 10 exp calls) |
| Memory per ticker | ~200 bytes (Python dict entries + float prices) |
| Cholesky rebuild cost | O(n²), negligible at n < 50 |
| Thread safety | Not required — runs entirely in the asyncio event loop |

The simulator is CPU-light enough that even at 50 tickers, it uses a negligible fraction of a single CPU core.
