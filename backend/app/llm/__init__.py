"""LLM chat integration for FinAlly.

Public surface:

- ``LLMChat`` — entrypoint used by the chat API route
- ``ChatResponse`` — dataclass returned by ``LLMChat.chat``
- ``LLMResponse``, ``TradeAction``, ``WatchlistChange`` — structured output models
- ``build_portfolio_context`` — formats portfolio state for the system prompt
"""

from .client import ChatResponse, LLMChat
from .models import LLMResponse, TradeAction, WatchlistChange
from .prompts import SYSTEM_PROMPT, build_portfolio_context

__all__ = [
    "ChatResponse",
    "LLMChat",
    "LLMResponse",
    "SYSTEM_PROMPT",
    "TradeAction",
    "WatchlistChange",
    "build_portfolio_context",
]
