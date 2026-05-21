# External Integrations

**Analysis Date:** 2026-05-21

## APIs & External Services

**Market Data:**
- Polygon.io (via `massive` package) — real US stock market data
  - SDK/Client: `massive 2.2.0` (`massive.RESTClient`, `massive.rest.models.SnapshotMarketType`)
  - Auth: `MASSIVE_API_KEY` env var
  - Implementation: `backend/app/market/massive_client.py` — `MassiveDataSource` class
  - Endpoint polled: `GET /v2/snapshot/locale/us/markets/stocks/tickers`
  - Rate limit: free tier 5 req/min → 15s poll interval (default); configurable via `poll_interval`
  - Mode: REST polling only (no WebSocket)
  - Activation: only used when `MASSIVE_API_KEY` is set and non-empty

**AI / LLM:**
- OpenAI GPT — LLM chat assistant for portfolio analysis and trade execution (planned, not yet implemented in code)
  - SDK/Client: LiteLLM (planned; not yet in `backend/pyproject.toml`; defined in `.claude/skills/openai-inference/SKILL.md`)
  - Model: `gpt-4.1-mini` (specified in PLAN.md and skill file)
  - Auth: `OPENAI_API_KEY` env var
  - Feature: structured outputs via `response_format=PydanticModel`
  - Mock mode: auto-enabled when `OPENAI_API_KEY` is absent/empty, or forced via `LLM_MOCK=true`

## Data Storage

**Databases:**
- SQLite — single-file relational database (planned backend implementation)
  - File location: `/app/db/finally.db` (in container); `./db/finally.db` on host
  - Client: Python stdlib `sqlite3` (no ORM specified; lazy initialization on first request)
  - Schema: 6 tables — `users_profile`, `watchlist`, `positions`, `trades`, `portfolio_snapshots`, `chat_messages`
  - Initialization: backend creates schema and seeds default data if file is missing or tables absent
  - Persistence: bind-mounted Docker volume (`-v "$PWD/db:/app/db"`)
  - Concurrency: `BEGIN IMMEDIATE` transactions for trade execution to prevent double-spend

**In-Memory:**
- `PriceCache` — thread-safe in-memory price store
  - Implementation: `backend/app/market/cache.py`
  - Contents: latest `PriceUpdate` per ticker (price, previous_price, timestamp, direction)
  - Version counter for SSE change detection (monotonic, increments on every update)
  - Protected by `threading.Lock`

**File Storage:**
- Local filesystem only — static Next.js export served by FastAPI from a `static/` directory inside the container

**Caching:**
- In-memory `PriceCache` (described above) — no Redis or external cache

## Authentication & Identity

**Auth Provider:**
- None — no authentication, no login, no signup
  - All database rows use a hardcoded `user_id = "default"`
  - Schema has `user_id` column for future multi-user migration without schema change

## Real-Time Communication

**Server-Sent Events (SSE):**
- Endpoint: `GET /api/stream/prices`
- Implementation: `backend/app/market/stream.py` — `create_stream_router()` factory
- Protocol: `text/event-stream`, `StreamingResponse` from Starlette
- Change detection: version-based (SSE handler tracks `last_version`; pushes only when `PriceCache.version` advances)
- Heartbeat: `: keep-alive\n\n` comment every 15 seconds to prevent proxy timeout
- Client retry directive: `retry: 1000` (1 second reconnect)
- Headers: `Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no`
- Client uses native browser `EventSource` API (no library)

## Monitoring & Observability

**Error Tracking:**
- None — no Sentry, Datadog, or equivalent

**Logs:**
- stdout only, plain text, INFO level via uvicorn's default formatter
- `docker logs finally` is the single observability surface
- Module-level `logging.getLogger(__name__)` used throughout `backend/app/market/`

## CI/CD & Deployment

**Hosting:**
- Docker container — single container, port 8000
- Target: AWS App Runner, Render, or any container platform

**CI Pipeline:**
- GitHub Actions — `.github/workflows/claude.yml` triggers `anthropics/claude-code-action@v1` on issue/PR comments mentioning `@claude`
- `.github/workflows/claude-code-review.yml` — separate review workflow

**Scripts:**
- `scripts/start_mac.sh` — build + run Docker container (macOS/Linux)
- `scripts/stop_mac.sh` — stop + remove container
- `scripts/start_windows.ps1` / `scripts/stop_windows.ps1` — PowerShell equivalents

## Environment Configuration

**Required env vars (for full functionality):**
- `OPENAI_API_KEY` — OpenAI key; absent = mock LLM mode
- `MASSIVE_API_KEY` — Polygon.io key; absent = GBM simulator mode
- `LLM_MOCK` — set to `true` to force mock LLM even with a valid OpenAI key (E2E test use)

**Secrets location:**
- `.env` file at project root (gitignored)
- `.env.example` documents keys without values (referenced in README; file not yet present in repo)
- Container reads via `--env-file .env` docker flag or bind-mount

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## E2E Testing Infrastructure (planned)

- Playwright — browser automation for E2E tests (location: `test/` directory)
- `test/docker-compose.test.yml` — spins up app container + Playwright container
- Tests run with `LLM_MOCK=true` for deterministic behavior

---

*Integration audit: 2026-05-21*
