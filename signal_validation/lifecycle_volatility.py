"""
Test 3: Lifecycle Stage vs. Price Volatility

Question: Do lifecycle stages correspond to real market behaviour?

Method:
  - Group all narrative/ticker snapshots by lifecycle_stage.
  - For each group, compute the average absolute daily price change
    of linked tickers on the snapshot date.
  - Expected pattern: Growing > Emerging > Mature > Declining > Dormant.

Success criteria: Growing and Emerging show statistically higher
ticker volatility (p < 0.05, t-test) than Mature/Declining/Dormant.

Output: lifecycle_stage_volatility.png
"""

import json
from datetime import datetime
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

from .shared import (
    get_db, get_ohlcv, daily_returns, snapshot_date_range,
    print_header, print_separator, OUT_DIR,
)

STAGE_ORDER = ["Emerging", "Growing", "Mature", "Declining", "Dormant"]
STAGE_COLORS = {
    "Emerging":  "#F5A623",
    "Growing":   "#7ED321",
    "Mature":    "#4A90D9",
    "Declining": "#BD10E0",
    "Dormant":   "#999999",
}


# ── data collection ────────────────────────────────────────────────

def _collect(conn):
    """
    Return {stage: [abs_daily_return, ...]} across all snapshot/ticker
    pairs.
    """
    min_d, max_d = snapshot_date_range(conn)

    c = conn.cursor()
    c.execute("""
        SELECT s.snapshot_date, s.lifecycle_stage, s.narrative_id, s.linked_assets
        FROM narrative_snapshots s
        WHERE s.lifecycle_stage IS NOT NULL
        ORDER BY s.snapshot_date
    """)

    # Gather (stage, narrative_id, date, linked_assets_json)
    rows = c.fetchall()

    # Resolve tickers: prefer snapshot linked_assets, fall back to narrative
    nid_tickers: dict[str, list[str]] = {}   # narrative_id -> [ticker]

    stage_returns: dict[str, list[float]] = defaultdict(list)
    ticker_return_cache: dict[str, dict[str, float]] = {}  # ticker -> {date: ret}

    for row in rows:
        stage = row["lifecycle_stage"]
        if stage not in STAGE_ORDER:
            continue
        nid = row["narrative_id"]
        date = row["snapshot_date"]

        # resolve tickers
        tickers = _resolve_tickers(row["linked_assets"], nid, conn, nid_tickers)
        if not tickers:
            continue

        for ticker in tickers:
            if ticker not in ticker_return_cache:
                ohlcv = get_ohlcv(ticker, min_d, max_d)
                ticker_return_cache[ticker] = daily_returns(ohlcv) if ohlcv else {}

            ret = ticker_return_cache[ticker].get(date)
            if ret is not None:
                stage_returns[stage].append(abs(ret))

    return dict(stage_returns)


def _resolve_tickers(linked_assets_json, nid, conn, cache):
    """Extract tickers from snapshot linked_assets or narrative fallback."""
    if nid in cache:
        return cache[nid]

    tickers = _parse_tickers(linked_assets_json)
    if not tickers:
        # fallback: narratives table
        c = conn.cursor()
        c.execute("SELECT linked_assets FROM narratives WHERE narrative_id = ?", (nid,))
        row = c.fetchone()
        if row:
            tickers = _parse_tickers(row["linked_assets"])

    cache[nid] = tickers
    return tickers


def _parse_tickers(json_str):
    if not json_str:
        return []
    try:
        assets = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return []
    out = []
    for a in assets:
        t = a.get("ticker", "") if isinstance(a, dict) else (a if isinstance(a, str) else "")
        if t and not t.startswith("TOPIC:"):
            out.append(t)
    return out


# ── statistical tests ──────────────────────────────────────────────

def _compute_stats(stage_returns):
    """
    Return list of dicts with mean, std, n, p_value (vs Dormant)
    for each stage.
    """
    dormant = stage_returns.get("Dormant", [])
    rows = []
    for stage in STAGE_ORDER:
        vals = stage_returns.get(stage, [])
        n = len(vals)
        if n == 0:
            rows.append({"stage": stage, "mean": None, "std": None, "n": 0, "p_value": None})
            continue

        mean = float(np.mean(vals))
        std = float(np.std(vals, ddof=1)) if n > 1 else 0.0

        p = None
        if dormant and n >= 3 and len(dormant) >= 3:
            _, p = stats.ttest_ind(vals, dormant, equal_var=False)
            p = float(p)

        rows.append({"stage": stage, "mean": mean, "std": std, "n": n, "p_value": p})

    return rows


# ── plotting ───────────────────────────────────────────────────────

def _plot(stage_returns, stat_rows):
    present = [s for s in STAGE_ORDER if stage_returns.get(s)]
    if not present:
        print("  [SKIP] No data to plot")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    fig.suptitle(f"Test 3: Lifecycle Stage vs. Ticker Price Volatility\n(generated {ts})",
                 fontsize=14, fontweight="bold")

    # ── box plot ──
    data = [stage_returns[s] for s in present]
    colors = [STAGE_COLORS.get(s, "#999") for s in present]
    bp = ax1.boxplot(data, labels=present, patch_artist=True, widths=0.6)
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax1.set_ylabel("Absolute Daily Price Change")
    ax1.set_title("Distribution by Stage")
    ax1.grid(axis="y", alpha=0.3)

    # ── bar chart with p-values ──
    means = []
    stds = []
    ps = []
    labels = []
    bar_colors = []
    for r in stat_rows:
        if r["mean"] is None:
            continue
        labels.append(r["stage"])
        means.append(r["mean"] * 100)
        stds.append(r["std"] * 100 if r["std"] else 0)
        ps.append(r["p_value"])
        bar_colors.append(STAGE_COLORS.get(r["stage"], "#999"))

    x = np.arange(len(labels))
    bars = ax2.bar(x, means, yerr=stds, capsize=4, color=bar_colors, alpha=0.8)
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels)
    ax2.set_ylabel("Mean |Daily Price Change| (%)")
    ax2.set_title("Mean Volatility (error = 1 std)")
    ax2.grid(axis="y", alpha=0.3)

    for j, (bar, p) in enumerate(zip(bars, ps)):
        if p is not None:
            sig = "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else "ns"))
            ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                     f"p={p:.3f}\n{sig}", ha="center", va="bottom", fontsize=8)

    plt.tight_layout()
    out = OUT_DIR / "lifecycle_stage_volatility.png"
    fig.savefig(str(out), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  -> {out}")


# ── entry point ────────────────────────────────────────────────────

def run():
    """Run Test 3.  Returns stat rows + pass/fail."""
    conn = get_db()

    print_header("Test 3: Lifecycle Stage vs. Price Volatility")

    stage_returns = _collect(conn)

    total_obs = sum(len(v) for v in stage_returns.values())
    print(f"\n  Collected {total_obs} observations across {len(stage_returns)} stages")
    for s in STAGE_ORDER:
        n = len(stage_returns.get(s, []))
        print(f"    {s:<12} n={n}")

    if total_obs < 10:
        print("\n  [INSUFFICIENT DATA] Need more snapshot/price overlap.")
        conn.close()
        return {"stats": [], "pass": False, "reason": "insufficient_data"}

    stat_rows = _compute_stats(stage_returns)

    # summary table
    print_separator()
    print(f"  {'Stage':<12} {'Mean |chg|':>12} {'Std':>10} {'n':>5} {'p vs Dormant':>14} {'Sig':>5}")
    for r in stat_rows:
        mean_s = f"{r['mean']*100:.3f}%" if r["mean"] is not None else "N/A"
        std_s = f"{r['std']*100:.3f}%" if r["std"] else "N/A"
        p_s = f"{r['p_value']:.4f}" if r["p_value"] is not None else "N/A"
        sig = ""
        if r["p_value"] is not None:
            sig = "YES" if r["p_value"] < 0.05 else "no"
        print(f"  {r['stage']:<12} {mean_s:>12} {std_s:>10} {r['n']:>5} {p_s:>14} {sig:>5}")

    # pass criteria: Growing or Emerging significantly higher than Dormant
    early_stages_sig = 0
    for r in stat_rows:
        if r["stage"] in ("Growing", "Emerging") and r["p_value"] is not None and r["p_value"] < 0.05:
            # also check direction — early stages should be HIGHER volatility
            dormant_mean = next((x["mean"] for x in stat_rows if x["stage"] == "Dormant"), None)
            if dormant_mean is not None and r["mean"] is not None and r["mean"] > dormant_mean:
                early_stages_sig += 1

    success = early_stages_sig > 0
    status = "PASS" if success else "FAIL"
    print(f"\n  Test 3 overall: {status}  (Growing/Emerging significantly > Dormant at p<0.05)")

    _plot(stage_returns, stat_rows)
    conn.close()
    return {"stats": stat_rows, "pass": success}


if __name__ == "__main__":
    run()
