"""System endpoints — health checks and similar."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe used by Docker / load balancers."""
    return {"status": "ok"}
