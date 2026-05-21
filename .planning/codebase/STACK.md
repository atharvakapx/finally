# Technology Stack

**Analysis Date:** 2026-05-21

## Languages

**Primary:**
- Python 3.12 — backend (FastAPI app, market data subsystem, all server logic)
- TypeScript — frontend (Next.js, planned but not yet implemented; `frontend/` directory exists but is empty)

**Secondary:**
- SQL (SQLite dialect) — database schema and queries (planned; not yet implemented in code)

## Runtime

**Environment:**
- Python 3.12 (required: `>=3.12` per `backend/pyproject.toml`)
- Node.js 20 — frontend build stage in the planned multi-stage Dockerfile

**Package Manager:**
- `uv` — Python dependency management for `backend/`
- Lockfile: `backend/uv.lock` (committed, 150KB, 37 packages resolved)
- npm — frontend JavaScript (frontend not yet built)

## Frameworks

**Core:**
- FastAPI 0.128.7 — HTTP API framework, SSE streaming, static file serving
- Starlette (transitive via FastAPI) — ASGI foundation, `StreamingResponse` for SSE

**ASGI Server:**
- Uvicorn 0.40.0 (`[standard]` extras: uvloop, httptools, websockets) — production ASGI server

**AI/LLM (planned, not yet implemented):**
- LiteLLM — LLM abstraction layer calling OpenAI GPT models (defined in skill at `.claude/skills/openai-inference/SKILL.md`; not yet in `pyproject.toml`)
- Pydantic 2.12.5 — data validation; used for structured outputs from LLM

**Testing:**
- pytest 9.0.2 — test runner
- pytest-asyncio 1.3.0 — async test support (`asyncio_mode = "auto"`)
- pytest-cov 7.0.0 — coverage reporting

**Build/Dev:**
- Ruff 0.15.0 — linter and formatter (line-length: 100, target: py312, rules: E/F/I/N/W)
- Rich 14.3.2 — terminal output (used in `backend/market_data_demo.py` for live price dashboard)
- Next.js — frontend framework (planned; `frontend/` directory empty)
- Tailwind CSS — frontend styling (planned per spec)

## Key Dependencies

**Critical:**
- `fastapi>=0.115.0` — all HTTP routing, SSE streaming, static file serving
- `uvicorn[standard]>=0.32.0` — production server; `[standard]` adds uvloop for performance
- `numpy>=2.0.0` (resolved: 2.4.2) — Cholesky decomposition for correlated GBM price simulation in `backend/app/market/simulator.py`
- `massive>=1.0.0` (resolved: 2.2.0) — Polygon.io REST API client; used in `backend/app/market/massive_client.py` via `massive.RESTClient` and `massive.rest.models.SnapshotMarketType`
- `pydantic>=2.x` (resolved: 2.12.5) — data validation, structured LLM output parsing
- `python-dotenv 1.2.1` — loads `.env` file into environment variables

**Infrastructure:**
- `anyio 4.12.1` — async I/O foundation used by FastAPI/Starlette
- `httptools`, `uvloop` (via uvicorn standard) — high-performance HTTP parsing and event loop
- `websockets` (via uvicorn standard) — WebSocket support (present but SSE is used instead)

## Configuration

**Environment:**
- Variables read from `.env` at project root (bind-mounted into Docker container)
- `.env` is gitignored; `.env.example` is committed (referenced in README but file not present yet in repo)
- `python-dotenv` loads `.env` automatically
- Key config vars: `OPENAI_API_KEY`, `MASSIVE_API_KEY`, `LLM_MOCK`
- Factory logic in `backend/app/market/factory.py` reads `MASSIVE_API_KEY` via `os.environ.get`

**Build:**
- `backend/pyproject.toml` — Python project config, deps, test config, ruff config, coverage config
- `backend/uv.lock` — locked dependency tree (committed for reproducibility)
- Build backend: `hatchling`
- Planned multi-stage Dockerfile: Stage 1 Node 20 slim (frontend build) → Stage 2 Python 3.12 slim (backend + static files)

## Platform Requirements

**Development:**
- Python 3.12+
- `uv` package manager (`uv sync --extra dev` to install all deps)
- Run tests: `cd backend && uv run --extra dev pytest -v`
- Run linter: `uv run --extra dev ruff check app/ tests/`
- Run demo: `uv run market_data_demo.py`

**Production:**
- Docker container, single port 8000
- SQLite file at `/app/db/finally.db` (bind-mounted from host `./db/`)
- FastAPI serves both REST API (`/api/*`, `/api/stream/*`) and Next.js static export (`/*`)
- Logging: stdout at INFO level (uvicorn default)
- Target platforms: AWS App Runner, Render, or any container platform

---

*Stack analysis: 2026-05-21*
