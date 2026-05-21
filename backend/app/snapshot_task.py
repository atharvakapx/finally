"""Background task that periodically records portfolio_snapshots.

Runs every `SNAPSHOT_INTERVAL` seconds. Only writes a snapshot when at
least one SSE client is connected — idle deployments don't accumulate
zero-information rows.

Each-trade snapshots are recorded inline by the trade endpoint, not here.
"""

from __future__ import annotations

import asyncio
import logging

from app.db import get_db
from app.db.crud import (
    get_positions,
    get_user_profile,
    insert_portfolio_snapshot,
)
from app.state import DEFAULT_USER_ID, AppState

logger = logging.getLogger(__name__)

SNAPSHOT_INTERVAL = 30.0


def _compute_total_value(state: AppState) -> float:
    """Read the current cash + position market value from the cache."""
    with get_db(state.db_path) as conn:
        profile = get_user_profile(conn, DEFAULT_USER_ID)
        positions = get_positions(conn, DEFAULT_USER_ID)
    total = float(profile["cash_balance"])
    for pos in positions:
        live = state.price_cache.get_price(pos["ticker"])
        total += float(pos["quantity"]) * float(
            live if live is not None else pos["avg_cost"]
        )
    return round(total, 4)


async def snapshot_loop(state: AppState, interval: float = SNAPSHOT_INTERVAL) -> None:
    """Long-running task: sleep `interval`, then snapshot iff a client is connected."""
    logger.info("Portfolio snapshot loop started (interval=%.1fs)", interval)
    while True:
        try:
            await asyncio.sleep(interval)
            if state.sse_clients.count == 0:
                logger.debug("Snapshot skipped — no SSE clients connected")
                continue
            total = _compute_total_value(state)
            with get_db(state.db_path) as conn:
                insert_portfolio_snapshot(conn, DEFAULT_USER_ID, total)
            logger.debug("Snapshot recorded: total_value=%.2f", total)
        except asyncio.CancelledError:
            logger.info("Portfolio snapshot loop stopped")
            raise
        except Exception:
            logger.exception("Snapshot loop iteration failed")
            # Don't break out — keep trying on the next interval.
