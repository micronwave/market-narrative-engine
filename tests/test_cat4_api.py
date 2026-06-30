"""
Category 4 API Integration test suite.

Tests Finding 7-10 from final_solution_5.md / final_solution_5_b.md:
  - F7: EdgarIngester wiring — triple gate in ApiIngestionManager
  - F8: Startup key mismatch logging — MARKETAUX / NEWSDATA warnings
  - F9: Source field in /api/stocks — nq.source passed through _apply_normalized
  - F10: Price API usage logging — DataNormalizer calls increment_api_usage

Run with:
    python -X utf8 tests/test_cat4_api.py

Exit code 0 if all tests pass, 1 if any fail.
"""

import asyncio
import os
import sys
import tempfile
from datetime import datetime, timezone, date as _date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Path setup — must come before any project imports
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
_API      = str(ROOT / "api")
_SERVICES = str(ROOT / "api" / "services")
_ADAPTERS = str(ROOT / "api" / "adapters")
for _p in [str(ROOT), _API, _SERVICES, _ADAPTERS]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")
_tmp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
_tmp_db.close()
os.environ.setdefault("DB_PATH", _tmp_db.name)

# ---------------------------------------------------------------------------
# Minimal test runner
# ---------------------------------------------------------------------------

_results: list[dict] = []
_current_section: str = "Unset"
_pass = 0
_fail = 0


def S(section_name: str) -> None:
    global _current_section
    _current_section = section_name
    print(f"\n{'=' * 60}")
    print(f"  {section_name}")
    print(f"{'=' * 60}")


def T(name: str, condition: bool, details: str = "") -> None:
    global _pass, _fail
    _results.append({"section": _current_section, "name": name,
                     "passed": bool(condition), "details": details})
    if condition:
        _pass += 1
    else:
        _fail += 1
    mark = "PASS" if condition else "FAIL"
    det = f"  ({details})" if details else ""
    print(f"  [{mark}] {name}{det}")


def _report():
    seen: list[str] = []
    for r in _results:
        if r["section"] not in seen:
            seen.append(r["section"])
    print("\n" + "=" * 60)
    print(f"  {'Section':<44} {'Pass':>4}  {'Fail':>4}")
    print("-" * 60)
    for sec in seen:
        items = [r for r in _results if r["section"] == sec]
        p = sum(1 for r in items if r["passed"])
        f = sum(1 for r in items if not r["passed"])
        print(f"  {sec:<44} {p:>4} {f:>5}")
    print("=" * 60)
    print(f"  TOTAL: {_pass} passed, {_fail} failed out of {_pass + _fail} tests")
    print("=" * 60)


# ===========================================================================
# Finding 7-A — settings.py EDGAR fields
# ===========================================================================

S("F7-A: settings.py — EDGAR fields")

from settings import Settings

_fields = Settings.model_fields

T("EDGAR_TICKERS field exists",
  "EDGAR_TICKERS" in _fields)

T("EDGAR_TICKERS defaults to empty string",
  _fields.get("EDGAR_TICKERS") is not None and _fields["EDGAR_TICKERS"].default == "",
  f"default={_fields.get('EDGAR_TICKERS', 'MISSING')!r}")

T("EDGAR_EMAIL field exists",
  "EDGAR_EMAIL" in _fields)

T("EDGAR_EMAIL defaults to empty string",
  _fields.get("EDGAR_EMAIL") is not None and _fields["EDGAR_EMAIL"].default == "",
  f"default={_fields.get('EDGAR_EMAIL', 'MISSING')!r}")

T("EDGAR_COMPANY_NAME field exists",
  "EDGAR_COMPANY_NAME" in _fields)

T("ENABLE_EDGAR field exists",
  "ENABLE_EDGAR" in _fields)

T("ENABLE_EDGAR defaults to False",
  _fields.get("ENABLE_EDGAR") is not None and _fields["ENABLE_EDGAR"].default is False,
  f"default={_fields.get('ENABLE_EDGAR', 'MISSING')!r}")


# ===========================================================================
# Finding 7-B — api_ingesters.py gate (runtime wiring sanity)
# ===========================================================================

S("F7-B: ApiIngestionManager runtime wiring sanity")

import api_ingesters

T("ApiIngestionManager class exported",
  hasattr(api_ingesters, "ApiIngestionManager"))

T("RawDocument import available for base ingesters",
  hasattr(api_ingesters, "RawDocument"))


# ===========================================================================
# Finding 7-C — ApiIngestionManager gate (unit tests)
# ===========================================================================

S("F7-C: ApiIngestionManager — gate unit tests")

import api_ingesters


def _mock_settings(**overrides):
    """SimpleNamespace with only the fields ApiIngestionManager.__init__ reads."""
    defaults = dict(
        ENABLE_EDGAR=False,
        EDGAR_EMAIL="",
        EDGAR_TICKERS="",
        EDGAR_COMPANY_NAME="TestCo",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _build_manager(settings_ns):
    """Instantiate ApiIngestionManager with the three base ingesters mocked."""
    mock_repo = MagicMock()
    with patch("api_ingesters.MarketauxIngester", return_value=MagicMock()), \
         patch("api_ingesters.NewsdataIngester",  return_value=MagicMock()), \
         patch("api_ingesters.RedditIngester",    return_value=MagicMock()):
        return api_ingesters.ApiIngestionManager(settings_ns, mock_repo)


# Gate off: ENABLE_EDGAR=False
try:
    m = _build_manager(_mock_settings(ENABLE_EDGAR=False))
    T("ENABLE_EDGAR=False → 3 base ingesters",
      len(m._ingesters) == 3, f"got {len(m._ingesters)}")
except Exception as exc:
    T("ENABLE_EDGAR=False → 3 base ingesters", False, str(exc))

# Gate off: EDGAR_EMAIL missing
try:
    m = _build_manager(_mock_settings(ENABLE_EDGAR=True, EDGAR_EMAIL="", EDGAR_TICKERS="AAPL"))
    T("ENABLE_EDGAR=True, EDGAR_EMAIL='' → 3 ingesters (gate blocked)",
      len(m._ingesters) == 3, f"got {len(m._ingesters)}")
except Exception as exc:
    T("ENABLE_EDGAR=True, EDGAR_EMAIL='' → 3 ingesters (gate blocked)", False, str(exc))

# Gate off: EDGAR_TICKERS empty string
try:
    m = _build_manager(_mock_settings(ENABLE_EDGAR=True, EDGAR_EMAIL="t@x.com", EDGAR_TICKERS=""))
    T("ENABLE_EDGAR=True, EDGAR_TICKERS='' → 3 ingesters (gate blocked)",
      len(m._ingesters) == 3, f"got {len(m._ingesters)}")
except Exception as exc:
    T("ENABLE_EDGAR=True, EDGAR_TICKERS='' → 3 ingesters (gate blocked)", False, str(exc))

# Gate off: EDGAR_TICKERS whitespace-only (all entries stripped to empty)
try:
    m = _build_manager(_mock_settings(ENABLE_EDGAR=True, EDGAR_EMAIL="t@x.com", EDGAR_TICKERS=" , , "))
    T("EDGAR_TICKERS=' , , ' (whitespace only) → 3 ingesters",
      len(m._ingesters) == 3, f"got {len(m._ingesters)}")
except Exception as exc:
    T("EDGAR_TICKERS=' , , ' (whitespace only) → 3 ingesters", False, str(exc))

# Gate open: all three conditions met → 4 ingesters
try:
    mock_edgar_cls = MagicMock()
    mock_edgar_instance = MagicMock()
    mock_edgar_cls.return_value = mock_edgar_instance

    with patch("api_ingesters.MarketauxIngester", return_value=MagicMock()), \
         patch("api_ingesters.NewsdataIngester",  return_value=MagicMock()), \
         patch("api_ingesters.RedditIngester",    return_value=MagicMock()), \
         patch("ingester.EdgarIngester", mock_edgar_cls):
        manager = api_ingesters.ApiIngestionManager(
            _mock_settings(ENABLE_EDGAR=True, EDGAR_EMAIL="t@x.com", EDGAR_TICKERS="AAPL"),
            MagicMock(),
        )
    T("All EDGAR conditions met → 4 ingesters",
      len(manager._ingesters) == 4, f"got {len(manager._ingesters)}")
    T("4th ingester is the EdgarIngester instance",
      manager._ingesters[-1] is mock_edgar_instance,
      f"last type: {type(manager._ingesters[-1])}")
except Exception as exc:
    T("All EDGAR conditions met → 4 ingesters", False, str(exc))
    T("4th ingester is the EdgarIngester instance", False, str(exc))

# Ticker parsing: spaces around entries stripped, all three parsed correctly
try:
    mock_edgar_cls = MagicMock()
    mock_edgar_cls.return_value = MagicMock()

    with patch("api_ingesters.MarketauxIngester", return_value=MagicMock()), \
         patch("api_ingesters.NewsdataIngester",  return_value=MagicMock()), \
         patch("api_ingesters.RedditIngester",    return_value=MagicMock()), \
         patch("ingester.EdgarIngester", mock_edgar_cls):
        api_ingesters.ApiIngestionManager(
            _mock_settings(
                ENABLE_EDGAR=True,
                EDGAR_EMAIL="t@x.com",
                EDGAR_TICKERS=" AAPL , MSFT , NVDA ",
            ),
            MagicMock(),
        )

    passed_tickers = mock_edgar_cls.call_args.kwargs.get("tickers") or \
                     mock_edgar_cls.call_args[1].get("tickers")
    T("Ticker whitespace stripped: ['AAPL', 'MSFT', 'NVDA']",
      passed_tickers == ["AAPL", "MSFT", "NVDA"],
      f"got {passed_tickers}")
    T("Exactly 3 tickers parsed from 3-item CSV",
      len(passed_tickers) == 3, f"got {len(passed_tickers)}")
except Exception as exc:
    T("Ticker whitespace stripped: ['AAPL', 'MSFT', 'NVDA']", False, str(exc))
    T("Exactly 3 tickers parsed from 3-item CSV", False, str(exc))

# company_name and email forwarded correctly
try:
    mock_edgar_cls = MagicMock()
    mock_edgar_cls.return_value = MagicMock()

    with patch("api_ingesters.MarketauxIngester", return_value=MagicMock()), \
         patch("api_ingesters.NewsdataIngester",  return_value=MagicMock()), \
         patch("api_ingesters.RedditIngester",    return_value=MagicMock()), \
         patch("ingester.EdgarIngester", mock_edgar_cls):
        api_ingesters.ApiIngestionManager(
            _mock_settings(
                ENABLE_EDGAR=True,
                EDGAR_EMAIL="researcher@corp.com",
                EDGAR_TICKERS="AAPL",
                EDGAR_COMPANY_NAME="CorpIntelligence",
            ),
            MagicMock(),
        )

    kw = mock_edgar_cls.call_args.kwargs
    T("email kwarg forwarded to EdgarIngester",
      kw.get("email") == "researcher@corp.com",
      f"got {kw.get('email')!r}")
    T("company_name kwarg forwarded to EdgarIngester",
      kw.get("company_name") == "CorpIntelligence",
      f"got {kw.get('company_name')!r}")
except Exception as exc:
    T("email kwarg forwarded to EdgarIngester", False, str(exc))
    T("company_name kwarg forwarded to EdgarIngester", False, str(exc))


# ===========================================================================
# Finding 8 — Startup key mismatch logging (runtime behavior)
# ===========================================================================

S("F8: start_price_refresh mismatch logging behavior")

import api.app_legacy as app_legacy

with patch.object(app_legacy, "_discover_linked_tickers", return_value={}), \
     patch.object(app_legacy.finnhub, "is_enabled", return_value=False), \
     patch.object(app_legacy, "_background_tasks_enabled", return_value=False), \
     patch.object(app_legacy._API_SETTINGS, "ENABLE_MARKETAUX", True), \
     patch.object(app_legacy._API_SETTINGS, "MARKETAUX_API_KEY", ""), \
     patch.object(app_legacy._API_SETTINGS, "ENABLE_NEWSDATA", True), \
     patch.object(app_legacy._API_SETTINGS, "NEWSDATA_API_KEY", ""), \
     patch.object(app_legacy.logger, "info") as info_mock:
    asyncio.run(app_legacy.start_price_refresh())

_msgs = [" ".join(str(a) for a in c.args) for c in info_mock.call_args_list]
T("MARKETAUX mismatch warning emitted",
  any("MarketAux enabled but MARKETAUX_API_KEY not set — ingester will be inactive" in m for m in _msgs),
  str(_msgs))
T("NEWSDATA mismatch warning emitted",
  any("NewsData enabled but NEWSDATA_API_KEY not set — ingester will be inactive" in m for m in _msgs),
  str(_msgs))


# ===========================================================================
# Finding 9-A — source field: runtime contract
# ===========================================================================

S("F9-A: NormalizedQuote runtime contract")

from data_normalizer import NormalizedQuote

T("NormalizedQuote.source is typed as str in model fields",
  NormalizedQuote.model_fields.get("source") is not None
  and NormalizedQuote.model_fields["source"].annotation is str)


# ===========================================================================
# Finding 9-B — source field: functional tests
# ===========================================================================

S("F9-B: _apply_normalized behaviour (functional tests)")

from data_normalizer import NormalizedQuote

_TS = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_quote(symbol="AAPL", price=180.0, close=170.0, source="finnhub"):
    return NormalizedQuote(
        symbol=symbol,
        instrument_type="equity",
        price=price,
        close=close,
        timestamp=_TS,
        source=source,
        delay="realtime",
    )


# Replicate _apply_normalized — same logic as api/main.py
def _apply(sec: dict, nq) -> None:
    if nq is None:
        return
    sec["current_price"] = nq.price
    sec["source"] = nq.source
    if nq.close and nq.close != 0:
        sec["price_change_24h"] = round((nq.price - nq.close) / nq.close * 100, 2)
    else:
        sec["price_change_24h"] = None


# Basic: source and price populated
sec = {}
_apply(sec, _make_quote(source="twelve_data", price=180.0, close=170.0))
T('source="twelve_data" written to sec',
  sec.get("source") == "twelve_data", f"got {sec.get('source')!r}")
T("current_price written to sec",
  sec.get("current_price") == 180.0, f"got {sec.get('current_price')}")

# price_change_24h calculation
_expected = round((180.0 - 170.0) / 170.0 * 100, 2)
T("price_change_24h correctly computed",
  sec.get("price_change_24h") == _expected,
  f"expected={_expected}, got={sec.get('price_change_24h')}")

# nq=None: sec dict left completely unchanged
sec2 = {"current_price": 100.0, "symbol": "X"}
_apply(sec2, None)
T("nq=None: sec unchanged",
  sec2 == {"current_price": 100.0, "symbol": "X"}, f"sec={sec2}")

# close=0: price_change_24h=None
sec3 = {}
_apply(sec3, _make_quote(source="coingecko", close=0.0))
T("close=0 → price_change_24h is None",
  sec3.get("price_change_24h") is None,
  f"got {sec3.get('price_change_24h')}")
T("close=0 → source still written",
  sec3.get("source") == "coingecko", f"got {sec3.get('source')!r}")

# close=None: price_change_24h=None
sec4 = {}
_apply(sec4, NormalizedQuote(
    symbol="BTC-USD", instrument_type="crypto", price=60000.0, close=None,
    timestamp=_TS, source="coingecko", delay="realtime",
))
T("close=None → price_change_24h is None",
  sec4.get("price_change_24h") is None,
  f"got {sec4.get('price_change_24h')}")

# All four source values pass through
for _src in ("finnhub", "twelve_data", "coingecko", "yfinance"):
    _s: dict = {}
    _apply(_s, _make_quote(source=_src))
    T(f'source="{_src}" round-trips correctly',
      _s.get("source") == _src, f"got {_s.get('source')!r}")

# Multiple securities: each gets its own source
sec_a: dict = {}
sec_b: dict = {}
_apply(sec_a, _make_quote(source="finnhub",    price=100.0, close=90.0))
_apply(sec_b, _make_quote(source="coingecko",  price=200.0, close=180.0))
T("Two securities get independent source fields",
  sec_a.get("source") == "finnhub" and sec_b.get("source") == "coingecko",
  f"sec_a={sec_a.get('source')!r}, sec_b={sec_b.get('source')!r}")


# ===========================================================================
# Finding 10-A — DataNormalizer usage logging (runtime smoke)
# ===========================================================================

S("F10-A: DataNormalizer runtime usage-log smoke")

from data_normalizer import DataNormalizer

class _NullAdapter:
    def fetch_quote(self, symbol, instrument_type="equity"):
        return None

dn_smoke = DataNormalizer(adapters=[_NullAdapter()], repository=None)
T("repository defaults to None without errors", dn_smoke._repository is None)
T("get_quote returns None cleanly when adapter misses",
  dn_smoke.get_quote("MISSING") is None)


# ===========================================================================
# Finding 10-B — DataNormalizer usage logging (unit tests)
# ===========================================================================

S("F10-B: DataNormalizer — usage logging unit tests")

from data_normalizer import DataNormalizer, NormalizedQuote

_NOW = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
_TODAY = _date.today().isoformat()


def _fake_adapter(class_name: str, return_value=None, raises=None):
    """Create a minimal adapter whose type().__name__ == class_name."""
    def fetch_quote(self, symbol, instrument_type="equity"):
        if raises is not None:
            raise raises
        return return_value
    return type(class_name, (), {"fetch_quote": fetch_quote})()


def _quote(source="finnhub"):
    return NormalizedQuote(
        symbol="AAPL", instrument_type="equity", price=150.0,
        timestamp=_NOW, source=source, delay="realtime",
    )


# ── repository=None (default): no error, quote returned ──────────────────

try:
    dn = DataNormalizer(adapters=[_fake_adapter("FinnhubAdapter", _quote())])
    result = dn.get_quote("AAPL")
    T("repository=None: quote returned without error",
      result is not None and result.price == 150.0, f"result={result}")
    T("repository=None: _repository attribute is None",
      dn._repository is None)
except Exception as exc:
    T("repository=None: quote returned without error", False, str(exc))
    T("repository=None: _repository attribute is None", False, str(exc))


# ── successful fetch → increment_api_usage called ─────────────────────────

try:
    mock_repo = MagicMock()
    dn = DataNormalizer(
        adapters=[_fake_adapter("FinnhubAdapter", _quote("finnhub"))],
        repository=mock_repo,
    )
    result = dn.get_quote("AAPL")

    T("get_quote returns quote",
      result is not None and result.source == "finnhub")
    T("increment_api_usage called exactly once",
      mock_repo.increment_api_usage.call_count == 1,
      f"calls={mock_repo.increment_api_usage.call_count}")

    _args = mock_repo.increment_api_usage.call_args[0]
    T("adapter_name='finnhub' passed",
      _args[0] == "finnhub", f"got {_args[0]!r}")
    T("date=today's ISO string passed",
      _args[1] == _TODAY, f"got {_args[1]!r}")
    T("limit=0 passed",
      _args[2] == 0, f"got {_args[2]!r}")
except Exception as exc:
    T("get_quote returns quote", False, str(exc))
    T("increment_api_usage called exactly once", False, str(exc))
    T("adapter_name='finnhub' passed", False, str(exc))
    T("date=today's ISO string passed", False, str(exc))
    T("limit=0 passed", False, str(exc))


# ── adapter returns None → NO logging ────────────────────────────────────

try:
    mock_repo = MagicMock()
    dn = DataNormalizer(
        adapters=[_fake_adapter("FinnhubAdapter", None)],  # returns None
        repository=mock_repo,
    )
    result = dn.get_quote("UNKNOWN")
    T("adapter returns None → get_quote returns None",
      result is None)
    T("adapter returns None → increment_api_usage NOT called",
      mock_repo.increment_api_usage.call_count == 0,
      f"calls={mock_repo.increment_api_usage.call_count}")
except Exception as exc:
    T("adapter returns None → get_quote returns None", False, str(exc))
    T("adapter returns None → increment_api_usage NOT called", False, str(exc))


# ── increment_api_usage raises → quote still returned ────────────────────

try:
    mock_repo = MagicMock()
    mock_repo.increment_api_usage.side_effect = RuntimeError("DB locked")
    dn = DataNormalizer(
        adapters=[_fake_adapter("FinnhubAdapter", _quote())],
        repository=mock_repo,
    )
    result = dn.get_quote("AAPL")
    T("increment_api_usage raises → quote still returned (exception swallowed)",
      result is not None and result.price == 150.0, f"result={result}")
except Exception as exc:
    T("increment_api_usage raises → quote still returned (exception swallowed)", False, str(exc))


# ── adapter name mapping ──────────────────────────────────────────────────

_adapter_name_cases = [
    ("FinnhubAdapter",    "finnhub"),
    ("TwelveDataAdapter", "twelve_data"),
    ("CoinGeckoAdapter",  "coingecko"),
]
for _cls_name, _expected_key in _adapter_name_cases:
    try:
        mock_repo = MagicMock()
        dn = DataNormalizer(
            adapters=[_fake_adapter(_cls_name, _quote(source=_expected_key))],
            repository=mock_repo,
        )
        dn.get_quote("AAPL")
        _logged_name = mock_repo.increment_api_usage.call_args[0][0]
        T(f"{_cls_name} maps to '{_expected_key}' in usage log",
          _logged_name == _expected_key, f"got {_logged_name!r}")
    except Exception as exc:
        T(f"{_cls_name} maps to '{_expected_key}' in usage log", False, str(exc))


# ── first adapter fails → second logs, not first ─────────────────────────

try:
    mock_repo = MagicMock()
    dn = DataNormalizer(
        adapters=[
            _fake_adapter("FinnhubAdapter",    raises=ConnectionError("timeout")),
            _fake_adapter("TwelveDataAdapter", _quote(source="twelve_data")),
        ],
        repository=mock_repo,
    )
    result = dn.get_quote("AAPL")
    T("fallback adapter used when first fails",
      result is not None and result.source == "twelve_data",
      f"source={result.source if result else None!r}")
    T("usage logged for successful backup adapter only",
      mock_repo.increment_api_usage.call_count == 1,
      f"calls={mock_repo.increment_api_usage.call_count}")
    _logged_name = mock_repo.increment_api_usage.call_args[0][0]
    T("backup adapter name 'twelve_data' logged (not failed 'finnhub')",
      _logged_name == "twelve_data", f"got {_logged_name!r}")
except Exception as exc:
    T("fallback adapter used when first fails", False, str(exc))
    T("usage logged for successful backup adapter only", False, str(exc))
    T("backup adapter name 'twelve_data' logged (not failed 'finnhub')", False, str(exc))


# ── get_quotes_batch: each successful symbol logs once ──────────────────

try:
    mock_repo = MagicMock()
    dn = DataNormalizer(
        adapters=[_fake_adapter("FinnhubAdapter", _quote())],
        repository=mock_repo,
    )
    results = dn.get_quotes_batch(["AAPL", "MSFT", "NVDA"])
    T("get_quotes_batch returns all 3 symbols",
      len(results) == 3, f"got {len(results)}")
    T("get_quotes_batch → increment_api_usage called 3 times (one per symbol)",
      mock_repo.increment_api_usage.call_count == 3,
      f"calls={mock_repo.increment_api_usage.call_count}")
    _all_names = {c[0][0] for c in mock_repo.increment_api_usage.call_args_list}
    T("all batch log calls use 'finnhub' adapter name",
      _all_names == {"finnhub"}, f"got {_all_names}")
except Exception as exc:
    T("get_quotes_batch returns all 3 symbols", False, str(exc))
    T("get_quotes_batch → increment_api_usage called 3 times (one per symbol)", False, str(exc))
    T("all batch log calls use 'finnhub' adapter name", False, str(exc))


# ── batch with some failures: only successes logged ──────────────────────

try:
    _call_count = {"n": 0}

    class _SometimesFailing:
        def fetch_quote(self, symbol, instrument_type="equity"):
            _call_count["n"] += 1
            if symbol == "FAIL":
                return None  # not found — no logging expected
            return _quote()

    # Give it a class name that maps to finnhub
    _SometimesFailing.__name__ = "FinnhubAdapter"

    mock_repo = MagicMock()
    dn = DataNormalizer(adapters=[_SometimesFailing()], repository=mock_repo)
    results = dn.get_quotes_batch(["AAPL", "FAIL", "MSFT"])

    T("batch with one miss: 3 results returned",
      len(results) == 3, f"got {len(results)}")
    T("FAIL symbol returns None in results",
      results.get("FAIL") is None, f"got {results.get('FAIL')}")
    T("successful symbols logged (2 calls, not 3)",
      mock_repo.increment_api_usage.call_count == 2,
      f"calls={mock_repo.increment_api_usage.call_count}")
except Exception as exc:
    T("batch with one miss: 3 results returned", False, str(exc))
    T("FAIL symbol returns None in results", False, str(exc))
    T("successful symbols logged (2 calls, not 3)", False, str(exc))


# ===========================================================================
# Finding 10-C — _init_data_normalizer_repo startup hook (runtime)
# ===========================================================================

S("F10-C: _init_data_normalizer_repo startup hook runtime")

app_legacy.data_normalizer._repository = None
fake_repo = MagicMock()
with patch.object(app_legacy, "get_repo", return_value=fake_repo):
    asyncio.run(app_legacy._init_data_normalizer_repo())
T("startup hook assigns repository when available",
  app_legacy.data_normalizer._repository is fake_repo)

app_legacy.data_normalizer._repository = fake_repo
with patch.object(app_legacy, "get_repo", return_value=None):
    asyncio.run(app_legacy._init_data_normalizer_repo())
T("startup hook keeps existing repository when get_repo is None",
  app_legacy.data_normalizer._repository is fake_repo)


# ---------------------------------------------------------------------------
# Final report
# ---------------------------------------------------------------------------

_report()
Path(_tmp_db.name).unlink(missing_ok=True)
sys.exit(0 if _fail == 0 else 1)
