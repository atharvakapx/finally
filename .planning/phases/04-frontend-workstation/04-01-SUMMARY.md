---
phase: 04-frontend-workstation
plan: 01
status: complete
subsystem: frontend
tags: [nextjs, typescript, sse, watchlist, sparkline, dark-theme, tailwind]
dependency_graph:
  requires: [phase-01-backend, phase-02-portfolio-watchlist, phase-03-chat]
  provides: [frontend-foundation, sse-hook, watchlist-panel, header]
  affects: [phase-04-02, phase-05-e2e]
tech_stack:
  added: [next@16.2.6, react@19, typescript, tailwind@v4, lightweight-charts]
  patterns: [static-export, app-router, client-components, sse-eventSource]
key_files:
  created:
    - frontend/next.config.ts
    - frontend/app/globals.css
    - frontend/app/layout.tsx
    - frontend/app/page.tsx
    - frontend/app/hooks/useSSE.ts
    - frontend/app/components/Sparkline.tsx
    - frontend/app/components/WatchlistPanel.tsx
    - frontend/app/components/Header.tsx
  modified: []
decisions:
  - "Used Next.js 16.2.6 with App Router and Tailwind v4 (no tailwind.config.ts — v4 CSS-first config)"
  - "Static export (output: 'export') confirmed working with next build producing out/"
  - "Tailwind v4 uses @import 'tailwindcss' in CSS instead of directives; postcss plugin @tailwindcss/postcss"
  - "page.tsx is 'use client' to allow useState + useSSE hooks"
  - "All API calls use same-origin /api/* paths — no hardcoded localhost"
metrics:
  duration_seconds: 319
  completed_date: "2026-05-21"
  tasks_completed: 5
  files_created: 8
  files_modified: 1
---

# Phase 4 Plan 1: Frontend Bootstrap — Next.js + SSE Watchlist

**One-liner:** Next.js 16 static export with dark Bloomberg terminal theme, EventSource SSE hook (green/yellow/red status), and a live watchlist with 120-point sparklines and price flash animations.

## What Was Built

### Bootstrap (Task 1)
- Created Next.js 16.2.6 app at `frontend/` using App Router, TypeScript, Tailwind v4, ESLint
- Configured `next.config.ts` with `output: 'export'`, `trailingSlash: true`, `images.unoptimized: true`
- Installed `lightweight-charts` for future chart components
- Build produces `out/` directory successfully

### Dark Theme (Task 2)
- Replaced `globals.css` with dark terminal theme: CSS vars `--bg-primary: #0d1117`, `--bg-secondary: #1a1a2e`, `--cyan: #38BDF8`, `--blue: #3B82F6`
- `@keyframes flash-green` / `flash-red` animations for 500ms price tick highlights
- `layout.tsx` updated: metadata title "FinAlly — AI Trading Workstation", full-height body

### useSSE Hook (Task 3)
- `frontend/app/hooks/useSSE.ts`: EventSource connecting to `/api/stream/prices`
- Tracks `lastEventRef` timestamp; `status` = `'green'` (OPEN + event ≤3s ago), `'yellow'` (OPEN but stale), `'red'` (CONNECTING/CLOSED)
- 1-second `setInterval` drives green→yellow transition
- Returns `{ prices: Record<string, PriceData>, status: ConnectionStatus }`

### Sparkline + WatchlistPanel (Task 4)
- `Sparkline.tsx`: SVG polyline with min/max normalization, cyan `#38BDF8` stroke
- `WatchlistPanel.tsx`: Fetches `GET /api/watchlist` on mount; table with Ticker | Price | Session Δ% | Sparkline
- 120-point ring buffer per ticker, updated from SSE `prices` prop
- `flashClass` per ticker: `flash-green`/`flash-red` set on price change, cleared after 600ms
- All required E2E test IDs: `add-ticker-input`, `add-ticker-btn`, `remove-ticker-{TICKER}`

### Header + Page Assembly (Task 5)
- `Header.tsx`: `GET /api/portfolio` every 5s; shows total portfolio value and cash balance
- Connection status dot: `data-testid="connection-dot"`, `bg-green-400`/`bg-yellow-400`/`bg-red-500`
- `page.tsx`: assembles `Header` + `WatchlistPanel` with SSE-driven `prices` and `status`
- `npm run build` passes clean — no TypeScript errors

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 70b66da | chore(04-01): bootstrap Next.js TypeScript static export with Tailwind |
| 2 | 3f4b01d | feat(04-01): apply dark terminal theme — CSS vars, flash animations |
| 3 | 1f4637e | feat(04-01): useSSE hook — EventSource with green/yellow/red status |
| 4 | 0adff19 | feat(04-01): Sparkline + WatchlistPanel with price flash and 120-point ring buffer |
| 5 | eaae7ad | feat(04-01): Header + page assembly — live watchlist with SSE foundation |

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None — WatchlistPanel fetches from the real `/api/watchlist` endpoint, session Δ% comes from the backend, and live prices are wired from the SSE hook.

## Self-Check: PASSED

- `frontend/app/hooks/useSSE.ts` — FOUND
- `frontend/app/components/WatchlistPanel.tsx` — FOUND
- `frontend/app/components/Sparkline.tsx` — FOUND
- `frontend/app/components/Header.tsx` — FOUND
- `frontend/app/page.tsx` — FOUND
- `frontend/next.config.ts` — FOUND
- `out/` directory produced by `npm run build` — FOUND
- `data-testid="connection-dot"` in Header — FOUND
- `data-testid="add-ticker-input"` in WatchlistPanel — FOUND
- `data-testid="add-ticker-btn"` in WatchlistPanel — FOUND
- `data-testid="remove-ticker-{TICKER}"` in WatchlistPanel — FOUND
- All commits exist: 70b66da, 3f4b01d, 1f4637e, 0adff19, eaae7ad
