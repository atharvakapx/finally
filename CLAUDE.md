# FinAlly Project - the Finance Ally

All project documentation is in the `planning` directory.

The key document is PLAN.md included in full below; the market data component has been completed and is summarized in the file `planning/MARKET_DATA_SUMMARY.md` with more details in the `planning/archive` folder. Consult these docs only when required. The remainder of the platform is still to be developed.

@planning/PLAN.md

## GSD Workflow

This project is managed with GSD (Get Shit Done). Planning artifacts live in `.planning/`.

**Current state:** `.planning/STATE.md`
**Project context:** `.planning/PROJECT.md`
**Requirements:** `.planning/REQUIREMENTS.md`
**Roadmap:** `.planning/ROADMAP.md`

### Workflow Enforcement

- Before implementing any phase, run `/gsd:discuss-phase N` to gather context
- Before executing, run `/gsd:plan-phase N` to create a PLAN.md
- Execute with `/gsd:execute-phase N`
- After execution, run `/gsd:verify-work` to confirm requirements met
- Commit planning artifacts alongside code changes

### Phase Status

| Phase | Name | Status |
|-------|------|--------|
| 1 | Backend Foundation | Not started |
| 2 | Portfolio & Watchlist APIs | Not started |
| 3 | AI Chat | Not started |
| 4 | Frontend Workstation | Not started |
| 5 | Docker & E2E | Not started |

### Key Constraints

- Market data subsystem (`backend/app/market/`) is **complete** — do not reimplement
- Use `PriceCache` and `MarketDataSource` abstractions from the existing package
- SQLite only — no Postgres, no Redis
- `uv` for Python package management — always use `uv run` or `uv add`
- Next.js static export (`output: 'export'`) — no SSR, no Next.js server
- LiteLLM → `gpt-4.1-mini` for chat — structured JSON output required
- Single Docker container on port 8000 — no multi-service docker-compose