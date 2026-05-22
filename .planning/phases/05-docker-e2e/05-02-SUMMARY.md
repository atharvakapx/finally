---
phase: 05-docker-e2e
plan: 02
status: complete
tests: 8
subsystem: testing
tags: [playwright, e2e, docker, sse, chat-mock]
dependency_graph:
  requires: [05-01]
  provides: [INFRA-08]
  affects: [test/]
tech_stack:
  added: ["@playwright/test ^1.40.0"]
  patterns: ["docker-compose for test isolation", "LLM_MOCK=true for determinism"]
key_files:
  created:
    - test/e2e.spec.ts
    - test/docker-compose.test.yml
    - test/playwright.config.ts
    - test/package.json
  modified: []
decisions:
  - "Included 9th SSE reconnection test (plan must_haves required it alongside 8 core flows)"
  - "All data-testid attributes verified present in Phase 4 components — no patching needed"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-22"
  tasks_completed: 2
  files_created: 4
---

# Phase 05 Plan 02: Playwright E2E Test Suite Summary

Playwright E2E suite with 9 tests covering all key user flows against the running app with LLM_MOCK=true for determinism.

## What Was Built

Four files were created in `test/`:

- **`test/package.json`** — Node project declaring `@playwright/test ^1.40.0` as dev dependency
- **`test/playwright.config.ts`** — Playwright config with `baseURL: http://localhost:8000`, 30s timeout, list + HTML reporters
- **`test/docker-compose.test.yml`** — Two-service compose: `app` (finally image with LLM_MOCK=true, health-checked on /api/health) and `playwright` (mcr.microsoft.com/playwright:v1.40.0-jammy, depends on app healthy, shares app's network)
- **`test/e2e.spec.ts`** — 9 E2E tests covering all required user flows

## Test Coverage

| # | Test | Covers |
|---|------|--------|
| 1 | Fresh start: default watchlist + $10k balance | Initial state, seeded data |
| 2 | Prices are streaming (SSE green dot) | SSE connection, connection-dot testid |
| 3 | Add ticker to watchlist | POST /api/watchlist, add-ticker-input/btn testids |
| 4 | Remove ticker from watchlist | DELETE /api/watchlist/{ticker}, remove-ticker-{TICKER} testid |
| 5 | Buy shares: cash decreases, position appears | POST /api/portfolio/trade buy side |
| 6 | Sell shares: position reduces | POST /api/portfolio/trade sell side |
| 7 | Portfolio heatmap renders after buy | heatmap testid, treemap visible after position |
| 8 | AI chat mock: send message, receive response | POST /api/chat with LLM_MOCK=true |
| 9 | SSE reconnection: disconnect and reconnect | page.route abort + unroute, dot recovers |

## data-testid Verification

All required testids were already present from Phase 4 — no component patching needed:

- `Header.tsx:87` — `data-testid="connection-dot"`
- `WatchlistPanel.tsx:143,163,248` — `add-ticker-input`, `add-ticker-btn`, `remove-ticker-${ticker}`
- `TradeBar.tsx:100,109,119,127` — `trade-ticker`, `trade-quantity`, `buy-btn`, `sell-btn`
- `PortfolioHeatmap.tsx:69` — `data-testid="heatmap"`
- `ChatPanel.tsx:156,246,267` — `chat-messages`, `chat-input`, `chat-submit`

## Deviations from Plan

### Auto-added

**[Rule 2 - Missing critical coverage] SSE reconnection test included**
- The plan's `must_haves.truths` explicitly listed "SSE reconnection" as a required test scenario
- The prompt summary listed 8 tests but the plan spec included 9 (with reconnection as the 9th)
- The plan spec was followed — reconnection test added to satisfy INFRA-08 completeness

## Self-Check

- [x] test/e2e.spec.ts exists with 9 tests
- [x] test/docker-compose.test.yml exists with `finally` image and LLM_MOCK=true
- [x] test/playwright.config.ts exists with `baseURL: http://localhost:8000`
- [x] All data-testid attributes verified present in frontend components
- [x] Task 1 commit: 6a14296
- [x] Task 2 commit: 763af60

## Self-Check: PASSED
