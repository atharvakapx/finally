"""Shared input validation helpers."""

from __future__ import annotations

import re

TICKER_PATTERN = re.compile(r"^[A-Z]{1,5}$")
WATCHLIST_CAP = 50


def normalize_ticker(raw: str | None) -> str | None:
    """Strip + uppercase a ticker string; returns None if input is empty."""
    if raw is None:
        return None
    candidate = raw.strip().upper()
    return candidate or None


def is_valid_ticker(ticker: str) -> bool:
    """Return True iff ticker matches the canonical format."""
    return bool(TICKER_PATTERN.match(ticker))
