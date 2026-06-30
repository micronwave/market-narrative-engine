from types import SimpleNamespace
from pathlib import Path
import sys

_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import signal_validation.lifecycle_volatility as mod


def test_accuracy_3_passes_with_early_stage_volatility(monkeypatch):
    fake_conn = SimpleNamespace(close=lambda: None)

    stage_returns = {
        "Emerging": [0.03, 0.031, 0.029, 0.032, 0.028],
        "Growing": [0.04, 0.042, 0.039, 0.041, 0.043],
        "Mature": [0.01, 0.011, 0.012, 0.009, 0.010],
        "Declining": [0.008, 0.009, 0.007, 0.008, 0.006],
        "Dormant": [0.002, 0.003, 0.002, 0.001, 0.002],
    }

    monkeypatch.setattr(mod, "get_db", lambda: fake_conn)
    monkeypatch.setattr(mod, "_collect", lambda conn: stage_returns)
    monkeypatch.setattr(mod, "_plot", lambda stage_returns, stat_rows: None)

    result = mod.run()

    assert result["pass"] is True
    assert any(row["stage"] == "Growing" and row["p_value"] < 0.05 for row in result["stats"])


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__]))
