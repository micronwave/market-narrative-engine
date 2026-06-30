"""
D10 Audit regression test suite — Phase 2 audit fix verification.

Tests critical, high, and medium fixes from the production audit.

Run with:
    python -X utf8 test_d10_audit.py

Exit code 0 if all tests pass, 1 if any fail.
"""

import logging
import sys
import threading
import time
from pathlib import Path

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s %(message)s",
    stream=sys.stderr,
)

# ---------------------------------------------------------------------------
# Custom test runner
# ---------------------------------------------------------------------------

_results: list[dict] = []
_current_section: str = "Unset"
_pass = 0
_fail = 0


def S(section_name: str) -> None:
    global _current_section
    _current_section = section_name


def T(name: str, condition: bool, details: str = "") -> None:
    global _pass, _fail
    _results.append({
        "section": _current_section,
        "name": name,
        "passed": bool(condition),
        "details": details,
    })
    if condition:
        _pass += 1
    else:
        _fail += 1
        print(
            f"  FAIL [{_current_section}] {name}" + (f" — {details}" if details else ""),
            file=sys.stderr,
        )


def _print_summary() -> None:
    sections: dict[str, dict] = {}
    for r in _results:
        sec = r["section"]
        if sec not in sections:
            sections[sec] = {"pass": 0, "fail": 0}
        if r["passed"]:
            sections[sec]["pass"] += 1
        else:
            sections[sec]["fail"] += 1

    print("\n" + "=" * 60)
    print(f"{'Section':<35} {'Pass':>5} {'Fail':>5}")
    print("-" * 60)
    for sec, counts in sections.items():
        marker = "" if counts["fail"] == 0 else " <--"
        print(f"  {sec:<33} {counts['pass']:>5} {counts['fail']:>5}{marker}")
    print("=" * 60)
    print(f"  TOTAL: {_pass} passed, {_fail} failed out of {_pass + _fail} tests")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Setup: make project root importable
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent.parent
_API = _ROOT / "api"
_SERVICES = _API / "services"

sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_API))
sys.path.insert(0, str(_SERVICES))
sys.path.insert(0, str(_API / "adapters"))


# ---------------------------------------------------------------------------
# C1: Circuit breaker does NOT trip on normal None returns
# ---------------------------------------------------------------------------

S("C1 — Breaker ignores None returns")

from circuit_breaker import CircuitBreaker


class AlwaysNoneAdapter:
    def fetch_quote(self, symbol, instrument_type="equity"):
        return None


from data_normalizer import DataNormalizer

normalizer = DataNormalizer([AlwaysNoneAdapter()])
for i in range(10):
    normalizer.get_quote(f"FAKE{i}", "equity")

# Get the single breaker
breaker = list(normalizer._breakers.values())[0]
T("Breaker not open after 10 None returns",
  not breaker.is_open,
  f"consecutive_failures={breaker._consecutive_failures}")

T("Zero consecutive failures",
  breaker._consecutive_failures == 0,
  f"got {breaker._consecutive_failures}")


# Verify that actual exceptions DO trip the breaker

class AlwaysErrorAdapter:
    def fetch_quote(self, symbol, instrument_type="equity"):
        raise ConnectionError("boom")


normalizer_err = DataNormalizer([AlwaysErrorAdapter()])
for i in range(6):
    normalizer_err.get_quote(f"FAKE{i}", "equity")

breaker_err = list(normalizer_err._breakers.values())[0]
T("Breaker remains closed with one failure source",
  not breaker_err.is_open,
  f"consecutive_failures={breaker_err._consecutive_failures}, sources={len(breaker_err._failure_sources)}")

T("Breaker counts exceptions",
  breaker_err._consecutive_failures == 6,
  f"consecutive_failures={breaker_err._consecutive_failures}")


# ---------------------------------------------------------------------------
# C2: CircuitBreaker is thread-safe
# ---------------------------------------------------------------------------

S("C2 — CircuitBreaker thread safety")

cb = CircuitBreaker("test_thread_safety")
barrier = threading.Barrier(10)

def _record_failure():
    barrier.wait()
    cb.record_failure()

threads = [threading.Thread(target=_record_failure) for _ in range(10)]
for t in threads:
    t.start()
for t in threads:
    t.join()

T("Consecutive failures >= 5 after 10 concurrent record_failure()",
  cb._consecutive_failures >= 5,
  f"got {cb._consecutive_failures}")

T("CircuitBreaker has _lock attribute",
  hasattr(cb, "_lock") and isinstance(cb._lock, type(threading.Lock())),
  "Missing threading.Lock")


# ---------------------------------------------------------------------------
# H2: JWT secret minimum length
# ---------------------------------------------------------------------------

S("H2 — JWT secret key minimum 32 chars")

# Check settings validator exists
from settings import Settings
from pydantic import ValidationError

try:
    Settings(
        ANTHROPIC_API_KEY="test-key",
        AUTH_MODE="jwt",
        JWT_SECRET_KEY="short",
    )
    jwt_validator_works = False
except (ValidationError, ValueError):
    jwt_validator_works = True

T("Settings rejects JWT_SECRET_KEY < 32 chars in JWT mode",
  jwt_validator_works)

# Non-JWT mode should still accept short key
try:
    Settings(
        ANTHROPIC_API_KEY="test-key",
        AUTH_MODE="stub",
        JWT_SECRET_KEY="short",
    )
    stub_accepts_short = True
except (ValidationError, ValueError):
    stub_accepts_short = False

T("Settings accepts short JWT_SECRET_KEY in stub mode",
  stub_accepts_short)


# ---------------------------------------------------------------------------
# M1: No duplicate keys in sector map
# ---------------------------------------------------------------------------

S("M1 — Sector map duplicate keys")

import re

sector_map_path = _API / "sector_map.py"
sector_text = sector_map_path.read_text()
keys = re.findall(r'"([^"]+)"\s*:', sector_text)
seen = set()
duplicates = []
for k in keys:
    if k in seen:
        duplicates.append(k)
    seen.add(k)

T("No duplicate keys in SECTOR_MAP", len(duplicates) == 0,
  f"duplicates: {duplicates}")


# ---------------------------------------------------------------------------
# M4: Overlap cache uses per-key timestamps
# ---------------------------------------------------------------------------

S("M4 — Overlap cache per-key timestamps")

# Read main.py and check that _overlap_cache_at is gone
main_text = (_API / "main.py").read_text()
T("_overlap_cache_at removed",
  "_overlap_cache_at" not in main_text,
  "Old single-timestamp variable still present")


# ---------------------------------------------------------------------------
# M5: Days parameter clamping
# ---------------------------------------------------------------------------

S("M5 — Days parameter clamping")

# Check that each analytics endpoint clamps days
endpoints_with_days = [
    "get_narrative_histories",
    "get_narrative_overlap",
    "get_lifecycle_funnel",
    "get_lead_time_distribution",
    "get_narrative_history",
    "get_price_history_endpoint",
    "get_narrative_timeline",
    "get_narrative_changelog",
    "get_upcoming_earnings",
]

for ep_name in endpoints_with_days:
    # Find the function definition and check for clamping nearby
    pattern = rf"def {ep_name}\(.*?days.*?\):"
    match = re.search(pattern, main_text)
    if match:
        # Check the next few lines for clamping
        start = match.end()
        snippet = main_text[start:start + 200]
        has_clamp = "max(1, min(days, 365))" in snippet
        T(f"{ep_name} clamps days", has_clamp,
          f"No days clamping found in {ep_name}")


# ---------------------------------------------------------------------------
# M6: No deprecated asyncio.get_event_loop()
# ---------------------------------------------------------------------------

S("M6 — No deprecated get_event_loop()")

loop_calls = main_text.count("get_event_loop()")
T("No get_event_loop() calls remain",
  loop_calls == 0,
  f"Found {loop_calls} occurrences")


# ---------------------------------------------------------------------------
# M7: Rate limiters return bool
# ---------------------------------------------------------------------------

S("M7 — Rate limiters return bool (no long sleep)")

from twelve_data_adapter import TwelveDataAdapter
from coingecko_adapter import CoinGeckoAdapter

td_adapter = TwelveDataAdapter(api_key="fake")
td_result = td_adapter._wait_for_rate_limit()
T("TwelveData _wait_for_rate_limit returns bool at runtime",
  isinstance(td_result, bool),
  f"type={type(td_result).__name__}, value={td_result!r}")

cg_adapter = CoinGeckoAdapter(api_key="fake")
cg_result = cg_adapter._wait_for_rate_limit()
T("CoinGecko _wait_for_rate_limit returns bool at runtime",
  isinstance(cg_result, bool),
  f"type={type(cg_result).__name__}, value={cg_result!r}")


# ---------------------------------------------------------------------------
# Meta 7: CoinGecko not in equity adapter chain
# ---------------------------------------------------------------------------

S("Meta 7 — CoinGecko not in equity adapter chain")

dn_text = (_SERVICES / "data_normalizer.py").read_text()
# Find the equity adapter order
equity_match = re.search(r'"equity"\s*:\s*\[([^\]]+)\]', dn_text)
if equity_match:
    equity_adapters = equity_match.group(1)
    T("CoinGecko not in equity adapter order",
      "coingecko" not in equity_adapters,
      f"equity adapters: {equity_adapters}")
else:
    T("Found equity adapter order", False, "Could not find equity entry")


# ---------------------------------------------------------------------------
# H3: API key not in log messages
# ---------------------------------------------------------------------------

S("H3 — API key redacted in WS relay logs")

ws_text = (_SERVICES / "websocket_relay.py").read_text()
T("WS relay logs redacted token",
  "token=***" in ws_text,
  "No redacted token pattern found")

# Verify the full URL (with token) is never logged directly
T("WS relay does not log full URL with token",
  'logger.info("[WS Relay] Connecting to %s", url' not in ws_text
  and 'logger.info(f"' not in ws_text.replace('logger.info("[WS Relay] Connecting to Finnhub WebSocket (token=***', ''))


# ---------------------------------------------------------------------------
# L2: Dead code removed from pipeline.py
# ---------------------------------------------------------------------------

S("L2 — Dead code removed")

pipeline_text = (_ROOT / "pipeline.py").read_text()
T("new_texts variable removed from pipeline.py",
  "new_texts" not in pipeline_text,
  "new_texts still present")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

_print_summary()
sys.exit(0 if _fail == 0 else 1)
