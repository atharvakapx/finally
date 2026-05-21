"""Uniform error contract for FinAlly API.

All non-2xx responses share the shape:
    {"error": "<machine_code>", "message": "<human readable>"}

See PLAN.md §8 for the canonical error code table.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class APIError(HTTPException):
    """HTTPException carrying a machine-readable error code.

    Raise from route handlers. The exception handler converts it into the
    standard `{"error": ..., "message": ...}` shape.
    """

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(status_code=status_code, detail={"error": code, "message": message})
        self.code = code
        self.message = message


def _error_payload(code: str, message: str) -> dict[str, Any]:
    return {"error": code, "message": message}


async def api_error_handler(_request: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(exc.code, exc.message),
    )


async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    """Translate generic HTTPExceptions into the uniform error shape."""
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    code = {
        status.HTTP_404_NOT_FOUND: "not_found",
        status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
        status.HTTP_400_BAD_REQUEST: "bad_request",
    }.get(exc.status_code, "http_error")
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(status_code=exc.status_code, content=_error_payload(code, message))


async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Convert pydantic validation errors into the standard shape."""
    # Pick the first validation error for the message; full detail is in logs.
    errors = exc.errors()
    if errors:
        first = errors[0]
        loc = ".".join(str(p) for p in first.get("loc", ()) if p not in ("body",))
        message = f"{loc}: {first.get('msg', 'invalid')}" if loc else first.get("msg", "invalid")
    else:
        message = "invalid request"
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=_error_payload("invalid_request", message),
    )


async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_payload("internal_error", "An unexpected error occurred."),
    )


def register_error_handlers(app: FastAPI) -> None:
    """Wire all error handlers into a FastAPI app."""
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)


# --- Convenience constructors for common errors ---


def invalid_ticker(ticker: str) -> APIError:
    return APIError(
        status.HTTP_400_BAD_REQUEST,
        "invalid_ticker",
        f"Ticker '{ticker}' is invalid. Must be 1-5 uppercase letters.",
    )


def watchlist_full(cap: int) -> APIError:
    return APIError(
        status.HTTP_400_BAD_REQUEST,
        "watchlist_full",
        f"Watchlist is already at the {cap}-ticker cap.",
    )


def ticker_held(ticker: str) -> APIError:
    return APIError(
        status.HTTP_400_BAD_REQUEST,
        "ticker_held",
        f"Cannot remove {ticker}: a position is still held.",
    )


def invalid_side(side: str) -> APIError:
    return APIError(
        status.HTTP_400_BAD_REQUEST,
        "invalid_side",
        f"Side '{side}' is invalid. Must be 'buy' or 'sell'.",
    )


def invalid_quantity(message: str = "Quantity must be a positive number.") -> APIError:
    return APIError(status.HTTP_400_BAD_REQUEST, "invalid_quantity", message)


def insufficient_cash(needed: float, have: float) -> APIError:
    return APIError(
        status.HTTP_400_BAD_REQUEST,
        "insufficient_cash",
        f"Need ${needed:.2f}, have ${have:.2f}",
    )


def insufficient_shares(needed: float, have: float, ticker: str) -> APIError:
    return APIError(
        status.HTTP_400_BAD_REQUEST,
        "insufficient_shares",
        f"Need {needed:.4f} shares of {ticker}, have {have:.4f}",
    )


def unknown_ticker(ticker: str) -> APIError:
    return APIError(
        status.HTTP_404_NOT_FOUND,
        "unknown_ticker",
        f"Ticker '{ticker}' is not recognized by the market data provider.",
    )


def not_found(resource: str) -> APIError:
    return APIError(status.HTTP_404_NOT_FOUND, "not_found", f"{resource} not found.")


def market_data_unavailable(ticker: str) -> APIError:
    return APIError(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "market_data_unavailable",
        f"No live price available for {ticker}.",
    )
