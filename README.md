# FinAlly — AI Trading Workstation

A visually stunning, AI-powered trading workstation that streams live market data, lets you trade a simulated portfolio, and includes an LLM chat assistant that can analyze positions and execute trades on your behalf. Looks and feels like a Bloomberg terminal with an AI copilot.

Built entirely by orchestrated AI coding agents as a capstone project for an agentic AI coding course.

---

## Features

- **Live price streaming** — prices flash green/red on uptick/downtick via SSE; no polling
- **Sparkline mini-charts** — 120-point ring buffer per ticker accumulated from the live stream
- **Simulated portfolio** — start with $10,000 in virtual cash; buy and sell with instant market-order fills
- **Portfolio heatmap** — treemap sized by position weight, colored by P&L
- **P&L chart** — total portfolio value over time
- **AI chat assistant** — powered by GPT-4.1-mini; analyzes your portfolio, suggests trades, and executes them via natural language
- **Watchlist management** — add/remove tickers manually or through the AI

## Architecture

Single container, single port. No microservices, no docker-compose in production.

```
FastAPI (port 8000)
├── /api/*          REST endpoints
├── /api/stream/*   SSE price streaming
└── /*              Next.js static export

SQLite             db/finally.db (bind-mounted, persists across restarts)
Market data        GBM simulator (default) or Polygon.io REST poller
LLM                LiteLLM → OpenAI gpt-4.1-mini with structured outputs
```

## Quick Start

```bash
# Copy and configure environment variables
cp .env.example .env
# Edit .env if you want real market data (MASSIVE_API_KEY) or AI chat (OPENAI_API_KEY)

# Start the app
./scripts/start_mac.sh        # macOS / Linux
./scripts/start_windows.ps1   # Windows PowerShell
```

Then open [http://localhost:8000](http://localhost:8000).

To stop:

```bash
./scripts/stop_mac.sh
./scripts/stop_windows.ps1
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | _(empty)_ | OpenAI key for AI chat. Omit to use deterministic mock responses. |
| `MASSIVE_API_KEY` | _(empty)_ | Polygon.io key for real market data. Omit to use the built-in GBM simulator. |
| `LLM_MOCK` | `false` | Force mock LLM responses even when `OPENAI_API_KEY` is set. Used by E2E tests. |

The app works with no keys set — the simulator generates realistic correlated price moves and the AI responds with canned but meaningful demo messages.

## Market Data

The built-in simulator uses **Geometric Brownian Motion** with Cholesky-correlated moves across sector groups (tech stocks correlate at 0.6, financials at 0.5, cross-sector at 0.3) and occasional random 2–5% shock events. Starts from realistic seed prices (AAPL ~$190, GOOGL ~$175, etc.) and updates every ~500ms.

When `MASSIVE_API_KEY` is set the backend switches to polling the Polygon.io REST API on a configurable interval instead.

Both sources implement the same abstract interface — all downstream code is source-agnostic.

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js + TypeScript (static export), Tailwind CSS |
| Backend | FastAPI, Python 3.12, managed with `uv` |
| Database | SQLite (lazy-initialized, seeded on first run) |
| Real-time | Server-Sent Events (`EventSource`) |
| AI | LiteLLM → OpenAI gpt-4.1-mini, structured outputs |
| Container | Docker (multi-stage Node → Python build) |

## Default Watchlist

AAPL · GOOGL · MSFT · AMZN · TSLA · NVDA · META · JPM · V · NFLX

The watchlist is capped at 50 tickers. Tickers with open positions cannot be removed.

## Resetting the Demo

```bash
rm db/finally.db
```

The backend recreates the database with fresh seed data on next request.

## Development

```bash
# Backend
cd backend
uv sync
uv run pytest          # 73 tests
uv run market_data_demo.py  # live terminal price dashboard
```

The market data demo displays a live Rich terminal dashboard for all 10 default tickers — useful for verifying the simulator or Massive client without running the full app.
