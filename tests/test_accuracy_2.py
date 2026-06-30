from types import SimpleNamespace
from pathlib import Path
import sys

_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import signal_validation.threshold_hit_rate as mod


def test_accuracy_2_passes_when_t70_lift_clears_threshold(monkeypatch):
    fake_conn = SimpleNamespace(close=lambda: None)

    def fake_find_crossings(conn, threshold):
        return [("nid", "Narrative", "AAPL", "2026-04-01")] if threshold == 0.7 else []

    def fake_hit_rate(crossings, conn, window):
        return (4, 5, 0.80) if window == 5 else (2, 5, 0.40)

    def fake_baseline(conn, tickers, n_samples_per_ticker, window):
        return 0.60 if window == 5 else 0.20

    monkeypatch.setattr(mod, "get_db", lambda: fake_conn)
    monkeypatch.setattr(mod, "_find_crossings", fake_find_crossings)
    monkeypatch.setattr(mod, "_hit_rate", fake_hit_rate)
    monkeypatch.setattr(mod, "_baseline", fake_baseline)
    monkeypatch.setattr(mod, "_plot", lambda results: None)

    result = mod.run()

    assert result["pass"] is True
    assert abs(result["results"][0.7][5]["lift"] - 0.20) < 1e-9


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__]))
