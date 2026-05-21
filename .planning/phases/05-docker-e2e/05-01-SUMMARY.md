---
phase: 05-docker-e2e
plan: 01
subsystem: docker-packaging
status: complete
tags: [docker, deployment, scripts, static-files]
dependency_graph:
  requires: [backend/app/main.py, frontend/package.json, backend/pyproject.toml, backend/uv.lock]
  provides: [Dockerfile, scripts/start_mac.sh, scripts/stop_mac.sh, scripts/start_windows.ps1, scripts/stop_windows.ps1, .env.example, db/.gitkeep]
  affects: [backend/app/main.py]
tech_stack:
  added: [node:20-slim, python:3.12-slim, uv, uvicorn]
  patterns: [multi-stage-docker-build, static-file-serving, bind-mount-volume]
key_files:
  created:
    - Dockerfile
    - scripts/start_mac.sh
    - scripts/stop_mac.sh
    - scripts/start_windows.ps1
    - scripts/stop_windows.ps1
    - .env.example
    - db/.gitkeep
  modified:
    - backend/app/main.py
    - .gitignore
decisions:
  - Use STATIC_DIR env var with Path.exists() guard in main.py so app runs without static files in dev mode
  - Include uv.lock in Dockerfile COPY to enable --frozen deterministic installs
  - Add db/.gitkeep so the db/ directory is tracked; db/finally.db remains gitignored
metrics:
  completed_date: "2026-05-21"
  tasks_completed: 3
  files_created: 7
  files_modified: 2
---

# Phase 05 Plan 01: Docker Packaging Summary

Multi-stage Dockerfile with Node 20 frontend build and Python 3.12 runtime; idempotent start/stop scripts for Mac and Windows; environment variable documentation via .env.example.

## What Was Built

**Task 1 — Multi-stage Dockerfile + main.py update (b0906c1)**

Created `Dockerfile` at repo root with two build stages:
- Stage 1 (`node:20-slim AS frontend-builder`): runs `npm ci` then `npm run build` to produce the Next.js static export at `frontend/out/`
- Stage 2 (`python:3.12-slim AS app`): installs uv, runs `uv sync --frozen --no-dev` from `backend/uv.lock`, copies backend sources and the frontend `out/` into `/app/backend/static`, sets `STATIC_DIR=/app/backend/static`, and runs uvicorn

Updated `backend/app/main.py` to replace the hardcoded `"static"` directory with a dynamic `STATIC_DIR` env-var lookup that falls back to `Path(__file__).parent.parent / "static"` for local dev. The mount is guarded with `Path(STATIC_DIR).exists()` so the server starts cleanly even when the static directory is absent.

**Task 2 — Start/stop scripts (e7cd13a)**

Created four scripts:
- `scripts/start_mac.sh`: builds Docker image if not present (or `--build` forced), removes any existing container, and runs with `-v $PWD/db:/app/db -p 8000:8000 --env-file .env`
- `scripts/stop_mac.sh`: removes the container, leaves the db volume intact
- `scripts/start_windows.ps1`: PowerShell equivalent with `-Build` switch
- `scripts/stop_windows.ps1`: PowerShell stop script

Both shell scripts are marked executable (`chmod +x`).

**Task 3 — .env.example, db/.gitkeep, .gitignore (7e29f8c)**

- `.env.example` documents all three env vars (`OPENAI_API_KEY`, `MASSIVE_API_KEY`, `LLM_MOCK=false`) with comments explaining each
- `db/.gitkeep` ensures the `db/` directory exists in the repo so bind-mount works on a fresh clone
- `.gitignore` updated to exclude `db/finally.db` (runtime SQLite) and `frontend/out/` (build output)

## Deviations from Plan

None — plan executed exactly as written.

The plan showed a redundant `COPY --from=frontend-builder` line (copying to `/app/static` and then again to `/app/backend/static`). The Dockerfile was written with only the single necessary copy to `/app/backend/static` matching the `STATIC_DIR` env var.

## Self-Check: PASSED

- Dockerfile: FOUND — two FROM stages (node:20-slim, python:3.12-slim)
- scripts/start_mac.sh: FOUND — executable
- scripts/stop_mac.sh: FOUND — executable
- scripts/start_windows.ps1: FOUND
- scripts/stop_windows.ps1: FOUND
- .env.example: FOUND — contains OPENAI_API_KEY, MASSIVE_API_KEY, LLM_MOCK
- db/.gitkeep: FOUND
- backend/app/main.py: FOUND — STATIC_DIR dynamic mount with exists() guard
- Commits: b0906c1, e7cd13a, 7e29f8c — all present in git log

## Known Stubs

None.

## Threat Flags

None — this plan only adds deployment packaging files and a conditional static file mount. No new network endpoints, auth paths, or trust boundaries introduced.
