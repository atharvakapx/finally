# Coding Conventions

**Analysis Date:** 2026-05-21

> Note: The frontend (`frontend/`) does not yet exist. Conventions below reflect the backend Python codebase only (`backend/`). Frontend conventions should be appended once the Next.js project is scaffolded.

---

## Naming Patterns

**Files:**
- Lowercase with underscores: `cache.py`, `massive_client.py`, `seed_prices.py`, `stream.py`
- Test files prefixed with `test_`: `test_cache.py`, `test_simulator.py`, `test_factory.py`
- One module per concern — each file has a single clear responsibility

**Classes:**
- PascalCase: `PriceCache`, `PriceUpdate`, `GBMSimulator`, `MassiveDataSource`, `SimulatorDataSource`, `MarketDataSource`
- Abstract base classes named as the abstract concept: `MarketDataSource` (not `AbstractMarketDataSource`)
- Concrete implementations named `<Concept>DataSource`: `SimulatorDataSource`, `MassiveDataSource`

**Functions and Methods:**
- `snake_case` for all functions and methods: `create_market_data_source`, `get_price`, `add_ticker`, `remove_ticker`
- Factory functions follow `create_<noun>` pattern: `create_market_data_source`, `create_stream_router`
- Private methods prefixed with single underscore: `_poll_once`, `_poll_loop`, `_rebuild_cholesky`, `_add_ticker_internal`, `_generate_events`, `_fetch_snapshots`
- `@staticmethod` methods also use `snake_case`: `_pairwise_correlation`

**Variables and Attributes:**
- `snake_case` for local variables: `api_key`, `poll_interval`, `initial_version`
- Private instance attributes prefixed with `_`: `self._prices`, `self._lock`, `self._version`, `self._task`, `self._client`
- Constants at module level in `UPPER_SNAKE_CASE`: `HEARTBEAT_INTERVAL`, `SEED_PRICES`, `TICKER_PARAMS`, `DEFAULT_PARAMS`, `CORRELATION_GROUPS`, `INTRA_TECH_CORR`, `TSLA_CORR`
- Class-level constants also in `UPPER_SNAKE_CASE`: `GBMSimulator.DEFAULT_DT`, `GBMSimulator.TRADING_SECONDS_PER_YEAR`

**Type Annotations:**
- All public function/method signatures are fully annotated with return types
- Use built-in generic types (Python 3.12+): `list[str]`, `dict[str, float]`, not `List[str]`, `Dict[str, float]`
- Union types use pipe syntax: `float | None`, `PriceUpdate | None`
- `__future__ annotations` import present on every module file for forward references

---

## Code Style

**Formatting:**
- Ruff formatter (configured in `backend/pyproject.toml`)
- Line length: 100 characters (`[tool.ruff] line-length = 100`)
- Target Python version: 3.12 (`target-version = "py312"`)

**Linting:**
- Ruff with rule sets: `["E", "F", "I", "N", "W"]`
  - `E` — pycodestyle errors
  - `F` — pyflakes (undefined names, unused imports)
  - `I` — isort (import ordering)
  - `N` — pep8-naming
  - `W` — pycodestyle warnings
- `E501` (line too long) explicitly ignored — formatter handles it

**Run linting:**
```bash
cd backend
uv run --extra dev ruff check app/ tests/
```

---

## Import Organization

**Order (enforced by ruff `I` rules / isort):**
1. `from __future__ import annotations` — always first when present
2. Standard library: `import asyncio`, `import logging`, `import os`, `import time`
3. Third-party: `import numpy as np`, `from fastapi import ...`, `from massive import ...`
4. Internal (relative): `from .cache import PriceCache`, `from .interface import MarketDataSource`

**Path style:**
- Relative imports within a package: `from .cache import PriceCache` (never absolute `from app.market.cache import ...`)
- Absolute imports in tests: `from app.market.cache import PriceCache`

**No path aliases defined** — the project is small enough that relative imports suffice.

---

## Module Structure Pattern

Every source module follows this layout:
1. Module-level docstring (one-liner for simple modules, multi-line for complex)
2. `from __future__ import annotations`
3. Standard library imports
4. Third-party imports
5. Local relative imports
6. Module-level constants
7. Logger: `logger = logging.getLogger(__name__)`
8. Class/function definitions

Example from `backend/app/market/factory.py`:
```python
"""Factory for creating market data sources."""

from __future__ import annotations

import logging
import os

from .cache import PriceCache
from .interface import MarketDataSource
from .massive_client import MassiveDataSource
from .simulator import SimulatorDataSource

logger = logging.getLogger(__name__)
```

---

## Docstrings

**Every module has a module-level docstring** — even one-liners:
- `"""Thread-safe in-memory price cache."""` — `cache.py`
- `"""Data models for market data."""` — `models.py`
- `"""Abstract interface for market data sources."""` — `interface.py`

**Every class has a class docstring** describing purpose and any usage notes:
```python
class PriceCache:
    """Thread-safe in-memory cache of the latest price for each ticker.

    Writers: SimulatorDataSource or MassiveDataSource (one at a time).
    Readers: SSE streaming endpoint, portfolio valuation, trade execution.
    """
```

**Every public method has a one-line docstring** (or multi-line if behavior is non-obvious):
```python
def get_all(self) -> dict[str, PriceUpdate]:
    """Snapshot of all current prices. Returns a shallow copy."""
```

**Private methods** (`_prefixed`) have docstrings only when the implementation is non-trivial:
```python
def _rebuild_cholesky(self) -> None:
    """Rebuild the Cholesky decomposition of the ticker correlation matrix.

    Called whenever tickers are added or removed. O(n^2) but n < 50.
    """
```

**Tests** have one-line docstrings stating what is being tested:
```python
def test_first_update_is_flat(self):
    """Test that the first update has flat direction."""
```

---

## Error Handling

**Background loop errors — catch, log, and continue:**
```python
# In simulator _run_loop:
except Exception:
    logger.exception("Simulator step failed")
# Continues loop — never raises from a background task

# In Massive _poll_once:
except Exception as e:
    logger.error("Massive poll failed: %s", e)
    # Don't re-raise — the loop will retry on the next interval.
```

**Specific exceptions for expected failure modes:**
```python
except (AttributeError, TypeError) as e:
    logger.warning("Skipping snapshot for %s: %s", getattr(snap, "ticker", "???"), e)
```

**Task cancellation — always propagate `CancelledError` after cleanup:**
```python
if self._task and not self._task.done():
    self._task.cancel()
    try:
        await self._task
    except asyncio.CancelledError:
        pass  # Expected; absorbed here after task stops
self._task = None
```

**Idempotent stop methods** — guard with `if self._task and not self._task.done()` to allow double-stop without error.

**No bare `except:` clauses** — always `except Exception:` or more specific.

---

## Logging

**Framework:** Python standard library `logging`

**Setup pattern per module:**
```python
logger = logging.getLogger(__name__)
```

**Levels used:**
- `logger.debug(...)` — high-frequency events (per-tick simulator events, per-poll debug counts)
- `logger.info(...)` — lifecycle events (start, stop, ticker add/remove, client connect/disconnect)
- `logger.warning(...)` — recoverable unexpected states (malformed API snapshot)
- `logger.error(...)` — recoverable failures (API poll failed, will retry)
- `logger.exception(...)` — unexpected exceptions in loops (includes stack trace automatically)

**Message format — printf-style with `%` substitution** (not f-strings):
```python
logger.info("Simulator started with %d tickers", len(tickers))
logger.warning("Skipping snapshot for %s: %s", getattr(snap, "ticker", "???"), e)
logger.debug("Massive poll: updated %d/%d tickers", processed, len(self._tickers))
```

---

## Dataclass Patterns

**Immutable data models use `@dataclass(frozen=True, slots=True)`:**
```python
@dataclass(frozen=True, slots=True)
class PriceUpdate:
    ticker: str
    price: float
    previous_price: float
    timestamp: float = field(default_factory=time.time)
```

- `frozen=True` — prevents mutation after creation; tests verify `AttributeError` on attempted mutation
- `slots=True` — memory efficiency for high-frequency objects
- Default values use `field(default_factory=...)` for mutable/callable defaults

**Computed properties on frozen dataclasses:**
- Pure computed values go on `@property` methods rather than being stored as fields
- Example: `change`, `change_percent`, `direction` on `PriceUpdate`

---

## Abstract Interface Pattern

Define the contract in a dedicated `interface.py`:
```python
from abc import ABC, abstractmethod

class MarketDataSource(ABC):
    """Contract docstring with lifecycle description."""

    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """Method docstring explaining contract obligations."""
```

Concrete implementations inherit and implement all abstract methods. The factory (`factory.py`) returns the abstract type, not the concrete type:
```python
def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
```

---

## Async Conventions

- Background tasks created with `asyncio.create_task(coro, name="descriptive-name")`
- Synchronous blocking calls wrapped with `await asyncio.to_thread(...)` to avoid blocking the event loop (see `massive_client._poll_once` calling `_fetch_snapshots`)
- Async generators typed as `AsyncGenerator[str, None]`
- `asyncio.CancelledError` always re-raised or absorbed explicitly — never swallowed accidentally inside a broad `except Exception`

---

## Public API Exports

Each package exposes a clean `__init__.py` that lists only public symbols:
```python
# backend/app/market/__init__.py
from .cache import PriceCache
from .factory import create_market_data_source
from .interface import MarketDataSource
from .models import PriceUpdate
from .stream import create_stream_router

__all__ = [
    "PriceUpdate",
    "PriceCache",
    "MarketDataSource",
    "create_market_data_source",
    "create_stream_router",
]
```

Consumers import from the package, not the submodule:
```python
from app.market import PriceCache, PriceUpdate, create_market_data_source
```

---

## Thread Safety

When a class is accessed from multiple threads, use `threading.Lock`:
```python
class PriceCache:
    def __init__(self) -> None:
        self._prices: dict[str, PriceUpdate] = {}
        self._lock = Lock()

    def update(self, ...) -> PriceUpdate:
        with self._lock:
            ...
```

Every mutation and read of shared state uses `with self._lock:`. The `version` property is intentionally not locked (read of a single integer is atomic in CPython).

---

*Convention analysis: 2026-05-21*
