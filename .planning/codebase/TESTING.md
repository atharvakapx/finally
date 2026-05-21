# Testing Patterns

**Analysis Date:** 2026-05-21

> Note: Only the backend (`backend/`) is currently implemented. All test patterns below apply to `backend/tests/`. Frontend tests do not yet exist. E2E tests (`test/`) are not yet scaffolded.

---

## Test Framework

**Runner:**
- pytest 8.3.0+
- Config: `backend/pyproject.toml` under `[tool.pytest.ini_options]`

**Assertion Library:**
- pytest built-in assertions (plain `assert` statements — no unittest-style `assertEqual`)

**Async support:**
- `pytest-asyncio` 0.24.0+
- Mode: `asyncio_mode = "auto"` — all `async def test_*` functions run automatically without `@pytest.mark.asyncio` on individual functions
- Exception: class-level `@pytest.mark.asyncio` is still required on async test classes (see `TestMassiveDataSource`, `TestSimulatorDataSource`)
- Loop scope: `asyncio_default_fixture_loop_scope = "function"` — fresh event loop per test function

**Coverage:**
- `pytest-cov` 5.0.0+
- Source: `app/` package
- Omit: `tests/*`
- Excludes: `pragma: no cover`, `__repr__`, `raise NotImplementedError`, `if TYPE_CHECKING:`, `if __name__ == "__main__":`

**Run Commands:**
```bash
cd backend
uv run --extra dev pytest -v              # All tests, verbose
uv run --extra dev pytest --cov=app       # With coverage report
uv run --extra dev pytest tests/market/test_cache.py -v  # Single file
uv run --extra dev ruff check app/ tests/ # Lint before test
```

---

## Test File Organization

**Location:**
- Separate `tests/` directory mirroring `app/` package structure
- `backend/tests/` mirrors `backend/app/`
- `backend/tests/market/` mirrors `backend/app/market/`

**Naming:**
- Test files: `test_<module_name>.py` — e.g., `test_cache.py` tests `cache.py`
- Each source module has exactly one corresponding test file

**Structure:**
```
backend/
├── app/
│   └── market/
│       ├── __init__.py
│       ├── cache.py
│       ├── factory.py
│       ├── interface.py
│       ├── massive_client.py
│       ├── models.py
│       ├── seed_prices.py
│       ├── simulator.py
│       └── stream.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    └── market/
        ├── __init__.py
        ├── test_cache.py
        ├── test_factory.py
        ├── test_massive.py
        ├── test_models.py
        ├── test_simulator.py
        └── test_simulator_source.py
```

**Note:** `simulator.py` has two test files — `test_simulator.py` covers `GBMSimulator` (the math/pure logic class) and `test_simulator_source.py` covers `SimulatorDataSource` (the async lifecycle wrapper). Split when a single module contains two distinct classes with different testing needs.

---

## Test Class Structure

All tests are organized in classes matching `Test<ClassName>`:

```python
class TestPriceCache:
    """Unit tests for the PriceCache."""

    def test_update_and_get(self):
        """Test updating and getting a price."""
        cache = PriceCache()
        update = cache.update("AAPL", 190.50)
        assert update.ticker == "AAPL"
        assert update.price == 190.50
        assert cache.get("AAPL") == update
```

- Class docstring: `"""Unit tests for the <ClassName>."""` or `"""Integration tests for..."""`
- Each test method has a one-line docstring stating what is being verified
- No `setUp`/`tearDown` methods — use local variables and `await source.stop()` inline
- No shared state between tests — each test instantiates fresh objects

---

## Test Types

**Unit Tests** (`test_cache.py`, `test_models.py`, `test_simulator.py`, `test_factory.py`):
- Scope: single class or function in isolation
- No async — purely synchronous logic
- No mocking needed for pure logic tests
- Environment mocking for factory tests (see Mocking section)

**Integration Tests** (`test_simulator_source.py`, `test_massive.py`):
- Scope: full async lifecycle (start → operate → stop)
- Real asyncio event loop, real `asyncio.sleep`
- External APIs mocked (`_fetch_snapshots`, `RESTClient`)
- Time-based assertions use short intervals and `asyncio.sleep`

**E2E Tests:**
- Not yet implemented. Per spec: Playwright + `docker-compose.test.yml` in `test/`, run with `LLM_MOCK=true`

---

## Async Testing Patterns

**Class-level marker for async test classes:**
```python
@pytest.mark.asyncio
class TestSimulatorDataSource:
    """Integration tests for the SimulatorDataSource."""

    async def test_start_populates_cache(self):
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL", "GOOGL"])

        assert cache.get("AAPL") is not None
        assert cache.get("GOOGL") is not None

        await source.stop()
```

**Teardown pattern — always call `await source.stop()` at end of async tests:**
```python
async def test_prices_update_over_time(self):
    cache = PriceCache()
    source = SimulatorDataSource(price_cache=cache, update_interval=0.05)
    await source.start(["AAPL"])

    initial_version = cache.version
    await asyncio.sleep(0.3)  # Several update cycles

    assert cache.version > initial_version

    await source.stop()  # Always clean up background tasks
```

**Time-based tests use short intervals + `asyncio.sleep`:**
- Tests use `update_interval=0.05` or `update_interval=0.1` (not default 0.5s)
- Sleep durations are multiples of the interval (e.g., `await asyncio.sleep(0.3)` with `update_interval=0.05` gives ~6 cycles)
- Version-based assertions (`cache.version > initial_version`) are preferred over checking exact values

---

## Mocking

**Framework:** `unittest.mock` — `patch`, `patch.dict`, `patch.object`, `MagicMock`

**Environment variable mocking with `patch.dict`:**
```python
from unittest.mock import patch
import os

def test_creates_simulator_when_no_api_key(self):
    cache = PriceCache()
    with patch.dict(os.environ, {}, clear=True):
        source = create_market_data_source(cache)
    assert isinstance(source, SimulatorDataSource)
```

- `clear=True` wipes the entire environment for isolation (critical for `MASSIVE_API_KEY` tests)
- The assertion is made **after** the `with` block — the object is already created, no need to stay inside the context

**Method mocking with `patch.object`:**
```python
with patch.object(source, "_fetch_snapshots", return_value=mock_snapshots):
    await source._poll_once()
```

- Prefer `patch.object(instance, "method_name")` over `patch("full.module.path.Class.method")`
- Use `side_effect=Exception(...)` to test error handling:
  ```python
  with patch.object(source, "_fetch_snapshots", side_effect=Exception("network error")):
      await source._poll_once()  # Should not raise
  ```

**Class mocking for external SDK:**
```python
with patch("app.market.massive_client.RESTClient"):
    with patch.object(source, "_fetch_snapshots", return_value=mock_snapshots):
        await source.start(["AAPL"])
```

- Mock `RESTClient` at the import path in the module under test, not at the source module
- Nest `patch` context managers for multiple mocks

**`MagicMock` for data objects:**
```python
def _make_snapshot(ticker: str, price: float, timestamp_ms: int) -> MagicMock:
    """Create a mock Massive snapshot object."""
    snap = MagicMock()
    snap.ticker = ticker
    snap.last_trade = MagicMock()
    snap.last_trade.price = price
    snap.last_trade.timestamp = timestamp_ms
    return snap
```

- Helper functions for creating mock data objects placed at module level (not inside test class)
- Named `_make_<noun>` (underscore prefix since it's a test helper, not a test case)
- `MagicMock()` used when attribute access behavior needs to be verified

**What to mock:**
- External network calls (`_fetch_snapshots`, `RESTClient`)
- Environment variables (`os.environ` via `patch.dict`)
- Time (via short intervals rather than mocking `time` itself)

**What NOT to mock:**
- `asyncio` primitives — use real async with short intervals
- `PriceCache` — pass a real instance; it has no external dependencies
- The module under test's own core logic

---

## Fixtures

**Global conftest** (`backend/tests/conftest.py`):
```python
@pytest.fixture
def event_loop_policy():
    """Use the default event loop policy for all async tests."""
    import asyncio
    return asyncio.DefaultEventLoopPolicy()
```

Currently minimal — only one fixture for the event loop policy. Tests construct fresh objects locally rather than relying on shared fixtures.

**No shared fixtures for domain objects** — each test creates its own `PriceCache()`, `SimulatorDataSource(...)` etc. This keeps tests independent and the setup visible in the test body.

---

## Error Case Testing

**Immutability via `pytest.raises`:**
```python
def test_immutability(self):
    update = PriceUpdate(ticker="AAPL", price=190.50, previous_price=190.00, timestamp=1234567890.0)
    with pytest.raises(AttributeError):
        update.price = 200.00
```

**No-op for missing keys (assert no raise):**
```python
def test_remove_nonexistent(self):
    """Test removing a ticker that doesn't exist."""
    cache = PriceCache()
    cache.remove("AAPL")  # Should not raise
```

- Comment `# Should not raise` makes intent explicit
- These tests verify graceful no-op behavior for common edge cases

**Resilience tests for background loops:**
```python
async def test_api_error_does_not_crash(self):
    """Test that API errors don't crash the poller."""
    with patch.object(source, "_fetch_snapshots", side_effect=Exception("network error")):
        await source._poll_once()  # Should not raise

    assert cache.get_price("AAPL") is None  # No update happened
```

---

## Coverage

**Requirements:** No hard minimum enforced in config, but the market data subsystem has comprehensive coverage.

**View coverage:**
```bash
cd backend
uv run --extra dev pytest --cov=app --cov-report=term-missing
```

**Coverage excludes** (from `pyproject.toml`):
- `pragma: no cover`
- `def __repr__`
- `raise AssertionError`, `raise NotImplementedError`
- `if __name__ == "__main__":`
- `if TYPE_CHECKING:`

---

## Test Data Patterns

**Concrete ticker names:** Always use real-looking tickers (`"AAPL"`, `"GOOGL"`, `"TSLA"`) rather than generic `"TICK1"`. Matches the actual system behavior and seed data.

**Boundary tickers:** Use `"ZZZZ"` or `"NOPE"` for unknown/invalid tickers to make intent clear.

**Prices:** Use realistic values (`190.50`, `175.25`) matching the seed price magnitude range.

**Timestamps:** Use concrete Unix epoch values (`1234567890.0`, `1707580800000`) rather than `time.time()` for deterministic assertions.

**Large iteration counts for stochastic property tests:**
```python
def test_prices_are_positive(self):
    """GBM prices can never go negative (exp() is always positive)."""
    sim = GBMSimulator(tickers=["AAPL"])
    for _ in range(10_000):
        prices = sim.step()
        assert prices["AAPL"] > 0
```

- Use `10_000` (with underscore separator) for large numbers
- These tests verify mathematical invariants that must hold across many random draws

---

## Adding New Tests

**New service/class:** Create `backend/tests/<package>/test_<module_name>.py` mirroring the source module path.

**New async class:** Add `@pytest.mark.asyncio` at the class level; ensure `await source.stop()` is called at the end of each test that starts a background task.

**New external API client:** Use `patch.object(instance, "_fetch_...", return_value=...)` to mock the lowest-level network call, keeping all async/retry logic exercised by real code.

**New environment-driven factory behavior:** Use `patch.dict(os.environ, {"VAR": "value"}, clear=True)` to isolate from the test runner's environment.

---

*Testing analysis: 2026-05-21*
