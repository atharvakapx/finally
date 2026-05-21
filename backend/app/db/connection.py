"""Thread-safe SQLite connection management.

The backend uses a connection-per-request pattern. `get_db` is a context
manager that yields a fresh connection with `check_same_thread=False` set so
that the connection can travel across the async/threadpool boundary that
FastAPI uses for sync dependencies.

The context manager commits on a clean exit and rolls back on an exception.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager


def _connect(db_path: str | os.PathLike[str]) -> sqlite3.Connection:
    conn = sqlite3.connect(
        str(db_path),
        check_same_thread=False,
        isolation_level="DEFERRED",
        timeout=30.0,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db(db_path: str | os.PathLike[str]) -> Iterator[sqlite3.Connection]:
    """Yield a SQLite connection scoped to a single unit of work.

    Commits on clean exit, rolls back if the block raises. Always closes the
    connection. Callers that need an immediate write lock (e.g. trade
    execution) should issue `BEGIN IMMEDIATE` themselves inside the block.
    """
    conn = _connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
