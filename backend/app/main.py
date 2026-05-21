"""FinAlly FastAPI application entry point.

Builds the FastAPI app, wires the lifespan (DB init, market data startup,
background tasks), mounts API routers, and serves the static frontend.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import chat as chat_api
from app.api import portfolio as portfolio_api
from app.api import system as system_api
from app.api import watchlist as watchlist_api
from app.db import get_db, init_db
from app.db.crud import get_positions, get_watchlist
from app.errors import register_error_handlers
from app.market import create_market_data_source, create_stream_router
from app.market.cache import PriceCache
from app.snapshot_task import snapshot_loop
from app.state import DEFAULT_USER_ID, AppState

logger = logging.getLogger(__name__)

PROD_DB_DIR = Path("/app/db")
DEV_DB_DIR = Path(__file__).resolve().parent.parent / "db"
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def resolve_db_path() -> str:
    """Use /app/db inside the container, ./db otherwise."""
    if PROD_DB_DIR.exists():
        return str(PROD_DB_DIR / "finally.db")
    DEV_DB_DIR.mkdir(parents=True, exist_ok=True)
    return str(DEV_DB_DIR / "finally.db")


def _bootstrap_active_tickers(db_path: str) -> list[str]:
    """Compute the initial active ticker set = watchlist ∪ positions."""
    with get_db(db_path) as conn:
        watchlist = {row["ticker"] for row in get_watchlist(conn, DEFAULT_USER_ID)}
        positions = {
            row["ticker"]
            for row in get_positions(conn, DEFAULT_USER_ID)
            if float(row["quantity"]) > 0
        }
    return sorted(watchlist | positions)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown: initialise DB, start market data, kick off background tasks."""
    db_path = os.environ.get("FINALLY_DB_PATH") or resolve_db_path()
    logger.info("Using SQLite database at %s", db_path)
    init_db(db_path)

    price_cache = PriceCache()
    market_source = create_market_data_source(price_cache)
    tickers = _bootstrap_active_tickers(db_path)
    await market_source.start(tickers)

    state = AppState(
        db_path=db_path,
        price_cache=price_cache,
        market_source=market_source,
    )
    app.state.app_state = state

    snapshot_task = asyncio.create_task(snapshot_loop(state), name="snapshot-loop")

    # Mount the SSE router now that we have the price cache + client tracker.
    app.include_router(create_stream_router(price_cache, client_tracker=state.sse_clients))

    try:
        yield
    finally:
        snapshot_task.cancel()
        try:
            await snapshot_task
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Snapshot task shutdown error")
        await market_source.stop()


def create_app() -> FastAPI:
    """Construct the FastAPI app — used by uvicorn and tests."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    app = FastAPI(
        title="FinAlly API",
        version="0.1.0",
        description="AI Trading Workstation backend.",
        lifespan=lifespan,
    )

    register_error_handlers(app)

    app.include_router(system_api.router)
    app.include_router(portfolio_api.router)
    app.include_router(watchlist_api.router)
    app.include_router(chat_api.router)

    _mount_static(app)
    return app


def _mount_static(app: FastAPI) -> None:
    """Serve the Next.js static export from `static/` with SPA fallback.

    The frontend may or may not be built at import time. We mount the
    directory if it exists; the SPA fallback handler 404s gracefully when
    `static/index.html` is missing so that the API still works for tests.
    """
    if STATIC_DIR.exists():
        # Mount nested asset directories that Next.js produces.
        assets_dir = STATIC_DIR / "_next"
        if assets_dir.exists():
            app.mount("/_next", StaticFiles(directory=str(assets_dir)), name="next-assets")

    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    async def spa_fallback(full_path: str, request: Request):  # noqa: ANN202
        # API routes are handled by their own routers — this catch-all only
        # runs for non-API paths.
        if full_path.startswith("api/"):
            return JSONResponse(
                status_code=404,
                content={"error": "not_found", "message": f"No route for /{full_path}"},
            )

        target: Path | None = None
        if full_path:
            candidate = STATIC_DIR / full_path
            if candidate.is_file():
                target = candidate

        if target is None:
            target = STATIC_DIR / "index.html"

        if not target.exists():
            return JSONResponse(
                status_code=404,
                content={
                    "error": "frontend_not_built",
                    "message": "Static frontend assets are not present. "
                    "Build the frontend or use the API directly.",
                },
            )
        return FileResponse(target)


app = create_app()
