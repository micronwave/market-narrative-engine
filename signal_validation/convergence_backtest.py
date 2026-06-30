"""
Test 4: Convergence Pressure Backtest

Question: When multiple independent narratives converge on a ticker,
          does the ticker move more?

Method:
  - Pull all ticker_convergence records with pressure_score > 0.
  - Bucket into quartiles by pressure_score.
  - For each quartile compute average absolute ticker price change
    over the next 1, 3, and 5 trading days.
  - Compare top quartile vs bottom quartile.

Success criteria: Top pressure quartile shows >= 1.5x the average
price movement of the bottom quartile.

Output: convergence_pressure_backtest.png
"""

from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .shared import (
    get_db, get_ohlcv, trading_days_after, snapshot_date_range,
    print_header, print_separator, OUT_DIR,
)

WINDOWS = [1, 3, 5]


# ── data collection ────────────────────────────────────────────────

def _load_convergence(conn):
    """
    Return list of dicts from ticker_convergence:
      {ticker, pressure_score, computed_at, convergence_count}
    sorted by pressure_score ascending.
    """
    c = conn.cursor()
    c.execute("""
        SELECT ticker, pressure_score, computed_at, convergence_count
        FROM ticker_convergence
        WHERE pressure_score > 0
        ORDER BY pressure_score ASC
    """)
    records = []
    for row in c.fetchall():
        ticker = row["ticker"] or ""
        if ticker.startswith("TOPIC:"):
            continue
        records.append(dict(row))
    return records


def _quartile_split(records):
    """
    Split records (already sorted by pressure_score ASC) into 4 roughly
    equal groups.  Returns [(label, [records])].
    """
    n = len(records)
    if n < 4:
        # not enough for proper quartiles — treat as two halves
        mid = n // 2
        return [("Bottom Half", records[:mid]), ("Top Half", records[mid:])]

    q = n // 4
    return [
        ("Q1 (lowest)", records[:q]),
        ("Q2",          records[q:2*q]),
        ("Q3",          records[2*q:3*q]),
        ("Q4 (highest)", records[3*q:]),
    ]


def _price_moves(records, conn, window):
    """
    For each record compute the absolute price change over *window*
    trading days after computed_at.  Returns list of |pct_change|.
    """
    min_d, max_d = snapshot_date_range(conn)
    moves = []

    for rec in records:
        ticker = rec["ticker"]
        date = rec["computed_at"][:10] if rec["computed_at"] else ""
        if not date:
            continue

        ohlcv = get_ohlcv(ticker, min_d, max_d)
        if not ohlcv or date not in ohlcv:
            # try closest prior trading day
            prior = [d for d in sorted(ohlcv) if d <= date]
            if prior:
                date = prior[-1]
            else:
                continue

        future = trading_days_after(ohlcv, date, window)
        if not future:
            continue

        base = ohlcv[date]["close"]
        end = ohlcv[future[-1]]["close"]
        moves.append(abs(end - base) / base)

    return moves


# ── plotting ───────────────────────────────────────────────────────

def _plot(quartile_results):
    """
    quartile_results = {window: [(label, mean_move, n, pressure_range)]}
    """
    n_win = len(WINDOWS)
    fig, axes = plt.subplots(1, n_win, figsize=(5.5 * n_win, 6), sharey=True)
    if n_win == 1:
        axes = [axes]

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    fig.suptitle(f"Test 4: Convergence Pressure vs. Ticker Price Movement\n(generated {ts})",
                 fontsize=14, fontweight="bold")

    cmap = plt.cm.Blues
    for i, w in enumerate(WINDOWS):
        ax = axes[i]
        rows = quartile_results[w]
        labels = [r[0] for r in rows]
        means = [r[1] * 100 for r in rows]
        ns = [r[2] for r in rows]

        colors = [cmap(0.3 + 0.6 * j / max(len(rows) - 1, 1)) for j in range(len(rows))]
        x = np.arange(len(labels))
        bars = ax.bar(x, means, color=colors, alpha=0.85)

        for j, (bar, n) in enumerate(zip(bars, ns)):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                    f"n={n}", ha="center", va="bottom", fontsize=9)

        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=8, rotation=15, ha="right")
        ax.set_title(f"{w}-Day Window")
        if i == 0:
            ax.set_ylabel("Mean |Price Change| (%)")
        ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    out = OUT_DIR / "convergence_pressure_backtest.png"
    fig.savefig(str(out), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  -> {out}")


# ── entry point ────────────────────────────────────────────────────

def run():
    """Run Test 4.  Returns quartile stats + pass/fail."""
    conn = get_db()

    print_header("Test 4: Convergence Pressure Backtest")

    records = _load_convergence(conn)
    print(f"\n  {len(records)} convergence records with pressure_score > 0")

    if len(records) < 4:
        print("  [INSUFFICIENT DATA] Need >= 4 real-ticker convergence records for quartile analysis.")
        if records:
            print(f"  Pressure scores present: {[r['pressure_score'] for r in records]}")
        conn.close()
        return {"quartiles": {}, "pass": False, "reason": "insufficient_data"}

    quartiles = _quartile_split(records)
    print(f"  Split into {len(quartiles)} groups:")
    for label, recs in quartiles:
        scores = [r["pressure_score"] for r in recs]
        print(f"    {label}: n={len(recs)}  pressure=[{min(scores):.2f} – {max(scores):.2f}]")

    quartile_results: dict[int, list] = {}

    for w in WINDOWS:
        quartile_results[w] = []
        for label, recs in quartiles:
            moves = _price_moves(recs, conn, w)
            mean_move = float(np.mean(moves)) if moves else 0.0
            scores = [r["pressure_score"] for r in recs]
            quartile_results[w].append((label, mean_move, len(moves),
                                        f"{min(scores):.2f}–{max(scores):.2f}"))

    # summary table
    print_separator()
    print(f"  {'Window':>7} {'Quartile':<18} {'Mean |chg|':>12} {'n':>5} {'Pressure Range':>16}")
    for w in WINDOWS:
        for label, mean_m, n, pr in quartile_results[w]:
            print(f"  {w:>6}d {label:<18} {mean_m*100:>11.3f}% {n:>5} {pr:>16}")
        print()

    # pass criteria: top group >= 1.5x bottom group at any tested window
    success = False
    for w in WINDOWS:
        rows = quartile_results[w]
        if len(rows) >= 2:
            bot = rows[0][1]
            top = rows[-1][1]
            if bot > 0:
                ratio = top / bot
                print(f"  {w}d: top/bottom ratio = {ratio:.2f}x  (need >= 1.5x)")
                if ratio >= 1.5:
                    success = True

    status = "PASS" if success else "FAIL"
    print(f"\n  Test 4 overall: {status}  (top quartile >= 1.5x bottom at 1d or 3d)")

    _plot(quartile_results)
    conn.close()
    return {"quartiles": quartile_results, "pass": success}


if __name__ == "__main__":
    run()
