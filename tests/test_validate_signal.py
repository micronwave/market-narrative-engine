"""
Tests for validate_signal.py (XA-15).

Run with:
    python -X utf8 tests/test_validate_signal.py
"""

import sqlite3
import sys
import types
import tempfile
from pathlib import Path
from unittest.mock import mock_open
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import validate_signal as vs  # noqa: E402

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


def _fake_price_df(dates: list[str], closes: list[float]) -> _FakeFrame:
    return _FakeFrame([(d, {"Close": c}) for d, c in zip(dates, closes)])


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


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """CREATE TABLE narratives (
            narrative_id TEXT PRIMARY KEY,
            name TEXT,
            linked_assets TEXT,
            suppressed INTEGER,
            document_count INTEGER,
            stage TEXT,
            ns_score REAL
        )"""
    )
    conn.execute(
        """CREATE TABLE narrative_snapshots (
            narrative_id TEXT,
            snapshot_date TEXT,
            velocity REAL,
            ns_score REAL,
            doc_count INTEGER
        )"""
    )
    return conn


try:
    # get_pairs / get_velocity_series
    conn = _make_conn()
    conn.executemany(
        "INSERT INTO narratives (narrative_id, name, linked_assets, suppressed, document_count, stage, ns_score) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("nar-1", "N1", '[{"ticker":"NVDA"},{"ticker":"TOPIC:ai"}]', 0, 10, "Growing", 0.7),
            ("nar-2", "N2", '[{"ticker":"AAPL"}]', 1, 9, "Growing", 0.6),
        ],
    )
    conn.executemany(
        "INSERT INTO narrative_snapshots (narrative_id, snapshot_date, velocity, ns_score, doc_count) VALUES (?, ?, ?, ?, ?)",
        [
            ("nar-1", "2026-04-01", 0.4, 0.7, 12),
            ("nar-1", "2026-04-02", 0.5, 0.8, 13),
        ],
    )
    pairs = vs.get_pairs(conn)
    T("get_pairs returns unsuppressed ticker pairs", len(pairs) == 1 and pairs[0][2] == "NVDA", str(pairs))

    v = vs.get_velocity_series(conn, "nar-1")
    T("get_velocity_series returns keyed snapshot map", list(v.keys()) == ["2026-04-01", "2026-04-02"], str(v))
    conn.close()

    # compute_correlation
    vel_small = {"2026-04-01": {"velocity": 1.0}, "2026-04-02": {"velocity": 2.0}}
    price_small = {"2026-04-01": 10.0, "2026-04-02": 11.0}
    corr_small = vs.compute_correlation(vel_small, price_small)
    T("compute_correlation returns no result for <3 points", corr_small[3] is None and corr_small[4] == 0, str(corr_small))

    vel = {
        "2026-04-01": {"velocity": 1.0},
        "2026-04-02": {"velocity": 2.0},
        "2026-04-03": {"velocity": 3.0},
        "2026-04-04": {"velocity": 4.0},
    }
    prices = {
        "2026-04-01": 10.0,
        "2026-04-02": 11.0,
        "2026-04-03": 13.0,
        "2026-04-04": 16.0,
        "2026-04-05": 20.0,
    }
    _, _, _, r_same, n_obs, r_lead = vs.compute_correlation(vel, prices)
    T("compute_correlation returns same-day r with aligned points", r_same is not None and n_obs == 4, f"r_same={r_same}, n={n_obs}")
    T("compute_correlation computes lead correlation", r_lead is not None, f"r_lead={r_lead}")

    # _select_validation_pairs
    conn_no_impact = _make_conn()
    pairs_missing_table = vs._select_validation_pairs(conn_no_impact, max_pairs=5)
    T("select_validation_pairs returns empty when impact_scores missing", pairs_missing_table == [], str(pairs_missing_table))
    conn_no_impact.close()

    conn_imp = _make_conn()
    conn_imp.execute(
        "CREATE TABLE impact_scores (narrative_id TEXT, ticker TEXT, direction TEXT, impact_score REAL, confidence REAL)"
    )
    conn_imp.executemany(
        "INSERT INTO narratives (narrative_id, name, linked_assets, suppressed, document_count, stage, ns_score) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("nar-a", "A", '[{"ticker":"MSFT"}]', 0, 10, "Mature", 0.9),
            ("nar-b", "B", '[{"ticker":"AAPL"}]', 0, 11, "Declining", 0.8),
        ],
    )
    conn_imp.executemany(
        "INSERT INTO impact_scores (narrative_id, ticker, direction, impact_score, confidence) VALUES (?, ?, ?, ?, ?)",
        [
            ("nar-a", "MSFT", "bullish", 0.8, 0.7),
            ("nar-a", "MSFT", "bullish", 0.7, 0.5),
            ("nar-b", "TOPIC:macro", "bearish", 0.9, 0.6),
        ],
    )
    selected = vs._select_validation_pairs(conn_imp, max_pairs=5)
    T("select_validation_pairs deduplicates and skips TOPIC tickers", len(selected) == 1 and selected[0]["ticker"] == "MSFT", str(selected))
    conn_imp.close()

    # _check_price_movement
    df = _fake_price_df(
        ["2026-04-01", "2026-04-02", "2026-04-03", "2026-04-04"],
        [100.0, 101.0, 103.5, 104.0],
    )
    with patch("validate_signal.yf.download", return_value=df):
        move = vs._check_price_movement("MSFT", "2026-04-01", "bullish", threshold_pct=2.0, window_days=3)
    T("check_price_movement detects favorable bullish move", move["data_available"] and move["moved_directional"], str(move))

    invalid = vs._check_price_movement("MSFT", "not-a-date", "bullish")
    T("check_price_movement handles invalid date safely", invalid["data_available"] is False, str(invalid))

    # get_price_series
    with patch("validate_signal.yf.download", return_value=df):
        prices_map = vs.get_price_series("MSFT", "2026-04-01", "2026-04-04")
    T("get_price_series parses adjusted close map", prices_map.get("2026-04-02") == 101.0, str(prices_map))

    with patch("validate_signal.yf.download", side_effect=RuntimeError("network down")):
        prices_fail = vs.get_price_series("MSFT", "2026-04-01", "2026-04-04")
    T("get_price_series handles yfinance exception", prices_fail == {}, str(prices_fail))

    # _run_correlation_at_lags
    conn_corr = _make_conn()
    conn_corr.executemany(
        "INSERT INTO narrative_snapshots (narrative_id, snapshot_date, velocity, ns_score, doc_count) VALUES (?, ?, ?, ?, ?)",
        [
            ("nar-c", "2026-04-01", 0.2, 0.5, 5),
            ("nar-c", "2026-04-02", 0.3, 0.6, 6),
            ("nar-c", "2026-04-03", 0.4, 0.7, 7),
            ("nar-c", "2026-04-04", 0.6, 0.8, 8),
        ],
    )
    df_corr = _fake_price_df(
        ["2026-04-01", "2026-04-02", "2026-04-03", "2026-04-04"],
        [100.0, 101.0, 103.0, 104.0],
    )
    fake_corr_mod = types.SimpleNamespace(
        compute_velocity_price_correlation=lambda _v, _p, lead_days: {
            "correlation": 0.1 * (lead_days + 1),
            "p_value": 0.04 if lead_days == 1 else 0.2,
            "n_observations": 4,
            "is_significant": lead_days == 1,
        }
    )
    with patch("validate_signal.yf.download", return_value=df_corr), patch.dict(sys.modules, {"api.correlation_service": fake_corr_mod}):
        lag_results = vs._run_correlation_at_lags(conn_corr, "nar-c", "MSFT", lead_days_list=(0, 1, 2))
    T("run_correlation_at_lags returns one result per lag", len(lag_results) == 3, str(lag_results))
    T("run_correlation_at_lags preserves significance flag", any(r["significant"] for r in lag_results), str(lag_results))
    conn_corr.close()

    # run_validation end-to-end (mocked internals for deterministic coverage)
    conn_run = _make_conn()
    conn_run.execute("CREATE TABLE ticker_convergence (ticker TEXT, pressure_score REAL)")
    conn_run.execute("INSERT INTO ticker_convergence (ticker, pressure_score) VALUES ('MSFT', 2.5)")
    pairs_for_run = [
        {"narrative_id": "nar-1", "name": "Narrative A", "ticker": "MSFT", "direction": "bullish", "impact_score": 0.8, "ns_score": 0.6},
        {"narrative_id": "nar-2", "name": "Narrative B", "ticker": "AAPL", "direction": "bearish", "impact_score": 0.2, "ns_score": 0.9},
    ]

    def _fake_pm(ticker: str, _peak: str, _direction: str):
        if ticker == "MSFT":
            return {"data_available": True, "moved_directional": True, "moved_either": True, "max_directional": 3.1, "max_either": 3.1}
        return {"data_available": True, "moved_directional": False, "moved_either": True, "max_directional": 0.4, "max_either": 2.8}

    with patch("validate_signal.sqlite3.connect", return_value=conn_run), \
        patch("validate_signal._select_validation_pairs", return_value=pairs_for_run), \
        patch("validate_signal._get_peak_velocity_date", return_value="2026-04-01"), \
        patch("validate_signal._check_price_movement", side_effect=_fake_pm), \
        patch("validate_signal._run_correlation_at_lags", return_value=[{"lead_days": 1, "r": 0.4, "p_value": 0.03, "n": 6, "significant": True}]), \
        patch("validate_signal._plot_validation_top5"), \
        patch("validate_signal._append_to_build_log"):
        run_out = vs.run_validation()
    T("run_validation returns summary payload", run_out.get("pairs_with_data") == 2 and "recommendation" in run_out, str(run_out))

    with patch("validate_signal.sqlite3.connect", return_value=conn_run), patch("validate_signal._select_validation_pairs", return_value=[]):
        run_empty = vs.run_validation()
    T("run_validation returns error when no pairs selected", "error" in run_empty, str(run_empty))
    conn_run.close()

    # _plot_validation_top5 with deterministic data
    conn_plot = _make_conn()
    dummy_pairs = [{"narrative_id": "nar-1", "name": "Narrative A", "ticker": "MSFT", "impact_score": 0.8, "moved_directional": True}]
    with patch("validate_signal.sqlite3.connect", return_value=conn_plot), \
        patch("validate_signal.get_velocity_series", return_value={"2026-04-01": {"velocity": 1.0}, "2026-04-02": {"velocity": 2.0}, "2026-04-03": {"velocity": 3.0}}), \
        patch("validate_signal.get_price_series", return_value={"2026-04-01": 10.0, "2026-04-02": 11.0, "2026-04-03": 12.0}), \
        patch("validate_signal.compute_correlation", return_value=(["2026-04-01", "2026-04-02", "2026-04-03"], [1.0, 2.0, 3.0], [10.0, 11.0, 12.0], 0.9, 3, 0.7)), \
        patch("validate_signal.plot_all") as plot_all_mock:
        vs._plot_validation_top5(dummy_pairs)
    T("plot_validation_top5 delegates final rendering", plot_all_mock.called, "plot_all not called")
    conn_plot.close()

    # _append_to_build_log success and warning path
    fake_pairs = [{
        "name": "Narrative A",
        "ticker": "MSFT",
        "direction": "bullish",
        "impact_score": 0.8,
        "ns_score": 0.6,
        "max_move_pct": 3.1,
        "old_hit": True,
        "new_hit": True,
    }]
    with patch("builtins.open", mock_open()) as m:
        vs._append_to_build_log(1, 1, 100.0, 1, 100.0, 1, 1, 100.0, "1 significant", "PROCEED", fake_pairs)
    T("append_to_build_log writes output on success", m.called, "open not called")

    with patch("builtins.open", side_effect=OSError("readonly")):
        # Should not raise.
        vs._append_to_build_log(1, 0, 0.0, 0, 0.0, 0, 0, 0.0, "none", "RETHINK", fake_pairs)
    T("append_to_build_log tolerates write failure", True)

    # print_summary / plot_all / main()
    summary_rows = [
        {"name": "Narrative A", "ticker": "MSFT", "n": 5, "r_same": 0.6, "r_lead": 0.4},
        {"name": "Narrative B", "ticker": "AAPL", "n": 5, "r_same": -0.2, "r_lead": -0.5},
    ]
    vs.print_summary(summary_rows)
    T("print_summary runs for mixed lead directions", True)

    plot_rows = [{
        "name": "Narrative A",
        "ticker": "MSFT",
        "r_same": 0.6,
        "r_lead": 0.4,
        "n": 3,
        "dates": ["2026-04-01", "2026-04-02", "2026-04-03"],
        "velocities": [1.0, 2.0, 3.0],
        "prices": [100.0, 102.0, 104.0],
    }]
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_png:
        tmp_path = Path(tmp_png.name)
    vs.plot_all(plot_rows, output_path=tmp_path)
    T("plot_all writes png output", tmp_path.exists(), str(tmp_path))
    tmp_path.unlink(missing_ok=True)

    conn_main = _make_conn()
    with patch("validate_signal.sqlite3.connect", return_value=conn_main), \
        patch("validate_signal.get_pairs", return_value=[("nar-1", "Narrative A", "MSFT", 3, 12)]), \
        patch("validate_signal.get_velocity_series", return_value={"2026-04-01": {"velocity": 1.0}, "2026-04-02": {"velocity": 2.0}, "2026-04-03": {"velocity": 3.0}}), \
        patch("validate_signal.get_price_series", return_value={"2026-04-01": 100.0, "2026-04-02": 101.0, "2026-04-03": 102.0}), \
        patch("validate_signal.compute_correlation", return_value=(["2026-04-01", "2026-04-02", "2026-04-03"], [1.0, 2.0, 3.0], [100.0, 101.0, 102.0], 0.9, 3, 0.5)), \
        patch("validate_signal.plot_all"), \
        patch("validate_signal.print_summary"):
        vs.main()
    T("main processes mocked pair flow", True)
    conn_main.close()

    conn_main_empty = _make_conn()
    with patch("validate_signal.sqlite3.connect", return_value=conn_main_empty), patch("validate_signal.get_pairs", return_value=[]):
        vs.main()
    T("main handles no-valid-pairs path", True)
    conn_main_empty.close()

    # _select_validation_pairs fallback stage query and _get_peak_velocity_date
    conn_fb = _make_conn()
    conn_fb.execute(
        "CREATE TABLE impact_scores (narrative_id TEXT, ticker TEXT, direction TEXT, impact_score REAL, confidence REAL)"
    )
    conn_fb.execute(
        "INSERT INTO narratives (narrative_id, name, linked_assets, suppressed, document_count, stage, ns_score) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("nar-z", "Fallback Narrative", '[{"ticker":"QQQ"}]', 0, 8, "Growing", 0.55),
    )
    conn_fb.execute(
        "INSERT INTO impact_scores (narrative_id, ticker, direction, impact_score, confidence) VALUES (?, ?, ?, ?, ?)",
        ("nar-z", "QQQ", "bullish", 0.61, 0.8),
    )
    fallback_pairs = vs._select_validation_pairs(conn_fb, max_pairs=3)
    T("select_validation_pairs falls back when no Mature/Declining rows", len(fallback_pairs) == 1 and fallback_pairs[0]["ticker"] == "QQQ", str(fallback_pairs))

    conn_fb.execute(
        "INSERT INTO narrative_snapshots (narrative_id, snapshot_date, velocity, ns_score, doc_count) VALUES (?, ?, ?, ?, ?)",
        ("nar-z", "2026-04-05", 0.9, 0.6, 4),
    )
    peak = vs._get_peak_velocity_date(conn_fb, "nar-z")
    no_peak = vs._get_peak_velocity_date(conn_fb, "missing")
    T("get_peak_velocity_date returns date for existing narrative", peak == "2026-04-05", str(peak))
    T("get_peak_velocity_date returns None when absent", no_peak is None, str(no_peak))
    conn_fb.close()
finally:
    _print_summary()

sys.exit(0 if all(ok for _, ok, _ in _results) else 1)
