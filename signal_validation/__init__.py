"""Signal validation charts and accuracy tests."""

from .generate import generate, METRICS, METRIC_LABELS

from . import component_lead_correlation  # Test 1
# Accuracy tests (Tests 1–7 from signal_accuracy_tests.md)
from . import threshold_hit_rate       # Test 2
from . import lifecycle_volatility     # Test 3
from . import convergence_backtest     # Test 4
from . import source_escalation        # Test 5
from . import llm_direction_accuracy   # Test 6
from . import burst_hit_rate           # Test 7
from . import run_accuracy             # Runner + GO/NO-GO gate

__all__ = [
    "generate", "METRICS", "METRIC_LABELS",
    "component_lead_correlation", "threshold_hit_rate", "lifecycle_volatility", "convergence_backtest",
    "source_escalation", "llm_direction_accuracy", "burst_hit_rate",
    "run_accuracy",
]
