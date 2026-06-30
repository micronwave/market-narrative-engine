"""
P02b Batch 5 verification:
1. JSON logger is configured on root logger.
2. HTTP middleware emits request timing with duration_ms metadata.

Run with:
    python -X utf8 tests/test_p02b_logging.py
"""

import sys
from pathlib import Path
from unittest.mock import patch

from pythonjsonlogger import jsonlogger

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
import api.app_legacy as main_mod  # noqa: E402
from api.main import app  # noqa: E402
from api.app_legacy import STUB_AUTH_TOKEN  # noqa: E402

_results: list[tuple[str, bool, str]] = []


def T(name: str, condition: bool, details: str = "") -> None:
    _results.append((name, bool(condition), details))
    if not condition:
        print(f"FAIL {name}" + (f" — {details}" if details else ""), file=sys.stderr)


def _print_summary() -> None:
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = len(_results) - passed
    print("\n" + "=" * 60)
    print(f"TOTAL: {passed} passed, {failed} failed out of {len(_results)} tests")
    print("=" * 60)


def _is_json_handler(handler) -> bool:
    return bool(
        getattr(handler, "_narrative_json", False)
        and isinstance(getattr(handler, "formatter", None), jsonlogger.JsonFormatter)
    )


root_logger = main_mod.logging.getLogger()
T(
    "root logger has narrative JSON handler",
    any(_is_json_handler(h) for h in root_logger.handlers),
    f"handlers={len(root_logger.handlers)}",
)

http_timing_calls: list[dict] = []
original_info = main_mod.logger.info


def _capture_info(message, *args, **kwargs):
    if message == "http_request":
        http_timing_calls.append(kwargs.get("extra") or {})
    return original_info(message, *args, **kwargs)


with patch.object(main_mod.logger, "info", side_effect=_capture_info):
    with TestClient(app) as client:
        response = client.get("/api/health", headers={"x-auth-token": STUB_AUTH_TOKEN})

T("health endpoint responds 200", response.status_code == 200, str(response.status_code))
T("http timing middleware logged request", len(http_timing_calls) >= 1, str(http_timing_calls))

if http_timing_calls:
    payload = http_timing_calls[-1]
    T("timing payload has method", payload.get("method") == "GET", str(payload))
    T("timing payload has path", payload.get("path") == "/api/health", str(payload))
    T("timing payload has status_code", payload.get("status_code") == 200, str(payload))
    T("timing payload has duration_ms", isinstance(payload.get("duration_ms"), (int, float)), str(payload))

_print_summary()
sys.exit(0 if all(ok for _, ok, _ in _results) else 1)
