"""
Tests for signal_validation/shared.py (XA-15).

Run with:
    python -X utf8 tests/test_signal_validation_shared.py
"""

import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from signal_validation import shared as svs  # noqa: E402

_results: list[tuple[str, bool, str]] = []


class _FakeTimestamp:
    def __init__(self, date_str: str) -> None:
        self._date_str = date_str

    def strftime(self, _fmt: str) -> str:
        return self._date_str


class _FakeFrame:
    def __init__(self, rows: list[tuple[str, dict[str, float]]]) -> None:
        self._rows = rows

    @property
    def empty(self) -> bool:
        return not self._rows

    def __len__(self) -> int:
        return len(self._rows)

    def iterrows(self):
        for date_str, row in self._rows:
            yield _FakeTimestamp(date_str), row


def _fake_ohlcv_df(dates: list[str], closes: list[float], volumes: list[float]) -> _FakeFrame:
    return _FakeFrame(
        [
            (d, {"Close": c, "Volume": v})
            for d, c, v in zip(dates, closes, volumes)
        ]
    )


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


def _conn_with_schema() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE narratives (
            narrative_id TEXT PRIMARY KEY,
            name TEXT,
            linked_assets TEXT,
            suppressed INTEGER,
            ns_score REAL,
            document_count INTEGER
        )"""
    )
    conn.execute(
        """CREATE TABLE narrative_snapshots (
            narrative_id TEXT,
            snapshot_date TEXT
        )"""
    )
    return conn


try:
    # _safe / date helpers / returns / volume window
    T("safe converts numpy scalars", svs._safe(np.float64(3.2)) == 3.2, str(svs._safe(np.float64(3.2))))

    ohlcv = {
        "2026-04-01": {"close": 100.0, "volume": 50},
        "2026-04-02": {"close": 110.0, "volume": 60},
        "2026-04-03": {"close": 121.0, "volume": 70},
    }
    T("trading_days_after returns strict next dates", svs.trading_days_after(ohlcv, "2026-04-01", 2) == ["2026-04-02", "2026-04-03"])
    T("trading_days_before returns strict prior dates", svs.trading_days_before(ohlcv, "2026-04-03", 2) == ["2026-04-01", "2026-04-02"])

    dr = svs.daily_returns(ohlcv)
    T("daily_returns computes pct change", round(dr["2026-04-02"], 4) == 0.1 and round(dr["2026-04-03"], 4) == 0.1, str(dr))

    vol_no_prior = svs.avg_volume_window({"2026-04-03": {"close": 10, "volume": 123}}, "2026-04-03", window=20)
    T("avg_volume_window includes same date when no prior", vol_no_prior == 123.0, str(vol_no_prior))

    # get_ohlcv (network mocked) + cache behavior
    svs._ohlcv_cache.clear()
    df = _fake_ohlcv_df(
        ["2026-04-01", "2026-04-02"],
        [100.0, 105.0],
        [1000.0, 1200.0],
    )
    with patch("signal_validation.shared.yf.download", return_value=df) as mocked:
        first = svs.get_ohlcv("MSFT", "2026-04-01", "2026-04-10")
        second = svs.get_ohlcv("MSFT", "2026-04-01", "2026-04-10")
    T("get_ohlcv returns parsed close/volume map", first.get("2026-04-01", {}).get("close") == 100.0, str(first))
    T("get_ohlcv uses in-memory cache", mocked.call_count == 1 and first == second, f"calls={mocked.call_count}")

    with patch("signal_validation.shared.yf.download", side_effect=RuntimeError("boom")):
        failed = svs.get_ohlcv("ERR", "2026-04-01", "2026-04-10")
    T("get_ohlcv handles fetch failure safely", failed == {}, str(failed))

    # narrative_ticker_pairs / snapshot_date_range
    conn = _conn_with_schema()
    conn.executemany(
        "INSERT INTO narratives (narrative_id, name, linked_assets, suppressed, ns_score, document_count) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("nar-1", "N1", '[{"ticker":"NVDA"},{"ticker":"TOPIC:ai"}]', 0, 0.7, 10),
            ("nar-2", "N2", '["AAPL"]', 0, 0.8, 9),
            ("nar-3", "N3", "[]", 0, 0.5, 8),
        ],
    )
    conn.executemany(
        "INSERT INTO narrative_snapshots (narrative_id, snapshot_date) VALUES (?, ?)",
        [
            ("nar-1", "2026-04-01"),
            ("nar-1", "2026-04-02"),
            ("nar-1", "2026-04-03"),
            ("nar-2", "2026-04-01"),
            ("nar-2", "2026-04-02"),
            ("nar-2", "2026-04-03"),
        ],
    )
    pairs = svs.narrative_ticker_pairs(conn, min_snaps=3, max_pairs=10)
    tickers = sorted(p[2] for p in pairs)
    T("narrative_ticker_pairs returns valid non-TOPIC tickers", tickers == ["AAPL", "NVDA"], str(pairs))

    min_d, max_d = svs.snapshot_date_range(conn)
    T("snapshot_date_range returns actual min/max", (min_d, max_d) == ("2026-04-01", "2026-04-03"), f"{min_d},{max_d}")
    conn.close()

    empty_conn = _conn_with_schema()
    min_def, max_def = svs.snapshot_date_range(empty_conn)
    T("snapshot_date_range falls back to defaults when empty", (min_def, max_def) == ("2026-01-01", "2026-04-01"), f"{min_def},{max_def}")
    empty_conn.close()
finally:
    _print_summary()

sys.exit(0 if all(ok for _, ok, _ in _results) else 1)
