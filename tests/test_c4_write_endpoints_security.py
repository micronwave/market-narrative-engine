"""
C4 write-endpoint security tests.

Run with:
    python -X utf8 tests/test_c4_write_endpoints_security.py
"""

import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from api.main import app  # noqa: E402
from api.app_legacy import get_optional_user  # noqa: E402
import api.app_legacy as main_mod  # noqa: E402
from repository import SqliteRepository  # noqa: E402

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


tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
tmp_db.close()
repo = SqliteRepository(tmp_db.name)
repo.migrate()

now = datetime.now(timezone.utc).isoformat()

other_watchlist_id = str(uuid.uuid4())
other_item_id = str(uuid.uuid4())
repo.create_watchlist(
    {
        "id": other_watchlist_id,
        "user_id": "other-user",
        "name": "Other WL",
        "created_at": now,
    }
)
repo.add_watchlist_item(
    {
        "id": other_item_id,
        "watchlist_id": other_watchlist_id,
        "item_type": "ticker",
        "item_id": "AAPL",
        "added_at": now,
    }
)

other_portfolio_id = str(uuid.uuid4())
other_holding_id = str(uuid.uuid4())
repo.create_portfolio(
    {
        "id": other_portfolio_id,
        "user_id": "other-user",
        "name": "Other PF",
        "created_at": now,
        "updated_at": now,
    }
)
repo.add_portfolio_holding(
    {
        "id": other_holding_id,
        "portfolio_id": other_portfolio_id,
        "ticker": "MSFT",
        "shares": 1.0,
        "added_at": now,
    }
)

orig_get_repo = main_mod.get_repo
orig_rl_enabled = main_mod._API_SETTINGS.RATE_LIMIT_ENABLED
orig_rl_rpm = main_mod._API_SETTINGS.RATE_LIMIT_REQUESTS_PER_MINUTE

main_mod.get_repo = lambda: repo
main_mod._API_SETTINGS.RATE_LIMIT_ENABLED = True
main_mod._API_SETTINGS.RATE_LIMIT_REQUESTS_PER_MINUTE = 2
app.dependency_overrides[get_optional_user] = lambda: {"user_id": "local", "role": "user"}

try:
    with TestClient(app) as client:
        resp_1 = client.post("/api/watchlist/add", json={"item_type": "ticker", "item_id": "TSLA"})
        resp_2 = client.post("/api/watchlist/add", json={"item_type": "ticker", "item_id": "NVDA"})
        resp_3 = client.post("/api/watchlist/add", json={"item_type": "ticker", "item_id": "META"})
        T("write limiter allows initial writes", resp_1.status_code == 200 and resp_2.status_code == 200)
        T("write limiter blocks burst write", resp_3.status_code == 429, str(resp_3.status_code))

        main_mod._API_SETTINGS.RATE_LIMIT_ENABLED = False
        resp_watchlist_forbidden = client.delete(f"/api/watchlist/remove/{other_item_id}")
        T(
            "cross-user watchlist delete returns 403",
            resp_watchlist_forbidden.status_code == 403,
            str(resp_watchlist_forbidden.status_code),
        )

        resp_holding_forbidden = client.delete(f"/api/portfolio/holdings/{other_holding_id}")
        T(
            "cross-user holding delete returns 403",
            resp_holding_forbidden.status_code == 403,
            str(resp_holding_forbidden.status_code),
        )
finally:
    app.dependency_overrides.pop(get_optional_user, None)
    main_mod.get_repo = orig_get_repo
    main_mod._API_SETTINGS.RATE_LIMIT_ENABLED = orig_rl_enabled
    main_mod._API_SETTINGS.RATE_LIMIT_REQUESTS_PER_MINUTE = orig_rl_rpm
    Path(tmp_db.name).unlink(missing_ok=True)

_print_summary()
sys.exit(0 if all(ok for _, ok, _ in _results) else 1)
