from pathlib import Path
from types import SimpleNamespace
import sys
from unittest.mock import mock_open

_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import signal_validation.component_lead_correlation as mod
import signal_validation.run_accuracy as run_mod


def test_accuracy_1_passes_with_two_strong_components(monkeypatch):
    fake_conn = SimpleNamespace(close=lambda: None)
    report_path = Path(__file__).resolve().parent.parent / "_component_lead_correlation_test.md"

    summary = [
        {
            "metric": "velocity",
            "label": "Velocity",
            "n_pairs": 5,
            "median_r_lead": 0.10,
            "median_abs_r_lead": 0.18,
            "pct_abs_gt_0_2": 0.40,
        },
        {
            "metric": "cohesion",
            "label": "Cohesion",
            "n_pairs": 5,
            "median_r_lead": 0.05,
            "median_abs_r_lead": 0.12,
            "pct_abs_gt_0_2": 0.20,
        },
        {
            "metric": "source_authority_score",
            "label": "Source Authority",
            "n_pairs": 5,
            "median_r_lead": -0.20,
            "median_abs_r_lead": 0.21,
            "pct_abs_gt_0_2": 0.60,
        },
        {
            "metric": "centrality",
            "label": "Centrality",
            "n_pairs": 5,
            "median_r_lead": -0.06,
            "median_abs_r_lead": 0.10,
            "pct_abs_gt_0_2": 0.10,
        },
    ]

    monkeypatch.setattr(mod, "get_db", lambda: fake_conn)
    monkeypatch.setattr(mod, "print_header", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "print_separator", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "_component_rows", lambda conn: (summary, 5, 5))
    monkeypatch.setattr(mod, "_append_build_log", lambda report: None)
    monkeypatch.setattr(mod, "REPORT_PATH", report_path)

    result = mod.run()

    assert result["pass"] is True
    assert result["strong_components"] == 2
    assert report_path.exists()
    assert "Source Authority" in report_path.read_text(encoding="utf-8")


class _FakeModule:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def run(self):
        self.calls += 1
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def test_run_accuracy_selected_ids_unknown_and_log_redirect(monkeypatch):
    fake_tests = {
        1: ("T1", _FakeModule({"pass": True, "strong_components": 2})),
        2: ("T2", _FakeModule({"pass": True, "results": {0.7: {5: {"lift": 0.2}}}})),
        3: ("T3", _FakeModule({"pass": True, "stats": [{"p_value": 0.01}]})),
        4: ("T4", _FakeModule({"pass": False, "quartiles": {1: {}}})),
        5: ("T5", _FakeModule({"pass": True, "pre": 0.01, "post": 0.02})),
        6: ("T6", _FakeModule({"pass": True, "overall_accuracy": 0.61})),
        7: ("T7", _FakeModule({"pass": False, "combined_rate": 0.3})),
    }
    monkeypatch.setattr(run_mod, "TESTS", fake_tests)
    log_path = Path("redirected_build_log.md")
    open_mock = mock_open()
    monkeypatch.setattr(run_mod, "BUILD_LOG_PATH", log_path)
    monkeypatch.setattr(run_mod, "print_header", lambda *_a, **_k: None)
    monkeypatch.setattr(run_mod, "print_separator", lambda *_a, **_k: None)
    monkeypatch.setattr("builtins.open", open_mock)

    out = run_mod.run([1, 2, 3, 4, 5, 6, 7, 99])

    assert out["gate"]["status"] == "GO"
    assert 99 not in out
    assert fake_tests[1][1].calls == 1
    assert fake_tests[7][1].calls == 1
    open_mock.assert_called_once_with(log_path, "a", encoding="utf-8")
    writes = "".join(call.args[0] for call in open_mock().write.call_args_list)
    assert "Signal Accuracy Suite" in writes
    assert "| 1 T1 | PASS | 2 |" in writes


def test_run_accuracy_handles_module_exception(monkeypatch):
    fake_tests = {
        1: ("T1", _FakeModule({"pass": True, "strong_components": 2})),
        2: ("T2", _FakeModule(RuntimeError("boom"))),
        3: ("T3", _FakeModule({"pass": True, "stats": []})),
        4: ("T4", _FakeModule({"pass": True, "quartiles": {1: {}}})),
        5: ("T5", _FakeModule({"pass": True, "pre": 0.01, "post": 0.02})),
        6: ("T6", _FakeModule({"pass": False, "overall_accuracy": 0.2})),
        7: ("T7", _FakeModule({"pass": True, "combined_rate": 0.5})),
    }
    monkeypatch.setattr(run_mod, "TESTS", fake_tests)
    monkeypatch.setattr(run_mod, "BUILD_LOG_PATH", Path("redirected_build_log.md"))
    monkeypatch.setattr(run_mod, "print_header", lambda *_a, **_k: None)
    monkeypatch.setattr(run_mod, "print_separator", lambda *_a, **_k: None)
    monkeypatch.setattr("builtins.open", mock_open())

    out = run_mod.run([2, 6])

    assert out[2]["pass"] is False
    assert out[2]["reason"] == "exception"
    assert out["gate"]["status"] == "NO-GO"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__]))
