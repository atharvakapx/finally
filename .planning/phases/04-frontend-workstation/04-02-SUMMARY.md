---
phase: 04-frontend-workstation
plan: 02
status: complete
subsystem: frontend
tags: [react, typescript, lightweight-charts, trading-ui, sse, chat]
dependency_graph:
  requires: ["04-01"]
  provides: ["complete-terminal-ui"]
  affects: ["05-docker-e2e"]
tech_stack:
  added: ["lightweight-charts@5.2.0"]
  patterns: ["ring-buffer-SSE", "custom-event-coordination", "css-flexbox-treemap"]
key_files:
  created:
    - frontend/app/components/MainChart.tsx
    - frontend/app/components/PortfolioHeatmap.tsx
    - frontend/app/components/PnLChart.tsx
    - frontend/app/components/PositionsTable.tsx
    - frontend/app/components/TradeBar.tsx
    - frontend/app/components/ChatPanel.tsx
  modified:
    - frontend/app/page.tsx
    - frontend/app/hooks/useSSE.ts
decisions:
  - "useSSE extended with optional onPrice callback to update ring buffer without extra re-renders"
  - "portfolio-updated CustomEvent used to coordinate TradeBar->Heatmap/Table/PnLChart refresh without prop drilling"
  - "lightweight-charts v5 addSeries(LineSeries/AreaSeries) API used (not deprecated addLineSeries)"
metrics:
  duration: 262s
  completed: "2026-05-21"
  tasks_completed: 5
  files_changed: 8
---

# Phase 4 Plan 2: Complete Bloomberg Terminal UI Summary

Six new components plus full layout assembly; all API endpoints wired, all E2E testids present, npm run build produces static export with zero TypeScript errors.

## What Was Built

### Task 1 — MainChart (894f8b4)
`frontend/app/components/MainChart.tsx` — lightweight-charts v5 `createChart` + `LineSeries` rendering the SSE price ring buffer. Dark theme (background `#0d1117`, grid `#30363d`, text `#8b949e`). Receives `ticker` and `priceHistory: number[]` from page.tsx. Handles window resize. Shows ticker + current price in header; shows placeholder when no ticker.

### Task 2 — Portfolio Components (4e60b5e)
- `PortfolioHeatmap.tsx` — CSS flexbox treemap; each position box sized by `(position_value / total_value) * 100%`, colored by `hsl(hue, saturation, 30%)` formula. Polls `/api/portfolio` every 3s. Refreshes on `portfolio-updated` event. `data-testid="heatmap"`.
- `PnLChart.tsx` — lightweight-charts `AreaSeries` with cyan gradient. Fetches `/api/portfolio/history`, polls every 30s, refreshes on `portfolio-updated` event.
- `PositionsTable.tsx` — Table with Ticker/Qty/Avg Cost/Current/Unrealized P&L/Change% columns. P&L/% colored green/red. Polls every 3s.

### Task 3 — TradeBar (29ba241)
`frontend/app/components/TradeBar.tsx` — Buy/Sell form with controlled inputs. Dispatches `portfolio-updated` CustomEvent on success to trigger portfolio refresh. Syncs ticker from selectedTicker prop. All E2E testids present.

### Task 4 — ChatPanel (b1b58a2)
`frontend/app/components/ChatPanel.tsx` — Full chat UI: message thread, loading indicator, POST `/api/chat`, inline confirmation badges for AI-executed trades and watchlist changes. Collapsible via toggle. Auto-scrolls to bottom. All E2E testids present.

### Task 5 — Full Layout Assembly (41a6e88)
`frontend/app/page.tsx` — Complete terminal layout: Header (full width), 320px WatchlistPanel left, main area center (MainChart 280px + Heatmap/PnLChart 200px + Positions + TradeBar), 320px ChatPanel right. `priceHistory` ring buffer (120 pts/ticker) maintained in page-level state, updated via `useSSE(onPrice)` callback.

`useSSE.ts` extended with optional `onPrice?: (data: PriceData) => void` callback stored in a ref (avoids stale closures) — fired on every SSE message without causing extra price-state re-renders in ring buffer updates.

## Deviations from Plan

None — plan executed exactly as written. The `useSSE` callback extension was additive (no breaking change to existing signature).

## Self-Check: PASSED

All 7 files created/modified verified on disk. All 5 commits verified in git history. Build produces `out/` with no TypeScript errors.
