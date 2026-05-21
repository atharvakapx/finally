# Codebase Concerns

**Analysis Date:** 2026-05-21

---

## Scope Note

Only one subsystem is built: `backend/app/market/` (market data, price cache, SSE streaming). The entire application described in `planning/PLAN.md` is not yet implemented. The concerns below cover both issues in the built code and the structural gaps that must be addressed before the application is functional.

---

## Missing Critical Features

**No FastAPI application entry point:**
- Problem: No `backend/app/main.py` or equivalent. No `FastAPI()` instance, no uvicorn startup, no app lifecycle hooks. The backend cannot be started.
- Blocks: Every API endpoint, SSE mounting, database initialization, market data startup, Docker deployment.
- The `backend/app/__init__.py` contains only a docstring.

**No REST API endpoints:**
- Problem: None of the 11 API endpoints from `planning/PLAN.md` §8 are implemented. Missing: `GET /api/portfolio`, `POST /api/portfolio/trade`, `GET /api/portfolio/history`, `GET /api/watchlist`, `POST /api/watchlist`, `DELETE /api/watchlist/{ticker}`, `POST /api/chat`, `GET /api/health`.
- Blocks: Portfolio management, watchlist management, AI chat, E2E tests.

**No database layer:**
- Problem: No `backend/app/db/` module. No schema initialization code, no migration logic, no seed data insertion for the default watchlist or user profile. The SQLite schema defined in `planning/PLAN.md` §7 has no corresponding Python code.
- Note: A `db/finally.db` file exists in the repo (committed to git) with tables and data, suggesting the DB was created outside the tracked codebase. There is no code path to recreate it from scratch.
- Blocks: All API endpoints, portfolio history, trade execution, chat history.

**No LLM integration:**
- Problem: No `backend/app/llm/` module. The `openai-inference` skill at `.claude/skills/openai-inference/SKILL.md` defines the LiteLLM + structured outputs pattern, but neither `litellm` nor `pydantic` appears in `backend/pyproject.toml` dependencies.
- Blocks: `POST /api/chat` endpoint, trade auto-execution from AI, mock LLM mode for E2E tests.

**Frontend is empty:**
- Problem: `frontend/` directory exists but contains zero files (only the directory itself, confirmed via `ls`). No Next.js project, no TypeScript, no components.
- Blocks: All user-facing functionality, E2E tests, Docker multi-stage build.

**No Dockerfile:**
- Problem: No `Dockerfile` in the repo root. The `README.md` and `planning/PLAN.md` document a multi-stage `Node → Python` Docker build, but no file implements it.
- Blocks: `./scripts/start_mac.sh` (also missing), single-command startup.

**No start/stop scripts:**
- Problem: `scripts/` directory referenced in `planning/PLAN.md` and `README.md` does not exist in the repo.
- Blocks: User onboarding, documented quick start.

**No `.env.example`:**
- Problem: `README.md` tells users to `cp .env.example .env`, but `.env.example` is not committed.
- Blocks: First-run experience for new contributors.

**No E2E test infrastructure:**
- Problem: `test/` directory referenced in `planning/PLAN.md` §12 does not exist. No Playwright tests, no `docker-compose.test.yml`.
- Blocks: Automated validation of the full application.

---

## Tech Debt

**`db/finally.db` committed to version control:**
- Issue: The SQLite database file is tracked by git (`git ls-files` confirms `db/finally.db` is committed). `planning/PLAN.md` §4 explicitly states: "finally.db is gitignored" and the `db/` directory should contain only a `.gitkeep`.
- Files: `db/finally.db`, `.gitignore`
- Impact: The repo carries mutable runtime state. Anyone who clones the repo gets a non-empty database with prior trades and a depleted cash balance ($9,786 instead of $10,000). `rm db/finally.db` to reset is undermined because the file reappears on `git checkout`. Credential-like data (cash balance, trade history) leaks into git history.
- Fix approach: Add `db/finally.db` to `.gitignore`, add `db/.gitkeep`, and remove the committed database from git history using `git rm --cached db/finally.db`.

**Module-level SSE router singleton:**
- Issue: `backend/app/market/stream.py` line 20 creates `router = APIRouter(...)` at module level. `create_stream_router()` registers a route on this shared object each time it is called. Calling it twice silently registers duplicate routes; the second cache injection is ignored without error.
- Files: `backend/app/market/stream.py:20–51`
- Impact: Low in production (single call path), but breaks test isolation — any test that creates a second router gets the first call's cache injected.
- Fix approach: Move `router = APIRouter(...)` inside `create_stream_router()` so each call produces a fresh router.

**`timestamp or time.time()` falsy-zero bug:**
- Issue: `backend/app/market/cache.py` line 30 uses `ts = timestamp or time.time()`. A `timestamp=0.0` argument (valid Unix epoch) evaluates as falsy and is replaced with the current time silently.
- Files: `backend/app/market/cache.py:30`
- Impact: Low (Unix timestamp 0 is 1970-01-01 and won't occur in practice), but is semantically wrong and could silently corrupt timestamp data if the calling convention changes.
- Fix approach: `ts = timestamp if timestamp is not None else time.time()`

**`add_ticker` normalization inconsistency between sources:**
- Issue: `MassiveDataSource.add_ticker()` normalizes input with `.upper().strip()` (`massive_client.py:67–68`). `SimulatorDataSource.add_ticker()` does not normalize at all (`simulator.py:120–125`). Both implement `MarketDataSource` ABC.
- Files: `backend/app/market/massive_client.py:67–68`, `backend/app/market/simulator.py:120–125`
- Impact: Violates Liskov Substitution Principle. While the watchlist API's format check prevents lowercase input from reaching this layer today, this assumption creates a hidden coupling between the API layer and the market data layer.
- Fix approach: Add `.upper().strip()` normalization to `SimulatorDataSource.add_ticker()` and `remove_ticker()`, matching Massive behavior.

**`PriceCache.version` property reads without lock:**
- Issue: All other `PriceCache` methods acquire `self._lock` before accessing `_version`. The `version` property (`cache.py:64–66`) reads `_version` without acquiring the lock.
- Files: `backend/app/market/cache.py:64–66`
- Impact: Trivial on CPython due to GIL. Becomes a data race on Python 3.13+ no-GIL builds. Inconsistent lock discipline is a code smell that makes the class harder to reason about.
- Fix approach: Add lock acquisition in the `version` property, or add a comment explaining intentional GIL reliance.

**Missing dependencies in `pyproject.toml` for planned features:**
- Issue: `backend/pyproject.toml` lists only market-data-relevant dependencies. The full application requires `litellm` and `pydantic` (LLM integration), likely `httpx` (SSE integration tests per code review), and an async SQLite driver. None are declared.
- Files: `backend/pyproject.toml`
- Impact: Downstream phases that add LLM or database code will hit missing-dependency errors at import time.
- Fix approach: Add `litellm>=1.0.0`, `pydantic>=2.0.0`, and an async SQLite client (e.g., `aiosqlite`) as core dependencies when those modules are built.

**Stale/conflicting design document at repo root:**
- Issue: `MARKET_DATA_DESIGN.md` in the project root (1,351 lines) is an older, different document than `planning/archive/MARKET_DATA_DESIGN.md` (1,490 lines). The root document appears to be an initial brainstorm with a more complex architecture (Redis, TimescaleDB, WebSocket) that was superseded by the simpler architecture that was actually built.
- Files: `MARKET_DATA_DESIGN.md`
- Impact: Future agents or developers may read the root file and implement against the wrong architecture spec.
- Fix approach: Remove `MARKET_DATA_DESIGN.md` from the repo root or add a clear deprecation notice pointing to `planning/archive/MARKET_DATA_DESIGN.md`.

---

## Security Considerations

**No authentication or authorization:**
- Risk: The application is intentionally single-user with no auth (`planning/PLAN.md` §1: "No login, no signup"). All trade and portfolio endpoints will be publicly accessible on port 8000.
- Files: Not yet built — applies to `backend/app/api/` (planned)
- Current mitigation: Single-user design with hardcoded `user_id="default"`. Acceptable for localhost demo use.
- Recommendations: If ever deployed to a publicly accessible URL, add at minimum a shared secret header or basic auth. The `user_id` column exists in all tables for future multi-user support.

**No rate limiting on trade endpoint:**
- Risk: `POST /api/portfolio/trade` (not yet built) will have no rate limiting. A malicious script could execute thousands of trades per second.
- Files: Planned `backend/app/api/portfolio.py`
- Current mitigation: None planned in spec.
- Recommendations: Add a simple per-IP rate limit (e.g., `slowapi`) on the trade endpoint to prevent runaway automation.

**API key stored in `.env` only:**
- Risk: `OPENAI_API_KEY` and `MASSIVE_API_KEY` are read from environment. No `.env.example` is committed, meaning contributors must know the correct variable names from the README alone.
- Files: `.env` (untracked), `.env.example` (missing)
- Current mitigation: The factory reads `MASSIVE_API_KEY` via `os.environ.get(..., "")`, which degrades gracefully to the simulator. `OPENAI_API_KEY` absence triggers mock mode.
- Recommendations: Add `.env.example` with placeholder values and instructions to the repo.

---

## Performance Bottlenecks

**SSE emits full price snapshot on every version bump, not a diff:**
- Problem: `_generate_events` in `backend/app/market/stream.py:84–89` calls `price_cache.get_all()` and serializes all prices whenever any version change is detected. This sends all N ticker payloads even if only one ticker changed.
- Files: `backend/app/market/stream.py:84–89`
- Cause: `PriceCache.version` is a single monotonic counter; there is no per-ticker version tracking. The SSE spec comment ("pushes the diff") is misleading — the implementation sends all prices.
- Impact: With the GBM simulator updating all tickers together at 500ms, this is equivalent to a diff in practice. With Massive API (which polls all tickers together), same situation. Only becomes inefficient if per-ticker update granularity is ever introduced (e.g., a WebSocket feed updating individual tickers).
- Improvement path: Add per-ticker version tracking to `PriceCache` for true diff streaming, if moving beyond REST polling sources.

**GBM Cholesky rebuild on every `add_ticker`/`remove_ticker`:**
- Problem: `GBMSimulator._rebuild_cholesky()` is O(n²) and called synchronously every time a ticker is added or removed via the watchlist API.
- Files: `backend/app/market/simulator.py:154–172`
- Cause: The correlation matrix is rebuilt from scratch on each change.
- Impact: Negligible at the 50-ticker cap (O(2500) operations). Not a concern for this application's scale.

---

## Fragile Areas

**SSE streaming is untested (32% coverage):**
- Files: `backend/app/market/stream.py`
- Why fragile: `_generate_events()` contains all the critical real-time logic (version detection, heartbeat timing, disconnect handling, JSON formatting) but has zero test coverage. The untested paths include: initial `retry:` directive, version-change detection, heartbeat emission, client disconnect exit, and `asyncio.CancelledError` handling.
- Test coverage: 32% — only the module import and `create_stream_router` function signature are indirectly exercised.
- Safe modification: Test against it using `httpx.AsyncClient` with `ASGITransport` before modifying any logic in `_generate_events`. The code review in `planning/MARKET_DATA_REVIEW.md` §5.5 provides a concrete test pattern.
- Priority: High — the SSE stream is the primary data channel to the frontend. Regressions here break the entire real-time UI.

**`MassiveDataSource._tickers` list is not thread-safe:**
- Files: `backend/app/market/massive_client.py:37, 67–75`
- Why fragile: `_tickers` is a plain `list[str]`. `add_ticker()` and `remove_ticker()` mutate it from the asyncio event loop, while `_fetch_snapshots()` reads it from a thread via `asyncio.to_thread`. On CPython the GIL makes list reads/writes effectively atomic, but this is not guaranteed behavior.
- Safe modification: Add a `threading.Lock` around `_tickers` mutations and reads, or convert to a thread-safe structure.

**Database committed to git without schema creation code:**
- Files: `db/finally.db`
- Why fragile: The SQLite file with the correct schema exists in git. There is no Python code that creates this schema from scratch. If the file is deleted or the schema drifts, there is no automated way to recreate it. Any schema migration (adding a column, index, constraint) has no migration mechanism.
- Safe modification: Build `backend/app/db/` with schema SQL and a lazy-initialization function before making any schema changes. The spec in `planning/PLAN.md` §7 documents the intended schema precisely.

---

## Test Coverage Gaps

**SSE streaming logic (`stream.py`):**
- What's not tested: `_generate_events()` generator — version-based change detection, heartbeat, disconnect exit, CancelledError handling, event payload format.
- Files: `backend/app/market/stream.py:54–99`
- Risk: Any regression in the primary real-time data channel goes undetected.
- Priority: High

**All planned API endpoints:**
- What's not tested: Nothing in `backend/app/api/` exists yet. When built, all portfolio, watchlist, chat, and health endpoints need unit and integration tests.
- Files: Planned `backend/app/api/`
- Risk: High — trade execution logic (double-spend prevention, P&L calculation) is correctness-critical.
- Priority: High

**LLM integration and mock mode:**
- What's not tested: Structured output parsing, mock response determinism, `LLM_MOCK=true` behavior.
- Files: Planned `backend/app/llm/`
- Risk: E2E tests depend on deterministic mock responses; if mock mode doesn't activate correctly, CI becomes flaky.
- Priority: High

**Database initialization and seed data:**
- What's not tested: Lazy schema creation, idempotent re-initialization, correct default watchlist seeding.
- Files: Planned `backend/app/db/`
- Risk: Fresh Docker container starts with a blank database and no seed data, giving a broken first-run experience.
- Priority: High

**`massive_client.py` poll loop (`_poll_loop`):**
- What's not tested: The `_poll_loop` sleep-and-poll cycle (`massive_client.py:83–87`) and `_fetch_snapshots` body are always mocked. Coverage is 94% but the actual polling cycle is untested end-to-end.
- Files: `backend/app/market/massive_client.py:83–87, 123–128`
- Risk: Rate limiting behavior and actual Massive API response parsing could fail silently.
- Priority: Low (acceptable for a mocked external dependency)

---

## Dependencies at Risk

**`massive` package (Polygon.io SDK):**
- Risk: Listed as `massive>=1.0.0` with no upper bound. The package is a rebranded Polygon.io client (rebranded October 2025 per `planning/MASSIVE_API.md`). Breaking API changes in `2.x` would silently break the Massive data path.
- Files: `backend/pyproject.toml:12`, `backend/uv.lock`
- Impact: Only affects users with `MASSIVE_API_KEY` set. Simulator path is unaffected.
- Migration plan: Pin to `massive>=1.0.0,<2.0.0` until a breaking-change review is done.

**`numpy>=2.0.0` with no upper bound:**
- Risk: NumPy 2.x introduced breaking changes from 1.x. The `>=2.0.0` pin is correct but an unconstrained upper bound risks future NumPy 3.x incompatibilities breaking the Cholesky decomposition path.
- Files: `backend/pyproject.toml:10`
- Impact: GBM simulator would fail on startup if NumPy 3 introduces breaking changes.
- Migration plan: Pin to `numpy>=2.0.0,<3.0.0` as a defensive measure.

---

*Concerns audit: 2026-05-21*
