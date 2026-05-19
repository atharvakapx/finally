# FinAlly — AI Trading Workstation

## Project Specification

## 1. Vision

FinAlly (Finance Ally) is a visually stunning AI-powered trading workstation that streams live market data, lets users trade a simulated portfolio, and integrates an LLM chat assistant that can analyze positions and execute trades on the user's behalf. It looks and feels like a modern Bloomberg terminal with an AI copilot.

This is the capstone project for an agentic AI coding course. It is built entirely by Coding Agents demonstrating how orchestrated AI agents can produce a production-quality full-stack application. Agents interact through files in `planning/`.

## 2. User Experience

### First Launch

The user runs a single Docker command (or a provided start script). A browser opens to `http://localhost:8000`. No login, no signup. They immediately see:

- A watchlist of 10 default tickers with live-updating prices in a grid
- $10,000 in virtual cash
- A dark, data-rich trading terminal aesthetic
- An AI chat panel ready to assist

### What the User Can Do

- **Watch prices stream** — prices flash green (uptick) or red (downtick) with subtle CSS animations that fade
- **View sparkline mini-charts** — price action beside each ticker in the watchlist, accumulated on the frontend from the SSE stream since page load (sparklines fill in progressively)
- **Click a ticker** to see a larger detailed chart in the main chart area
- **Buy and sell shares** — market orders only, instant fill at current price, no fees, no confirmation dialog
- **Monitor their portfolio** — a heatmap (treemap) showing positions sized by weight and colored by P&L, plus a P&L chart tracking total portfolio value over time
- **View a positions table** — ticker, quantity, average cost, current price, unrealized P&L, % change
- **Chat with the AI assistant** — ask about their portfolio, get analysis, and have the AI execute trades and manage the watchlist through natural language
- **Manage the watchlist** — add/remove tickers manually or via the AI chat

### Visual Design

- **Dark theme**: backgrounds around `#0d1117` or `#1a1a2e`, muted gray borders, no pure black
- **Price flash animations**: brief green/red background highlight on price change, fading over ~500ms via CSS transitions
- **Connection status indicator**: a small colored dot in the header. Green when the SSE connection is `OPEN` and an event has arrived within the last 3 seconds. Yellow when `OPEN` but no event for >3 seconds (transient stall or reconnect). Red when the EventSource is `CONNECTING` or `CLOSED`.
- **Professional, data-dense layout**: inspired by Bloomberg/trading terminals — every pixel earns its place
- **Responsive but desktop-first**: optimized for wide screens, functional on tablet

### Color Scheme
- Accent Cyan: #38BDF8
- Blue Primary: #3B82F6
- Blue Secondary: #2563EB (submit buttons)

## 3. Architecture Overview

### Single Container, Single Port

```
┌─────────────────────────────────────────────────┐
│  Docker Container (port 8000)                   │
│                                                 │
│  FastAPI (Python/uv)                            │
│  ├── /api/*          REST endpoints             │
│  ├── /api/stream/*   SSE streaming              │
│  └── /*              Static file serving         │
│                      (Next.js export)            │
│                                                 │
│  SQLite database (volume-mounted)               │
│  Background task: market data polling/sim        │
└─────────────────────────────────────────────────┘
```

- **Frontend**: Next.js with TypeScript, built as a static export (`output: 'export'`), served by FastAPI as static files
- **Backend**: FastAPI (Python), managed as a `uv` project
- **Database**: SQLite, single file at `db/finally.db`, volume-mounted for persistence
- **Real-time data**: Server-Sent Events (SSE) — simpler than WebSockets, one-way server→client push, works everywhere
- **AI Integration**: LiteLLM → OpenAI GPT models with structured outputs for trade execution
- **Market data**: Environment-variable driven — simulator by default, real data via Massive API if key provided

### Why These Choices

| Decision | Rationale |
|---|---|
| SSE over WebSockets | One-way push is all we need; simpler, no bidirectional complexity, universal browser support |
| Static Next.js export | Single origin, no CORS issues, one port, one container, simple deployment |
| SQLite over Postgres | No auth = no multi-user = no need for a database server; self-contained, zero config |
| Single Docker container | Students run one command; no docker-compose for production, no service orchestration |
| uv for Python | Fast, modern Python project management; reproducible lockfile; what students should learn |
| Market orders only | Eliminates order book, limit order logic, partial fills — dramatically simpler portfolio math |

---

## 4. Directory Structure

```
finally/
├── frontend/                 # Next.js TypeScript project (static export)
├── backend/                  # FastAPI uv project (Python)
│   └── db/                   # Schema definitions, seed data, migration logic
├── planning/                 # Project-wide documentation for agents
│   ├── PLAN.md               # This document
│   └── ...                   # Additional agent reference docs
├── scripts/
│   ├── start_mac.sh          # Launch Docker container (macOS/Linux)
│   ├── stop_mac.sh           # Stop Docker container (macOS/Linux)
│   ├── start_windows.ps1     # Launch Docker container (Windows PowerShell)
│   └── stop_windows.ps1      # Stop Docker container (Windows PowerShell)
├── test/                     # Playwright E2E tests + docker-compose.test.yml
├── db/                       # Bind-mounted into the container at /app/db; SQLite file lives here at runtime
│   └── .gitkeep              # Directory exists in repo; finally.db is gitignored
├── Dockerfile                # Multi-stage build (Node → Python)
├── .env                      # Environment variables (gitignored, .env.example committed)
└── .gitignore
```

### Key Boundaries

- **`frontend/`** is a self-contained Next.js project. It knows nothing about Python. It talks to the backend via `/api/*` endpoints and `/api/stream/*` SSE endpoints. Internal structure is up to the Frontend Engineer agent.
- **`backend/`** is a self-contained uv project with its own `pyproject.toml`. It owns all server logic including database initialization, schema, seed data, API routes, SSE streaming, market data, and LLM integration. Internal structure is up to the Backend/Market Data agents.
- **`backend/db/`** contains schema SQL definitions and seed logic. The backend lazily initializes the database on first request — creating tables and seeding default data if the SQLite file doesn't exist or is empty.
- **`db/`** at the top level is bind-mounted into the container at `/app/db`. The SQLite file (`db/finally.db`) is created here by the backend and persists across container restarts. Inspecting or backing up the database is just a file copy.
- **`planning/`** contains project-wide documentation, including this plan. All agents reference files here as the shared contract.
- **`test/`** contains Playwright E2E tests and supporting infrastructure (e.g., `docker-compose.test.yml`). Unit tests live within `frontend/` and `backend/` respectively, following each framework's conventions.
- **`scripts/`** contains start/stop scripts that wrap Docker commands.

---

## 5. Environment Variables

```bash
# Optional: OpenAI API key for LLM chat functionality
# If absent or empty, the backend automatically uses deterministic mock responses
OPENAI_API_KEY=

# Optional: Massive (Polygon.io) API key for real market data
# If not set, the built-in market simulator is used (recommended for most users)
MASSIVE_API_KEY=

# Optional: Force deterministic mock LLM responses even when OPENAI_API_KEY is set
LLM_MOCK=false
```

### Behavior

- If `MASSIVE_API_KEY` is set and non-empty → backend uses Massive REST API for market data
- If `MASSIVE_API_KEY` is absent or empty → backend uses the built-in market simulator
- If `OPENAI_API_KEY` is absent or empty → backend auto-enables LLM mock mode (no separate flag needed)
- If `LLM_MOCK=true` → mock mode is forced even when `OPENAI_API_KEY` is set (used by E2E tests)
- The backend reads `.env` from the project root (mounted into the container or read via docker `--env-file`)
- The real `OPENAI_API_KEY` value lives only in the untracked `.env` file — never in this spec or any committed file. A committed `.env.example` documents the keys without values.

---

## 6. Market Data

### Two Implementations, One Interface

Both the simulator and the Massive client implement the same abstract interface. The backend selects which to use based on the environment variable. All downstream code (SSE streaming, price cache, frontend) is agnostic to the source.

### Simulator (Default)

- Generates prices using geometric Brownian motion (GBM) with configurable drift and volatility per ticker
- Updates at ~500ms intervals
- Correlated moves across tickers (e.g., tech stocks move together)
- Occasional random "events" — sudden 2-5% moves on a ticker for drama
- Starts from realistic seed prices (e.g., AAPL ~$190, GOOGL ~$175, etc.)
- Runs as an in-process background task — no external dependencies

### Massive API (Optional)

- REST API polling (not WebSocket) — simpler, works on all tiers
- Polls for the union of all watched tickers on a configurable interval
- Free tier (5 calls/min): poll every 15 seconds
- Paid tiers: poll every 2-15 seconds depending on tier
- Parses REST response into the same format as the simulator

### Shared Price Cache

- A single background task (simulator or Massive poller) writes to an in-memory price cache
- The cache holds the latest price, previous price, and timestamp for each ticker
- SSE streams read from this cache and push updates to connected clients
- This architecture supports future multi-user scenarios without changes to the data layer

### SSE Streaming

- Endpoint: `GET /api/stream/prices`
- Long-lived SSE connection; client uses native `EventSource` API
- The server emits events **on price change**, not on a fixed timer. The `PriceCache` carries a monotonic version counter; the SSE handler holds the last version it sent per client and pushes the diff whenever the counter advances. In practice this fires at roughly the simulator/Massive update cadence, but quiet tickers do not emit no-op events.
- A heartbeat comment (`: keep-alive\n\n`) is sent every 15 seconds so idle proxies don't close the connection and the client's "yellow" indicator never trips on a truly-still market
- Each SSE event contains ticker, price, previous price, timestamp, and change direction
- Client handles reconnection automatically (EventSource has built-in retry)

### Active Ticker Set

The "active ticker set" — the tickers the price source streams and the cache holds — is the **union of the watchlist and the tickers in the positions table**. Adding to the watchlist or opening a position adds a ticker; only when a ticker leaves the watchlist *and* has zero position is it dropped.

### Ticker Validation

`POST /api/watchlist` validates the symbol before adding it:

- **Format check (both modes):** uppercase A–Z, 1–5 characters. Anything else returns `400 invalid_ticker`.
- **Simulator mode:** format check is the only check. New tickers are seeded at `$100.00` with the default GBM parameters (drift ≈ 0, volatility ≈ 0.02/tick) — see `seed_prices.py` for the canonical defaults.
- **Massive mode:** the backend additionally probes the symbol with one Massive REST call before accepting. Unknown symbols return `404 unknown_ticker`.

### Watchlist Size Cap

The watchlist is capped at **50 tickers**. `POST /api/watchlist` returns `400 watchlist_full` once the cap is reached. The cap protects the SSE payload size, the in-memory cache, and the Massive API quota.

### Held-but-Unwatched Tickers

A user cannot remove a ticker from the watchlist while they hold a position in it (`quantity > 0`). `DELETE /api/watchlist/{ticker}` returns `400 ticker_held` in that case. This keeps the active ticker set as a clean function of the watchlist alone in the common case, and avoids "your portfolio P&L silently froze" surprises.

### Session Change %

The watchlist's "% change" column is **session change**, not daily change. The baseline is the first price the cache observes for a ticker after the server starts (or after the ticker is first added). The UI labels this column "Session Δ%" to avoid implying real market-day semantics.

### Sparkline Buffer

Sparklines accumulate prices from the SSE stream into a **ring buffer of 120 points** per ticker on the frontend. At the simulator's ~500ms cadence this covers the most recent minute and bounds memory regardless of session length.

---

## 7. Database

### SQLite with Lazy Initialization

The backend checks for the SQLite database on startup (or first request). If the file doesn't exist or tables are missing, it creates the schema and seeds default data. This means:

- No separate migration step
- No manual database setup
- Fresh Docker volumes start with a clean, seeded database automatically

### Schema

All tables include a `user_id` column defaulting to `"default"`. This is hardcoded for now (single-user) but enables future multi-user support without schema migration.

**users_profile** — User state (cash balance)
- `id` TEXT PRIMARY KEY (default: `"default"`)
- `cash_balance` REAL (default: `10000.0`)
- `created_at` TEXT (ISO timestamp)

**watchlist** — Tickers the user is watching
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `added_at` TEXT (ISO timestamp)
- UNIQUE constraint on `(user_id, ticker)`

**positions** — Current holdings (one row per ticker per user)
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `quantity` REAL (fractional shares supported)
- `avg_cost` REAL
- `updated_at` TEXT (ISO timestamp)
- UNIQUE constraint on `(user_id, ticker)`

**trades** — Trade history (append-only log)
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `side` TEXT (`"buy"` or `"sell"`)
- `quantity` REAL (fractional shares supported)
- `price` REAL
- `executed_at` TEXT (ISO timestamp)

**portfolio_snapshots** — Portfolio value over time (for P&L chart). A snapshot is recorded every 30 seconds **while at least one SSE client is connected**, and immediately after each trade execution. When no client is connected the cadence task pauses, so idle deployments don't accumulate snapshots.
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `total_value` REAL
- `recorded_at` TEXT (ISO timestamp)

**chat_messages** — Conversation history with LLM
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `role` TEXT (`"user"` or `"assistant"`)
- `content` TEXT
- `actions` TEXT (JSON — trades executed, watchlist changes made; null for user messages)
- `created_at` TEXT (ISO timestamp)

### Money Representation

All monetary fields (`cash_balance`, `avg_cost`, `price`, `total_value`) use SQLite `REAL` (IEEE-754 double). This is fine for a simulated environment with fake money — there are no rounding-sensitive ledger reconciliations to worry about. Display layers should `toFixed(2)` for currency and `toFixed(4)` for fractional shares.

### Default Seed Data

- One user profile: `id="default"`, `cash_balance=10000.0`
- Ten watchlist entries: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX

---

## 8. API Endpoints

### Market Data
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stream/prices` | SSE stream of live price updates |

### Portfolio
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolio` | Current positions, cash balance, total value, unrealized P&L |
| POST | `/api/portfolio/trade` | Execute a trade: `{ticker, quantity, side}` |
| GET | `/api/portfolio/history` | Portfolio value snapshots over time (for P&L chart) |

### Watchlist
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/watchlist` | Current watchlist tickers with latest prices |
| POST | `/api/watchlist` | Add a ticker: `{ticker}` |
| DELETE | `/api/watchlist/{ticker}` | Remove a ticker |

### Chat
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send a message, receive complete JSON response (message + executed actions) |

### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check (for Docker/deployment) |

### Trade Request and Response Shape

`POST /api/portfolio/trade`

Request body:
```json
{ "ticker": "AAPL", "side": "buy", "quantity": 10 }
```

- `ticker` — uppercase symbol; must be present in the active ticker set (watchlist ∪ positions)
- `side` — `"buy"` or `"sell"`
- `quantity` — positive number; fractional shares allowed (4 decimal places)

Success response (`200 OK`):
```json
{
  "trade": {
    "id": "9f1c…",
    "ticker": "AAPL",
    "side": "buy",
    "quantity": 10,
    "price": 192.43,
    "executed_at": "2026-05-19T14:22:01Z"
  },
  "cash_balance": 8075.70,
  "position": { "ticker": "AAPL", "quantity": 10, "avg_cost": 192.43 }
}
```

Validation failure (`400 Bad Request`):
```json
{ "error": "insufficient_cash", "message": "Need $1924.30, have $500.00" }
```

### Concurrency

`POST /api/portfolio/trade` runs inside a SQLite `BEGIN IMMEDIATE` transaction. Cash and position rows are re-read inside the transaction and validated before the trade is written, which prevents two near-simultaneous buys from double-spending the cash balance.

### Error Contract

All non-2xx responses share a single shape:
```json
{ "error": "<machine_code>", "message": "<human readable>" }
```

| Status | error code | When |
|--------|------------|------|
| 400 | `invalid_ticker` | Ticker fails format check (regex `^[A-Z]{1,5}$`) |
| 400 | `watchlist_full` | Watchlist is already at the 50-ticker cap |
| 400 | `ticker_held` | Trying to remove a watchlist ticker with a non-zero position |
| 400 | `invalid_side` | Trade `side` is not `"buy"` or `"sell"` |
| 400 | `invalid_quantity` | Trade `quantity` is non-positive or non-numeric |
| 400 | `insufficient_cash` | Buy would drive `cash_balance` below 0 |
| 400 | `insufficient_shares` | Sell quantity exceeds held quantity |
| 404 | `unknown_ticker` | Massive mode: symbol not recognized by the API |
| 404 | `not_found` | Generic missing resource |
| 503 | `market_data_unavailable` | Cache has no price for the ticker (transient) |
| 500 | `internal_error` | Unhandled server error |

---

## 9. LLM Integration

When writing code to make calls to LLMs, use LiteLLM with OpenAI GPT models. Structured Outputs should be used to interpret the results.

Use the `gpt-4.1-mini` model by default for fast responses and strong reasoning performance.

There is an `OPENAI_API_KEY` in the `.env` file in the project root.

### How It Works

When the user sends a chat message, the backend:

1. Loads the user's current portfolio context (cash, positions with P&L, watchlist with live prices, total portfolio value). Live prices are included so the LLM can convert dollar amounts to share counts.
2. Loads the **last 20 messages** from the `chat_messages` table as conversation history (hard cap; oldest dropped if the user has chatted longer)
3. Constructs a prompt with a system message, portfolio context, conversation history, and the user's new message
4. Calls the LLM via LiteLLM → OpenAI `gpt-4.1-mini`, requesting structured output, using the `openai-inference` skill
5. Parses the complete structured JSON response
6. Auto-executes any trades or watchlist changes specified in the response
7. Stores the message and executed actions in `chat_messages`
8. Returns the complete JSON response to the frontend (no token-by-token streaming — `gpt-4.1-mini` is fast enough that a single loading indicator is sufficient)

### Structured Output Schema

The LLM is instructed to respond with JSON matching this schema:

```json
{
  "message": "Your conversational response to the user",
  "trades": [
    {"ticker": "AAPL", "side": "buy", "quantity": 10}
  ],
  "watchlist_changes": [
    {"ticker": "PYPL", "action": "add"}
  ]
}
```

- `message` (required): The conversational text shown to the user
- `trades` (optional): Array of trades to auto-execute. Each trade goes through the same validation as manual trades (sufficient cash for buys, sufficient shares for sells)
- `watchlist_changes` (optional): Array of watchlist modifications

### Trade Quantity Semantics

The structured-output schema requires `quantity` as a share count. If the user asks for a dollar amount ("buy $500 of NVDA"), the LLM is responsible for converting it to a share count using the live price provided in its portfolio context. The system prompt explicitly instructs this behavior, so the API surface stays minimal (one quantity field, not a discriminated `shares | notional_usd` union).

### Auto-Execution

Trades specified by the LLM execute automatically — no confirmation dialog. This is a deliberate design choice:
- It's a simulated environment with fake money, so the stakes are zero
- It creates an impressive, fluid demo experience
- It demonstrates agentic AI capabilities — the core theme of the course

If a trade fails validation (e.g., insufficient cash), the error is included in the chat response so the LLM can inform the user.

### System Prompt Guidance

The LLM should be prompted as "FinAlly, an AI trading assistant" with instructions to:
- Analyze portfolio composition, risk concentration, and P&L
- Suggest trades with reasoning
- Execute trades when the user asks or agrees
- Manage the watchlist proactively
- Be concise and data-driven in responses
- Always respond with valid structured JSON

### LLM Mock Mode

Mock mode returns deterministic canned responses instead of calling OpenAI. It activates in either of two cases:

- **Auto:** `OPENAI_API_KEY` is absent or empty. No flag needed — running without a key Just Works for demos and CI.
- **Override:** `LLM_MOCK=true` is set, even when `OPENAI_API_KEY` is present. E2E tests use this to keep behavior deterministic on machines that happen to have a key configured.

Mock mode enables:
- Fast, free, reproducible E2E tests
- Development without an API key
- CI/CD pipelines

---

## 10. Frontend Design

### Layout

The frontend is a single-page application with a dense, terminal-inspired layout. The specific component architecture and layout system is up to the Frontend Engineer, but the UI should include these elements:

- **Watchlist panel** — grid/table of watched tickers with: ticker symbol, current price (flashing green/red on change), session change % (labeled "Session Δ%" — see §6), and a sparkline mini-chart (120-point ring buffer accumulated from SSE)
- **Main chart area** — larger chart for the currently selected ticker, with at minimum price over time. Clicking a ticker in the watchlist selects it here.
- **Portfolio heatmap** — treemap visualization where each rectangle is a position, sized by portfolio weight, colored by P&L (green = profit, red = loss)
- **P&L chart** — line chart showing total portfolio value over time, using data from `portfolio_snapshots`
- **Positions table** — tabular view of all positions: ticker, quantity, avg cost, current price, unrealized P&L, % change
- **Trade bar** — simple input area: ticker field, quantity field, buy button, sell button. Market orders, instant fill.
- **AI chat panel** — docked/collapsible sidebar. Message input, scrolling conversation history, loading indicator while waiting for LLM response. Trade executions and watchlist changes shown inline as confirmations.
- **Header** — portfolio total value (updating live), connection status indicator, cash balance

### Technical Notes

- Use `EventSource` for SSE connection to `/api/stream/prices`
- Canvas-based charting library preferred (Lightweight Charts or Recharts) for performance
- Price flash effect: on receiving a new price, briefly apply a CSS class with background color transition, then remove it
- All API calls go to the same origin (`/api/*`) — no CORS configuration needed
- Tailwind CSS for styling with a custom dark theme

### Connection Status Logic

The header dot reflects three states, derived on the client:

- **Green** — `EventSource.readyState === OPEN` **and** the last event arrived ≤3 seconds ago
- **Yellow** — `OPEN` **but** no event for >3 seconds (transient stall; the 15s server heartbeat will eventually retrigger green if the connection is healthy)
- **Red** — `CONNECTING` or `CLOSED`

A single `setInterval(1000)` is enough to drive the green→yellow transition; the green→red and red→green transitions piggyback on `EventSource` lifecycle events.

### Browser Support

Targets the latest two stable versions of Chrome, Firefox, Edge, and Safari. No IE, no polyfills for `EventSource`, `fetch`, `ResizeObserver`, or `Intl.NumberFormat`.

---

## 11. Docker & Deployment

### Multi-Stage Dockerfile

```
Stage 1: Node 20 slim
  - Copy frontend/
  - npm install && npm run build (produces static export)

Stage 2: Python 3.12 slim
  - Install uv
  - Copy backend/
  - uv sync (install Python dependencies from lockfile)
  - Copy frontend build output into a static/ directory
  - Expose port 8000
  - CMD: uvicorn serving FastAPI app
```

FastAPI serves the static frontend files and all API routes on port 8000.

### Docker Volume

The SQLite database persists via a bind mount of the project's top-level `db/` directory:

```bash
docker run -v "$PWD/db:/app/db" -p 8000:8000 --env-file .env finally
```

`./db` on the host maps to `/app/db` in the container, and the backend writes `finally.db` there. Bind-mounting (rather than a named volume) means students can inspect or back up the SQLite file with a plain file copy, and `rm db/finally.db` resets the demo cleanly.

### Logging

The backend logs to stdout as plain text at `INFO` level (uvicorn's default formatter). Docker captures stdout automatically — `docker logs finally` is the single observability surface. No log files, no log aggregation, no JSON structured logs in v1.

### Start/Stop Scripts

**`scripts/start_mac.sh`** (macOS/Linux):
- Builds the Docker image if not already built (or if `--build` flag passed)
- Runs the container with the volume mount, port mapping, and `.env` file
- Prints the URL to access the app
- Optionally opens the browser

**`scripts/stop_mac.sh`** (macOS/Linux):
- Stops and removes the running container
- Does NOT remove the volume (data persists)

**`scripts/start_windows.ps1`** / **`scripts/stop_windows.ps1`**: PowerShell equivalents for Windows.

All scripts should be idempotent — safe to run multiple times.

### Optional Cloud Deployment

The container is designed to deploy to AWS App Runner, Render, or any container platform. A Terraform configuration for App Runner may be provided in a `deploy/` directory as a stretch goal, but is not part of the core build.

---

## 12. Testing Strategy

### Unit Tests (within `frontend/` and `backend/`)

**Backend (pytest)**:
- Market data: simulator generates valid prices, GBM math is correct, Massive API response parsing works, both implementations conform to the abstract interface
- Portfolio: trade execution logic, P&L calculations, edge cases (selling more than owned, buying with insufficient cash, selling at a loss)
- LLM: structured output parsing handles all valid schemas, graceful handling of malformed responses, trade validation within chat flow
- API routes: correct status codes, response shapes, error handling

**Frontend (React Testing Library or similar)**:
- Component rendering with mock data
- Price flash animation triggers correctly on price changes
- Watchlist CRUD operations
- Portfolio display calculations
- Chat message rendering and loading state

### E2E Tests (in `test/`)

**Infrastructure**: A separate `docker-compose.test.yml` in `test/` that spins up the app container plus a Playwright container. This keeps browser dependencies out of the production image.

**Environment**: Tests run with `LLM_MOCK=true` by default for speed and determinism.

**Key Scenarios**:
- Fresh start: default watchlist appears, $10k balance shown, prices are streaming
- Add and remove a ticker from the watchlist
- Buy shares: cash decreases, position appears, portfolio updates
- Sell shares: cash increases, position updates or disappears
- Portfolio visualization: heatmap renders with correct colors, P&L chart has data points
- AI chat (mocked): send a message, receive a response, trade execution appears inline
- SSE resilience: disconnect and verify reconnection

