"""
Test 1: Per-Component Lead Correlation.

Ranks the individual narrative snapshot components by their median
one-day lead correlation to next-day price change across narrative/ticker
pairs. The source-authority component prefers the historical
weighted_source_score series when available and falls back to
cross_source_score for older snapshots.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from statistics import median


from api.correlation_service import compute_metric_price_correlation

from .shared import (
    get_db,
    get_ohlcv,
    daily_returns,
    narrative_ticker_pairs,
    snapshot_date_range,
    print_header,
    print_separator,
    OUT_DIR,
)

MIN_SNAPSHOTS = 30
MIN_PAIRS = 5
MAX_PAIRS = 80
LEAD_DAYS = 1

REPORT_PATH = OUT_DIR / "component_lead_correlation.md"
BUILD_LOG_PATH = Path(__file__).resolve().parent.parent / "BUILD_LOG.md"

COMPONENTS = [
    ("velocity", "Velocity"),
    ("cohesion", "Cohesion"),
    ("polarization", "Polarization"),
    ("entropy", "Entropy"),
    ("source_authority_score", "Source Authority"),
    ("centrality", "Centrality"),
    ("intent_weight", "Intent Weight"),
]

_SNAPSHOT_COLUMNS_CACHE: set[str] | None = None


def _snapshot_columns(conn: sqlite3.Connection) -> set[str]:
    global _SNAPSHOT_COLUMNS_CACHE
    if _SNAPSHOT_COLUMNS_CACHE is not None:
        return _SNAPSHOT_COLUMNS_CACHE
    c = conn.cursor()
    c.execute("PRAGMA table_info(narrative_snapshots)")
    _SNAPSHOT_COLUMNS_CACHE = {row[1] for row in c.fetchall()}
    return _SNAPSHOT_COLUMNS_CACHE


def _load_metric_history(conn: sqlite3.Connection, narrative_id: str, metric_key: str) -> list[dict]:
    available_columns = _snapshot_columns(conn)
    if metric_key != "source_authority_score" and metric_key not in available_columns:
        return []

    if metric_key == "source_authority_score":
        if "weighted_source_score" in available_columns:
            query = """
                SELECT snapshot_date, cross_source_score, weighted_source_score
                FROM narrative_snapshots
                WHERE narrative_id = ?
                ORDER BY snapshot_date
            """
        else:
            query = """
                SELECT snapshot_date, cross_source_score
                FROM narrative_snapshots
                WHERE narrative_id = ?
                ORDER BY snapshot_date
            """
    else:
        query = f"""
            SELECT snapshot_date, {metric_key}
            FROM narrative_snapshots
            WHERE narrative_id = ?
            ORDER BY snapshot_date
        """

    c = conn.cursor()
    c.execute(query, (narrative_id,))

    history: list[dict] = []
    for row in c.fetchall():
        value = None
        if metric_key == "source_authority_score":
            value = row["weighted_source_score"] if "weighted_source_score" in row.keys() else None
            if value is None:
                value = row["cross_source_score"]
        else:
            value = row[1]

        if value is None:
            continue

        try:
            history.append({"date": row["snapshot_date"], metric_key: float(value)})
        except (TypeError, ValueError):
            continue

    return history


def _load_price_history(ticker: str, start: str, end: str) -> list[dict]:
    ohlcv = get_ohlcv(ticker, start, end)
    if not ohlcv:
        return []

    returns = daily_returns(ohlcv)
    return [{"date": d, "change_pct": pct} for d, pct in sorted(returns.items())]


def _component_rows(conn: sqlite3.Connection) -> tuple[list[dict], int, int]:
    pairs = narrative_ticker_pairs(conn, min_snaps=MIN_SNAPSHOTS, max_pairs=MAX_PAIRS)
    if len(pairs) < MIN_PAIRS:
        return [], len(pairs), 0

    min_date, max_date = snapshot_date_range(conn)
    by_metric: dict[str, list[float]] = {metric: [] for metric, _label in COMPONENTS}
    per_pair_rows: list[dict] = []

    for narrative_id, name, ticker, snap_days, _ns_score in pairs:
        price_history = _load_price_history(ticker, min_date, max_date)
        if not price_history:
            continue

        pair_row = {
            "narrative_id": narrative_id,
            "name": name,
            "ticker": ticker,
            "snap_days": snap_days,
            "metric_results": {},
        }

        for metric_key, _label in COMPONENTS:
            metric_history = _load_metric_history(conn, narrative_id, metric_key)
            if len(metric_history) < MIN_SNAPSHOTS:
                continue

            result = compute_metric_price_correlation(
                metric_history,
                price_history,
                metric_key=metric_key,
                lead_days=LEAD_DAYS,
                min_observations=MIN_SNAPSHOTS,
            )
            r = result.get("correlation")
            if r is None:
                continue

            by_metric[metric_key].append(float(r))
            pair_row["metric_results"][metric_key] = {
                "r_lead": float(r),
                "n": int(result.get("n_observations", 0)),
            }

        per_pair_rows.append(pair_row)

    summary_rows = []
    for metric_key, label in COMPONENTS:
        values = by_metric.get(metric_key, [])
        if values:
            median_signed = float(median(values))
            median_abs = float(median(abs(v) for v in values))
            pct_gt_02 = float(sum(abs(v) > 0.2 for v in values) / len(values))
        else:
            median_signed = None
            median_abs = None
            pct_gt_02 = 0.0

        summary_rows.append({
            "metric": metric_key,
            "label": label,
            "n_pairs": len(values),
            "median_r_lead": median_signed,
            "median_abs_r_lead": median_abs,
            "pct_abs_gt_0_2": pct_gt_02,
        })

    summary_rows.sort(
        key=lambda row: (
            row["median_abs_r_lead"] is not None,
            row["median_abs_r_lead"] or 0.0,
        ),
        reverse=True,
    )

    return summary_rows, len(pairs), len(per_pair_rows)


def _render_report(summary_rows: list[dict], pair_count: int, evaluated_pairs: int) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    strong_components = [
        row for row in summary_rows
        if row["median_abs_r_lead"] is not None and row["median_abs_r_lead"] > 0.15
    ]

    lines = [
        "# Test 1: Per-Component Lead Correlation",
        "",
        f"Generated: {ts}",
        f"Pairs scanned: {pair_count}",
        f"Pairs evaluated: {evaluated_pairs}",
        f"Strong components: {len(strong_components)}",
        "",
        "| Component | Median r_lead | Median abs r_lead | % pairs with abs(r_lead) > 0.2 | n pairs |",
        "|---|---:|---:|---:|---:|",
    ]

    for row in summary_rows:
        median_r = "N/A" if row["median_r_lead"] is None else f"{row['median_r_lead']:+.3f}"
        median_abs = "N/A" if row["median_abs_r_lead"] is None else f"{row['median_abs_r_lead']:.3f}"
        pct = f"{row['pct_abs_gt_0_2'] * 100:.1f}%"
        lines.append(
            f"| {row['label']} | {median_r} | {median_abs} | {pct} | {row['n_pairs']} |"
        )

    lines.extend([
        "",
        "Success criteria: at least 2 components with median |r_lead| > 0.15.",
    ])
    return "\n".join(lines) + "\n"


def _append_build_log(report: str) -> None:
    section = [
        "",
        f"## Signal Accuracy Test 1 — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        report,
    ]
    try:
        with open(BUILD_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write("\n".join(section))
    except Exception:
        # Build-log writes must never block the core analysis.
        pass


def run():
    conn = get_db()
    print_header("Test 1: Per-Component Lead Correlation")

    summary_rows, pair_count, evaluated_pairs = _component_rows(conn)

    if pair_count < MIN_PAIRS or not evaluated_pairs:
        report = _render_report(summary_rows, pair_count, evaluated_pairs)
        REPORT_PATH.write_text(report, encoding="utf-8")
        _append_build_log(report)
        conn.close()
        print("\n  [INSUFFICIENT DATA] Not enough narrative/ticker pairs with snapshot history.")
        return {
            "pass": False,
            "reason": "insufficient_data",
            "pairs": pair_count,
            "evaluated_pairs": evaluated_pairs,
            "summary": summary_rows,
            "strong_components": 0,
            "report_path": str(REPORT_PATH),
        }

    strong_components = [
        row for row in summary_rows
        if row["median_abs_r_lead"] is not None and row["median_abs_r_lead"] > 0.15
    ]
    success = len(strong_components) >= 2

    print_separator()
    print(f"  {'Component':<24} {'Median r_lead':>14} {'Median abs r':>12} {'|r|>0.2':>10} {'n pairs':>8}")
    for row in summary_rows:
        median_r = "N/A" if row["median_r_lead"] is None else f"{row['median_r_lead']:+.3f}"
        median_abs = "N/A" if row["median_abs_r_lead"] is None else f"{row['median_abs_r_lead']:.3f}"
        pct = f"{row['pct_abs_gt_0_2'] * 100:.1f}%"
        print(f"  {row['label']:<24} {median_r:>14} {median_abs:>12} {pct:>10} {row['n_pairs']:>8}")

    status = "PASS" if success else "FAIL"
    print(
        f"\n  Test 1 overall: {status}  "
        f"({len(strong_components)} components with median |r_lead| > 0.15; need >= 2)"
    )

    report = _render_report(summary_rows, pair_count, evaluated_pairs)
    REPORT_PATH.write_text(report, encoding="utf-8")
    _append_build_log(report)
    conn.close()
    return {
        "pass": success,
        "pairs": pair_count,
        "evaluated_pairs": evaluated_pairs,
        "summary": summary_rows,
        "strong_components": len(strong_components),
        "report_path": str(REPORT_PATH),
    }


if __name__ == "__main__":
    run()
