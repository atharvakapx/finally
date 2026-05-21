---
phase: 02-portfolio-watchlist-apis
reviewed: 2026-05-21T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - backend/app/services/portfolio.py
  - backend/app/services/watchlist.py
  - backend/app/services/snapshots.py
  - backend/app/services/__init__.py
  - backend/app/routers/portfolio.py
  - backend/app/routers/watchlist.py
  - backend/app/main.py
  - backend/app/market/stream.py
  - backend/tests/test_portfolio.py
  - backend/tests/test_watchlist.py
  - backend/tests/test_snapshots.py
  - backend/tests/test_main_integration.py
findings:
  critical: 2
  warning: 5
  info: 4
  total: 11
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-05-21T00:00:00Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

This phase implements the portfolio, watchlist, and snapshot APIs for the FinAlly backend. The
overall architecture is sound — the service/router split is clean, trade execution uses
`BEGIN IMMEDIATE` to serialize concurrent writers, and the SSE counter lifecycle is correctly
guarded by a `finally` block. However, two correctness defects were found that affect observable
behavior in production: an unhandled `JSONDecodeError` in the watchlist `POST` handler and
hardcoded `'default'` string literals in two modules that import `DEFAULT_USER_ID` from a
sibling file. Five quality/robustness warnings are also present, including an unused factory
parameter, a data-inconsistency window on duplicate ticker adds, and a missing 404 response when
deleting a ticker that was never in the watchlist.

---

## Critical Issues

### CR-01: Unhandled `JSONDecodeError` on Malformed POST Body to `/api/watchlist`

**File:** `backend/app/routers/watchlist.py:43`

**Issue:** `await request.json()` raises `json.JSONDecodeError` (a subclass of `ValueError`) when
the client sends a body that is not valid JSON (e.g., an empty body, plain text, or malformed
JSON). There is no `try/except` around this call, so FastAPI propagates an unhandled 500 response
instead of a documented 400. The portfolio router avoids this by using a Pydantic `BaseModel`
(`TradeBody`) which FastAPI parses safely and returns 422 automatically; the watchlist router
opted for manual `request.json()` and did not replicate the same safety.

Reproducer:
```bash
curl -X POST http://localhost:8000/api/watchlist -H 'Content-Type: text/plain' -d 'notjson'
# -> 500 Internal Server Error (unhandled exception)
```

**Fix:**
```python
@router.post("")
async def add_ticker(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"error": "invalid_ticker", "message": "Request body must be valid JSON"},
            status_code=400,
        )
    ticker = (body.get("ticker") or "") if isinstance(body, dict) else ""
    result = await add_ticker_to_watchlist(ticker, request.app.state.market_source)
    if isinstance(result, tuple):
        code, msg, status = result
        return JSONResponse({"error": code, "message": msg}, status_code=status)
    return JSONResponse(result, status_code=200)
```

---

### CR-02: Hardcoded `'default'` String in `snapshots.py` and `portfolio.py` Router Instead of `DEFAULT_USER_ID` Constant

**File:** `backend/app/services/snapshots.py:58,67` and `backend/app/routers/portfolio.py:73`

**Issue:** `DEFAULT_USER_ID = "default"` is the single source of truth defined in `app/db.py`.
Three SQL queries use the raw string `'default'` instead of the constant:

- `snapshots.py` line 58: `"WHERE id='default'"`
- `snapshots.py` line 67: `"WHERE user_id='default' AND quantity > 0"`
- `routers/portfolio.py` line 73: `"WHERE user_id='default' ORDER BY recorded_at ASC"`

Neither `snapshots.py` nor `routers/portfolio.py` imports `DEFAULT_USER_ID`. If the default user
ID is ever changed in `db.py` (e.g., for a migration or multi-tenant rollout), these three
queries will silently return empty results or miss the correct user row — `snapshots.py` would
return 0 for portfolio value, and the history endpoint would always return `[]`. This is a
correctness defect that is invisible to tests because the test database also uses `"default"`.

**Fix:** Add `DEFAULT_USER_ID` to the import in both files and use parametrized queries:

`backend/app/services/snapshots.py`:
```python
from app.db import get_db, _now_iso, DEFAULT_USER_ID
# ...
"SELECT cash_balance FROM users_profile WHERE id=?", (DEFAULT_USER_ID,)
# ...
"WHERE user_id=? AND quantity > 0", (DEFAULT_USER_ID,)
```

`backend/app/routers/portfolio.py`:
```python
from app.db import get_db, DEFAULT_USER_ID
# ...
"WHERE user_id=? ORDER BY recorded_at ASC", (DEFAULT_USER_ID,)
```

---

## Warnings

### WR-01: `DELETE /api/watchlist/{ticker}` Returns 200 for Non-Existent Ticker

**File:** `backend/app/services/watchlist.py:122-130`

**Issue:** `remove_ticker_from_watchlist` issues a `DELETE` SQL statement without checking
`cursor.rowcount`. If the ticker was never in the watchlist, the query silently succeeds,
`market_source.remove_ticker` is still awaited (harmless but misleading), and a 200 `{"status":
"removed", "ticker": "X"}` is returned to the caller. The spec defines a `404 not_found` error
code for missing resources. This is an incorrect success response for an idempotent but
"resource not found" scenario, and will confuse clients.

**Fix:**
```python
cursor = conn.execute(
    "DELETE FROM watchlist WHERE user_id=? AND ticker=?",
    (DEFAULT_USER_ID, ticker),
)
if cursor.rowcount == 0:
    return ("not_found", f"Ticker {ticker} is not in the watchlist", 404)
```
Place this check before the `await market_source.remove_ticker(ticker)` call.

---

### WR-02: `add_ticker_to_watchlist` Silently Succeeds with Wrong Timestamp for Duplicate Add

**File:** `backend/app/services/watchlist.py:93-100`

**Issue:** `INSERT OR IGNORE` silently no-ops when the ticker is already in the watchlist (due to
the `UNIQUE(user_id, ticker)` constraint). The function then unconditionally calls
`await market_source.add_ticker(ticker)` (redundant but harmless) and returns
`{"ticker": ticker, "added_at": _now_iso()}` — where `_now_iso()` is a freshly generated
timestamp that is **not** the `added_at` stored in the database for that ticker. The caller
receives a stale/fabricated timestamp and has no way to know the ticker was already present.

The correct fix is to query the actual `added_at` from the DB when the ticker already exists, or
return a distinct response (e.g., `200` with the real `added_at`, or `409 Conflict`).

**Fix:**
```python
with get_db() as conn:
    # ... cap check ...
    conn.execute(
        "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
        (str(uuid.uuid4()), DEFAULT_USER_ID, ticker, _now_iso()),
    )
    # Fetch the authoritative added_at from DB (handles both insert and already-existed)
    row = conn.execute(
        "SELECT added_at FROM watchlist WHERE user_id=? AND ticker=?",
        (DEFAULT_USER_ID, ticker),
    ).fetchone()
    added_at = row["added_at"]

await market_source.add_ticker(ticker)
return {"ticker": ticker, "added_at": added_at}
```

---

### WR-03: `PriceCache.version` Property Reads `_version` Without the Lock

**File:** `backend/app/market/cache.py:65-67`

**Issue:** `_version` is written inside `self._lock` in the `update()` method (line 41) but read
without acquiring the lock in the `version` property (line 67). On CPython this is harmless in
practice (GIL makes integer reads atomic), but:
1. The class already uses `threading.Lock` consistently everywhere else — the omission is
   inconsistent and will silently break on alternative Python implementations (PyPy, Jython).
2. The SSE handler reads `price_cache.version` on every poll cycle; a stale read could cause it
   to miss a version bump and delay delivery of a price event by one cycle.

**Fix:**
```python
@property
def version(self) -> int:
    """Current version counter. Useful for SSE change detection."""
    with self._lock:
        return self._version
```

---

### WR-04: `create_portfolio_router` and `create_watchlist_router` Accept Unused `price_cache` Parameter

**File:** `backend/app/routers/portfolio.py:38`, `backend/app/routers/watchlist.py:20`

**Issue:** Both router factories accept a `price_cache: PriceCache` parameter that is never used
inside the factory body. Every handler reads `request.app.state.price_cache` at request time
instead. The parameter has no effect but creates a misleading API contract — callers passing in a
*different* `PriceCache` instance than the one stored in `app.state` would see it silently
ignored, which could cause confusing bugs during testing or if the factory pattern is extended.
`PriceCache` is also imported in `watchlist.py` solely for this unused parameter.

**Fix:** Remove the `price_cache` parameter from both factory signatures and remove the unused
`PriceCache` import from `watchlist.py`:

```python
# portfolio.py
def create_portfolio_router() -> APIRouter:
    ...

# watchlist.py
def create_watchlist_router() -> APIRouter:
    ...
```

Update callers in `main.py` accordingly:
```python
app.include_router(create_portfolio_router(), prefix="/api")
app.include_router(create_watchlist_router(), prefix="/api")
```

---

### WR-05: `test_snapshot_after_trade` Contains a Misleading Dead Assignment

**File:** `backend/tests/test_snapshots.py:140`

**Issue:** Line 140 reads:
```python
db_path = module.app.state.price_cache  # just need access to DB path
```
This assigns a `PriceCache` object to a variable named `db_path`. The variable is never used
again; the subsequent DB access goes through `app.db.get_db()` directly. The comment "just need
access to DB path" is factually incorrect — no DB path is extracted here. This is dead code with
a misleading comment that implies the variable is needed, obscuring intent. Any reader trying to
understand the test setup will be confused.

**Fix:** Delete the dead assignment entirely (line 140). The test functions correctly without it.

---

## Info

### IN-01: Unused `logger` in Both Router Modules

**File:** `backend/app/routers/portfolio.py:16`, `backend/app/routers/watchlist.py:17`

**Issue:** Both router files create a module-level `logger = logging.getLogger(__name__)` but
never call `logger.info/warning/error/debug(...)` anywhere in the file. The `logging` import is
also unused as a result.

**Fix:** Either add useful log statements (e.g., log trade executions, watchlist changes at INFO
level) or remove the unused `import logging` and `logger = ...` lines.

---

### IN-02: `session_baselines` Zero-Price Edge Case Silently Produces Wrong Session Change

**File:** `backend/app/services/watchlist.py:52-55`

**Issue:** The session change calculation guards against division by zero with `if price is not
None and baseline` — Python's truthiness test. If a ticker's baseline price is exactly `0.0`
(which the simulator does not produce but is theoretically possible via a corrupt or injected
cache entry), `baseline` evaluates as falsy and the session change is returned as `0.0` instead
of raising. This is a latent correctness issue: a price of `0.0` would produce incorrect session
Δ% silently. The guard should test `baseline is not None` or `baseline != 0.0` explicitly.

**Fix:**
```python
session_change_pct = (
    (price - baseline) / baseline * 100
    if price is not None and baseline is not None and baseline != 0.0
    else 0.0
)
```

---

### IN-03: Test Coverage Gap — No Test for `DELETE /api/watchlist/{ticker}` When Ticker Not in Watchlist

**File:** `backend/tests/test_watchlist.py`

**Issue:** `TestRemoveWatchlist` covers only two cases: held ticker (400) and unheld ticker in
watchlist (200). There is no test that deletes a ticker that was never added, which would expose
the WR-01 bug above. Adding this test would both document the expected 404 behavior and prevent
regressions once WR-01 is fixed.

**Fix:** Add a test case:
```python
def test_remove_nonexistent_ticker_returns_404(self, app_client) -> None:
    client, module, mock_source = app_client
    resp = client.delete("/api/watchlist/ZZZZ")
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"
    mock_source.remove_ticker.assert_not_awaited()
```

---

### IN-04: Test Coverage Gap — No Test for `POST /api/watchlist` with Duplicate Ticker

**File:** `backend/tests/test_watchlist.py`

**Issue:** `TestAddWatchlist` does not test adding a ticker that is already present in the
watchlist (e.g., adding `AAPL` again after the 10 default tickers are seeded). The current
behavior (silent INSERT OR IGNORE + 200 with wrong timestamp) is never observed in tests, meaning
WR-02 is invisible in CI. Adding a test would pin the current behavior and make the stale
timestamp issue apparent.

**Fix:** Add a test:
```python
def test_add_duplicate_ticker(self, app_client) -> None:
    """POST a ticker that is already in the watchlist → 200, count unchanged."""
    client, module, mock_source = app_client
    # AAPL is seeded by default
    resp = client.post("/api/watchlist", json={"ticker": "AAPL"})
    assert resp.status_code == 200
    items = client.get("/api/watchlist").json()
    aapl_items = [i for i in items if i["ticker"] == "AAPL"]
    assert len(aapl_items) == 1, "Duplicate add must not create a second watchlist row"
```

---

_Reviewed: 2026-05-21T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
