"""
Comprehensive XA-14 user-state security tests.

Run with:
    python -X utf8 tests/test_user_state_comprehensive.py
"""

import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from api.main import app  # noqa: E402
import api.app_legacy as main_mod  # noqa: E402
from api.app_legacy import get_user_state_user  # noqa: E402
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

orig_get_repo = main_mod.get_repo
orig_auth_mode = main_mod._AUTH_MODE
orig_auth_required = main_mod._API_SETTINGS.AUTH_REQUIRED_FOR_USER_STATE
orig_rate_limit_enabled = main_mod._API_SETTINGS.RATE_LIMIT_ENABLED
orig_rate_limit_rpm = main_mod._API_SETTINGS.RATE_LIMIT_REQUESTS_PER_MINUTE

main_mod.get_repo = lambda: repo

try:
    with TestClient(app) as client:
        # 1) Auth requirement in JWT mode: unauthenticated user-state access is blocked.
        app.dependency_overrides.pop(get_user_state_user, None)
        main_mod._AUTH_MODE = "jwt"
        main_mod._API_SETTINGS.AUTH_REQUIRED_FOR_USER_STATE = True
        r_unauth = client.get("/api/portfolio")
        T("jwt mode unauthenticated user-state call returns 401", r_unauth.status_code == 401, str(r_unauth.status_code))
        T("401 response uses detail shape", isinstance(r_unauth.json().get("detail"), str), str(r_unauth.json()))

        # 2) Stub mode dev path remains available.
        main_mod._AUTH_MODE = "stub"
        r_stub = client.get("/api/portfolio")
        T("stub mode user-state call succeeds", r_stub.status_code == 200, str(r_stub.status_code))

        # 3) Ownership check: User A cannot delete User B holding.
        app.dependency_overrides[get_user_state_user] = lambda: {"user_id": "user-a", "role": "user"}
        other_pid = str(uuid.uuid4())
        other_hid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        repo.create_portfolio(
            {
                "id": other_pid,
                "user_id": "user-b",
                "name": "Other Portfolio",
                "created_at": now,
                "updated_at": now,
            }
        )
        repo.add_portfolio_holding(
            {
                "id": other_hid,
                "portfolio_id": other_pid,
                "ticker": "AAPL",
                "shares": 3.0,
                "added_at": now,
            }
        )
        r_forbidden = client.delete(f"/api/portfolio/holdings/{other_hid}")
        T("cross-user delete blocked with 403", r_forbidden.status_code == 403, str(r_forbidden.status_code))
        T("403 response uses detail shape", isinstance(r_forbidden.json().get("detail"), str), str(r_forbidden.json()))

        # 4) Rate limiting is keyed by user_id: User A hits limit; User B remains unaffected.
        main_mod._API_SETTINGS.RATE_LIMIT_ENABLED = True
        main_mod._API_SETTINGS.RATE_LIMIT_REQUESTS_PER_MINUTE = 2

        app.dependency_overrides[get_user_state_user] = lambda: {"user_id": "user-a-rate", "role": "user"}
        r1 = client.post("/api/watchlist/add", json={"item_type": "ticker", "item_id": "MSFT"})
        r2 = client.post("/api/watchlist/add", json={"item_type": "ticker", "item_id": "NVDA"})
        r3 = client.post("/api/watchlist/add", json={"item_type": "ticker", "item_id": "AAPL"})
        T("user A first write accepted", r1.status_code == 200, str(r1.status_code))
        T("user A second write accepted", r2.status_code == 200, str(r2.status_code))
        T("user A third write is rate-limited", r3.status_code == 429, str(r3.status_code))
        T("429 response uses detail shape", isinstance(r3.json().get("detail"), str), str(r3.json()))

        app.dependency_overrides[get_user_state_user] = lambda: {"user_id": "user-b-rate", "role": "user"}
        r_other = client.post("/api/watchlist/add", json={"item_type": "ticker", "item_id": "TSLA"})
        T("user B write not blocked by user A limit", r_other.status_code == 200, str(r_other.status_code))
finally:
    app.dependency_overrides.pop(get_user_state_user, None)
    main_mod.get_repo = orig_get_repo
    main_mod._AUTH_MODE = orig_auth_mode
    main_mod._API_SETTINGS.AUTH_REQUIRED_FOR_USER_STATE = orig_auth_required
    main_mod._API_SETTINGS.RATE_LIMIT_ENABLED = orig_rate_limit_enabled
    main_mod._API_SETTINGS.RATE_LIMIT_REQUESTS_PER_MINUTE = orig_rate_limit_rpm
    Path(tmp_db.name).unlink(missing_ok=True)

_print_summary()
sys.exit(0 if all(ok for _, ok, _ in _results) else 1)
