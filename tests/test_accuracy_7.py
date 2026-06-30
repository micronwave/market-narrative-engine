from types import SimpleNamespace
from pathlib import Path
import sys

_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import signal_validation.burst_hit_rate as mod


def test_accuracy_7_passes_when_combined_hit_rate_is_above_threshold(monkeypatch):
    fake_conn = SimpleNamespace(close=lambda: None)
    events = [
        ("n1", "Narrative 1", "AAPL", "2026-04-01", 3.2),
        ("n2", "Narrative 2", "MSFT", "2026-04-01", 3.4),
        ("n3", "Narrative 3", "NVDA", "2026-04-01", 3.5),
    ]

    def fake_eval(ticker, date, conn):
        if ticker == "NVDA":
            return (False, False, 1.1, 0.01)
        return (True, False, 1.6, 0.03)

    monkeypatch.setattr(mod, "get_db", lambda: fake_conn)
    monkeypatch.setattr(mod, "_find_burst_events", lambda conn: events)
    monkeypatch.setattr(mod, "_evaluate_event", fake_eval)
    monkeypatch.setattr(mod, "_plot", lambda *args, **kwargs: None)

    result = mod.run()

    assert result["pass"] is True
    assert result["combined_rate"] > 0.40


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__]))
