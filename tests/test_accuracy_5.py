from types import SimpleNamespace
from pathlib import Path
import sys

_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import signal_validation.source_escalation as mod


def test_accuracy_5_passes_when_post_pickup_beats_pre_and_control(monkeypatch):
    fake_conn = SimpleNamespace(close=lambda: None)

    pickups = [
        ("n1", "Narrative 1", 0.70, ["AAPL"], "2026-04-01"),
        ("n2", "Narrative 2", 0.80, ["MSFT"], "2026-04-02"),
    ]
    control = [("c1", "Control 1", 0.68, ["NVDA"]), ("c2", "Control 2", 0.78, ["AMD"])]

    def fake_avg_abs_move(tickers, center_date, conn, direction="after"):
        if direction == "before":
            return 0.01
        if direction == "after":
            return 0.03
        return None

    monkeypatch.setattr(mod, "get_db", lambda: fake_conn)
    monkeypatch.setattr(mod, "_pickup_narratives", lambda conn: pickups)
    monkeypatch.setattr(mod, "_control_narratives", lambda conn, scores: control)
    monkeypatch.setattr(mod, "_avg_abs_move", fake_avg_abs_move)
    monkeypatch.setattr(mod, "_control_avg_move", lambda control, conn: 0.015)
    monkeypatch.setattr(mod, "_plot", lambda *args, **kwargs: None)

    result = mod.run()

    assert result["pass"] is True
    assert result["post"] > result["pre"]
    assert result["control"] < result["post"]


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__]))
