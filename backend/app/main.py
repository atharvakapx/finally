"""FinAlly backend FastAPI entrypoint."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.market import PriceCache, create_market_data_source, create_stream_router
from app.db import init_db, DEFAULT_TICKERS
from app.routers import health
from app.routers.portfolio import create_portfolio_router
from app.routers.watchlist import create_watchlist_router
from app.routers.chat import create_chat_router
from app.services.snapshots import ClientCounter, snapshot_loop

load_dotenv()  # Must be first — before any os.environ reads

logger = logging.getLogger(__name__)

# Module-scope PriceCache — no lifecycle of its own; market source lifecycle is in lifespan.
# Constructed here so router factories can be called at module scope (before lifespan fires).
price_cache = PriceCache()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: startup and shutdown hooks."""
    # --- startup ---
    init_db()
    source = create_market_data_source(price_cache)
    await source.start(list(DEFAULT_TICKERS))
    app.state.price_cache = price_cache
    app.state.market_source = source
    app.state.session_baselines = {}  # process-local; reset on restart by design (PLAN.md §6)
    app.state.sse_clients = ClientCounter()
    snapshot_task = asyncio.create_task(snapshot_loop(app), name="snapshot-loop")
    logger.info("FinAlly backend started (source=%s)", type(source).__name__)
    yield
    # --- shutdown ---
    snapshot_task.cancel()
    try:
        await snapshot_task
    except asyncio.CancelledError:
        pass
    await source.stop()
    logger.info("FinAlly backend stopped")


app = FastAPI(title="FinAlly", lifespan=lifespan)

# Register API routes BEFORE the static mount so /api/* always wins.
# Registration order determines route priority for overlapping prefixes.
app.include_router(health.router, prefix="/api")
app.include_router(create_portfolio_router(price_cache), prefix="/api")
app.include_router(create_watchlist_router(price_cache), prefix="/api")
app.include_router(create_chat_router(price_cache), prefix="/api")

# stream.py's APIRouter already has prefix="/api/stream" — do NOT add prefix="/api" again
# (that would produce /api/api/stream/prices).
app.include_router(create_stream_router(price_cache))

# StaticFiles mount LAST — catch-all for frontend assets; /api/* routes take priority
# STATIC_DIR env var is set in the Dockerfile; falls back to a local dev path
STATIC_DIR = os.environ.get("STATIC_DIR", str(Path(__file__).parent.parent / "static"))
if Path(STATIC_DIR).exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
