"""Health check router for FinAlly backend."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])


@router.get("/health")
async def health_check() -> JSONResponse:
    """Return 200 OK to confirm the backend is running."""
    return JSONResponse({"status": "ok"})
