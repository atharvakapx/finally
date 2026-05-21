"""FastAPI route modules.

Each submodule exposes a `router` object that is mounted by `app.main`.
"""

from app.api import chat, portfolio, system, watchlist

__all__ = ["chat", "portfolio", "system", "watchlist"]
