# Requirements: FinAlly

**Defined:** 2026-05-21
**Core Value:** Prices stream live, users can buy/sell instantly, and an AI assistant can analyze their portfolio and execute trades on their behalf — all in one browser tab, no setup beyond a single Docker command.

## v1 Requirements

### Backend Foundation (CORE)

- [ ] **CORE-01**: FastAPI application entry point exists at `backend/app/main.py` with lifespan startup/shutdown
- [ ] **CORE-02**: Market data source starts on app startup and stops on shutdown (PriceCache + source wired together)
- [ ] **CORE-03**: FastAPI serves Next.js static export files at the root path (`/*`)
- [ ] **CORE-04**: `GET /api/health` returns `{"status": "ok"}`
- [ ] **CORE-05**: App reads `.env` from project root; `OPENAI_API_KEY` and `MASSIVE_API_KEY` control behavior

### Database (DB)

- [ ] **DB-01**: SQLite DB created at `db/finally.db` on first request if file doesn't exist
- [ ] **DB-02**: All 6 tables created on init: `users_profile`, `watchlist`, `positions`, `trades`, `portfolio_snapshots`, `chat_messages`
- [ ] **DB-03**: Default user seeded: `id="default"`, `cash_balance=10000.0`
- [ ] **DB-04**: 10 default watchlist entries seeded: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX
- [ ] **DB-05**: Trade execution uses `BEGIN IMMEDIATE` transaction to prevent double-spend

### Portfolio (PORT)

- [ ] **PORT-01**: `GET /api/portfolio` returns cash balance, positions with live P&L, and total portfolio value
- [ ] **PORT-02**: `POST /api/portfolio/trade` with `side=buy` validates sufficient cash before executing
- [ ] **PORT-03**: `POST /api/portfolio/trade` with `side=sell` validates sufficient shares before executing
- [ ] **PORT-04**: `GET /api/portfolio/history` returns `portfolio_snapshots` time series for P&L chart
- [ ] **PORT-05**: Trades fill at current price from `PriceCache` (no spread, instant fill)

### Watchlist (WATCH)

- [ ] **WATCH-01**: `GET /api/watchlist` returns tickers with latest prices and session change % (baseline = first observed price)
- [ ] **WATCH-02**: `POST /api/watchlist` adds ticker after format validation (`^[A-Z]{1,5}$`); returns `400 invalid_ticker` on failure
- [ ] **WATCH-03**: `DELETE /api/watchlist/{ticker}` removes ticker; returns `400 ticker_held` if user holds position
- [ ] **WATCH-04**: Watchlist capped at 50 tickers; `POST` returns `400 watchlist_full` when at cap
- [ ] **WATCH-05**: Adding a ticker to watchlist seeds it in the active data source immediately

### Chat / LLM (CHAT)

- [ ] **CHAT-01**: `POST /api/chat` sends user message with full portfolio context (cash, positions, watchlist with live prices) to LLM
- [ ] **CHAT-02**: LLM response uses structured output schema: `{message, trades[], watchlist_changes[]}`
- [ ] **CHAT-03**: Trades specified in LLM response auto-execute via same validation as manual trades
- [ ] **CHAT-04**: Watchlist changes in LLM response auto-apply (add/remove)
- [ ] **CHAT-05**: Mock mode returns deterministic canned responses when `OPENAI_API_KEY` is absent or empty
- [ ] **CHAT-06**: `LLM_MOCK=true` forces mock mode even when `OPENAI_API_KEY` is set
- [ ] **CHAT-07**: Last 20 messages loaded as conversation history context for each LLM call
- [ ] **CHAT-08**: Dollar-amount requests ("buy $500 of NVDA") handled by LLM converting to share count using live price in context

### Background Tasks (SNAP)

- [ ] **SNAP-01**: Portfolio value snapshot recorded every 30 seconds while at least one SSE client is connected
- [ ] **SNAP-02**: Portfolio value snapshot recorded immediately after each trade execution

### Frontend Core (FE)

- [ ] **FE-01**: Next.js TypeScript app configured with `output: 'export'` (static export, no SSR)
- [ ] **FE-02**: `EventSource` connection to `/api/stream/prices`; auto-reconnects on disconnect
- [ ] **FE-03**: Dark theme applied globally (background ~`#0d1117`, accent cyan `#38BDF8`, blue primary `#3B82F6`)
- [ ] **FE-04**: SSE connection status dot in header (green = OPEN + event ≤3s ago; yellow = OPEN + no event >3s; red = CONNECTING/CLOSED)
- [ ] **FE-05**: All API calls use same-origin `/api/*` paths (no CORS configuration needed)

### UI Components (UI)

- [ ] **UI-01**: Watchlist panel shows ticker symbol, current price, session Δ%, and sparkline for each watched ticker
- [ ] **UI-02**: Price flash animation: brief green/red background CSS transition (~500ms) on each price update
- [ ] **UI-03**: Sparkline ring buffer accumulates 120 price points from SSE stream per ticker
- [ ] **UI-04**: Clicking a watchlist ticker selects it and displays it in the main chart area
- [ ] **UI-05**: Main chart area shows price-over-time chart for the selected ticker
- [ ] **UI-06**: Portfolio heatmap (treemap) where rectangles are sized by portfolio weight and colored by P&L
- [ ] **UI-07**: P&L chart (line chart) showing total portfolio value over time from `/api/portfolio/history`
- [ ] **UI-08**: Positions table showing ticker, quantity, avg cost, current price, unrealized P&L, % change
- [ ] **UI-09**: Trade bar with ticker input, quantity input, buy button, and sell button (market orders, instant fill)
- [ ] **UI-10**: AI chat panel (collapsible/docked) with message history, text input, loading indicator, and inline trade confirmations
- [ ] **UI-11**: Header displays total portfolio value (live-updating), cash balance, and SSE connection status dot

### Infrastructure (INFRA)

- [ ] **INFRA-01**: Multi-stage Dockerfile: Stage 1 (Node 20) builds Next.js static export; Stage 2 (Python 3.12) runs uvicorn
- [ ] **INFRA-02**: Frontend static build output copied into the Python stage and served by FastAPI
- [ ] **INFRA-03**: Container exposes and serves on port 8000 only (CMD: `uvicorn app.main:app`)
- [ ] **INFRA-04**: `scripts/start_mac.sh` builds image if needed and runs container with volume mount, port mapping, and `--env-file .env`
- [ ] **INFRA-05**: `scripts/stop_mac.sh` stops and removes container without deleting volume
- [ ] **INFRA-06**: `scripts/start_windows.ps1` and `scripts/stop_windows.ps1` are PowerShell equivalents of the Mac scripts
- [ ] **INFRA-07**: `.env.example` committed with all keys documented but values empty
- [ ] **INFRA-08**: E2E Playwright tests in `test/` cover: fresh start, add/remove ticker, buy shares, sell shares, portfolio viz, AI chat (mocked), SSE reconnection
- [ ] **INFRA-09**: `db/` directory has `.gitkeep`; `db/finally.db` is gitignored

## v2 Requirements

### Performance & Observability

- **PERF-01**: Structured JSON logging (beyond uvicorn default stdout)
- **PERF-02**: Metrics endpoint for request latency, SSE client count
- **PERF-03**: Grafana/dashboard integration

### Enhanced Trading

- **TRADE-01**: Limit orders with order book
- **TRADE-02**: Trade confirmation dialog before execution
- **TRADE-03**: Trade history export (CSV)

### Multi-User

- **AUTH-01**: User authentication (login/signup)
- **AUTH-02**: Per-user portfolio isolation
- **AUTH-03**: OAuth (Google, GitHub)

### Cloud Deployment

- **CLOUD-01**: Terraform configuration for AWS App Runner or Render
- **CLOUD-02**: CI/CD pipeline for automated deployment

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time multi-user chat | Single-user app by design |
| Limit orders / order book | Market orders only; eliminates partial fills and ledger complexity |
| OAuth / social login | No auth layer; `user_id="default"` hardcoded |
| Mobile-first layout | Desktop-first; functional on tablet |
| WebSockets | SSE is sufficient for one-way price push |
| Video/rich media uploads | Trading terminal context |
| Polyfills (IE, old browsers) | Latest two stable versions of Chrome/Firefox/Edge/Safari only |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CORE-01–05 | Phase 1 | Pending |
| DB-01–05 | Phase 1 | Pending |
| PORT-01–05 | Phase 2 | Pending |
| WATCH-01–05 | Phase 2 | Pending |
| SNAP-01–02 | Phase 2 | Pending |
| CHAT-01–08 | Phase 3 | Pending |
| FE-01–05 | Phase 4 | Pending |
| UI-01–11 | Phase 4 | Pending |
| INFRA-01–09 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 47 total
- Mapped to phases: 47
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-21*
*Last updated: 2026-05-21 after initial definition*
