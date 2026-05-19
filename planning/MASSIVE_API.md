# Massive API (formerly Polygon.io) — Reference

Massive rebranded from Polygon.io on October 30, 2025. All API endpoints, keys, and SDKs continue to work unchanged. The base URL moved from `api.polygon.io` to `api.massive.com`.

---

## Authentication

Every request must include a Bearer token in the `Authorization` header:

```
Authorization: Bearer YOUR_API_KEY
```

The Python SDK handles this automatically:

```python
from massive import RESTClient

client = RESTClient(api_key="YOUR_API_KEY")
```

---

## Base URL

```
https://api.massive.com
```

---

## Rate Limits

| Plan | Requests / minute | Notes |
|------|------------------|-------|
| Free (Starter) | 5 | 15-minute delayed data |
| Developer | Unlimited | 15-minute delayed data |
| Advanced | Unlimited | Real-time data |
| Business | Unlimited | Real-time + websocket |

On the free tier, poll no more than once every **15 seconds** to stay within 5 req/min. HTTP 429 is returned when the limit is exceeded; back off and retry.

---

## Key Endpoints for Stock Prices

### 1. Last Trade — single ticker, latest price

```
GET /v2/last/trade/{stocksTicker}
```

Returns the most recent executed trade with price, size, exchange, and timestamp.

**Request:**
```python
trade = client.get_last_trade(ticker="AAPL")
print(trade.price, trade.timestamp)
```

**Raw HTTP:**
```
GET https://api.massive.com/v2/last/trade/AAPL
Authorization: Bearer YOUR_API_KEY
```

**Response:**
```json
{
  "status": "OK",
  "request_id": "f05562305bd26ced64b98ed68b3c5d96",
  "results": {
    "T": "AAPL",
    "p": 129.8473,
    "s": 25,
    "t": 1617901342969834000,
    "f": 1617901342969796400,
    "y": 1617901342968000000,
    "x": 4,
    "z": 3,
    "c": [37],
    "i": "118749",
    "q": 3135876,
    "r": 202,
    "ds": "25.0"
  }
}
```

Key fields: `p` = price, `s` = size (shares), `t` = SIP timestamp (nanoseconds), `x` = exchange ID.

---

### 2. Last Quote — NBBO bid/ask

```
GET /v2/last/nbbo/{stocksTicker}
```

Returns the most recent National Best Bid and Offer.

**Request:**
```python
quote = client.get_last_quote(ticker="AAPL")
print(quote.bid_price, quote.ask_price)  # p, P fields
```

**Response:**
```json
{
  "status": "OK",
  "request_id": "b84e24636301f19f88e0dfbf9a45ed5c",
  "results": {
    "T": "AAPL",
    "P": 127.98,
    "S": 7,
    "p": 127.96,
    "s": 1,
    "t": 1617827221349730300,
    "y": 1617827221349366000,
    "x": 11,
    "X": 19,
    "q": 83480742,
    "z": 3
  }
}
```

Key fields: `P` = ask price, `p` = bid price, `S` = ask size, `s` = bid size.

---

### 3. Single Ticker Snapshot — full market state

```
GET /v2/snapshot/locale/us/markets/stocks/tickers/{stocksTicker}
```

Returns the current minute bar, last trade, last quote, previous day bar, today's change, and VWAP in one call. The most useful endpoint for a trading dashboard.

**Request:**
```python
snap = client.get_snapshot_ticker("stocks", "AAPL")
price = snap.last_trade.price
change_pct = snap.todays_change_perc
```

**Response:**
```json
{
  "status": "OK",
  "request_id": "657e430f1ae768891f018e08e03598d8",
  "ticker": {
    "ticker": "AAPL",
    "todaysChange": 0.98,
    "todaysChangePerc": 0.82,
    "updated": 1605195918306274000,
    "day": {
      "o": 119.62,
      "h": 120.53,
      "l": 118.81,
      "c": 120.4229,
      "v": 28727868,
      "vw": 119.725,
      "dv": "28727868.0"
    },
    "lastTrade": {
      "p": 120.47,
      "s": 236,
      "t": 1605195918306274000,
      "x": 10,
      "c": [14, 41],
      "i": "4046",
      "ds": "236.0"
    },
    "lastQuote": {
      "P": 120.47,
      "p": 120.46,
      "S": 4,
      "s": 8,
      "t": 1605195918507251700
    },
    "min": {
      "o": 120.435,
      "h": 120.468,
      "l": 120.37,
      "c": 120.4201,
      "v": 270796,
      "vw": 120.4129,
      "t": 1684428720000,
      "av": 28724441,
      "n": 762
    },
    "prevDay": {
      "o": 117.19,
      "h": 119.63,
      "l": 116.44,
      "c": 119.49,
      "v": 110597265,
      "vw": 118.4998
    }
  }
}
```

---

### 4. Multiple Tickers Snapshot — batch price fetch

```
GET /v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,MSFT,GOOGL
```

Returns snapshots for a comma-separated list of tickers in a single request. This is the recommended approach for polling a watchlist — one API call covers all tickers.

**Request:**
```python
snapshots = client.get_snapshot_all(
    market_type=SnapshotMarketType.STOCKS,
    tickers=["AAPL", "MSFT", "GOOGL", "TSLA"],
)
for snap in snapshots:
    print(snap.ticker, snap.last_trade.price)
```

**Raw HTTP:**
```
GET https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,MSFT,GOOGL
Authorization: Bearer YOUR_API_KEY
```

**Response:**
```json
{
  "status": "OK",
  "tickers": [
    {
      "ticker": "AAPL",
      "todaysChange": 0.98,
      "todaysChangePerc": 0.82,
      "lastTrade": { "p": 120.47, "s": 100, "t": 1605195918306274000 },
      "day": { "o": 119.62, "h": 120.53, "l": 118.81, "c": 120.42, "v": 28727868 }
    },
    {
      "ticker": "MSFT",
      "todaysChange": -1.20,
      "todaysChangePerc": -0.32,
      "lastTrade": { "p": 374.20, "s": 50, "t": 1605195918000000000 }
    }
  ]
}
```

No defined cap on tickers per request for this endpoint (the Unified Snapshot `/v3/snapshot` accepts up to 250 via `ticker.any_of`).

---

### 5. Unified Snapshot — cross-asset, multi-ticker

```
GET /v3/snapshot?ticker.any_of=AAPL,MSFT&type=stocks
```

The newer v3 snapshot endpoint. Supports up to 250 tickers per call, cross-asset filtering, and pagination.

**Parameters:**

| Parameter | Type | Notes |
|-----------|------|-------|
| `ticker.any_of` | string | Comma-separated list, max 250 |
| `type` | string | `stocks`, `options`, `fx`, `crypto`, `indices` |
| `limit` | integer | Max 250, default 10 |
| `sort` | string | Field to sort by |
| `order` | string | `asc` or `desc` |

**Response fields per ticker:**
- `last_trade.price` — last executed trade price
- `last_trade.size` — shares traded
- `session.change` / `session.change_percent` — today's move
- `session.open`, `session.high`, `session.low`, `session.close`
- `session.volume`, `session.vwap`
- `market_status` — `open`, `closed`, `extended-hours`

---

### 6. Daily Open/Close — OHLC for a specific date

```
GET /v1/open-close/{stocksTicker}/{date}
```

End-of-day summary. Useful for historical context, P&L calculation, and charting.

**Parameters:**

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `stocksTicker` | string | Yes | e.g. `AAPL` |
| `date` | string | Yes | `YYYY-MM-DD` |
| `adjusted` | boolean | No | Default `true` (split-adjusted) |

**Request:**
```python
ohlc = client.get_daily_open_close_agg("AAPL", "2024-01-15")
print(ohlc.open, ohlc.close, ohlc.high, ohlc.low)
```

**Response:**
```json
{
  "status": "OK",
  "symbol": "AAPL",
  "from": "2024-01-15",
  "open": 183.92,
  "close": 186.19,
  "high": 186.57,
  "low": 183.72,
  "volume": 65602027,
  "preMarket": 184.25,
  "afterHours": 186.40
}
```

---

### 7. Aggregate Bars (OHLCV) — historical candles

```
GET /v2/aggs/ticker/{stocksTicker}/range/{multiplier}/{timespan}/{from}/{to}
```

Historical OHLCV candles at any resolution. Use for building price charts.

**Parameters:**

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `stocksTicker` | string | Yes | e.g. `AAPL` |
| `multiplier` | integer | Yes | e.g. `1`, `5`, `15` |
| `timespan` | string | Yes | `second`, `minute`, `hour`, `day`, `week`, `month`, `quarter`, `year` |
| `from` | string | Yes | `YYYY-MM-DD` or Unix ms |
| `to` | string | Yes | `YYYY-MM-DD` or Unix ms |
| `adjusted` | boolean | No | Default `true` |
| `sort` | string | No | `asc` or `desc` |
| `limit` | integer | No | 1–50000, default 5000 |

**Request — 1-minute bars for the last trading day:**
```python
from datetime import date

aggs = []
for bar in client.list_aggs(
    ticker="AAPL",
    multiplier=1,
    timespan="minute",
    from_="2024-01-15",
    to="2024-01-15",
    limit=50000,
):
    aggs.append(bar)
```

**Response:**
```json
{
  "status": "OK",
  "ticker": "AAPL",
  "adjusted": true,
  "queryCount": 390,
  "resultsCount": 390,
  "results": [
    {
      "t": 1705327800000,
      "o": 183.92,
      "h": 184.10,
      "l": 183.85,
      "c": 184.05,
      "v": 1234567,
      "vw": 183.97,
      "n": 8421
    }
  ]
}
```

Bar fields: `t` = Unix ms timestamp, `o/h/l/c` = OHLC, `v` = volume, `vw` = VWAP, `n` = trade count.

---

## Python SDK — Installation and Setup

```bash
uv add massive
```

```python
from massive import RESTClient
from massive.rest.models import SnapshotMarketType

client = RESTClient(api_key="YOUR_API_KEY")

# Optional: enable request tracing for debugging
client = RESTClient(api_key="YOUR_API_KEY", trace=True, verbose=True)

# Optional: disable auto-pagination (for endpoints that return lists)
client = RESTClient(api_key="YOUR_API_KEY", pagination=False)
```

The SDK is synchronous. In an async context (FastAPI), run calls in a thread pool:

```python
import asyncio

snapshots = await asyncio.to_thread(
    client.get_snapshot_all,
    market_type=SnapshotMarketType.STOCKS,
    tickers=["AAPL", "MSFT"],
)
```

---

## Error Handling

| HTTP Status | Meaning | Action |
|-------------|---------|--------|
| 200 | OK | Parse response |
| 400 | Bad request | Fix the request (invalid ticker format, bad params) |
| 401 | Unauthorized | Check `MASSIVE_API_KEY` value |
| 403 | Forbidden | Endpoint requires a higher-tier plan |
| 404 | Not found | Ticker not recognized or no data for date |
| 429 | Rate limit exceeded | Back off; wait until next minute window |
| 503 | Service unavailable | Transient; retry with exponential backoff |

The SDK raises exceptions for non-2xx responses. Wrap poll calls in a broad `except Exception` to prevent transient errors from crashing the application:

```python
try:
    snapshots = await asyncio.to_thread(self._fetch_snapshots)
except Exception as e:
    logger.error("Massive poll failed: %s", e)
    # Loop continues; next poll will retry automatically
```

---

## Data Availability by Plan

| Data | Free (Starter) | Developer | Advanced / Business |
|------|---------------|-----------|---------------------|
| Last trade / quote | 15-min delayed | 15-min delayed | Real-time |
| Snapshots | 15-min delayed | 15-min delayed | Real-time |
| Daily OHLC | Yes | Yes | Yes |
| Minute bars | Yes | Yes | Yes |
| Tick-level trades/quotes | Limited | Unlimited | Unlimited |
| WebSocket streams | No | No | Yes |

For the FinAlly simulator-default design, the free tier (15-minute delay) is acceptable for demo purposes when a `MASSIVE_API_KEY` is provided; users who want live prices need a paid plan.

---

## Ticker Validation

Before adding a ticker to the watchlist in Massive mode, probe the symbol with one API call:

```python
async def validate_ticker(client: RESTClient, ticker: str) -> bool:
    try:
        snap = await asyncio.to_thread(
            client.get_snapshot_ticker, "stocks", ticker
        )
        return snap is not None
    except Exception:
        return False
```

A 404 response means the symbol is not recognized by Massive.
