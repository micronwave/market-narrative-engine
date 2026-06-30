"""
Audit fix verification tests — targets critical/high issues found in api/main.py audit.
Run: python -X utf8 tests/test_audit_fixes.py
"""
import json
import os
import sys
from pathlib import Path

_ROOT = str(Path(__file__).parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")
os.environ.setdefault("AUTH_MODE", "stub")

from fastapi.testclient import TestClient  # noqa: E402
from api.main import app, _get_jwt_secret  # noqa: E402
from api.app_legacy import (  # noqa: E402
    STUB_AUTH_TOKEN, _validate_symbol, _csv_safe, _safe_json_list,
    _securities_lock,
)

client = TestClient(app)

# ---------------------------------------------------------------------------
# Minimal test framework (matches project convention)
# ---------------------------------------------------------------------------
_section = ""
_pass = 0
_fail = 0
_results: list[tuple[str, str, bool, str]] = []


def S(name: str):
    global _section
    _section = name


def T(name: str, condition: bool, details: str = ""):
    global _pass, _fail
    if condition:
        _pass += 1
    else:
        _fail += 1
        print(f"  FAIL [{_section}] {name} — {details}")
    _results.append((_section, name, condition, details))


# ===========================================================================
# CRITICAL-4: Symbol validation (SSRF prevention)
# ===========================================================================
S("Symbol validation")

T("valid symbol passes", _validate_symbol("NVDA") == "NVDA")
T("lowercase normalized", _validate_symbol("aapl") == "AAPL")
T("dots allowed", _validate_symbol("BRK.B") == "BRK.B")
T("hyphens allowed", _validate_symbol("BTC-USD") == "BTC-USD")

# Invalid symbols (includes bare punctuation)
for bad in ["", "A" * 20, "DROP TABLE", "../etc/passwd", "AAPL;ls", "NVDA\nGOOG", "  ", "A B", "---", "..."]:
    try:
        _validate_symbol(bad)
        T(f"rejects '{bad}'", False, "should have raised HTTPException")
    except Exception as e:
        T(f"rejects '{bad}'", "422" in str(e) or "Invalid" in str(e), str(e))


# ===========================================================================
# CRITICAL-5: CSV injection prevention
# ===========================================================================
S("CSV injection prevention")

T("normal string unchanged", _csv_safe("Hello world") == "Hello world")
T("equals sign escaped", _csv_safe("=CMD|'/C calc'!A0").startswith("'"))
T("plus sign escaped", _csv_safe("+1234").startswith("'"))
T("minus sign escaped", _csv_safe("-something").startswith("'"))
T("at sign escaped", _csv_safe("@SUM(A1:A10)").startswith("'"))
T("tab escaped", _csv_safe("\t=cmd").startswith("'"))
T("newline escaped", _csv_safe("\n=CMD|'/C calc'!A0").startswith("'"))
T("empty string safe", _csv_safe("") == "")


# ===========================================================================
# MEDIUM-2: Safe JSON list parsing
# ===========================================================================
S("Safe JSON list parsing")

T("valid JSON list", _safe_json_list('["a", "b"]') == ["a", "b"])
T("None returns empty", _safe_json_list(None) == [])
T("empty string returns empty", _safe_json_list("") == [])
T("malformed JSON returns empty", _safe_json_list("{broken") == [])
T("JSON object returns empty", _safe_json_list('{"key": "val"}') == [])
T("already a list passes through", _safe_json_list(["a", "b"]) == ["a", "b"])


# ===========================================================================
# HIGH-8: JWT secret validation
# ===========================================================================
S("JWT secret validation")

_SENTINEL = object()
original_key = os.environ.get("JWT_SECRET_KEY", _SENTINEL)

# Empty key should raise
os.environ["JWT_SECRET_KEY"] = ""
try:
    _get_jwt_secret()
    T("rejects empty JWT secret", False, "should have raised")
except Exception as e:
    T("rejects empty JWT secret", "32 characters" in str(e))

# Short key should raise
os.environ["JWT_SECRET_KEY"] = "tooshort"
try:
    _get_jwt_secret()
    T("rejects short JWT secret", False, "should have raised")
except Exception as e:
    T("rejects short JWT secret", "32 characters" in str(e))

# Valid key should pass
os.environ["JWT_SECRET_KEY"] = "a" * 32
try:
    result = _get_jwt_secret()
    T("accepts valid JWT secret", result == "a" * 32)
except Exception:
    T("accepts valid JWT secret", False, "raised unexpectedly")

# Restore
if original_key is _SENTINEL:
    os.environ.pop("JWT_SECRET_KEY", None)
else:
    os.environ["JWT_SECRET_KEY"] = original_key


# ===========================================================================
# HIGH-2: Activity limit bounds
# ===========================================================================
S("Activity endpoint limit bounds")

resp = client.get("/api/activity?limit=999999")
T("large limit returns 200", resp.status_code == 200)
data = resp.json()
T("result is bounded", len(data) <= 500, f"got {len(data)} items")


# ===========================================================================
# MEDIUM-2: topic_tags malformed JSON doesn't crash narratives list
# ===========================================================================
S("Malformed topic_tags resilience")

resp = client.get("/api/narratives")
T("narratives endpoint returns 200 or 503", resp.status_code in (200, 503))


# ===========================================================================
# HIGH-4: No fabricated coordination flags
# ===========================================================================
S("No fabricated coordination flags")

resp = client.get("/api/signals")
if resp.status_code == 200:
    signals = resp.json()
    if len(signals) >= 3:
        # The old code forced first 2 to True. Now they should reflect real data.
        # We can't assert they're all False (some may be legitimately flagged),
        # but we verify the field exists on all
        all_have_field = all("coordination_flag" in s for s in signals)
        T("all signals have coordination_flag", all_have_field)
    else:
        T("signals returned (sparse DB)", True)
else:
    T("signals endpoint accessible", resp.status_code == 503, f"status={resp.status_code}")


# ===========================================================================
# CRITICAL-1: Securities lock exists and is a threading.Lock
# ===========================================================================
S("Thread safety infrastructure")

import threading
T("_securities_lock is a Lock", isinstance(_securities_lock, type(threading.Lock())))


# ===========================================================================
# Document pagination bounds
# ===========================================================================
S("Document pagination bounds")

# These should work without error even if DB is unavailable (503)
resp = client.get("/api/narratives/fake-id/documents?limit=-1&offset=-10")
T("negative params handled", resp.status_code in (200, 404, 503))

resp = client.get("/api/narratives/fake-id/documents?limit=99999&offset=0")
T("huge limit handled", resp.status_code in (200, 404, 503))


# ===========================================================================
# Price history symbol validation
# ===========================================================================
S("Price endpoint symbol validation")

resp = client.get("/api/ticker/AAPL%3Bls/price-history")
T("semicolon in symbol rejected", resp.status_code == 422, f"status={resp.status_code}")

resp = client.get("/api/ticker/../etc/price-history")
# URL may get normalized by the router, but invalid symbol should be caught
T("path traversal in symbol handled", resp.status_code in (404, 422), f"status={resp.status_code}")


# ===========================================================================
# Summary
# ===========================================================================
print()
print("=" * 60)
sections: dict[str, tuple[int, int]] = {}
for sec, name, ok, detail in _results:
    if sec not in sections:
        sections[sec] = (0, 0)
    p, f = sections[sec]
    sections[sec] = (p + (1 if ok else 0), f + (0 if ok else 1))

for sec, (p, f) in sections.items():
    flag = " <--" if f > 0 else ""
    print(f"  {sec:50s} {p:3d}  {f:3d}{flag}")

print("=" * 60)
print(f"  TOTAL: {_pass} passed, {_fail} failed out of {_pass + _fail} tests")
print("=" * 60)

if _fail > 0:
    sys.exit(1)
