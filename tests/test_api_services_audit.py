"""
Audit tests for API Services & Adapters layer.

Targets: edge cases, failure scenarios, boundary conditions, and critical logic paths
identified during production code audit.

Run:  python -X utf8 tests/test_api_services_audit.py
"""

import math
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# --- path setup (mirrors api/main.py) ---
_ROOT = str(Path(__file__).parent.parent)
_API = str(Path(__file__).parent.parent / "api")
_SERVICES = str(Path(__file__).parent.parent / "api" / "services")
_ADAPTERS = str(Path(__file__).parent.parent / "api" / "adapters")
for p in [_ROOT, _API, _SERVICES, _ADAPTERS]:
    if p not in sys.path:
        sys.path.insert(0, p)


passed = 0
failed = 0
errors = []


def S(section_name):
    print(f"\n{'='*60}")
    print(f"  {section_name}")
    print(f"{'='*60}")


def T(name, condition, details=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        msg = f"  FAIL  {name}"
        if details:
            msg += f" — {details}"
        print(msg)
        errors.append(name)


# ============================================================
# 1. FinnhubService
# ============================================================
S("FinnhubService — Thread-safe rate limiting")

from finnhub_service import FinnhubService

svc = FinnhubService(api_key="test", cache_ttl=5)

# Test: rate limiter has a lock attribute
T("Rate lock exists", hasattr(svc, "_rate_lock"),
  "Thread-safe rate limiter requires _rate_lock")

# Test: disabled service returns None
disabled = FinnhubService(api_key="", cache_ttl=5)
T("Disabled service returns None", disabled.fetch_quote("AAPL") is None)
T("Disabled service is_enabled=False", not disabled.is_enabled())

# Test: whitespace-only key is disabled
ws_svc = FinnhubService(api_key="   ", cache_ttl=5)
T("Whitespace key is disabled", not ws_svc.is_enabled())

# Test: cache TTL respected
svc._cache["TEST"] = (time.time(), {"c": 100})
T("Fresh cache returns data", svc._is_cached("TEST"))
T("Fresh cache returns correct data", svc._get_cached("TEST") == {"c": 100})

svc._cache["OLD"] = (time.time() - 999, {"c": 50})
T("Expired cache returns False for _is_cached", not svc._is_cached("OLD"))
T("_get_cached returns stale data (fallback)", svc._get_cached("OLD") == {"c": 50})

# Test: get_current_price with zero
svc._cache["ZERO"] = (time.time(), {"c": 0})
T("Price=0 returns None", svc.get_current_price("ZERO") is None,
  "Finnhub c=0 means no data")

# Test: get_current_price with valid data from cache
svc._cache["GOOD"] = (time.time(), {"c": 150.5})
T("Valid price from cache", svc.get_current_price("GOOD") == 150.5)

# Test: get_price_change_24h
svc._cache["CHG"] = (time.time(), {"d": -2.5})
T("Price change from cache", svc.get_price_change_24h("CHG") == -2.5)

svc._cache["NOCHG"] = (time.time(), {"d": None})
T("Null change returns None", svc.get_price_change_24h("NOCHG") is None)

# Test: concurrent rate limit doesn't exceed 60
S("FinnhubService — Concurrent rate limit safety")

concurrent_svc = FinnhubService(api_key="test", cache_ttl=5)
# Pre-fill 57 call times ~59s ago so any sleep is < 2s
now = time.time()
for i in range(57):
    concurrent_svc._call_times.append(now - 59)

call_counts = []
barrier = threading.Barrier(3)


def rate_limit_worker():
    barrier.wait()
    concurrent_svc._wait_for_rate_limit()
    call_counts.append(1)


threads = [threading.Thread(target=rate_limit_worker) for _ in range(3)]
for t in threads:
    t.start()
for t in threads:
    t.join(timeout=10)

T("Concurrent calls all complete", len(call_counts) == 3,
  f"Expected 3, got {len(call_counts)}")
T("Call times within limit", len(concurrent_svc._call_times) <= 60,
  f"Got {len(concurrent_svc._call_times)}")


# ============================================================
# 2. DataNormalizer — Adapter naming (CRITICAL fix verification)
# ============================================================
S("DataNormalizer — Adapter name derivation")

from data_normalizer import DataNormalizer, NormalizedQuote


# Use class names that match _CLASS_NAME_TO_KEY in DataNormalizer
class FinnhubAdapter:
    def fetch_quote(self, symbol, instrument_type="equity"):
        return None


class TwelveDataAdapter:
    def fetch_quote(self, symbol, instrument_type="equity"):
        return None


class CoinGeckoAdapter:
    def fetch_quote(self, symbol, instrument_type="crypto"):
        return None


dn = DataNormalizer(adapters=[
    FinnhubAdapter(), TwelveDataAdapter(), CoinGeckoAdapter()
])

T("finnhub adapter registered", "finnhub" in dn._adapters_by_name,
  f"Keys: {list(dn._adapters_by_name.keys())}")
T("twelve_data adapter registered", "twelve_data" in dn._adapters_by_name,
  f"Keys: {list(dn._adapters_by_name.keys())}")
T("coingecko adapter registered", "coingecko" in dn._adapters_by_name,
  f"Keys: {list(dn._adapters_by_name.keys())}")

# Verify ordering
equity_order = dn._ordered_adapters("equity")
T("Equity ordering: finnhub first",
  isinstance(equity_order[0], FinnhubAdapter))
T("Equity ordering: twelve_data second",
  isinstance(equity_order[1], TwelveDataAdapter))

crypto_order = dn._ordered_adapters("crypto")
T("Crypto ordering: coingecko first",
  isinstance(crypto_order[0], CoinGeckoAdapter))


# ============================================================
# 3. FinnhubAdapter — OHLC zero handling
# ============================================================
S("FinnhubAdapter — OHLC zero handling")

from finnhub_adapter import FinnhubAdapter

mock_service = MagicMock()
adapter = FinnhubAdapter(mock_service)

# Test: zero OHLC values preserved (not treated as None)
mock_service.fetch_quote.return_value = {
    "c": 100.0, "o": 0, "h": 0, "l": 0, "pc": 0, "t": 1700000000
}
quote = adapter.fetch_quote("TEST")
T("open=0 preserved (not None)", quote is not None and quote.open == 0.0,
  f"Got open={quote.open if quote else 'None'}")
T("high=0 preserved", quote is not None and quote.high == 0.0)
T("low=0 preserved", quote is not None and quote.low == 0.0)
T("close=0 preserved", quote is not None and quote.close == 0.0)

# Test: None OHLC values become None
mock_service.fetch_quote.return_value = {
    "c": 100.0, "t": 1700000000
}
quote2 = adapter.fetch_quote("TEST2")
T("Missing OHLC → None", quote2 is not None and quote2.open is None)

# Test: price=0 returns None
mock_service.fetch_quote.return_value = {"c": 0, "t": 1700000000}
T("Price=0 returns None", adapter.fetch_quote("HALT") is None)

# Test: null response
mock_service.fetch_quote.return_value = None
T("Null response returns None", adapter.fetch_quote("GONE") is None)


# ============================================================
# 4. TwelveDataAdapter — OHLC zero handling
# ============================================================
S("TwelveDataAdapter — OHLC zero handling")

from twelve_data_adapter import TwelveDataAdapter

td = TwelveDataAdapter(api_key="fake")

# Simulate a response with zero volume
mock_resp = MagicMock()
mock_resp.status_code = 200
mock_resp.json.return_value = {
    "close": "42.0", "open": "0", "high": "0", "low": "0",
    "volume": "0", "datetime": "2024-01-15 10:30:00"
}

with patch("requests.get", return_value=mock_resp):
    q = td.fetch_quote("TEST", instrument_type="equity")

T("TwelveData: open=0 preserved",
  q is not None and q.open == 0.0, f"Got {q.open if q else 'None'}")
T("TwelveData: volume=0 preserved",
  q is not None and q.volume == 0.0, f"Got {q.volume if q else 'None'}")


# ============================================================
# 5. TwelveDataAdapter — Sleep outside lock
# ============================================================
S("TwelveDataAdapter — Rate lock not held during sleep")

td2 = TwelveDataAdapter(api_key="fake")
# Fill rate limit
now = time.time()
for _ in range(8):
    td2._call_times.append(now - 2)  # 2 seconds ago — will need small sleep

# Check that another thread can acquire the lock quickly
lock_acquired = threading.Event()


def try_lock():
    acquired = td2._rate_lock.acquire(timeout=0.5)
    if acquired:
        lock_acquired.set()
        td2._rate_lock.release()


t1 = threading.Thread(target=td2._wait_for_rate_limit)
t1.start()
time.sleep(0.05)  # Let t1 start

t2 = threading.Thread(target=try_lock)
t2.start()
t2.join(timeout=3)
t1.join(timeout=5)

T("Lock released during sleep", lock_acquired.is_set(),
  "Other threads should not be blocked while sleeping")


# ============================================================
# 6. CoinGecko — Symbol resolution edge cases
# ============================================================
S("CoinGeckoAdapter — Symbol resolution")

from coingecko_adapter import CoinGeckoAdapter

cg = CoinGeckoAdapter(api_key="fake")

T("BTC-USD resolves", cg._resolve_coingecko_id("BTC-USD") == "bitcoin")
T("BTC/USD resolves", cg._resolve_coingecko_id("BTC/USD") == "bitcoin")
T("BTCUSD resolves", cg._resolve_coingecko_id("BTCUSD") == "bitcoin")
T("BTCUSDT resolves", cg._resolve_coingecko_id("BTCUSDT") == "bitcoin")
T("BINANCE:BTCUSDT resolves", cg._resolve_coingecko_id("BINANCE:BTCUSDT") == "bitcoin")
T("eth-usd resolves (case-insensitive)", cg._resolve_coingecko_id("eth-usd") == "ethereum")
T("Unknown symbol returns None", cg._resolve_coingecko_id("FAKECOIN") is None)
T("Empty string returns None", cg._resolve_coingecko_id("") is None)
T("MATIC resolves", cg._resolve_coingecko_id("MATIC") == "polygon-ecosystem-token")
T("POL resolves (same coin)", cg._resolve_coingecko_id("POL") == "polygon-ecosystem-token")


# ============================================================
# 7. Correlation Service — Performance & edge cases
# ============================================================
S("Correlation Service — Edge cases")

from correlation_service import compute_velocity_price_correlation

# Negative lead days
r = compute_velocity_price_correlation([], [], lead_days=-1)
T("Negative lead_days rejected", r["n_observations"] == 0)

# Empty inputs
r = compute_velocity_price_correlation([], [])
T("Empty inputs → insufficient data", r["n_observations"] == 0)

# Constant velocity (zero variance → NaN handled)
vel = [{"date": f"2024-01-{i:02d}", "velocity": 5.0} for i in range(1, 35)]
prices = [{"date": f"2024-01-{i:02d}", "change_pct": float(i)} for i in range(1, 35)]
r = compute_velocity_price_correlation(vel, prices, lead_days=0)
T("Constant velocity → r=0 (NaN handled)", r["correlation"] == 0.0)

# Missing date key — should not crash
bad_vel = [{"velocity": 1.0}, {"date": "2024-01-01", "velocity": 2.0}]
bad_price = [{"change_pct": 0.5}, {"date": "2024-01-01", "change_pct": 1.0}]
try:
    r = compute_velocity_price_correlation(bad_vel, bad_price)
    T("Missing date key handled gracefully", True)
except KeyError as e:
    T("Missing date key handled gracefully", False, f"KeyError: {e}")

# Perfect positive correlation
vel_p = [{"date": f"2024-01-{i:02d}", "velocity": float(i)} for i in range(1, 35)]
prices_p = [{"date": f"2024-01-{i:02d}", "change_pct": float(i)} for i in range(1, 35)]
r = compute_velocity_price_correlation(vel_p, prices_p, lead_days=0)
T("Perfect correlation → r≈1.0", abs(r["correlation"] - 1.0) < 0.01,
  f"Got r={r['correlation']}")
T("Perfect correlation is significant", r["is_significant"])

# Runtime sanity guard: moderately large aligned inputs should complete and
# produce a valid correlation payload (without relying on source strings).
vel_large = [{"date": f"2024-02-{(i % 28) + 1:02d}", "velocity": float(i)} for i in range(1, 400)]
prices_large = [{"date": f"2024-02-{(i % 28) + 1:02d}", "change_pct": float(i) / 10.0} for i in range(1, 400)]
r_large = compute_velocity_price_correlation(vel_large, prices_large, lead_days=0)
T("Large correlation input returns structured result",
  isinstance(r_large, dict) and "correlation" in r_large and "n_observations" in r_large,
  f"Got keys={list(r_large.keys()) if isinstance(r_large, dict) else type(r_large).__name__}")


# ============================================================
# 8. Circuit Breaker
# ============================================================
S("Circuit Breaker")

from circuit_breaker import CircuitBreaker

cb = CircuitBreaker("TestAdapter")
T("Initially closed", not cb.is_open)

# Record 9 failures from a single source — still closed
for _ in range(9):
    cb.record_failure(source="provider_a")
T("9 failures from one source → still closed", not cb.is_open)

# 10th failure but still one source — still closed
cb.record_failure(source="provider_a")
T("10 failures from one source → still closed", not cb.is_open)

# Add second failure source to open
cb.record_failure(source="provider_b")
T("10+ failures across two sources → open", cb.is_open)

# Success resets
cb2 = CircuitBreaker("TestAdapter2")
for _ in range(3):
    cb2.record_failure()
cb2.record_success()
T("Success resets counter", not cb2.is_open)

for _ in range(10):
    cb2.record_failure(source="provider_a")
cb2.record_failure(source="provider_b")
T("Can re-open after reset", cb2.is_open)


# ============================================================
# 9. WebSocket Relay
# ============================================================
S("WebSocket Relay — Thread safety")

from websocket_relay import FinnhubWebSocketRelay

ws = FinnhubWebSocketRelay(api_key="test", symbols_limit=5)
T("Has _sym_lock for thread safety", hasattr(ws, "_sym_lock"))
T("Has _pending_desired for disconnect queuing", hasattr(ws, "_pending_desired"))

# update_symbols while disconnected stores to pending
ws.update_symbols(["AAPL", "MSFT", "GOOGL"])
T("Pending desired set populated",
  ws._pending_desired == {"AAPL", "MSFT", "GOOGL"},
  f"Got {ws._pending_desired}")

# Symbols limit enforced
ws.update_symbols(["A", "B", "C", "D", "E", "F", "G"])
T("Symbols limit enforced (max 5)",
  ws._pending_desired is not None and len(ws._pending_desired) == 5,
  f"Got {len(ws._pending_desired) if ws._pending_desired else 0}")

# Buffer warning not spammy
T("Has buffer_warning_logged flag", hasattr(ws, "_buffer_warning_logged"))

# Test: _handle_message with valid trade
ws._handle_message('{"type": "trade", "data": [{"s": "AAPL", "p": 150.5, "v": 100, "t": 1700000000000}]}')
T("Trade buffered", ws.get_tick_buffer_size() == 1)
ticks = ws.drain_tick_buffer()
T("Drain returns ticks", len(ticks) == 1)
T("Drained tick has correct symbol", ticks[0]["symbol"] == "AAPL")
T("Buffer empty after drain", ws.get_tick_buffer_size() == 0)

# Test: non-trade messages ignored
ws._handle_message('{"type": "ping"}')
T("Non-trade message ignored", ws.get_tick_buffer_size() == 0)

# Test: trade with missing price ignored
ws._handle_message('{"type": "trade", "data": [{"s": "AAPL", "v": 100}]}')
T("Trade without price ignored", ws.get_tick_buffer_size() == 0)


# ============================================================
# 10. Sector Map
# ============================================================
S("Sector Map — Sanity checks")

from sector_map import SECTOR_MAP

T("AAPL is Technology", SECTOR_MAP.get("AAPL") == "Technology")
T("SPY is Broad Market", SECTOR_MAP.get("SPY") == "Broad Market")
T("BTC-USD is Crypto", SECTOR_MAP.get("BTC-USD") == "Crypto")
T("ATVI removed (delisted)", "ATVI" not in SECTOR_MAP,
  "ATVI was acquired by MSFT in Oct 2023")

# Check no duplicate values that are actually different sectors
# (Sanity: VIX should be Volatility, not something else)
T("VIX is Volatility", SECTOR_MAP.get("VIX") == "Volatility")
T("GLD is Commodities", SECTOR_MAP.get("GLD") == "Commodities")


# ============================================================
# 11. Earnings Service
# ============================================================
S("Earnings Service — Cache and edge cases")

from earnings_service import get_upcoming_earnings, _cache

# Clear module cache
_cache.clear()

# Test: empty ticker list
r = get_upcoming_earnings([])
T("Empty list returns empty", r == [])

# Test: unknown ticker doesn't crash
r = get_upcoming_earnings(["ZZZZZNOTREAL123"])
T("Unknown ticker returns gracefully", isinstance(r, list))


# ============================================================
# 12. Second-pass: Rate limiter post-sleep capacity recheck
# ============================================================
S("Rate limiter — post-sleep capacity recheck")

# FinnhubService: Fill to capacity, verify the post-sleep path re-checks
fh_race = FinnhubService(api_key="test", cache_ttl=5)
now = time.time()
# Fill window completely with fresh timestamps (no room, nothing to purge)
for _ in range(60):
    fh_race._call_times.append(now - 5)  # 5s ago — won't age out for 55s

fixed_now = time.time()
with patch("finnhub_service.time.time", return_value=fixed_now), \
     patch("finnhub_service.time.sleep", return_value=None):
    fh_race._wait_for_rate_limit()
T("Finnhub full window does not exceed 60 entries", len(fh_race._call_times) == 60,
  f"Got {len(fh_race._call_times)} entries")

td_race = TwelveDataAdapter(api_key="fake")
for _ in range(8):
    td_race._call_times.append(fixed_now - 5)
with patch("twelve_data_adapter.time.time", return_value=fixed_now), \
     patch("twelve_data_adapter.time.sleep", return_value=None):
    td_allowed = td_race._wait_for_rate_limit()
T("TwelveData full window returns False", td_allowed is False, f"Got {td_allowed!r}")
T("TwelveData full window does not exceed 8 entries", len(td_race._call_times) == 8,
  f"Got {len(td_race._call_times)} entries")

from coingecko_adapter import CoinGeckoAdapter as RealCoinGeckoAdapter
cg_race = RealCoinGeckoAdapter(api_key="fake")
for _ in range(30):
    cg_race._call_times.append(fixed_now - 5)
with patch("coingecko_adapter.time.time", return_value=fixed_now), \
     patch("coingecko_adapter.time.sleep", return_value=None):
    cg_allowed = cg_race._wait_for_rate_limit()
T("CoinGecko full window returns False", cg_allowed is False, f"Got {cg_allowed!r}")
T("CoinGecko full window does not exceed 30 entries", len(cg_race._call_times) == 30,
  f"Got {len(cg_race._call_times)} entries")


# ============================================================
# 13. Second-pass: WS relay volume=0 preserved
# ============================================================
S("WebSocket Relay — volume=0 preserved")

ws_vol = FinnhubWebSocketRelay(api_key="test", symbols_limit=50)
ws_vol._handle_message('{"type": "trade", "data": [{"s": "AAPL", "p": 150.0, "v": 0, "t": 1700000000000}]}')
ticks_v = ws_vol.drain_tick_buffer()
T("WS tick with volume=0 preserved (not None)",
  len(ticks_v) == 1 and ticks_v[0]["volume"] == 0.0,
  f"Got volume={ticks_v[0]['volume'] if ticks_v else 'NO TICK'}")

ws_vol._handle_message('{"type": "trade", "data": [{"s": "MSFT", "p": 400.0, "t": 1700000000000}]}')
ticks_v2 = ws_vol.drain_tick_buffer()
T("WS tick with missing volume → None",
  len(ticks_v2) == 1 and ticks_v2[0]["volume"] is None,
  f"Got volume={ticks_v2[0]['volume'] if ticks_v2 else 'NO TICK'}")


# ============================================================
# 14. Second-pass: TwelveData exception log doesn't leak API key
# ============================================================
S("TwelveDataAdapter — exception log sanitization")

td_bad = TwelveDataAdapter(api_key="secret-api-key")
with patch("twelve_data_adapter.requests.get", side_effect=RuntimeError("URL leaked apikey=SECRET123")), \
     patch("twelve_data_adapter.logger.warning") as td_warn:
    td_result = td_bad.fetch_quote("AAPL")

T("Exception path returns None", td_result is None)
T("Exception log emitted", td_warn.called, f"calls={td_warn.call_count}")
if td_warn.called:
    warn_args = td_warn.call_args[0]
    T("Exception log includes type name", "RuntimeError" in str(warn_args), str(warn_args))
    T("Exception log does not include raw API key",
      "SECRET123" not in str(warn_args) and "secret-api-key" not in str(warn_args),
      str(warn_args))


# ============================================================
# SUMMARY
# ============================================================
print(f"\n{'='*60}")
print(f"  RESULTS: {passed} passed, {failed} failed")
print(f"{'='*60}")
if errors:
    print("  Failed tests:")
    for e in errors:
        print(f"    - {e}")
sys.exit(1 if failed else 0)
