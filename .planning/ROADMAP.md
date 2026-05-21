# Roadmap: FinAlly

## Overview

FinAlly is a single-container AI trading workstation that streams live prices, runs a simulated portfolio, and lets an LLM assistant analyze positions and execute trades on the user's behalf. The market data subsystem (GBM simulator, PriceCache, SSE stream, Massive client — 73 tests passing) is already validated. This roadmap delivers the remaining 47 v1 requirements as five vertical-MVP phases: each phase ends with a user-observable capability working end-to-end, so the product feels alive earlier rather than after a "big bang" integration at the end.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Backend Foundation** - FastAPI app wired to market data, SQLite lazy init, health check live
- [ ] **Phase 2: Portfolio & Watchlist APIs** - Trade execution, watchlist CRUD, and portfolio snapshots over the existing price cache
- [ ] **Phase 3: AI Chat** - LiteLLM + GPT-4.1-mini with structured outputs, auto-executing trades, and deterministic mock mode
- [ ] **Phase 4: Frontend Workstation** - Next.js static export delivering the full Bloomberg-style terminal UI against live SSE + REST
- [ ] **Phase 5: Docker & E2E** - Multi-stage container, start/stop scripts, `.env.example`, Playwright E2E suite

## Phase Details

### Phase 1: Backend Foundation
**Goal**: A running FastAPI process boots cleanly, brings up the market data source, lazy-initializes the SQLite database with seed data, and serves a health check.
**Mode:** mvp
**Depends on**: Nothing (first phase); consumes the already-validated `backend/app/market/` package
**Requirements**: CORE-01, CORE-02, CORE-03, CORE-04, CORE-05, DB-01, DB-02, DB-03, DB-04, DB-05
**Success Criteria** (what must be TRUE):
  1. Running `uvicorn app.main:app` starts the server with no errors and `GET /api/health` returns `{"status": "ok"}`
  2. First request creates `db/finally.db` with all 6 tables (`users_profile`, `watchlist`, `positions`, `trades`, `portfolio_snapshots`, `chat_messages`) and seeds the default user with $10,000 cash plus the 10 default tickers
  3. Market data source (simulator by default, Massive when `MASSIVE_API_KEY` is set) is running and the PriceCache is populated within seconds of startup
  4. The Next.js static export directory is served at `/` (placeholder index is fine until Phase 4)
  5. Restarting the process preserves the database (existing `db/finally.db` is reused, not re-seeded)
**Plans**: TBD

### Phase 2: Portfolio & Watchlist APIs
**Goal**: A user (or a future LLM caller) can manage their watchlist and execute trades against live prices, with cash, positions, and portfolio snapshots updating consistently.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: PORT-01, PORT-02, PORT-03, PORT-04, PORT-05, WATCH-01, WATCH-02, WATCH-03, WATCH-04, WATCH-05, SNAP-01, SNAP-02
**Success Criteria** (what must be TRUE):
  1. `GET /api/portfolio` returns cash, every position with live price and unrealized P&L, and a total portfolio value that matches `cash + Σ(qty × price)`
  2. Buying via `POST /api/portfolio/trade` debits cash at the cache's current price, creates/updates the position with a correct weighted-average cost, and refuses with `400 insufficient_cash` when the cash would go negative (verified under concurrent buys via `BEGIN IMMEDIATE`)
  3. Selling debits shares, credits cash, removes the position when quantity hits zero, and refuses with `400 insufficient_shares` when oversold
  4. `POST /api/watchlist` and `DELETE /api/watchlist/{ticker}` enforce the regex format, the 50-ticker cap, and the held-position guard, returning the documented `400` codes; adds immediately seed the ticker into the active data source
  5. `GET /api/portfolio/history` returns a time series of snapshots; a snapshot is recorded after every trade and every 30s while at least one SSE client is connected, and the cadence task pauses when no client is connected
**Plans**: TBD

### Phase 3: AI Chat
**Goal**: A user can chat with FinAlly, receive structured analyses, and have the assistant auto-execute trades and watchlist edits, with deterministic behavior whenever an API key is absent or `LLM_MOCK=true`.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: CHAT-01, CHAT-02, CHAT-03, CHAT-04, CHAT-05, CHAT-06, CHAT-07, CHAT-08
**Success Criteria** (what must be TRUE):
  1. `POST /api/chat` with `OPENAI_API_KEY` set calls `gpt-4.1-mini` via LiteLLM with structured outputs and returns `{message, trades[], watchlist_changes[]}` validated against the schema
  2. Any `trades[]` in the response auto-execute through the Phase 2 trade endpoint's validation, and any `watchlist_changes[]` apply through the watchlist endpoints; failures are reported back in the chat reply rather than crashing the request
  3. The LLM call carries the user's current cash, positions with live prices, watchlist with live prices, and the last 20 messages from `chat_messages` as conversation history
  4. A dollar-amount request like "buy $500 of NVDA" is converted to a share count by the LLM using the live price provided in its context and executes correctly
  5. With `OPENAI_API_KEY` absent/empty **or** `LLM_MOCK=true`, the endpoint returns deterministic canned responses (no network call), so tests and demos work without a key
**Plans**: TBD

### Phase 4: Frontend Workstation
**Goal**: A user opens `http://localhost:8000` and sees a working Bloomberg-style terminal: live-streaming watchlist with sparklines, a main chart, portfolio heatmap, P&L chart, positions table, trade bar, AI chat panel, and a header with live total value and connection dot.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: FE-01, FE-02, FE-03, FE-04, FE-05, UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, UI-08, UI-09, UI-10, UI-11
**Success Criteria** (what must be TRUE):
  1. On first load the dark-themed page renders the 10 default tickers in the watchlist with prices, session Δ%, and sparklines that fill in progressively as SSE events arrive; price cells flash green/red and fade over ~500ms on each change
  2. Clicking a watchlist row selects the ticker and displays its price-over-time chart in the main chart area, and the connection status dot in the header transitions green / yellow / red correctly based on `EventSource.readyState` and event-recency
  3. The trade bar executes market buys and sells against `/api/portfolio/trade`, and the positions table, portfolio heatmap (sized by weight, colored by P&L), and P&L chart (`/api/portfolio/history`) all update accordingly
  4. The header live-updates total portfolio value and cash balance as prices stream and trades execute
  5. The AI chat panel can send messages, shows a loading indicator while waiting, renders assistant responses with inline confirmations for any auto-executed trades or watchlist changes, and all API calls use same-origin `/api/*` paths with zero CORS configuration
**Plans**: TBD
**UI hint**: yes

### Phase 5: Docker & E2E
**Goal**: One command builds and runs the full app in a single container on port 8000, with cross-platform start/stop scripts, a documented `.env.example`, and a Playwright E2E suite that exercises the key user flows deterministically.
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06, INFRA-07, INFRA-08, INFRA-09
**Success Criteria** (what must be TRUE):
  1. The multi-stage Dockerfile builds: Stage 1 (Node 20) produces the Next.js static export; Stage 2 (Python 3.12 + `uv`) installs backend deps, copies in the static export, and exposes port 8000 via `uvicorn app.main:app`
  2. `scripts/start_mac.sh` / `scripts/start_windows.ps1` build the image if needed and run the container with `-v $PWD/db:/app/db`, `-p 8000:8000`, and `--env-file .env`; `stop_mac.sh` / `stop_windows.ps1` stop and remove the container without touching the bind-mounted database
  3. `.env.example` is committed at the project root documenting `OPENAI_API_KEY`, `MASSIVE_API_KEY`, and `LLM_MOCK`; `db/.gitkeep` is committed and `db/finally.db` is gitignored
  4. The Playwright suite under `test/` (via `docker-compose.test.yml`, run with `LLM_MOCK=true`) passes end-to-end for: fresh start (default watchlist + $10k), add/remove ticker, buy shares, sell shares, portfolio visualization, mocked AI chat with trade execution, and SSE reconnection after a forced disconnect
  5. A clean checkout on a developer machine reaches a fully working app via a single start script invocation, with the database persisting across container restarts
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Backend Foundation | 0/TBD | Not started | - |
| 2. Portfolio & Watchlist APIs | 0/TBD | Not started | - |
| 3. AI Chat | 0/TBD | Not started | - |
| 4. Frontend Workstation | 0/TBD | Not started | - |
| 5. Docker & E2E | 0/TBD | Not started | - |
