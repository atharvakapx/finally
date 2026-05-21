"""Portfolio snapshot service: ClientCounter, record_snapshot, snapshot_loop."""

from __future__ import annotations

import asyncio
import logging
import uuid
from threading import Lock

from app.db import get_db, _now_iso
from app.market import PriceCache

logger = logging.getLogger(__name__)


class ClientCounter:
    """Thread-safe SSE client connection counter.

    Provides increment/decrement operations that clamp at 0 (never negative),
    protected by a threading Lock so SSE handler threads and the cadence
    background task can read/write concurrently without races.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._count = 0

    def increment(self) -> None:
        """Increment the client counter by 1."""
        with self._lock:
            self._count += 1

    def decrement(self) -> None:
        """Decrement the client counter by 1, clamped at 0 (never negative)."""
        with self._lock:
            self._count = max(0, self._count - 1)

    @property
    def count(self) -> int:
        """Return the current counter value under the lock."""
        with self._lock:
            return self._count


def record_snapshot(price_cache: PriceCache) -> None:
    """Compute total portfolio value and INSERT a portfolio_snapshots row.

    total = cash_balance + Σ(quantity × live_price) for all positions with
    a cache entry. Positions whose price is not in the cache are skipped
    (not counted), so the snapshot is conservative during cold-start.

    Uses two separate get_db() calls: one read (cash + positions) and one
    write (INSERT snapshot) — this is safe because record_snapshot is called
    post-commit after a trade, not inside any transaction.
    """
    with get_db() as conn:
        cash_row = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id='default'"
        ).fetchone()
        if cash_row is None:
            logger.warning("record_snapshot: no user profile found, skipping")
            return
        cash = cash_row["cash_balance"]

        rows = conn.execute(
            "SELECT ticker, quantity FROM positions "
            "WHERE user_id='default' AND quantity > 0"
        ).fetchall()

    total = cash
    for r in rows:
        price = price_cache.get_price(r["ticker"])
        if price is not None:
            total += r["quantity"] * price

    with get_db() as conn:
        conn.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
            "VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), "default", total, _now_iso()),
        )

    logger.debug("Snapshot recorded: total_value=%.2f", total)


async def snapshot_loop(app) -> None:
    """Background asyncio task: record a portfolio snapshot every 30s,
    gated on at least one SSE client being connected (SNAP-01).

    Pauses automatically when no client is connected, preventing disk
    exhaustion on idle deployments. Handles CancelledError cleanly so
    the lifespan shutdown can cancel and await this task.
    """
    try:
        while True:
            await asyncio.sleep(30)
            if app.state.sse_clients.count > 0:
                record_snapshot(app.state.price_cache)
    except asyncio.CancelledError:
        pass
