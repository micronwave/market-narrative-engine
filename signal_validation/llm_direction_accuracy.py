"""
Test 6: LLM Direction Accuracy

Question: Does the LLM-extracted direction (bullish/bearish/neutral)
          match actual price direction over the stated timeframe?

Method:
  - Pull all narrative_signals where direction != 'neutral' and
    timeframe != 'unknown'.
  - Join with impact_scores to get ticker(s) for each narrative.
  - Map timeframe to trading days: immediate=1, near_term=5, long_term=20.
  - Check whether ticker price moved in the predicted direction over
    that window.
  - Stratify by certainty level (speculative, rumored, expected, confirmed).

Success criteria: Overall accuracy > 55 %. "Confirmed" certainty
should exceed 65 %.

Output: llm_direction_accuracy.png
"""

from datetime import datetime
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import json

from .shared import (
    get_db, get_ohlcv, trading_days_after, snapshot_date_range,
    print_header, print_separator, OUT_DIR,
)

TIMEFRAME_DAYS = {
    "immediate":  1,
    "near_term":  5,
    "short_term": 5,   # alias
    "long_term":  20,
    "medium_term": 10,  # alias
}

CERTAINTY_ORDER = ["speculative", "rumored", "expected", "confirmed"]
CERTAINTY_COLORS = {
    "speculative": "#F5A623",
    "rumored":     "#BD10E0",
    "expected":    "#4A90D9",
    "confirmed":   "#7ED321",
}


# ── data collection ────────────────────────────────────────────────

def _load_signals(conn):
    """
    Return one row per signal/ticker pair:
      [(narrative_id, direction, timeframe, certainty, confidence,
        ticker, extracted_at)]
    by joining narrative_signals with narratives.linked_assets.
    """
    c = conn.cursor()
    c.execute("""
        SELECT ns.narrative_id, ns.direction, ns.timeframe, ns.certainty,
               ns.confidence, ns.extracted_at,
               n.linked_assets, n.name
        FROM narrative_signals ns
        JOIN narratives n ON ns.narrative_id = n.narrative_id
        WHERE ns.direction != 'neutral'
          AND ns.timeframe != 'unknown'
          AND n.suppressed = 0
          AND n.linked_assets IS NOT NULL
          AND n.linked_assets != '[]'
    """)
    rows = []
    for row in c.fetchall():
        try:
            assets = json.loads(row["linked_assets"])
        except (json.JSONDecodeError, TypeError):
            continue
        tickers = []
        for a in assets:
            ticker = a.get("ticker", "") if isinstance(a, dict) else (a if isinstance(a, str) else "")
            if ticker and not ticker.startswith("TOPIC:"):
                tickers.append(ticker)
        for ticker in tickers:
            rows.append({
                "narrative_id": row["narrative_id"],
                "name": row["name"],
                "direction": row["direction"],
                "timeframe": row["timeframe"],
                "certainty": row["certainty"],
                "confidence": row["confidence"],
                "ticker": ticker,
                "extracted_at": row["extracted_at"],
            })
    return rows


def _check_direction(signal, conn):
    """
    Check whether the ticker moved in the predicted direction over the
    timeframe window.  Returns (correct: bool, actual_pct: float) or None.
    """
    tf = signal["timeframe"]
    window = TIMEFRAME_DAYS.get(tf)
    if window is None:
        return None

    ticker = signal["ticker"]
    anchor = signal["extracted_at"][:10] if signal["extracted_at"] else None
    if not anchor:
        return None

    min_d, max_d = snapshot_date_range(conn)
    ohlcv = get_ohlcv(ticker, min_d, max_d)
    if not ohlcv:
        return None

    # Find nearest trading day to anchor
    if anchor not in ohlcv:
        prior = [d for d in sorted(ohlcv) if d <= anchor]
        if not prior:
            return None
        anchor = prior[-1]

    future = trading_days_after(ohlcv, anchor, window)
    if not future:
        return None

    base = ohlcv[anchor]["close"]
    end = ohlcv[future[-1]]["close"]
    pct = (end - base) / base

    direction = signal["direction"]
    if direction == "bullish":
        correct = pct > 0
    elif direction == "bearish":
        correct = pct < 0
    else:
        return None

    return correct, pct


# ── plotting ───────────────────────────────────────────────────────

def _plot(by_certainty, overall_acc, overall_n):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    fig.suptitle(f"Test 6: LLM Direction Accuracy\n(generated {ts})",
                 fontsize=14, fontweight="bold")

    # ── left: accuracy by certainty ──
    labels, accs, ns, colors = [], [], [], []
    for cert in CERTAINTY_ORDER:
        if cert in by_certainty and by_certainty[cert]["n"] > 0:
            labels.append(cert.title())
            accs.append(by_certainty[cert]["accuracy"] * 100)
            ns.append(by_certainty[cert]["n"])
            colors.append(CERTAINTY_COLORS.get(cert, "#999"))

    if labels:
        x = np.arange(len(labels))
        bars = ax1.bar(x, accs, color=colors, alpha=0.85, width=0.55)
        for j, (bar, n) in enumerate(zip(bars, ns)):
            ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                     f"n={n}", ha="center", va="bottom", fontsize=9)
        ax1.axhline(y=55, color="#E5533C", linestyle="--", linewidth=1.5,
                    label="55% threshold")
        ax1.axhline(y=50, color="#999", linestyle=":", linewidth=1, label="Coin flip")
        ax1.set_xticks(x)
        ax1.set_xticklabels(labels)
        ax1.set_ylabel("Accuracy (%)")
        ax1.set_title("Accuracy by Certainty Level")
        ax1.legend(fontsize=9)
        ax1.set_ylim(0, 100)
        ax1.grid(axis="y", alpha=0.3)

    # ── right: overall accuracy gauge ──
    ax2.set_xlim(-1.5, 1.5)
    ax2.set_ylim(-1.5, 1.5)
    ax2.set_aspect("equal")
    ax2.axis("off")

    color = "#7ED321" if overall_acc >= 0.55 else ("#F5A623" if overall_acc >= 0.50 else "#E5533C")
    circle = plt.Circle((0, 0), 1.0, fill=False, linewidth=6, color=color)
    ax2.add_patch(circle)
    ax2.text(0, 0.15, f"{overall_acc*100:.1f}%", ha="center", va="center",
             fontsize=36, fontweight="bold", color=color)
    ax2.text(0, -0.35, f"n={overall_n}", ha="center", va="center", fontsize=14, color="#666")
    ax2.set_title("Overall Direction Accuracy", fontsize=13, fontweight="bold")

    threshold_label = "PASS (>55%)" if overall_acc >= 0.55 else "FAIL (<55%)"
    ax2.text(0, -1.2, threshold_label, ha="center", va="center", fontsize=12,
             fontweight="bold", color=color)

    plt.tight_layout()
    out = OUT_DIR / "llm_direction_accuracy.png"
    fig.savefig(str(out), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  -> {out}")


# ── entry point ────────────────────────────────────────────────────

def run():
    """Run Test 6.  Returns accuracy stats + pass/fail."""
    conn = get_db()

    print_header("Test 6: LLM Direction Accuracy")

    signals = _load_signals(conn)
    print(f"\n  {len(signals)} directional signal/ticker pairs")

    if not signals:
        print("  [INSUFFICIENT DATA] No directional signals joined with tickers.")
        conn.close()
        return {"overall": 0, "by_certainty": {}, "pass": False, "reason": "insufficient_data"}

    # evaluate each signal
    correct_total = 0
    total = 0
    by_certainty: dict[str, dict] = defaultdict(lambda: {"correct": 0, "total": 0, "magnitudes": []})

    for sig in signals:
        result = _check_direction(sig, conn)
        if result is None:
            continue

        is_correct, actual_pct = result
        cert = sig["certainty"] or "speculative"
        total += 1
        by_certainty[cert]["total"] += 1
        if is_correct:
            correct_total += 1
            by_certainty[cert]["correct"] += 1
            by_certainty[cert]["magnitudes"].append(abs(actual_pct))

    overall_acc = correct_total / total if total else 0.0

    # compute per-certainty accuracy
    by_cert_stats = {}
    for cert in CERTAINTY_ORDER:
        if cert in by_certainty:
            d = by_certainty[cert]
            acc = d["correct"] / d["total"] if d["total"] else 0.0
            avg_mag = float(np.mean(d["magnitudes"])) if d["magnitudes"] else 0.0
            by_cert_stats[cert] = {"accuracy": acc, "n": d["total"],
                                   "correct": d["correct"], "avg_mag_correct": avg_mag}

    # summary table
    print_separator()
    print(f"  {'Certainty':<14} {'Accuracy':>10} {'Correct':>9} {'Total':>7} {'Avg |Mag| Correct':>20}")
    for cert in CERTAINTY_ORDER:
        if cert in by_cert_stats:
            s = by_cert_stats[cert]
            print(f"  {cert:<14} {s['accuracy']:>10.1%} {s['correct']:>9} {s['n']:>7} "
                  f"{s['avg_mag_correct']*100:>19.3f}%")
    print(f"  {'─'*70}")
    print(f"  {'OVERALL':<14} {overall_acc:>10.1%} {correct_total:>9} {total:>7}")

    # pass criteria
    confirmed_acc = by_cert_stats.get("confirmed", {}).get("accuracy", 0)
    overall_pass = overall_acc > 0.55
    confirmed_pass = confirmed_acc > 0.65 if "confirmed" in by_cert_stats else None

    print(f"\n  Overall accuracy: {overall_acc:.1%}  (need > 55%)  {'PASS' if overall_pass else 'FAIL'}")
    if confirmed_pass is not None:
        print(f"  Confirmed accuracy: {confirmed_acc:.1%}  (need > 65%)  "
              f"{'PASS' if confirmed_pass else 'FAIL'}")

    success = overall_pass and (confirmed_pass is not False)
    status = "PASS" if success else "FAIL"
    print(f"\n  Test 6 overall: {status}")

    _plot(by_cert_stats, overall_acc, total)
    conn.close()
    return {"overall_accuracy": overall_acc, "by_certainty": by_cert_stats,
            "n": total, "pass": success}


if __name__ == "__main__":
    run()
