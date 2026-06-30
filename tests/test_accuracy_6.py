from types import SimpleNamespace
from pathlib import Path
import sys

_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import signal_validation.llm_direction_accuracy as mod


def test_accuracy_6_passes_when_overall_and_confirmed_clear_threshold(monkeypatch):
    fake_conn = SimpleNamespace(close=lambda: None)
    signals = [
        {"narrative_id": "n1", "direction": "bullish", "timeframe": "near_term", "certainty": "confirmed", "confidence": 0.9, "ticker": "AAPL", "extracted_at": "2026-04-01T12:00:00+00:00"},
        {"narrative_id": "n2", "direction": "bearish", "timeframe": "near_term", "certainty": "expected", "confidence": 0.7, "ticker": "MSFT", "extracted_at": "2026-04-01T12:00:00+00:00"},
        {"narrative_id": "n3", "direction": "bullish", "timeframe": "immediate", "certainty": "speculative", "confidence": 0.4, "ticker": "NVDA", "extracted_at": "2026-04-01T12:00:00+00:00"},
    ]

    results = {
        "AAPL": (True, 0.03),
        "MSFT": (True, -0.02),
        "NVDA": (False, -0.01),
    }

    monkeypatch.setattr(mod, "get_db", lambda: fake_conn)
    monkeypatch.setattr(mod, "_load_signals", lambda conn: signals)
    monkeypatch.setattr(mod, "_check_direction", lambda signal, conn: results[signal["ticker"]])
    monkeypatch.setattr(mod, "_plot", lambda *args, **kwargs: None)

    result = mod.run()

    assert result["pass"] is True
    assert result["overall_accuracy"] > 0.55
    assert result["by_certainty"]["confirmed"]["accuracy"] > 0.65


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__]))
