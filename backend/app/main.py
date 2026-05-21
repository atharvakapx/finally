"""FinAlly backend FastAPI entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routers import health

load_dotenv()  # Must be first — before any os.environ reads

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: startup/shutdown hooks.

    Plan 03 adds PriceCache + MarketDataSource + stream router here.
    """
    # --- startup ---
    init_db()
    logger.info("FinAlly backend starting")
    yield
    # --- shutdown ---
    logger.info("FinAlly backend stopped")


app = FastAPI(title="FinAlly", lifespan=lifespan)

# Register API routes BEFORE the static mount so /api/* always wins
app.include_router(health.router, prefix="/api")

# StaticFiles mount LAST — catch-all for frontend assets
app.mount("/", StaticFiles(directory="static", html=True), name="static")
