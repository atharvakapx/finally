# FinAlly

## What This Is

FinAlly (Finance Ally) is a visually stunning AI-powered trading workstation that streams live market data, lets users trade a simulated portfolio, and integrates an LLM chat assistant that can analyze positions and execute trades on the user's behalf. It runs in a single Docker container on port 8000, has no login, and gives users $10,000 in virtual cash to trade with from the moment they open a browser.

The aesthetic is a modern Bloomberg terminal with an AI copilot — dark theme, data-dense layout, price flash animations, sparklines, and a heatmap portfolio view.

## Core Value

Prices stream live, users can buy/sell instantly, and an AI assistant can analyze their portfolio and execute trades on their behalf — all in one browser tab, no setup beyond a single Docker command.

## Requirements

### Validated

- ✓ Market data simulator (GBM with Cholesky-correlated sector moves, random shock events) — market subsystem
- ✓ PriceCache (thread-safe, version-counter-based change detection) — market subsystem
- ✓ SSE streaming endpoint (`/api/stream/prices`) with heartbeat — market subsystem
- ✓ Massive API client (Polygon.io REST polling, same interface as simulator) — market subsystem
- ✓ MarketDataSource ABC (strategy pattern, factory selection via env var) — market subsystem
- ✓ Seed prices for 10 default tickers (AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX) — market subsystem
- ✓ 73 tests passing (84% coverage) — market subsystem

### Active

- [ ] FastAPI application entry point (`backend/app/main.py`) wiring market data, DB, all routers
- [ ] SQLite database with lazy initialization (schema + seed on first run)
- [ ] Portfolio API: `GET /api/portfolio`, `POST /api/portfolio/trade`, `GET /api/portfolio/history`
- [ ] Watchlist API: `GET /api/watchlist`, `POST /api/watchlist`, `DELETE /api/watchlist/{ticker}`
- [ ] Chat API: `POST /api/chat` with LLM integration (LiteLLM → GPT-4.1-mini, structured outputs)
- [ ] LLM mock mode (deterministic responses when OPENAI_API_KEY absent or LLM_MOCK=true)
- [ ] Portfolio snapshot background task (every 30s while SSE clients connected, plus after every trade)
- [ ] Next.js frontend (TypeScript, static export, dark terminal aesthetic)
  - [ ] Watchlist panel (prices, session Δ%, sparklines, flash animations)
  - [ ] Main chart area (selected ticker price chart)
  - [ ] Portfolio heatmap (treemap by weight, colored by P&L)
  - [ ] P&L chart (portfolio value over time)
  - [ ] Positions table (ticker, qty, avg cost, price, unrealized P&L, % change)
  - [ ] Trade bar (ticker, quantity, buy/sell buttons)
  - [ ] AI chat panel (messages, loading state, inline trade confirmations)
  - [ ] Header (total value, cash balance, SSE connection status dot)
- [ ] Multi-stage Dockerfile (Node → Python, static export served by FastAPI)
- [ ] Start/stop scripts (macOS/Linux shell, Windows PowerShell)
- [ ] `.env.example` with documented keys
- [ ] E2E Playwright tests (key user flows with LLM_MOCK=true)

### Out of Scope

- Real-time chat between users — single-user app by design
- Limit orders, order book, partial fills — market orders only, simplifies portfolio math
- OAuth/social login — no auth layer; single default user
- Mobile-first design — desktop-first, functional on tablet
- Video posts / complex media uploads — trading terminal context, text/charts only
- Cloud deployment (Terraform, App Runner) — stretch goal, not in core build
- WebSockets — SSE is sufficient for one-way price push

## Context

This is the capstone project for an agentic AI coding course, built entirely by coding agents. The market data subsystem (`backend/app/market/`) is complete and tested — all new backend code should integrate with it using the `PriceCache` and `MarketDataSource` abstractions rather than reimplementing them.

Key constraints from the design:
- Single container, single port (8000) — no docker-compose in production
- SQLite for persistence — no Postgres, no Redis
- `uv` for Python package management (lockfile already exists)
- `next export` static output — no SSR, no Next.js server process
- `gpt-4.1-mini` via LiteLLM for chat — fast and cost-effective
- All monetary values as SQLite REAL; display with `toFixed(2)` for currency, `toFixed(4)` for shares

## Constraints

- **Tech stack**: FastAPI (Python/uv) + Next.js (TypeScript, static export) + SQLite — no deviations
- **Container**: Single Docker container, port 8000 — no multi-service docker-compose
- **AI model**: LiteLLM → `gpt-4.1-mini` — structured JSON output required
- **Market data**: The existing `backend/app/market/` package is the canonical interface — no reimplementation
- **OPENAI_API_KEY**: Lives only in `.env` (gitignored) — never committed
- **Database**: SQLite at `db/finally.db`, bind-mounted volume — lazy init on first request

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SSE over WebSockets | One-way push is all we need; simpler, universal browser support | — Pending |
| Static Next.js export served by FastAPI | Single origin, no CORS, one port, one container | — Pending |
| SQLite over Postgres | Single-user, no multi-user concurrency; self-contained, zero config | — Pending |
| Market orders only | Eliminates order book complexity, dramatically simpler portfolio math | — Pending |
| GPT-4.1-mini via LiteLLM | Fast responses, strong reasoning, cost-effective | — Pending |
| LLM auto-execution (no confirmation) | Simulated money, zero stakes, impressive demo of agentic capabilities | — Pending |
| GBM simulator with Cholesky correlation | Realistic-looking price action, no external dependencies for default mode | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-21 after initialization*
