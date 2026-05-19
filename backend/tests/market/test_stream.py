"""Tests for the SSE streaming endpoint."""

import json
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI

from app.market.cache import PriceCache
from app.market.stream import _generate_events, create_stream_router

# The router mounts at /api/stream, route is /prices → full path /api/stream/prices
PRICES_URL = "/api/stream/prices"


def _mock_request(disconnected_after: int = 100) -> MagicMock:
    """Return a mock Request that reports disconnected after N is_disconnected() calls."""
    call_count = 0

    async def is_disconnected() -> bool:
        nonlocal call_count
        call_count += 1
        return call_count > disconnected_after

    request = MagicMock()
    request.client = None  # Suppresses IP logging
    request.is_disconnected = is_disconnected
    return request


async def _collect_events(
    cache: PriceCache,
    *,
    max_events: int = 10,
    disconnected_after: int = 20,
    interval: float = 0.01,
    heartbeat_interval: float = 0.1,
) -> list[str]:
    """Drive _generate_events and return all non-empty SSE lines."""
    request = _mock_request(disconnected_after=disconnected_after)
    lines: list[str] = []
    async for chunk in _generate_events(
        cache, request, interval=interval, heartbeat_interval=heartbeat_interval
    ):
        for line in chunk.split("\n"):
            stripped = line.strip()
            if stripped:
                lines.append(stripped)
        if len(lines) >= max_events:
            break
    return lines


@pytest.mark.asyncio
class TestGenerateEvents:
    """Unit tests for _generate_events (the core SSE generator)."""

    async def test_first_event_is_retry_directive(self):
        """The generator must open with a retry directive."""
        cache = PriceCache()
        lines = await _collect_events(cache, max_events=1)
        assert lines[0] == "retry: 1000"

    async def test_emits_data_event_when_prices_present(self):
        """With prices in cache, the generator must emit a data: event."""
        cache = PriceCache()
        cache.update("AAPL", 190.50)
        lines = await _collect_events(cache, max_events=5)
        data_lines = [ln for ln in lines if ln.startswith("data:")]
        assert data_lines, "No data: event emitted"

    async def test_data_event_contains_ticker_payload(self):
        """The data payload must be valid JSON containing the updated ticker."""
        cache = PriceCache()
        cache.update("AAPL", 190.50)
        cache.update("GOOGL", 175.25)
        lines = await _collect_events(cache, max_events=10)
        data_lines = [ln for ln in lines if ln.startswith("data:")]
        assert data_lines
        payload = json.loads(data_lines[0][len("data:"):].strip())
        assert "AAPL" in payload
        assert "GOOGL" in payload
        assert payload["AAPL"]["price"] == 190.50
        assert payload["GOOGL"]["price"] == 175.25

    async def test_data_event_has_required_fields(self):
        """Each ticker entry in the payload must carry all required fields."""
        cache = PriceCache()
        cache.update("AAPL", 190.50)
        lines = await _collect_events(cache, max_events=10)
        data_lines = [ln for ln in lines if ln.startswith("data:")]
        assert data_lines
        aapl = json.loads(data_lines[0][len("data:"):].strip())["AAPL"]
        for field in ("ticker", "price", "previous_price", "timestamp",
                      "change", "change_percent", "direction"):
            assert field in aapl, f"Missing field: {field}"
        assert aapl["ticker"] == "AAPL"
        assert aapl["direction"] in ("up", "down", "flat")

    async def test_emits_heartbeat_when_no_price_changes(self):
        """With a static (empty) cache, a keep-alive heartbeat must be emitted."""
        cache = PriceCache()  # version stays at 0 after first seen
        lines = await _collect_events(
            cache,
            max_events=3,
            disconnected_after=50,
            heartbeat_interval=0.05,  # Short so the test doesn't wait 15s
        )
        heartbeat_lines = [ln for ln in lines if ln.startswith(":")]
        assert heartbeat_lines, "No keep-alive emitted"
        assert all(ln == ": keep-alive" for ln in heartbeat_lines)

    async def test_stops_when_disconnected(self):
        """The generator must stop looping once is_disconnected() returns True."""
        cache = PriceCache()
        cache.update("AAPL", 190.50)
        # Disconnect immediately after the first check
        lines = await _collect_events(cache, disconnected_after=1, max_events=100)
        # Shouldn't have accumulated hundreds of lines; generator stops quickly
        assert len(lines) < 20

    async def test_empty_cache_no_data_events(self):
        """With an empty cache, no data: events should be emitted."""
        cache = PriceCache()
        lines = await _collect_events(
            cache,
            max_events=3,
            disconnected_after=10,
            heartbeat_interval=0.05,
        )
        data_lines = [ln for ln in lines if ln.startswith("data:")]
        assert not data_lines


@pytest.mark.asyncio
class TestCreateStreamRouter:
    """Tests for the create_stream_router factory."""

    async def test_create_stream_router_is_idempotent(self):
        """Calling create_stream_router twice must produce independent routers."""
        cache1 = PriceCache()
        cache2 = PriceCache()
        router1 = create_stream_router(cache1)
        router2 = create_stream_router(cache2)
        assert router1 is not router2

    async def test_router_registers_prices_route(self):
        """The router must register a GET route at /api/stream/prices."""
        cache = PriceCache()
        router = create_stream_router(cache)
        route_paths = [str(r.path) for r in router.routes]
        assert "/api/stream/prices" in route_paths

    async def test_endpoint_returns_event_stream_content_type(self):
        """GET /api/stream/prices must respond with text/event-stream."""
        cache = PriceCache()
        cache.update("AAPL", 190.50)
        app = FastAPI()
        app.include_router(create_stream_router(cache, heartbeat_interval=0.1))

        # Drive the generator directly to avoid ASGI streaming teardown issues.
        # The router/endpoint wiring is validated by the route_paths test above;
        # here we confirm the StreamingResponse carries the correct content type
        # by inspecting what create_stream_router returns.
        from fastapi.responses import StreamingResponse  # noqa: PLC0415
        request = MagicMock()
        request.client = None

        call_count = 0

        async def is_disconnected() -> bool:
            nonlocal call_count
            call_count += 1
            return call_count > 2

        request.is_disconnected = is_disconnected

        # Obtain the StreamingResponse from the route handler
        routes = {str(r.path): r for r in app.routes}
        handler = routes[PRICES_URL].endpoint
        response = await handler(request)
        assert isinstance(response, StreamingResponse)
        assert response.media_type == "text/event-stream"
        assert response.headers.get("cache-control") == "no-cache"
