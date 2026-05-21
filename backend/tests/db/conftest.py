"""Shared fixtures for database tests."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.db import get_db, init_db


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Return a fresh, initialized SQLite path for each test."""
    path = tmp_path / "finally.db"
    init_db(path)
    return path


@pytest.fixture
def conn(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Yield a connection scoped to a single test."""
    with get_db(db_path) as connection:
        yield connection
