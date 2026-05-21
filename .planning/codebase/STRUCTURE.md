# Codebase Structure

**Analysis Date:** 2026-05-21

## Directory Layout

```
finally/                          # Project root
├── backend/                      # FastAPI uv project (Python 3.12)
│   ├── app/                      # Application package
│   │   ├── __init__.py
│   │   └── market/               # Market data subsystem (complete)
│   │       ├── __init__.py       # Public API surface
│   │       ├── models.py         # PriceUpdate dataclass
│   │       ├── interface.py      # MarketDataSource ABC
│   │       ├── cache.py          # PriceCache (thread-safe store)
│   │       ├── simulator.py      # GBMSimulator + SimulatorDataSource
│   │       ├── massive_client.py # MassiveDataSource (Polygon.io)
│   │       ├── factory.py        # create_market_data_source()
│   │       ├── seed_prices.py    # Seed prices, GBM params, correlations
│   │       └── stream.py         # SSE router factory
│   ├── tests/                    # pytest test suite
│   │   ├── conftest.py           # Shared fixtures
│   │   ├── __init__.py
│   │   └── market/               # Tests for app/market/
│   │       ├── __init__.py
│   │       ├── test_models.py
│   │       ├── test_cache.py
│   │       ├── test_simulator.py
│   │       ├── test_simulator_source.py
│   │       ├── test_factory.py
│   │       └── test_massive.py
│   ├── market_data_demo.py       # Standalone Rich terminal demo
│   ├── pyproject.toml            # uv project manifest + tool config
│   ├── uv.lock                   # Lockfile (committed)
│   ├── CLAUDE.md                 # Backend developer guide for agents
│   └── README.md                 # Backend README
├── frontend/                     # Next.js TypeScript project (NOT YET BUILT)
│   └── (empty)
├── planning/                     # Project-wide documentation
│   ├── PLAN.md                   # Master project specification
│   ├── MARKET_DATA_SUMMARY.md    # Completed market data subsystem summary
│   ├── MARKET_DATA_REVIEW.md     # Code review findings + resolutions
│   ├── MARKET_INTERFACE.md       # Market interface design doc
│   ├── MARKET_SIMULATOR.md       # Simulator design doc
│   ├── MASSIVE_API.md            # Massive/Polygon.io integration doc
│   └── archive/                  # Older planning artifacts
├── .planning/                    # GSD agent output (codebase maps, phase plans)
│   └── codebase/                 # Codebase map documents (this file lives here)
├── .claude/                      # Claude agent configuration
│   ├── agents/                   # Agent definitions
│   ├── commands/gsd/             # GSD command scripts
│   ├── skills/
│   │   └── openai-inference/     # LiteLLM + OpenAI structured output patterns
│   │       └── SKILL.md
│   └── hooks/                    # Git/tool hooks
├── .github/workflows/            # GitHub Actions CI
│   ├── claude.yml                # Claude agent workflow
│   └── claude-code-review.yml    # Automated code review workflow
├── db/                           # SQLite bind-mount directory
│   └── .gitkeep                  # Directory tracked; finally.db is gitignored
├── CLAUDE.md                     # Root project instructions for agents
├── MARKET_DATA_DESIGN.md         # Top-level market data design reference
├── README.md                     # Project README
├── .gitignore
└── .env                          # Secrets (gitignored; .env.example to be created)
```

## Directory Purposes

**`backend/app/`:**
- Purpose: All Python application code for the FastAPI backend
- Contains: Subpackages per feature area; `market/` is the only implemented subpackage
- Key files: `backend/app/__init__.py`
- Note: `backend/app/main.py` (FastAPI app entry point) does not yet exist — it is the next major deliverable

**`backend/app/market/`:**
- Purpose: Self-contained market data subsystem — price simulation, real data, caching, SSE streaming
- Contains: 8 Python modules (~500 lines total), complete with tests
- Key files: `__init__.py` (public API), `models.py`, `cache.py`, `simulator.py`, `factory.py`, `stream.py`
- Import via: `from app.market import PriceCache, create_market_data_source, create_stream_router`

**`backend/tests/`:**
- Purpose: pytest test suite, mirroring the `app/` package structure
- Contains: One test module per source module in `app/market/`
- Run via: `cd backend && uv run --extra dev pytest -v`

**`frontend/`:**
- Purpose: Next.js TypeScript static export (not yet built)
- Contains: Currently empty
- Will contain: `package.json`, `next.config.ts` (with `output: 'export'`), `src/` or `app/` directory
- Build output: `out/` directory, copied into Docker image for FastAPI to serve

**`planning/`:**
- Purpose: Project-wide specification and design documents for agent coordination
- Contains: Master plan (`PLAN.md`), completed subsystem summaries, design docs
- Key file: `planning/PLAN.md` — the authoritative specification for the entire project

**`db/`:**
- Purpose: Bind-mount point for the SQLite database file
- Contains: Only `.gitkeep` in the repo; `finally.db` is created at runtime by the backend
- Note: `db/finally.db` is gitignored; `rm db/finally.db` resets the app cleanly

**`.planning/codebase/`:**
- Purpose: GSD agent codebase map output (this directory)
- Generated: Yes, by `/gsd:map-codebase` agent
- Committed: Yes

## Key File Locations

**Entry Points:**
- `backend/market_data_demo.py`: Standalone demo — run with `uv run market_data_demo.py`
- `backend/app/main.py`: FastAPI application entry point — **does not yet exist**; to be created

**Configuration:**
- `backend/pyproject.toml`: Python dependencies, pytest/ruff/coverage config, build system
- `backend/uv.lock`: Lockfile — committed, ensures reproducible installs
- `.env`: Runtime secrets (gitignored) — `OPENAI_API_KEY`, `MASSIVE_API_KEY`, `LLM_MOCK`

**Core Logic:**
- `backend/app/market/simulator.py`: GBM price simulation (GBMSimulator + SimulatorDataSource)
- `backend/app/market/cache.py`: Shared price state (PriceCache)
- `backend/app/market/stream.py`: SSE streaming endpoint factory
- `backend/app/market/factory.py`: Environment-driven data source selection

**Testing:**
- `backend/tests/market/`: 6 test modules, 73 tests, 84% coverage
- `backend/tests/conftest.py`: Shared pytest fixtures (asyncio event loop policy)

**Agent Documentation:**
- `backend/CLAUDE.md`: Backend developer guide — imports, usage patterns, test commands
- `planning/PLAN.md`: Full project specification including API contracts, DB schema, LLM integration

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `seed_prices.py`, `massive_client.py`)
- Test files: `test_<module_name>.py` co-located under `tests/` mirroring `app/` structure
- Planning docs: `UPPER_SNAKE_CASE.md` (e.g., `MARKET_DATA_SUMMARY.md`)

**Directories:**
- Python packages: `snake_case/` (e.g., `app/market/`)
- All packages include `__init__.py`

**Classes:**
- PascalCase (e.g., `PriceCache`, `SimulatorDataSource`, `MassiveDataSource`, `GBMSimulator`)
- Abstract base classes use the ABC suffix by convention of the module, not the class name
- Test classes: `Test<ClassName>` (e.g., `TestPriceCache`, `TestGBMSimulator`)

**Functions:**
- `snake_case` for all functions and methods
- Factory functions prefixed with `create_` (e.g., `create_market_data_source`, `create_stream_router`)
- Internal/private methods and attributes prefixed with `_` (e.g., `_run_loop`, `_poll_once`, `_prices`)

**Constants:**
- `UPPER_SNAKE_CASE` for module-level constants (e.g., `SEED_PRICES`, `TICKER_PARAMS`, `HEARTBEAT_INTERVAL`)

## Where to Add New Code

**New backend API feature (e.g., portfolio endpoints):**
- Create a new subpackage: `backend/app/<feature>/` with `__init__.py`
- Follow the pattern of `app/market/`: models → interface/ABC → implementations → factory → router
- Add tests in: `backend/tests/<feature>/test_<module>.py`
- Register router in: `backend/app/main.py` (to be created)

**New FastAPI router:**
- Use the factory pattern: `def create_<feature>_router(dependencies) -> APIRouter`
- Register in `backend/app/main.py` via `app.include_router(create_<feature>_router(...))`
- Prefix all API routes with `/api/`

**New data model:**
- Add a frozen dataclass to the relevant `models.py` (e.g., `backend/app/market/models.py`)
- Include a `to_dict()` method for JSON serialization
- Use `from __future__ import annotations` for forward references

**Frontend (when built):**
- All frontend code goes under `frontend/`
- Must be a self-contained Next.js project with `output: 'export'` in `next.config.ts`
- API calls use relative `/api/*` paths (same origin, no CORS)
- SSE connection to `/api/stream/prices` via native `EventSource`

**New tests:**
- Place under `backend/tests/<subpackage>/test_<module>.py`
- Use `class Test<ClassName>:` grouping
- Mark async tests with `@pytest.mark.asyncio` (or rely on `asyncio_mode = "auto"` from pyproject.toml)
- Mock external dependencies; use `unittest.mock.patch` or `patch.object`

**New seed data (for simulator):**
- Add ticker prices to `SEED_PRICES` in `backend/app/market/seed_prices.py`
- Add GBM parameters to `TICKER_PARAMS` (sigma = annualized volatility, mu = annualized drift)
- Add to the appropriate `CORRELATION_GROUPS` set (`tech` or `finance`)
- Unknown tickers default to `DEFAULT_PARAMS` (sigma=0.25, mu=0.05) at $100.00

## Special Directories

**`db/`:**
- Purpose: Runtime SQLite database bind-mount
- Generated: `finally.db` is created at runtime; `.gitkeep` is committed
- Committed: Only `.gitkeep`

**`backend/.venv/` (if present after `uv sync`):**
- Purpose: Python virtual environment managed by uv
- Generated: Yes, by `uv sync`
- Committed: No (gitignored)

**`.planning/`:**
- Purpose: GSD system output — codebase maps, phase plans, research docs
- Generated: Yes, by GSD agent commands
- Committed: Yes (tracked for agent coordination)

**`planning/archive/`:**
- Purpose: Older planning artifacts superseded by current docs
- Generated: No
- Committed: Yes

---

*Structure analysis: 2026-05-21*
