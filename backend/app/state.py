"""Application state container.

Holds the shared singletons used across routes: the PriceCache, the active
MarketDataSource, the SQLite database path, the SSE client tracker, and a
reference to the snapshot task (if running).

A single instance is created during FastAPI startup and attached to the
`app.state` namespace. Routes resolve it via the `get_state` dependency.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from fastapi import Request

if TYPE_CHECKING:
    from app.market import MarketDataSource, PriceCache

DEFAULT_USER_ID = "default"


class SSEClientTracker:
    """Thread-safe counter of currently connected SSE clients."""

    def __init__(self) -> None:
        self._count = 0
        self._lock = threading.Lock()

    def increment(self) -> int:
        with self._lock:
            self._count += 1
            return self._count

    def decrement(self) -> int:
        with self._lock:
            self._count = max(0, self._count - 1)
            return self._count

    @property
    def count(self) -> int:
        with self._lock:
            return self._count


@dataclass
class AppState:
    """Container for application-wide singletons."""

    db_path: str
    price_cache: "PriceCache"
    market_source: "MarketDataSource"
    sse_clients: SSEClientTracker = field(default_factory=SSEClientTracker)


def get_state(request: Request) -> AppState:
    """FastAPI dependency that returns the shared AppState."""
    return request.app.state.app_state  # type: ignore[no-any-return]
