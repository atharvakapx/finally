"""Database layer for FinAlly.

Public surface:

- :func:`init_db` — create the SQLite file, apply schema, seed defaults.
- :func:`get_db` — context manager yielding a per-request connection.

CRUD helpers live in :mod:`app.db.crud` and operate on an open connection.
"""

from app.db.connection import get_db
from app.db.schema import (
    DEFAULT_CASH_BALANCE,
    DEFAULT_USER_ID,
    DEFAULT_WATCHLIST,
    init_db,
)

__all__ = [
    "DEFAULT_CASH_BALANCE",
    "DEFAULT_USER_ID",
    "DEFAULT_WATCHLIST",
    "get_db",
    "init_db",
]
