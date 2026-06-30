"""Shared utilities for signal accuracy tests."""

import sqlite3
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import yfinance as yf

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "narrative_engine.db"
OUT_DIR = Path(__file__).resolve().parent

# Make project root importable (for source_tiers etc.)
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ── Price data (OHLCV) ────────────────────────────────────────────

_ohlcv_cache: dict[str, dict[str, dict]] = {}


def _safe(val):
    """Convert numpy scalar to Python float."""
    return float(val.item() if hasattr(val, "item") else val)


def get_ohlcv(ticker: str, start: str, end: str) -> dict[str, dict]:
    """
    Fetch daily OHLCV from yfinance with 30-day pre-buffer and 15-day
    post-buffer.  Returns {date_str: {close, volume}}.
    """
    key = f"{ticker}|{start}|{end}"
    if key in _ohlcv_cache:
        return _ohlcv_cache[key]

    s = datetime.strptime(start, "%Y-%m-%d") - timedelta(days=30)
    e = datetime.strptime(end, "%Y-%m-%d") + timedelta(days=15)
    try:
        df = yf.download(
            ticker,
            start=s.strftime("%Y-%m-%d"),
            end=e.strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=True,
        )
        if df.empty:
            _ohlcv_cache[key] = {}
            return {}
        result = {}
        for idx, row in df.iterrows():
            d = idx.strftime("%Y-%m-%d")
            result[d] = {
                "close": _safe(row["Close"]),
                "volume": _safe(row["Volume"]),
            }
        _ohlcv_cache[key] = result
        return result
    except Exception as exc:
        print(f"  [WARN] yfinance failed for {ticker}: {exc}")
        _ohlcv_cache[key] = {}
        return {}


def trading_days_after(ohlcv: dict, date: str, n: int) -> list[str]:
    """Next *n* trading dates strictly after *date*."""
    return [d for d in sorted(ohlcv) if d > date][:n]


def trading_days_before(ohlcv: dict, date: str, n: int) -> list[str]:
    """Previous *n* trading dates strictly before *date*."""
    return [d for d in sorted(ohlcv) if d < date][-n:]


def daily_returns(ohlcv: dict) -> dict[str, float]:
    """Compute {date: pct_change} from OHLCV dict."""
    dates = sorted(ohlcv)
    out = {}
    for i in range(1, len(dates)):
        prev = ohlcv[dates[i - 1]]["close"]
        cur = ohlcv[dates[i]]["close"]
        if prev != 0:
            out[dates[i]] = (cur - prev) / prev
    return out


def avg_volume_window(ohlcv: dict, date: str, window: int = 20) -> float:
    """Average volume over the *window* trading days ending on *date*."""
    before = trading_days_before(ohlcv, date, window)
    if not before:
        # include the date itself if we have no prior data
        before = [date] if date in ohlcv else []
    vols = [ohlcv[d]["volume"] for d in before if d in ohlcv and ohlcv[d]["volume"] > 0]
    return float(np.mean(vols)) if vols else 0.0


# ── Narrative / ticker helpers ────────────────────────────────────

def narrative_ticker_pairs(conn, min_snaps: int = 3, max_pairs: int = 30):
    """
    Return [(narrative_id, name, ticker, snap_count, ns_score)].
    Skips TOPIC: pseudo-tickers and suppressed narratives.
    """
    c = conn.cursor()
    c.execute("""
        SELECT n.narrative_id, n.name, n.linked_assets, n.ns_score,
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
        assets = json.loads(row["linked_assets"])
        for a in assets:
            ticker = a.get("ticker", "") if isinstance(a, dict) else (a if isinstance(a, str) else "")
            if not ticker or ticker.startswith("TOPIC:"):
                continue
            key = (row["narrative_id"], ticker)
            if key not in seen and row["snap_days"] >= min_snaps:
                pairs.append((row["narrative_id"], row["name"], ticker, row["snap_days"], row["ns_score"]))
                seen.add(key)
            if len(pairs) >= max_pairs:
                return pairs
    return pairs


def snapshot_date_range(conn) -> tuple[str, str]:
    """(min_date, max_date) across all narrative_snapshots."""
    c = conn.cursor()
    c.execute("SELECT MIN(snapshot_date), MAX(snapshot_date) FROM narrative_snapshots")
    row = c.fetchone()
    return row[0] or "2026-01-01", row[1] or "2026-04-01"


def print_header(title: str):
    print(f"\n{'=' * 90}")
    print(f"  {title}")
    print(f"{'=' * 90}")


def print_separator():
    print(f"{'─' * 90}")
