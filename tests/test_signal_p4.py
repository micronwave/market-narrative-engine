"""
Signal Redesign Phase 4 — Catalyst Anchoring Tests

Section 1: FOMC dates (2 tests)
  SP4-FOMC-1: get_fomc_dates() returns non-empty list of valid date strings
  SP4-FOMC-2: get_fomc_dates() includes dates in 2026

Section 2: Macro alignment (1 test)
  SP4-MACRO-1: compute_macro_alignment("bearish", {}) returns 0.0

Section 3: Catalyst proximity (3 tests)
  SP4-CAT-1: no catalyst within 14 days -> has_near_catalyst=False, proximity_score=0.0
  SP4-CAT-2: earnings within 7 days -> has_near_catalyst=True
  SP4-CAT-3: proximity_score decay — 7-day catalyst > 12-day catalyst

Section 4: FRED resilience (1 test)
  SP4-FRED-1: get_fred_series returns empty list on network failure

Section 5: Schema (1 test)
  SP4-SCH-1: new narrative columns exist after migrate()

Section 6: Settings (1 test)
  SP4-SET-1: FRED_API_KEY, CATALYST_LOOKFORWARD_DAYS, FRED_CACHE_TTL_HOURS exist

Section 7: Pipeline integration (1 test)
  SP4-INT-1: Step 19.1 completes without error (even if FRED unreachable)
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_ADAPTER_PATH = str(Path(__file__).parent.parent / "api" / "adapters")
if _ADAPTER_PATH not in sys.path:
    sys.path.insert(0, _ADAPTER_PATH)
_SERVICE_PATH = str(Path(__file__).parent.parent / "api" / "services")
if _SERVICE_PATH not in sys.path:
    sys.path.insert(0, _SERVICE_PATH)

from catalyst_service import (
    get_fomc_dates,
    compute_macro_alignment,
    compute_catalyst_proximity,
    get_fred_series,
)
from repository import SqliteRepository

# ---------------------------------------------------------------------------
# Test runner helpers
# ---------------------------------------------------------------------------
_results = []


def S(section: str):
    print(f"\n--- {section} ---")


def T(name: str, condition: bool, details: str = ""):
    _results.append((name, condition))
    marker = "\u2713" if condition else "\u2717"
    msg = f"  [{marker}] {name}"
    if details and not condition:
        msg += f"\n      details: {details}"
    elif details and condition:
        msg += f"  ({details})"
    print(msg)


_tmp_db_paths: list[str] = []


def _make_repo() -> SqliteRepository:
    f = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    f.close()
    _tmp_db_paths.append(f.name)
    repo = SqliteRepository(f.name)
    repo.migrate()
    return repo


class _FakeRequestsResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


# ---------------------------------------------------------------------------
# Section 1: FOMC dates
# ---------------------------------------------------------------------------
S("Section 1: FOMC dates")

dates = get_fomc_dates()
T("SP4-FOMC-1: non-empty list of valid date strings",
  len(dates) > 0 and all(len(d) == 10 and d[4] == "-" for d in dates),
  f"count={len(dates)}")

has_2026 = any(d.startswith("2026") for d in dates)
T("SP4-FOMC-2: includes dates in 2026", has_2026)

# ---------------------------------------------------------------------------
# Section 2: Macro alignment
# ---------------------------------------------------------------------------
S("Section 2: Macro alignment")

result_empty = compute_macro_alignment("bearish", {})
T("SP4-MACRO-1: bearish + empty data = 0.0", result_empty == 0.0, f"got={result_empty}")

# ---------------------------------------------------------------------------
# Section 3: Catalyst proximity
# ---------------------------------------------------------------------------
S("Section 3: Catalyst proximity")

# SP4-CAT-1: No catalyst within 14 days
# Mock earnings to return nothing, and set FOMC dates far in future
with patch("catalyst_service.get_fomc_dates", return_value=["2099-01-01"]):
    with patch("catalyst_service.get_fred_series", return_value=[]):
        with patch("api.earnings_service.get_upcoming_earnings", return_value=[]):
            cat1 = compute_catalyst_proximity("FAKE", "neutral", [])
T("SP4-CAT-1: no catalyst -> has_near_catalyst=False, proximity_score=0.0",
  cat1["has_near_catalyst"] is False and cat1["proximity_score"] == 0.0,
  f"has_near={cat1['has_near_catalyst']}, prox={cat1['proximity_score']}")

# SP4-CAT-2: Earnings within 7 days -> has_near_catalyst=True
mock_earnings = [{"ticker": "AAPL", "earnings_date": (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%d"), "days_until": 3}]
with patch("catalyst_service.get_fomc_dates", return_value=["2099-01-01"]):
    with patch("catalyst_service.get_fred_series", return_value=[]):
        with patch("api.earnings_service.get_upcoming_earnings", return_value=mock_earnings):
            cat2 = compute_catalyst_proximity("AAPL", "bullish", [])
T("SP4-CAT-2: earnings in 3 days -> has_near_catalyst=True",
  cat2["has_near_catalyst"] is True and cat2["catalyst_type"] == "earnings",
  f"has_near={cat2['has_near_catalyst']}, type={cat2['catalyst_type']}")

# SP4-CAT-3: Proximity score decay — 7-day should score higher than 12-day
mock_earn_7d = [{"ticker": "MSFT", "earnings_date": "X", "days_until": 7}]
mock_earn_12d = [{"ticker": "MSFT", "earnings_date": "X", "days_until": 12}]
with patch("catalyst_service.get_fomc_dates", return_value=["2099-01-01"]):
    with patch("catalyst_service.get_fred_series", return_value=[]):
        with patch("api.earnings_service.get_upcoming_earnings", return_value=mock_earn_7d):
            cat3a = compute_catalyst_proximity("MSFT", "neutral", [])
        with patch("api.earnings_service.get_upcoming_earnings", return_value=mock_earn_12d):
            cat3b = compute_catalyst_proximity("MSFT", "neutral", [])
T("SP4-CAT-3: 7-day catalyst scores higher than 12-day",
  cat3a["proximity_score"] > cat3b["proximity_score"],
  f"7d={cat3a['proximity_score']}, 12d={cat3b['proximity_score']}")

# ---------------------------------------------------------------------------
# Section 4: FRED resilience
# ---------------------------------------------------------------------------
S("Section 4: FRED resilience")

# Mock urllib to raise an exception
with patch("urllib.request.urlopen", side_effect=Exception("network error")):
    # Clear any cached data first
    import catalyst_service as _cs
    _cs._fred_cache.clear()
    fred_result = get_fred_series("FAKESERIES", lookback_days=30)
T("SP4-FRED-1: returns empty list on network failure",
  fred_result == [], f"got={fred_result}")

# ---------------------------------------------------------------------------
# Section 5: Schema
# ---------------------------------------------------------------------------
S("Section 5: Schema")

repo = _make_repo()
with repo._get_conn() as conn:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(narratives)").fetchall()}
expected_cols = {"catalyst_proximity_score", "days_to_catalyst", "catalyst_type", "macro_alignment"}
missing = expected_cols - cols
T("SP4-SCH-1: new narrative columns exist after migrate()",
  len(missing) == 0, f"missing={missing}")

# ---------------------------------------------------------------------------
# Section 6: Settings
# ---------------------------------------------------------------------------
S("Section 6: Settings")

from settings import Settings
# Check that the fields exist with correct defaults via the model fields
fields = Settings.model_fields
has_fred_key = "FRED_API_KEY" in fields
has_lookforward = "CATALYST_LOOKFORWARD_DAYS" in fields
has_cache_ttl = "FRED_CACHE_TTL_HOURS" in fields
defaults_ok = (
    fields["FRED_API_KEY"].default == ""
    and fields["CATALYST_LOOKFORWARD_DAYS"].default == 14
    and fields["FRED_CACHE_TTL_HOURS"].default == 6
)
T("SP4-SET-1: settings exist with correct defaults",
  has_fred_key and has_lookforward and has_cache_ttl and defaults_ok,
  f"FRED_API_KEY={has_fred_key}, LOOKFORWARD={has_lookforward}, CACHE_TTL={has_cache_ttl}, defaults_ok={defaults_ok}")

# ---------------------------------------------------------------------------
# Section 7: Pipeline integration
# ---------------------------------------------------------------------------
S("Section 7: Pipeline integration")

# Test that Step 19.1 runs without error on a repo with narratives
repo2 = _make_repo()
from datetime import datetime as dt
nid = "test-catalyst-narrative"
repo2.insert_narrative({
    "narrative_id": nid,
    "name": "Test Catalyst Narrative",
    "stage": "Growing",
    "created_at": dt.now(timezone.utc).isoformat(),
    "last_updated_at": dt.now(timezone.utc).isoformat(),
    "linked_assets": json.dumps([{"ticker": "AAPL", "asset_name": "Apple Inc", "similarity_score": 0.8}]),
    "suppressed": 0,
    "document_count": 5,
})
# Insert a signal for this narrative
repo2.upsert_narrative_signal({
    "narrative_id": nid,
    "direction": "bullish",
    "confidence": 0.7,
    "timeframe": "near_term",
    "magnitude": "significant",
    "certainty": "probable",
    "affected_sectors": json.dumps(["Technology"]),
})

step_ok = False
try:
    from catalyst_service import compute_catalyst_proximity as _ccp
    active = repo2.get_all_active_narratives()
    for narrative in active:
        linked_raw = narrative.get("linked_assets")
        if not linked_raw:
            continue
        assets = json.loads(linked_raw)
        signal = repo2.get_narrative_signal(narrative["narrative_id"])
        direction = signal.get("direction", "neutral") if signal else "neutral"
        sectors = json.loads(signal.get("affected_sectors", "[]")) if signal else []
        for asset in assets:
            ticker = asset.get("ticker", "")
            if not ticker or ticker.startswith("TOPIC:"):
                continue
            # Mock external calls to avoid real network
            with patch("catalyst_service.get_fred_series", return_value=[]):
                with patch("api.earnings_service.get_upcoming_earnings", return_value=[]):
                    result = _ccp(ticker, direction, sectors)
            repo2.update_narrative(narrative["narrative_id"], {
                "catalyst_proximity_score": result["proximity_score"],
                "days_to_catalyst": result.get("days_to_earnings") or result.get("days_to_fomc"),
                "catalyst_type": result["catalyst_type"],
                "macro_alignment": result["macro_alignment"],
            })
    step_ok = True
except Exception as exc:
    step_ok = False
    print(f"      error: {exc}")

T("SP4-INT-1: Step 19.1 completes without error", step_ok)

# ---------------------------------------------------------------------------
# Section 8: Adapter parser/error realism (no network)
# ---------------------------------------------------------------------------
S("Section 8: Adapter parser and error realism")

from twelve_data_adapter import TwelveDataAdapter  # noqa: E402
from coingecko_adapter import CoinGeckoAdapter  # noqa: E402

td = TwelveDataAdapter(api_key="demo-key")
with patch.object(td, "_wait_for_rate_limit", return_value=True), \
     patch("twelve_data_adapter.requests.get", return_value=_FakeRequestsResponse(200, {
         "symbol": "AAPL",
         "datetime": "2026-04-01 15:30:00",
         "open": "100.0",
         "high": "101.5",
         "low": "99.8",
         "close": "100.7",
         "volume": "123456",
     })):
    td_quote = td.fetch_quote("AAPL", instrument_type="equity")
T("SP4-ADP-1: TwelveData parses realistic quote payload",
  td_quote is not None and td_quote.source == "twelve_data" and td_quote.price == 100.7,
  f"quote={td_quote}")

with patch.object(td, "_wait_for_rate_limit", return_value=True), \
     patch("twelve_data_adapter.requests.get", return_value=_FakeRequestsResponse(200, {"code": 400, "message": "bad symbol"})):
    td_error = td.fetch_quote("BAD", instrument_type="equity")
T("SP4-ADP-2: TwelveData returns None for provider error payload", td_error is None, f"got={td_error!r}")

with patch.object(td, "_wait_for_rate_limit", return_value=True), \
     patch("twelve_data_adapter.requests.get", return_value=_FakeRequestsResponse(200, {"symbol": "AAPL", "close": None})):
    td_partial = td.fetch_quote("AAPL", instrument_type="equity")
T("SP4-ADP-3: TwelveData returns None for partial payload without close", td_partial is None, f"got={td_partial!r}")

with patch.object(td, "_wait_for_rate_limit", return_value=True), \
     patch("twelve_data_adapter.requests.get", return_value=_FakeRequestsResponse(200, {"symbol": "AAPL", "datetime": "bad-ts", "close": "100.0"})):
    td_bad_ts = td.fetch_quote("AAPL", instrument_type="equity")
T("SP4-ADP-4: TwelveData tolerates malformed datetime and still returns quote",
  td_bad_ts is not None and td_bad_ts.price == 100.0,
  f"quote={td_bad_ts}")

cg = CoinGeckoAdapter(api_key="demo-key")
with patch.object(cg, "_wait_for_rate_limit", return_value=True), \
     patch("coingecko_adapter.requests.get", return_value=_FakeRequestsResponse(200, {"bitcoin": {"usd": 64000.5, "usd_24h_vol": 999999.0}})):
    cg_quote = cg.fetch_quote("BINANCE:BTCUSDT", instrument_type="crypto")
T("SP4-ADP-5: CoinGecko parses realistic payload with symbol normalization",
  cg_quote is not None and cg_quote.source == "coingecko" and cg_quote.price == 64000.5,
  f"quote={cg_quote}")

with patch.object(cg, "_wait_for_rate_limit", return_value=True), \
     patch("coingecko_adapter.requests.get", return_value=_FakeRequestsResponse(200, {})):
    cg_missing = cg.fetch_quote("BTC", instrument_type="crypto")
T("SP4-ADP-6: CoinGecko returns None on empty provider payload", cg_missing is None, f"got={cg_missing!r}")

with patch.object(cg, "_wait_for_rate_limit", return_value=True), \
     patch("coingecko_adapter.requests.get", return_value=_FakeRequestsResponse(200, {"bitcoin": {"usd_24h_vol": 12.0}})):
    cg_partial = cg.fetch_quote("BTC", instrument_type="crypto")
T("SP4-ADP-7: CoinGecko returns None for partial payload without usd", cg_partial is None, f"got={cg_partial!r}")

with patch("coingecko_adapter.requests.get") as cg_get_mock:
    cg_unknown = cg.fetch_quote("UNKNOWNCOIN", instrument_type="crypto")
T("SP4-ADP-8: CoinGecko skips unsupported symbol without HTTP call",
  cg_unknown is None and not cg_get_mock.called,
  f"got={cg_unknown!r}, called={cg_get_mock.called}")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
passed = sum(1 for _, ok in _results if ok)
total = len(_results)
print(f"Phase 4 results: {passed}/{total} passed")
for _tp in _tmp_db_paths:
    Path(_tp).unlink(missing_ok=True)
if passed < total:
    print("FAILED:")
    for name, ok in _results:
        if not ok:
            print(f"  - {name}")
    sys.exit(1)
else:
    print("All Phase 4 tests passed.")
