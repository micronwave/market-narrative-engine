"""
Multi-Metric Signal Validation — generates one chart per metric vs. ticker price.

Each chart lives in signal_validation/<metric>_vs_price.png and is overwritten
on every run so that it always reflects the latest snapshot data.

Usage:
    python -m signal_validation.generate          # all metrics
    python -m signal_validation.generate ns_score  # single metric
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import yfinance as yf

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "narrative_engine.db"
OUT_DIR = Path(__file__).resolve().parent

# All metrics stored in narrative_snapshots that are worth correlating to price.
METRICS = [
    "velocity",
    "ns_score",
    "burst_ratio",
    "cohesion",
    "entropy",
    "polarization",
    "sentiment_mean",
    "sentiment_variance",
    "doc_count",
    "source_count",
    "intent_weight",
    "cross_source_score",
    "weighted_source_score",
    "centrality",
    "velocity_windowed",
    "public_interest",
]

# Human-readable labels for chart titles.
METRIC_LABELS = {
    "velocity": "Velocity",
    "ns_score": "Narrative Score",
    "burst_ratio": "Burst Ratio",
    "cohesion": "Cohesion",
    "entropy": "Entropy",
    "polarization": "Polarization",
    "sentiment_mean": "Sentiment Mean",
    "sentiment_variance": "Sentiment Variance",
    "doc_count": "Document Count",
    "source_count": "Source Count",
    "intent_weight": "Intent Weight",
    "cross_source_score": "Cross-Source Score",
    "weighted_source_score": "Weighted Source Score",
    "centrality": "Centrality",
    "velocity_windowed": "Windowed Velocity",
    "public_interest": "Public Interest",
}


# ── Schema helpers ──────────────────────────────────────────────────

_snapshot_columns_cache: set[str] | None = None


def _snapshot_columns(conn) -> set[str]:
    global _snapshot_columns_cache
    if _snapshot_columns_cache is not None:
        return _snapshot_columns_cache
    c = conn.cursor()
    c.execute("PRAGMA table_info(narrative_snapshots)")
    _snapshot_columns_cache = {row[1] for row in c.fetchall()}
    return _snapshot_columns_cache


# ── Gather narrative/ticker pairs ───────────────────────────────────

def _get_pairs(conn, max_pairs=8):
    """Return list of (narrative_id, name, ticker, snap_days, doc_count)."""
    c = conn.cursor()
    c.execute("""
        SELECT n.narrative_id, n.name, n.linked_assets, n.document_count,
               (SELECT COUNT(*) FROM narrative_snapshots s
                WHERE s.narrative_id = n.narrative_id) AS snap_days
        FROM narratives n
        WHERE n.suppressed = 0
          AND n.linked_assets IS NOT NULL AND n.linked_assets != '[]'
        ORDER BY snap_days DESC, n.document_count DESC
    """)
    pairs = []
    seen = set()
    for row in c.fetchall():
        assets = json.loads(row[2])
        for a in assets:
            ticker = a.get("ticker", "") if isinstance(a, dict) else (a if isinstance(a, str) else "")
            if not ticker or ticker.startswith("TOPIC:"):
                continue
            key = (row[0], ticker)
            if key not in seen:
                pairs.append((row[0], row[1], ticker, row[4], row[3]))
                seen.add(key)
            if len(pairs) >= max_pairs:
                break
        if len(pairs) >= max_pairs:
            break
    return pairs


# ── Load snapshot metric series ─────────────────────────────────────

def _get_metric_series(conn, narrative_id, metric_key):
    """Return dict {date_str: metric_value} for a given metric."""
    if metric_key not in _snapshot_columns(conn):
        return {}

    c = conn.cursor()
    c.execute(f"""
        SELECT snapshot_date, {metric_key}
        FROM narrative_snapshots
        WHERE narrative_id = ?
        ORDER BY snapshot_date
    """, (narrative_id,))
    data = {}
    for row in c.fetchall():
        val = row[1]
        if val is not None:
            data[row[0]] = float(val)
    return data


# ── Load price data (cached across metrics for same ticker) ────────

_price_cache: dict[str, dict[str, float]] = {}


def _get_price_series(ticker, start_date, end_date):
    """Fetch daily close prices from yfinance, with per-run caching."""
    cache_key = f"{ticker}|{start_date}|{end_date}"
    if cache_key in _price_cache:
        return _price_cache[cache_key]

    start = datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=3)
    end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=3)
    try:
        df = yf.download(ticker, start=start.strftime("%Y-%m-%d"),
                         end=end.strftime("%Y-%m-%d"), progress=False, auto_adjust=True)
        if df.empty:
            _price_cache[cache_key] = {}
            return {}
        result = {}
        for idx, row in df.iterrows():
            date_str = idx.strftime("%Y-%m-%d")
            close_val = row["Close"]
            if hasattr(close_val, "item"):
                close_val = close_val.item()
            result[date_str] = float(close_val)
        _price_cache[cache_key] = result
        return result
    except Exception as e:
        print(f"  [WARN] yfinance failed for {ticker}: {e}")
        _price_cache[cache_key] = {}
        return {}


# ── Align + correlate ───────────────────────────────────────────────

def _correlate(metric_series, price_series):
    """
    Align metric and price by date.
    Returns (dates, metric_vals, prices, r_same, n, r_lead).
    """
    common_dates = sorted(set(metric_series.keys()) & set(price_series.keys()))
    if len(common_dates) < 3:
        return common_dates, [], [], None, 0, None

    vals = [metric_series[d] for d in common_dates]
    prices = [price_series[d] for d in common_dates]

    # Same-day correlation
    r_same = None
    if np.std(vals) > 0 and np.std(prices) > 0:
        r_same = float(np.corrcoef(vals, prices)[0, 1])

    # Lead correlation: metric today vs. price change tomorrow
    r_lead = None
    if len(common_dates) >= 4:
        all_price_dates = sorted(price_series.keys())
        price_changes = []
        metric_aligned = []
        for d in common_dates:
            idx = all_price_dates.index(d) if d in all_price_dates else -1
            if idx >= 0 and idx + 1 < len(all_price_dates):
                next_d = all_price_dates[idx + 1]
                pct_change = (price_series[next_d] - price_series[d]) / price_series[d]
                price_changes.append(pct_change)
                metric_aligned.append(metric_series[d])
        if len(price_changes) >= 3 and np.std(metric_aligned) > 0 and np.std(price_changes) > 0:
            r_lead = float(np.corrcoef(metric_aligned, price_changes)[0, 1])

    return common_dates, vals, prices, r_same, len(common_dates), r_lead


# ── Plot one metric across all pairs ────────────────────────────────

def _plot_metric(metric_key, results):
    """Generate a single PNG for one metric across all narrative/ticker pairs."""
    label = METRIC_LABELS.get(metric_key, metric_key)
    n = len(results)
    if n == 0:
        return

    fig, axes = plt.subplots(n, 1, figsize=(14, 4 * n), sharex=False)
    if n == 1:
        axes = [axes]

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    fig.suptitle(f"Signal Validation: {label} vs. Ticker Price\n(generated {timestamp})",
                 fontsize=16, fontweight="bold", y=1.0)

    for i, res in enumerate(results):
        ax1 = axes[i]
        name = res["name"][:50]
        ticker = res["ticker"]
        r_same = res["r_same"]
        r_lead = res["r_lead"]
        n_obs = res["n"]

        dates = [datetime.strptime(d, "%Y-%m-%d") for d in res["dates"]]
        vals = res["values"]
        prices = res["prices"]

        if not dates:
            ax1.text(0.5, 0.5, f"{name} / {ticker}\nNo overlapping data",
                     ha="center", va="center", transform=ax1.transAxes, fontsize=12)
            continue

        # Metric (left axis)
        color_metric = "#4A90D9"
        ax1.set_ylabel(label, color=color_metric, fontsize=10)
        ax1.plot(dates, vals, color=color_metric, marker="o", linewidth=2,
                 markersize=6, label=label)
        ax1.tick_params(axis="y", labelcolor=color_metric)
        ax1.fill_between(dates, vals, alpha=0.15, color=color_metric)

        # Price (right axis)
        ax2 = ax1.twinx()
        color_price = "#E5533C"
        ax2.set_ylabel(f"{ticker} Close ($)", color=color_price, fontsize=10)
        ax2.plot(dates, prices, color=color_price, marker="s", linewidth=2,
                 markersize=6, label=f"{ticker}")
        ax2.tick_params(axis="y", labelcolor=color_price)

        # Title with correlation info
        r_same_str = f"r={r_same:+.3f}" if r_same is not None else "r=N/A"
        r_lead_str = f"r_lead={r_lead:+.3f}" if r_lead is not None else "r_lead=N/A"
        ax1.set_title(
            f"{name}  |  {ticker}  |  {r_same_str}  |  {r_lead_str}  |  n={n_obs}",
            fontsize=11, fontweight="bold", pad=10,
        )

        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        ax1.grid(True, alpha=0.3)

    plt.tight_layout()
    out_path = OUT_DIR / f"{metric_key}_vs_price.png"
    fig.savefig(str(out_path), dpi=150, bbox_inches="tight")
    plt.close()
    return out_path


# ── Summary table ───────────────────────────────────────────────────

def _print_summary(metric_key, results):
    label = METRIC_LABELS.get(metric_key, metric_key)
    print(f"\n{'─' * 100}")
    print(f"  {label} vs. Ticker Price")
    print(f"{'─' * 100}")
    print(f"  {'Narrative':<45} {'Ticker':<8} {'n':>3} {'r_same':>8} {'r_lead':>8} {'Signal':>10}")
    for res in results:
        name = res["name"][:44]
        r_same_str = f"{res['r_same']:+.3f}" if res["r_same"] is not None else "  N/A"
        r_lead_str = f"{res['r_lead']:+.3f}" if res["r_lead"] is not None else "  N/A"
        if res["r_lead"] is not None:
            signal = "PROMISING" if res["r_lead"] > 0.3 else ("INVERSE" if res["r_lead"] < -0.3 else "WEAK")
        else:
            signal = "NO DATA"
        print(f"  {name:<45} {res['ticker']:<8} {res['n']:>3} {r_same_str:>8} {r_lead_str:>8} {signal:>10}")


# ── Main entry point ────────────────────────────────────────────────

def generate(metrics=None):
    """
    Generate signal validation charts for the given metrics (or all metrics).
    Each metric produces one PNG in signal_validation/<metric>_vs_price.png.
    """
    if metrics is None:
        metrics = METRICS

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    pairs = _get_pairs(conn)
    if not pairs:
        print("No narrative/ticker pairs found. Ensure pipeline has run.")
        conn.close()
        return

    print(f"Found {len(pairs)} narrative/ticker pairs.")
    print(f"Generating charts for {len(metrics)} metrics: {', '.join(metrics)}\n")

    generated = []

    for metric_key in metrics:
        if metric_key not in METRICS:
            print(f"[SKIP] Unknown metric: {metric_key}")
            continue

        results = []
        for narrative_id, name, ticker, snap_days, doc_count in pairs:
            metric_data = _get_metric_series(conn, narrative_id, metric_key)
            if not metric_data:
                continue

            date_range = sorted(metric_data.keys())
            price_data = _get_price_series(ticker, date_range[0], date_range[-1])
            if not price_data:
                continue

            dates, vals, prices, r_same, n, r_lead = _correlate(metric_data, price_data)
            if n < 3:
                continue

            results.append({
                "narrative_id": narrative_id,
                "name": name,
                "ticker": ticker,
                "dates": dates,
                "values": vals,
                "prices": prices,
                "r_same": r_same,
                "r_lead": r_lead,
                "n": n,
            })

        if not results:
            print(f"[SKIP] {metric_key}: no valid pairs with data")
            continue

        out_path = _plot_metric(metric_key, results)
        _print_summary(metric_key, results)
        generated.append(out_path)
        print(f"  -> {out_path}")

    conn.close()

    print(f"\n{'=' * 100}")
    print(f"Generated {len(generated)} charts in {OUT_DIR}")
    print(f"{'=' * 100}")
    return generated


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        generate(metrics=sys.argv[1:])
    else:
        generate()
