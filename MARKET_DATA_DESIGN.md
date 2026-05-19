# Market Data Backend Design

## Overview

This document describes the complete market data backend for **finally** — a real-time trading and portfolio management platform. The backend is composed of three integrated layers:

1. **Internal Market Data API** — REST + WebSocket service exposing quotes, OHLCV bars, order books, and tickers to frontend clients and other backend services.
2. **Market Data Simulator** — Deterministic and stochastic price generator for local development, testing, and backtesting without hitting live data sources.
3. **Massive API Integration** — High-throughput ingestion pipeline that normalises data from external market data providers (Alpaca, Polygon.io, etc.) and publishes it to the internal bus.

---

## Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                          Client Layer                              │
│   Browser / Mobile App / Internal Services                        │
└───────────────┬────────────────────────────────┬───────────────────┘
                │ REST                           │ WebSocket
                ▼                               ▼
┌───────────────────────────────────────────────────────────────────┐
│                    Internal Market Data API                        │
│          (FastAPI  ·  /v1/quotes  ·  /v1/bars  ·  ws://)          │
└──────────────────────────┬────────────────────────────────────────┘
                           │ reads / subscribes
            ┌──────────────┴─────────────────────┐
            ▼                                     ▼
┌───────────────────────┐           ┌─────────────────────────────┐
│   Redis (tick cache)  │           │   TimescaleDB (OHLCV, ticks)│
└───────────────────────┘           └─────────────────────────────┘
            ▲                                     ▲
            │ publishes                           │ writes
┌───────────────────────────────────────────────────────────────────┐
│                        Ingestion Layer                             │
│   Massive API Connector  ◄──or──►  Market Data Simulator          │
│   (Alpaca / Polygon.io)                                           │
└───────────────────────────────────────────────────────────────────┘
```

---

## 1. Data Models

All three layers share a common set of Pydantic models.

```python
# market_data/models.py
from __future__ import annotations
from decimal import Decimal
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class AssetClass(str, Enum):
    EQUITY = "equity"
    CRYPTO = "crypto"
    FX = "fx"
    OPTION = "option"


class Quote(BaseModel):
    symbol: str
    ask: Decimal
    bid: Decimal
    ask_size: Decimal
    bid_size: Decimal
    timestamp: datetime
    source: str = "live"

    @property
    def mid(self) -> Decimal:
        return (self.ask + self.bid) / 2

    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid


class Bar(BaseModel):
    symbol: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    vwap: Optional[Decimal] = None
    timestamp: datetime
    resolution: str  # "1m" | "5m" | "1h" | "1d"


class Tick(BaseModel):
    symbol: str
    price: Decimal
    size: Decimal
    timestamp: datetime
    conditions: list[str] = Field(default_factory=list)


class OrderBookLevel(BaseModel):
    price: Decimal
    size: Decimal


class OrderBook(BaseModel):
    symbol: str
    bids: list[OrderBookLevel]  # sorted descending by price
    asks: list[OrderBookLevel]  # sorted ascending by price
    timestamp: datetime


class SubscriptionRequest(BaseModel):
    symbols: list[str]
    channels: list[str]  # "quotes" | "trades" | "bars.1m"
```

---

## 2. Internal Market Data API

### 2.1 Application Bootstrap

```python
# market_data/api/app.py
from fastapi import FastAPI
from market_data.api.routes import router
from market_data.api.websocket import ws_router
from market_data.store.redis import init_redis
from market_data.store.timescale import init_db

app = FastAPI(title="Finally Market Data API", version="1.0.0")

app.include_router(router, prefix="/v1")
app.include_router(ws_router)


@app.on_event("startup")
async def startup():
    await init_redis()
    await init_db()
```

### 2.2 REST Endpoints

```python
# market_data/api/routes.py
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime
from typing import Optional
from market_data.models import Quote, Bar, OrderBook
from market_data.store.redis import get_latest_quote
from market_data.store.timescale import query_bars, query_latest_bar

router = APIRouter()


@router.get("/quotes/{symbol}", response_model=Quote)
async def get_quote(symbol: str):
    """Return the latest NBBO quote for a symbol."""
    quote = await get_latest_quote(symbol.upper())
    if quote is None:
        raise HTTPException(status_code=404, detail=f"No quote found for {symbol}")
    return quote


@router.get("/quotes", response_model=list[Quote])
async def get_quotes(symbols: list[str] = Query(...)):
    """Batch-fetch latest quotes for multiple symbols."""
    results = []
    for sym in symbols:
        q = await get_latest_quote(sym.upper())
        if q:
            results.append(q)
    return results


@router.get("/bars/{symbol}", response_model=list[Bar])
async def get_bars(
    symbol: str,
    resolution: str = "1d",
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = Query(default=100, le=5000),
):
    """
    Return OHLCV bars for a symbol.

    resolution: 1m | 5m | 15m | 1h | 4h | 1d | 1w
    """
    bars = await query_bars(
        symbol=symbol.upper(),
        resolution=resolution,
        start=start,
        end=end,
        limit=limit,
    )
    return bars


@router.get("/bars/{symbol}/latest", response_model=Bar)
async def get_latest_bar(symbol: str, resolution: str = "1d"):
    bar = await query_latest_bar(symbol.upper(), resolution)
    if bar is None:
        raise HTTPException(status_code=404, detail="No bar data found")
    return bar
```

**Example calls:**

```bash
# Latest quote
GET /v1/quotes/AAPL

# Batch quotes
GET /v1/quotes?symbols=AAPL&symbols=TSLA&symbols=BTC-USD

# 100 daily bars for AAPL
GET /v1/bars/AAPL?resolution=1d&limit=100

# Minute bars in a time window
GET /v1/bars/AAPL?resolution=1m&start=2026-05-19T09:30:00Z&end=2026-05-19T16:00:00Z
```

**Example response — Quote:**

```json
{
  "symbol": "AAPL",
  "ask": "195.42",
  "bid": "195.40",
  "ask_size": "300",
  "bid_size": "500",
  "timestamp": "2026-05-19T14:32:01.123Z",
  "source": "alpaca"
}
```

### 2.3 WebSocket Real-Time Feed

```python
# market_data/api/websocket.py
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from market_data.bus import MarketBus
from market_data.models import SubscriptionRequest

ws_router = APIRouter()
bus = MarketBus()


@ws_router.websocket("/ws/market")
async def market_websocket(websocket: WebSocket):
    await websocket.accept()

    # Step 1: receive subscription payload
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        req = SubscriptionRequest.model_validate_json(raw)
    except Exception:
        await websocket.close(code=1008)
        return

    queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
    token = bus.subscribe(req.symbols, req.channels, queue)

    try:
        while True:
            event = await queue.get()
            await websocket.send_text(event.model_dump_json())
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(token)
```

**WebSocket protocol — client side:**

```javascript
// Subscribe to real-time quotes and 1-minute bars for AAPL + BTC-USD
const ws = new WebSocket("wss://api.finally.app/ws/market");

ws.onopen = () => {
  ws.send(JSON.stringify({
    symbols: ["AAPL", "BTC-USD"],
    channels: ["quotes", "bars.1m"]
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // data.type === "quote" | "bar" | "tick"
  console.log(data);
};
```

### 2.4 In-Memory Pub/Sub Bus

The bus decouples the ingestion layer from WebSocket connections and REST caches.

```python
# market_data/bus.py
import asyncio
from dataclasses import dataclass, field
from typing import Union
from market_data.models import Quote, Bar, Tick
import uuid

MarketEvent = Union[Quote, Bar, Tick]


@dataclass
class Subscription:
    token: str
    symbols: set[str]
    channels: set[str]
    queue: asyncio.Queue


class MarketBus:
    """Thread-safe, async pub/sub bus for market events."""

    def __init__(self):
        self._subs: dict[str, Subscription] = {}

    def subscribe(
        self,
        symbols: list[str],
        channels: list[str],
        queue: asyncio.Queue,
    ) -> str:
        token = str(uuid.uuid4())
        self._subs[token] = Subscription(
            token=token,
            symbols={s.upper() for s in symbols},
            channels=set(channels),
            queue=queue,
        )
        return token

    def unsubscribe(self, token: str) -> None:
        self._subs.pop(token, None)

    async def publish(self, event: MarketEvent) -> None:
        channel = _event_channel(event)
        for sub in self._subs.values():
            if event.symbol in sub.symbols and channel in sub.channels:
                try:
                    sub.queue.put_nowait(event)
                except asyncio.QueueFull:
                    pass  # drop stale subscriber rather than block


def _event_channel(event: MarketEvent) -> str:
    if isinstance(event, Quote):
        return "quotes"
    if isinstance(event, Tick):
        return "trades"
    if isinstance(event, Bar):
        return f"bars.{event.resolution}"
    return "unknown"
```

### 2.5 Redis Cache Layer

```python
# market_data/store/redis.py
import json
from datetime import timedelta
from typing import Optional
import redis.asyncio as aioredis
from market_data.models import Quote

_redis: aioredis.Redis = None
QUOTE_TTL = timedelta(seconds=30)


async def init_redis(url: str = "redis://localhost:6379"):
    global _redis
    _redis = await aioredis.from_url(url, decode_responses=True)


async def set_quote(quote: Quote) -> None:
    key = f"quote:{quote.symbol}"
    await _redis.set(key, quote.model_dump_json(), ex=int(QUOTE_TTL.total_seconds()))


async def get_latest_quote(symbol: str) -> Optional[Quote]:
    key = f"quote:{symbol}"
    raw = await _redis.get(key)
    if raw is None:
        return None
    return Quote.model_validate_json(raw)
```

### 2.6 TimescaleDB Schema and Query Layer

```sql
-- migrations/001_market_data.sql

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE ticks (
    symbol      TEXT        NOT NULL,
    price       NUMERIC     NOT NULL,
    size        NUMERIC     NOT NULL,
    conditions  TEXT[]      NOT NULL DEFAULT '{}',
    ts          TIMESTAMPTZ NOT NULL
);

SELECT create_hypertable('ticks', 'ts');
CREATE INDEX ON ticks (symbol, ts DESC);

CREATE TABLE bars (
    symbol      TEXT        NOT NULL,
    resolution  TEXT        NOT NULL,
    open        NUMERIC     NOT NULL,
    high        NUMERIC     NOT NULL,
    low         NUMERIC     NOT NULL,
    close       NUMERIC     NOT NULL,
    volume      NUMERIC     NOT NULL,
    vwap        NUMERIC,
    ts          TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (symbol, resolution, ts)
);

SELECT create_hypertable('bars', 'ts');
CREATE INDEX ON bars (symbol, resolution, ts DESC);
```

```python
# market_data/store/timescale.py
from datetime import datetime
from typing import Optional
import asyncpg
from market_data.models import Bar, Tick

_pool: asyncpg.Pool = None


async def init_db(dsn: str = "postgresql://localhost/finally"):
    global _pool
    _pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)


async def write_tick(tick: Tick) -> None:
    await _pool.execute(
        """
        INSERT INTO ticks (symbol, price, size, conditions, ts)
        VALUES ($1, $2, $3, $4, $5)
        """,
        tick.symbol, tick.price, tick.size, tick.conditions, tick.timestamp,
    )


async def write_bar(bar: Bar) -> None:
    await _pool.execute(
        """
        INSERT INTO bars (symbol, resolution, open, high, low, close, volume, vwap, ts)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (symbol, resolution, ts) DO UPDATE
          SET open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
              close=EXCLUDED.close, volume=EXCLUDED.volume, vwap=EXCLUDED.vwap
        """,
        bar.symbol, bar.resolution, bar.open, bar.high, bar.low,
        bar.close, bar.volume, bar.vwap, bar.timestamp,
    )


async def query_bars(
    symbol: str,
    resolution: str,
    start: Optional[datetime],
    end: Optional[datetime],
    limit: int = 100,
) -> list[Bar]:
    rows = await _pool.fetch(
        """
        SELECT symbol, resolution, open, high, low, close, volume, vwap, ts
        FROM bars
        WHERE symbol=$1 AND resolution=$2
          AND ($3::timestamptz IS NULL OR ts >= $3)
          AND ($4::timestamptz IS NULL OR ts <= $4)
        ORDER BY ts DESC
        LIMIT $5
        """,
        symbol, resolution, start, end, limit,
    )
    return [_row_to_bar(r) for r in reversed(rows)]


async def query_latest_bar(symbol: str, resolution: str) -> Optional[Bar]:
    row = await _pool.fetchrow(
        "SELECT * FROM bars WHERE symbol=$1 AND resolution=$2 ORDER BY ts DESC LIMIT 1",
        symbol, resolution,
    )
    return _row_to_bar(row) if row else None


def _row_to_bar(row) -> Bar:
    return Bar(
        symbol=row["symbol"],
        resolution=row["resolution"],
        open=row["open"],
        high=row["high"],
        low=row["low"],
        close=row["close"],
        volume=row["volume"],
        vwap=row["vwap"],
        timestamp=row["ts"],
    )
```

---

## 3. Market Data Simulator

The simulator runs in place of the Massive API connector during local development and CI. It produces statistically plausible price series using Geometric Brownian Motion (GBM) and publishes events to the same `MarketBus`.

### 3.1 GBM Price Engine

```python
# market_data/simulator/engine.py
import math
import random
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class GBMConfig:
    symbol: str
    initial_price: float
    annual_drift: float = 0.08        # 8% expected annual return
    annual_volatility: float = 0.25   # 25% annual volatility
    tick_interval_s: float = 0.5      # new tick every 500 ms


class GBMEngine:
    """
    Geometric Brownian Motion price simulator.

    dS = S * (mu*dt + sigma*sqrt(dt)*Z)  where Z ~ N(0,1)
    """

    def __init__(self, config: GBMConfig):
        self.config = config
        self._price = config.initial_price

    def next_price(self) -> Decimal:
        dt = self.config.tick_interval_s / (252 * 6.5 * 3600)  # fraction of trading year
        mu = self.config.annual_drift
        sigma = self.config.annual_volatility
        z = random.gauss(0, 1)
        drift = (mu - 0.5 * sigma ** 2) * dt
        diffusion = sigma * math.sqrt(dt) * z
        self._price *= math.exp(drift + diffusion)
        return Decimal(str(round(self._price, 2)))

    @property
    def current_price(self) -> Decimal:
        return Decimal(str(round(self._price, 2)))
```

### 3.2 Quote and Bar Generators

```python
# market_data/simulator/generators.py
from datetime import datetime, timezone
from decimal import Decimal
import random
from market_data.models import Quote, Bar, Tick
from market_data.simulator.engine import GBMEngine, GBMConfig


class QuoteGenerator:
    """Wraps a GBMEngine and adds a bid/ask spread."""

    def __init__(self, config: GBMConfig, spread_bps: float = 5.0):
        self._engine = GBMEngine(config)
        self._spread_bps = spread_bps
        self._symbol = config.symbol

    def next_quote(self) -> Quote:
        mid = self._engine.next_price()
        half_spread = mid * Decimal(str(self._spread_bps / 10000 / 2))
        ask = (mid + half_spread).quantize(Decimal("0.01"))
        bid = (mid - half_spread).quantize(Decimal("0.01"))
        return Quote(
            symbol=self._symbol,
            ask=ask,
            bid=bid,
            ask_size=Decimal(random.randint(100, 1000)),
            bid_size=Decimal(random.randint(100, 1000)),
            timestamp=datetime.now(timezone.utc),
            source="simulator",
        )


class BarAggregator:
    """
    Accumulates ticks within a window and emits a Bar when the window closes.
    Supports multiple resolutions simultaneously.
    """

    RESOLUTIONS = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "1h": 3600,
    }

    def __init__(self, symbol: str):
        self._symbol = symbol
        self._buckets: dict[str, dict] = {
            r: self._empty_bucket() for r in self.RESOLUTIONS
        }

    def feed(self, tick: Tick) -> list[Bar]:
        """Feed a tick; returns any bars that closed."""
        closed: list[Bar] = []
        for resolution, window_s in self.RESOLUTIONS.items():
            bucket = self._buckets[resolution]
            ts = tick.timestamp.timestamp()
            window_start = (ts // window_s) * window_s

            if bucket["window_start"] is None:
                bucket["window_start"] = window_start
                bucket["open"] = tick.price

            if window_start != bucket["window_start"]:
                # window closed — emit bar
                closed.append(Bar(
                    symbol=self._symbol,
                    open=bucket["open"],
                    high=bucket["high"],
                    low=bucket["low"],
                    close=bucket["last"],
                    volume=bucket["volume"],
                    vwap=self._calc_vwap(bucket),
                    timestamp=datetime.fromtimestamp(
                        bucket["window_start"], tz=timezone.utc
                    ),
                    resolution=resolution,
                ))
                bucket = self._empty_bucket()
                bucket["window_start"] = window_start
                bucket["open"] = tick.price
                self._buckets[resolution] = bucket

            bucket["high"] = max(bucket["high"], tick.price)
            bucket["low"] = min(bucket["low"] if bucket["low"] else tick.price, tick.price)
            bucket["last"] = tick.price
            bucket["volume"] += tick.size
            bucket["cum_pv"] += tick.price * tick.size

        return closed

    @staticmethod
    def _empty_bucket() -> dict:
        return {
            "window_start": None,
            "open": None,
            "high": Decimal(0),
            "low": None,
            "last": None,
            "volume": Decimal(0),
            "cum_pv": Decimal(0),
        }

    @staticmethod
    def _calc_vwap(bucket: dict) -> Decimal | None:
        if bucket["volume"] == 0:
            return None
        return (bucket["cum_pv"] / bucket["volume"]).quantize(Decimal("0.0001"))
```

### 3.3 Simulator Service

```python
# market_data/simulator/service.py
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import random
from market_data.bus import MarketBus
from market_data.models import Tick
from market_data.simulator.generators import QuoteGenerator, BarAggregator
from market_data.simulator.engine import GBMConfig
from market_data.store.redis import set_quote
from market_data.store.timescale import write_tick, write_bar

DEFAULT_SYMBOLS = [
    GBMConfig("AAPL",    initial_price=195.0,  annual_volatility=0.28),
    GBMConfig("TSLA",    initial_price=250.0,  annual_volatility=0.55),
    GBMConfig("MSFT",    initial_price=420.0,  annual_volatility=0.22),
    GBMConfig("BTC-USD", initial_price=65000.0, annual_volatility=0.80),
    GBMConfig("ETH-USD", initial_price=3500.0,  annual_volatility=0.85),
]


class SimulatorService:
    def __init__(self, bus: MarketBus, symbols: list[GBMConfig] = DEFAULT_SYMBOLS):
        self._bus = bus
        self._generators = {cfg.symbol: QuoteGenerator(cfg) for cfg in symbols}
        self._aggregators = {cfg.symbol: BarAggregator(cfg.symbol) for cfg in symbols}
        self._running = False

    async def run(self):
        self._running = True
        tasks = [
            asyncio.create_task(self._symbol_loop(sym))
            for sym in self._generators
        ]
        await asyncio.gather(*tasks)

    async def _symbol_loop(self, symbol: str):
        gen = self._generators[symbol]
        agg = self._aggregators[symbol]
        config = gen._engine.config

        while self._running:
            quote = gen.next_quote()

            # Derive a tick from the quote mid
            tick = Tick(
                symbol=symbol,
                price=quote.mid,
                size=Decimal(random.randint(1, 500)),
                timestamp=quote.timestamp,
            )

            # Publish to bus (WebSocket subscribers)
            await self._bus.publish(quote)
            await self._bus.publish(tick)

            # Update Redis cache
            await set_quote(quote)

            # Persist tick and any closed bars
            await write_tick(tick)
            for bar in agg.feed(tick):
                await write_bar(bar)
                await self._bus.publish(bar)

            await asyncio.sleep(config.tick_interval_s)

    def stop(self):
        self._running = False
```

### 3.4 Using the Simulator in Tests

```python
# tests/test_simulator.py
import asyncio
from market_data.simulator.engine import GBMConfig, GBMEngine
from market_data.simulator.generators import QuoteGenerator, BarAggregator
from market_data.models import Tick
from decimal import Decimal
from datetime import datetime, timezone, timedelta


def test_gbm_price_stays_positive():
    engine = GBMEngine(GBMConfig("TEST", initial_price=100.0))
    for _ in range(10_000):
        price = engine.next_price()
        assert price > 0


def test_quote_spread():
    gen = QuoteGenerator(GBMConfig("TEST", initial_price=100.0), spread_bps=10)
    quote = gen.next_quote()
    assert quote.ask > quote.bid
    spread_bps = float((quote.ask - quote.bid) / quote.mid * 10000)
    assert abs(spread_bps - 10.0) < 0.01  # within rounding


def test_bar_aggregation_emits_on_window_close():
    agg = BarAggregator("TEST")
    base_ts = datetime(2026, 1, 1, 9, 30, 0, tzinfo=timezone.utc)

    def make_tick(offset_s: float, price: float) -> Tick:
        return Tick(
            symbol="TEST",
            price=Decimal(str(price)),
            size=Decimal("100"),
            timestamp=base_ts + timedelta(seconds=offset_s),
        )

    # Feed ticks in minute 0 — no bar should close
    for i in range(5):
        bars = agg.feed(make_tick(i * 10, 100.0 + i))
        assert bars == []

    # Feed a tick in minute 1 — the 1m bar should close
    bars = agg.feed(make_tick(65, 105.0))
    one_min_bars = [b for b in bars if b.resolution == "1m"]
    assert len(one_min_bars) == 1
    bar = one_min_bars[0]
    assert bar.open == Decimal("100.0")
    assert bar.high == Decimal("104.0")
    assert bar.low == Decimal("100.0")
    assert bar.close == Decimal("104.0")
```

---

## 4. Massive API Integration

The "Massive API" connector ingests real-time and historical market data from external providers. The design is provider-agnostic — a `MassiveProvider` abstract base class exposes a uniform interface; concrete implementations exist for **Alpaca Markets** and **Polygon.io**.

### 4.1 Provider Interface

```python
# market_data/massive/base.py
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from market_data.models import Quote, Bar, Tick


class MassiveProvider(ABC):
    """
    Uniform interface for any external market data provider.
    Implementations handle auth, reconnection, and normalisation.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Authenticate and open the streaming connection."""

    @abstractmethod
    async def subscribe(self, symbols: list[str], channels: list[str]) -> None:
        """Subscribe to channels for the given symbols."""

    @abstractmethod
    def stream(self) -> AsyncIterator[Quote | Bar | Tick]:
        """Yield normalised market events as they arrive."""

    @abstractmethod
    async def get_bars_history(
        self,
        symbol: str,
        resolution: str,
        start: str,
        end: str,
        limit: int = 1000,
    ) -> list[Bar]:
        """Fetch historical OHLCV bars."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the streaming connection gracefully."""
```

### 4.2 Alpaca Markets Implementation

```python
# market_data/massive/alpaca.py
import asyncio
import json
import os
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from decimal import Decimal
import websockets
import httpx
from market_data.massive.base import MassiveProvider
from market_data.models import Quote, Bar, Tick

ALPACA_WS_URL = "wss://stream.data.alpaca.markets/v2/iex"
ALPACA_REST_URL = "https://data.alpaca.markets/v2"


class AlpacaProvider(MassiveProvider):
    def __init__(
        self,
        api_key: str = os.getenv("ALPACA_API_KEY", ""),
        api_secret: str = os.getenv("ALPACA_API_SECRET", ""),
    ):
        self._api_key = api_key
        self._api_secret = api_secret
        self._ws = None
        self._queue: asyncio.Queue = asyncio.Queue()
        self._http = httpx.AsyncClient(
            base_url=ALPACA_REST_URL,
            headers={
                "APCA-API-KEY-ID": api_key,
                "APCA-API-SECRET-KEY": api_secret,
            },
        )

    async def connect(self) -> None:
        self._ws = await websockets.connect(
            ALPACA_WS_URL,
            extra_headers={
                "APCA-API-KEY-ID": self._api_key,
                "APCA-API-SECRET-KEY": self._api_secret,
            },
        )
        # Authenticate
        await self._ws.send(json.dumps({
            "action": "auth",
            "key": self._api_key,
            "secret": self._api_secret,
        }))
        auth_msg = json.loads(await self._ws.recv())
        if auth_msg[0].get("T") != "success":
            raise ConnectionError(f"Alpaca auth failed: {auth_msg}")

        # Start background receiver
        asyncio.create_task(self._receive_loop())

    async def subscribe(self, symbols: list[str], channels: list[str]) -> None:
        payload = {"action": "subscribe"}
        if "quotes" in channels:
            payload["quotes"] = symbols
        if "trades" in channels:
            payload["trades"] = symbols
        if any(c.startswith("bars") for c in channels):
            payload["bars"] = symbols
        await self._ws.send(json.dumps(payload))

    async def _receive_loop(self) -> None:
        async for raw in self._ws:
            for msg in json.loads(raw):
                event = self._normalise(msg)
                if event is not None:
                    await self._queue.put(event)

    async def stream(self) -> AsyncIterator[Quote | Bar | Tick]:
        while True:
            yield await self._queue.get()

    def _normalise(self, msg: dict) -> Quote | Bar | Tick | None:
        t = msg.get("T")
        if t == "q":
            return Quote(
                symbol=msg["S"],
                ask=Decimal(str(msg["ap"])),
                bid=Decimal(str(msg["bp"])),
                ask_size=Decimal(str(msg.get("as", 0))),
                bid_size=Decimal(str(msg.get("bs", 0))),
                timestamp=datetime.fromisoformat(msg["t"].replace("Z", "+00:00")),
                source="alpaca",
            )
        if t == "t":
            return Tick(
                symbol=msg["S"],
                price=Decimal(str(msg["p"])),
                size=Decimal(str(msg["s"])),
                timestamp=datetime.fromisoformat(msg["t"].replace("Z", "+00:00")),
                conditions=msg.get("c", []),
            )
        if t == "b":
            return Bar(
                symbol=msg["S"],
                open=Decimal(str(msg["o"])),
                high=Decimal(str(msg["h"])),
                low=Decimal(str(msg["l"])),
                close=Decimal(str(msg["c"])),
                volume=Decimal(str(msg["v"])),
                vwap=Decimal(str(msg["vw"])) if "vw" in msg else None,
                timestamp=datetime.fromisoformat(msg["t"].replace("Z", "+00:00")),
                resolution="1m",
            )
        return None

    async def get_bars_history(
        self,
        symbol: str,
        resolution: str,
        start: str,
        end: str,
        limit: int = 1000,
    ) -> list[Bar]:
        resolution_map = {"1m": "1Min", "5m": "5Min", "1h": "1Hour", "1d": "1Day"}
        params = {
            "symbols": symbol,
            "timeframe": resolution_map.get(resolution, "1Day"),
            "start": start,
            "end": end,
            "limit": limit,
            "feed": "iex",
        }
        resp = await self._http.get("/stocks/bars", params=params)
        resp.raise_for_status()
        data = resp.json()
        bars = []
        for item in data.get("bars", {}).get(symbol, []):
            bars.append(Bar(
                symbol=symbol,
                open=Decimal(str(item["o"])),
                high=Decimal(str(item["h"])),
                low=Decimal(str(item["l"])),
                close=Decimal(str(item["c"])),
                volume=Decimal(str(item["v"])),
                vwap=Decimal(str(item["vw"])) if "vw" in item else None,
                timestamp=datetime.fromisoformat(item["t"].replace("Z", "+00:00")),
                resolution=resolution,
            ))
        return bars

    async def disconnect(self) -> None:
        if self._ws:
            await self._ws.close()
        await self._http.aclose()
```

### 4.3 Polygon.io Implementation

```python
# market_data/massive/polygon.py
import asyncio
import json
import os
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from decimal import Decimal
import websockets
import httpx
from market_data.massive.base import MassiveProvider
from market_data.models import Quote, Bar, Tick

POLYGON_WS_URL = "wss://socket.polygon.io/stocks"
POLYGON_REST_URL = "https://api.polygon.io"


class PolygonProvider(MassiveProvider):
    def __init__(self, api_key: str = os.getenv("POLYGON_API_KEY", "")):
        self._api_key = api_key
        self._ws = None
        self._queue: asyncio.Queue = asyncio.Queue()
        self._http = httpx.AsyncClient(
            base_url=POLYGON_REST_URL,
            params={"apiKey": api_key},
        )

    async def connect(self) -> None:
        self._ws = await websockets.connect(POLYGON_WS_URL)
        await self._ws.send(json.dumps({"action": "auth", "params": self._api_key}))
        await self._ws.recv()  # connected msg
        auth_msg = json.loads(await self._ws.recv())
        if auth_msg[0].get("status") != "auth_success":
            raise ConnectionError(f"Polygon auth failed: {auth_msg}")
        asyncio.create_task(self._receive_loop())

    async def subscribe(self, symbols: list[str], channels: list[str]) -> None:
        subs = []
        for sym in symbols:
            if "quotes" in channels:
                subs.append(f"Q.{sym}")
            if "trades" in channels:
                subs.append(f"T.{sym}")
            if any(c.startswith("bars") for c in channels):
                subs.append(f"A.{sym}")  # per-second aggregates
        await self._ws.send(json.dumps({"action": "subscribe", "params": ",".join(subs)}))

    async def _receive_loop(self) -> None:
        async for raw in self._ws:
            for msg in json.loads(raw):
                event = self._normalise(msg)
                if event:
                    await self._queue.put(event)

    async def stream(self) -> AsyncIterator[Quote | Bar | Tick]:
        while True:
            yield await self._queue.get()

    def _normalise(self, msg: dict) -> Quote | Bar | Tick | None:
        ev = msg.get("ev")
        if ev == "Q":
            return Quote(
                symbol=msg["sym"],
                ask=Decimal(str(msg["ap"])),
                bid=Decimal(str(msg["bp"])),
                ask_size=Decimal(str(msg.get("as", 0))),
                bid_size=Decimal(str(msg.get("bs", 0))),
                timestamp=datetime.fromtimestamp(msg["t"] / 1000, tz=timezone.utc),
                source="polygon",
            )
        if ev == "T":
            return Tick(
                symbol=msg["sym"],
                price=Decimal(str(msg["p"])),
                size=Decimal(str(msg["s"])),
                timestamp=datetime.fromtimestamp(msg["t"] / 1000, tz=timezone.utc),
                conditions=msg.get("c", []),
            )
        if ev in ("A", "AM"):
            return Bar(
                symbol=msg["sym"],
                open=Decimal(str(msg["o"])),
                high=Decimal(str(msg["h"])),
                low=Decimal(str(msg["l"])),
                close=Decimal(str(msg["c"])),
                volume=Decimal(str(msg["av"])),
                vwap=Decimal(str(msg["vw"])) if "vw" in msg else None,
                timestamp=datetime.fromtimestamp(msg["s"] / 1000, tz=timezone.utc),
                resolution="1m",
            )
        return None

    async def get_bars_history(
        self,
        symbol: str,
        resolution: str,
        start: str,
        end: str,
        limit: int = 1000,
    ) -> list[Bar]:
        multiplier_map = {"1m": (1, "minute"), "5m": (5, "minute"), "1h": (1, "hour"), "1d": (1, "day")}
        mult, span = multiplier_map.get(resolution, (1, "day"))
        resp = await self._http.get(
            f"/v2/aggs/ticker/{symbol}/range/{mult}/{span}/{start}/{end}",
            params={"limit": limit, "sort": "asc"},
        )
        resp.raise_for_status()
        data = resp.json()
        bars = []
        for item in data.get("results", []):
            bars.append(Bar(
                symbol=symbol,
                open=Decimal(str(item["o"])),
                high=Decimal(str(item["h"])),
                low=Decimal(str(item["l"])),
                close=Decimal(str(item["c"])),
                volume=Decimal(str(item["v"])),
                vwap=Decimal(str(item["vw"])) if "vw" in item else None,
                timestamp=datetime.fromtimestamp(item["t"] / 1000, tz=timezone.utc),
                resolution=resolution,
            ))
        return bars

    async def disconnect(self) -> None:
        if self._ws:
            await self._ws.close()
        await self._http.aclose()
```

### 4.4 Massive Ingestion Service

The ingestion service wires a provider to the internal bus, Redis cache, and TimescaleDB, with automatic reconnection.

```python
# market_data/massive/service.py
import asyncio
import logging
from market_data.bus import MarketBus
from market_data.massive.base import MassiveProvider
from market_data.models import Quote, Bar, Tick
from market_data.store.redis import set_quote
from market_data.store.timescale import write_tick, write_bar

logger = logging.getLogger(__name__)


class MassiveIngestionService:
    def __init__(
        self,
        provider: MassiveProvider,
        bus: MarketBus,
        symbols: list[str],
        channels: list[str] = ("quotes", "trades", "bars.1m"),
        max_retries: int = 10,
    ):
        self._provider = provider
        self._bus = bus
        self._symbols = symbols
        self._channels = list(channels)
        self._max_retries = max_retries
        self._running = False

    async def run(self) -> None:
        self._running = True
        retries = 0
        backoff = 1.0

        while self._running and retries <= self._max_retries:
            try:
                await self._provider.connect()
                await self._provider.subscribe(self._symbols, self._channels)
                retries = 0
                backoff = 1.0
                logger.info("Massive API connected, streaming %s", self._symbols)
                async for event in self._provider.stream():
                    await self._dispatch(event)
            except Exception as exc:
                logger.warning("Massive API error (retry %d): %s", retries, exc)
                retries += 1
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
            finally:
                await self._provider.disconnect()

        if retries > self._max_retries:
            logger.error("Massive API: exceeded max retries — giving up")

    async def _dispatch(self, event: Quote | Bar | Tick) -> None:
        await self._bus.publish(event)

        if isinstance(event, Quote):
            await set_quote(event)
        elif isinstance(event, Tick):
            await write_tick(event)
        elif isinstance(event, Bar):
            await write_bar(event)

    def stop(self) -> None:
        self._running = False
```

### 4.5 Provider Selection at Runtime

```python
# market_data/massive/factory.py
import os
from market_data.massive.base import MassiveProvider
from market_data.massive.alpaca import AlpacaProvider
from market_data.massive.polygon import PolygonProvider


def make_provider(name: str | None = None) -> MassiveProvider:
    """
    Select the market data provider based on MARKET_DATA_PROVIDER env var
    or the explicit `name` argument.

    Values: "alpaca" | "polygon" | "simulator"
    """
    selected = (name or os.getenv("MARKET_DATA_PROVIDER", "alpaca")).lower()
    if selected == "alpaca":
        return AlpacaProvider()
    if selected == "polygon":
        return PolygonProvider()
    raise ValueError(f"Unknown provider: {selected!r}. Use MARKET_DATA_PROVIDER=simulator to use the built-in simulator.")
```

---

## 5. Application Entry Point

This wires everything together — the API server and either the live ingestion service or the simulator, based on environment configuration.

```python
# market_data/main.py
import asyncio
import os
import uvicorn
from market_data.api.app import app
from market_data.bus import MarketBus
from market_data.store.redis import init_redis
from market_data.store.timescale import init_db

SYMBOLS = os.getenv("SYMBOLS", "AAPL,TSLA,MSFT,BTC-USD").split(",")
PROVIDER = os.getenv("MARKET_DATA_PROVIDER", "alpaca")


async def main():
    await init_redis(os.getenv("REDIS_URL", "redis://localhost:6379"))
    await init_db(os.getenv("DATABASE_URL", "postgresql://localhost/finally"))

    bus = MarketBus()
    # Share the bus with the FastAPI app
    app.state.bus = bus

    if PROVIDER == "simulator":
        from market_data.simulator.engine import GBMConfig
        from market_data.simulator.service import SimulatorService
        ingestion = SimulatorService(bus)
    else:
        from market_data.massive.factory import make_provider
        from market_data.massive.service import MassiveIngestionService
        provider = make_provider(PROVIDER)
        channels = os.getenv("CHANNELS", "quotes,trades,bars.1m").split(",")
        ingestion = MassiveIngestionService(provider, bus, SYMBOLS, channels)

    server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=8080))
    await asyncio.gather(
        server.serve(),
        ingestion.run(),
    )


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 6. Configuration Reference

| Environment Variable      | Default              | Description                                          |
|---------------------------|----------------------|------------------------------------------------------|
| `MARKET_DATA_PROVIDER`    | `alpaca`             | `alpaca` \| `polygon` \| `simulator`                |
| `ALPACA_API_KEY`          | —                    | Alpaca API key ID                                    |
| `ALPACA_API_SECRET`       | —                    | Alpaca API secret key                                |
| `POLYGON_API_KEY`         | —                    | Polygon.io API key                                   |
| `SYMBOLS`                 | `AAPL,TSLA,MSFT,...` | Comma-separated symbols to subscribe                 |
| `CHANNELS`                | `quotes,trades,bars.1m` | Comma-separated channels to subscribe            |
| `REDIS_URL`               | `redis://localhost:6379` | Redis connection URL                             |
| `DATABASE_URL`            | `postgresql://localhost/finally` | TimescaleDB connection string            |

---

## 7. Project Layout

```
market_data/
├── models.py                   # Shared Pydantic models
├── bus.py                      # In-process pub/sub bus
├── main.py                     # Entry point
├── api/
│   ├── app.py                  # FastAPI application
│   ├── routes.py               # REST endpoints
│   └── websocket.py            # WebSocket feed
├── store/
│   ├── redis.py                # Quote cache
│   └── timescale.py            # OHLCV persistence
├── simulator/
│   ├── engine.py               # GBM price engine
│   ├── generators.py           # Quote / bar generators
│   └── service.py              # Simulator async service
└── massive/
    ├── base.py                 # Provider interface
    ├── alpaca.py               # Alpaca Markets connector
    ├── polygon.py              # Polygon.io connector
    ├── service.py              # Ingestion service (retry, dispatch)
    └── factory.py              # Provider selection

migrations/
└── 001_market_data.sql         # TimescaleDB schema

tests/
└── test_simulator.py           # Simulator unit tests
```

---

## 8. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| API framework | FastAPI | Native async, automatic OpenAPI docs, Pydantic integration |
| Tick store | TimescaleDB | Hypertable compression, time-range queries, `time_bucket()` aggregation |
| Quote cache | Redis | Sub-millisecond reads for the REST `/quotes` endpoint |
| Internal bus | In-process `asyncio.Queue` | Zero-overhead for single-process deployment; swap for Redis Streams or Kafka for multi-process |
| Price simulation | Geometric Brownian Motion | Industry-standard continuous-time model; deterministic with seeded RNG for CI |
| Provider normalisation | `MassiveProvider` ABC | Swap providers without touching the ingestion service or API layer |
| Reconnection | Exponential backoff up to 60 s | Handles transient provider outages without hammering the connection |
