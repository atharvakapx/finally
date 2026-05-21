"""Chat router for FinAlly backend (stub — implemented in Phase 3)."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def create_chat_router() -> APIRouter:
    """Router factory. Phase 3 adds LLM client and DB injection."""
    router = APIRouter(prefix="/chat", tags=["chat"])

    @router.post("")
    async def send_message() -> JSONResponse:
        return JSONResponse({"error": "not_implemented", "message": "Coming in Phase 3"}, status_code=501)

    return router
