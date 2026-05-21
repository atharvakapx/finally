"""Pytest configuration and fixtures."""

import os
import tempfile

import pytest

# Set DB_PATH to a temp directory before any app modules are imported.
# This prevents init_db() from trying to create /app/db/ (which doesn't
# exist outside the Docker container) when the lifespan fires in tests.
# Tests that need their own isolated DB (e.g. test_db.py) override this
# per-test via monkeypatch.setenv + importlib.reload(app.db).
_TEST_DB_DIR = tempfile.mkdtemp(prefix="finally_test_")
os.environ.setdefault("DB_PATH", os.path.join(_TEST_DB_DIR, "test.db"))


@pytest.fixture
def event_loop_policy():
    """Use the default event loop policy for all async tests."""
    import asyncio

    return asyncio.DefaultEventLoopPolicy()
