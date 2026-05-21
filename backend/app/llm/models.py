"""Pydantic models for LLM structured outputs.

These mirror the schema in PLAN.md §9. The LLM is constrained to return JSON
matching ``LLMResponse``; the chat API layer then auto-executes any trades
and watchlist changes the response contains.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Side = Literal["buy", "sell"]
WatchlistActionName = Literal["add", "remove"]


class TradeAction(BaseModel):
    """A trade the LLM wants the system to execute on the user's behalf."""

    ticker: str
    side: Side
    quantity: float


class WatchlistChange(BaseModel):
    """A watchlist mutation the LLM wants the system to apply."""

    ticker: str
    action: WatchlistActionName


class LLMResponse(BaseModel):
    """Top-level structured response from the LLM.

    ``message`` is always present — it's the conversational text rendered in
    the chat UI. ``trades`` and ``watchlist_changes`` are optional batches the
    API layer auto-executes after the response is parsed.
    """

    message: str
    trades: list[TradeAction] = Field(default_factory=list)
    watchlist_changes: list[WatchlistChange] = Field(default_factory=list)
