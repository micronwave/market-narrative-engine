from types import SimpleNamespace
from pathlib import Path
import sys

_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import signal_validation.convergence_backtest as mod


def test_accuracy_4_passes_when_top_quartile_moves_more(monkeypatch):
    fake_conn = SimpleNamespace(close=lambda: None)
    records = [
        {"ticker": "AAPL", "pressure_score": 0.10, "computed_at": "2026-04-01T00:00:00+00:00", "convergence_count": 1},
        {"ticker": "MSFT", "pressure_score": 0.20, "computed_at": "2026-04-01T00:00:00+00:00", "convergence_count": 1},
        {"ticker": "NVDA", "pressure_score": 0.30, "computed_at": "2026-04-01T00:00:00+00:00", "convergence_count": 1},
        {"ticker": "AMD", "pressure_score": 0.40, "computed_at": "2026-04-01T00:00:00+00:00", "convergence_count": 1},
        {"ticker": "GOOG", "pressure_score": 0.50, "computed_at": "2026-04-01T00:00:00+00:00", "convergence_count": 1},
        {"ticker": "META", "pressure_score": 0.60, "computed_at": "2026-04-01T00:00:00+00:00", "convergence_count": 1},
        {"ticker": "TSLA", "pressure_score": 0.70, "computed_at": "2026-04-01T00:00:00+00:00", "convergence_count": 1},
        {"ticker": "AVGO", "pressure_score": 0.80, "computed_at": "2026-04-01T00:00:00+00:00", "convergence_count": 1},
    ]

    def fake_price_moves(group, conn, window):
        if group and group[0]["pressure_score"] >= 0.50:
            return [0.03, 0.04]
        return [0.01, 0.01]

    monkeypatch.setattr(mod, "get_db", lambda: fake_conn)
    monkeypatch.setattr(mod, "_load_convergence", lambda conn: records)
    monkeypatch.setattr(mod, "_price_moves", fake_price_moves)
    monkeypatch.setattr(mod, "_plot", lambda quartile_results: None)

    result = mod.run()

    assert result["pass"] is True
    assert 1 in result["quartiles"]


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__]))
