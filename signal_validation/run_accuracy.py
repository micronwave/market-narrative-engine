"""
Signal Accuracy Test Runner

Executes Tests 1–7 from signal_accuracy_tests.md, collects results,
and evaluates the GO/NO-GO gate for proceeding to Block 3.

Usage:
    python -m signal_validation.run_accuracy          # all tests
    python -m signal_validation.run_accuracy 2 6 7    # specific tests

GO/NO-GO criteria (from signal_accuracy_tests.md):
  - At least 3 of Tests 1–4 produce positive results.
  - Test 6 (LLM direction) accuracy > 55%.
  - Confirmed certainty should also clear 65% when available.
  - If fewer than 3 tests pass, iterate on signal quality before expanding.
"""

import sys
import traceback
from datetime import datetime
from pathlib import Path

from .shared import print_header, print_separator

# Import each test module
from . import component_lead_correlation  # Test 1
from . import threshold_hit_rate      # Test 2
from . import lifecycle_volatility    # Test 3
from . import convergence_backtest    # Test 4
from . import source_escalation       # Test 5
from . import llm_direction_accuracy  # Test 6
from . import burst_hit_rate          # Test 7

TESTS = {
    1: ("Per-Component Lead Correlation", component_lead_correlation),
    2: ("NS Threshold Hit Rate",         threshold_hit_rate),
    3: ("Lifecycle Stage vs Volatility",  lifecycle_volatility),
    4: ("Convergence Pressure Backtest",  convergence_backtest),
    5: ("Source Escalation Indicator",    source_escalation),
    6: ("LLM Direction Accuracy",        llm_direction_accuracy),
    7: ("Burst Velocity Hit Rate",       burst_hit_rate),
}

BUILD_LOG_PATH = Path(__file__).resolve().parent.parent / "BUILD_LOG.md"


def _append_build_log(results: dict, test_ids: list[int]) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "",
        f"## Signal Accuracy Suite — {ts}",
        "",
        "| Test | Status | Key Result |",
        "|---|---|---:|",
    ]

    for tid in test_ids:
        name = TESTS.get(tid, (f"Test {tid}",))[0]
        result = results.get(tid, {}) if results else {}
        passed = bool(result.get("pass"))
        status = "PASS" if passed else "FAIL"

        key_result = "N/A"
        if tid == 1:
            key_result = str(result.get("strong_components", 0))
        elif tid == 2:
            key_result = f"{result.get('results', {}).get(0.7, {}).get(5, {}).get('lift', 0.0):+.1%}"
        elif tid == 3:
            stats = result.get("stats") or []
            key_result = str(sum(1 for row in stats if row.get("p_value") is not None))
        elif tid == 4:
            quartiles = result.get("quartiles") or {}
            key_result = str(len(quartiles))
        elif tid == 5:
            pre = result.get("pre")
            post = result.get("post")
            if pre and post and pre > 0:
                key_result = f"{((post - pre) / pre):+.1%}"
        elif tid == 6:
            key_result = f"{result.get('overall_accuracy', 0.0):.1%}"
        elif tid == 7:
            key_result = f"{result.get('combined_rate', 0.0):.1%}"

        lines.append(f"| {tid} {name} | {status} | {key_result} |")

    gate = results.get("gate", {}) if results else {}
    lines.extend([
        "",
        f"- Gate: {gate.get('status', 'N/A')}",
        f"- Tests 1-4 passing: {gate.get('tests_1_4', 'N/A')}",
        f"- Test 6 accuracy: {gate.get('test_6_acc', 0.0):.1%}" if gate else "- Test 6 accuracy: N/A",
    ])

    try:
        with open(BUILD_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except Exception as exc:
        print(f"  [WARN] Failed to append accuracy summary to BUILD_LOG.md: {exc}")


def run(test_ids=None):
    """
    Execute selected tests (or all).  Returns dict of results keyed by
    test number, plus a top-level 'gate' key with GO/NO-GO status.
    """
    if test_ids is None:
        test_ids = sorted(TESTS.keys())
    else:
        test_ids = list(test_ids)

    print_header("Signal Accuracy Test Suite")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"  Started at {ts}")
    print(f"  Running tests: {test_ids}\n")

    results = {}

    for tid in test_ids:
        if tid not in TESTS:
            print(f"  [SKIP] Unknown test ID: {tid}")
            continue

        name, module = TESTS[tid]
        try:
            res = module.run()
            results[tid] = res
        except Exception:
            print(f"\n  [ERROR] Test {tid} ({name}) failed:")
            traceback.print_exc()
            results[tid] = {"pass": False, "reason": "exception"}

    # ── GO / NO-GO gate ──────────────────────────────────────────

    print_header("GO / NO-GO Gate Evaluation")

    # Tests 1–4 pass count
    tests_1_4_pass = 0
    t1_pass = results.get(1, {}).get("pass", False)
    print(f"  Test 1 ({TESTS[1][0]}): {'PASS' if t1_pass else 'FAIL'}")
    tests_1_4_pass += int(t1_pass)

    for tid in [2, 3, 4]:
        passed = results.get(tid, {}).get("pass", False)
        print(f"  Test {tid} ({TESTS[tid][0]}): {'PASS' if passed else 'FAIL'}")
        tests_1_4_pass += int(passed)

    # Test 5 (informational)
    t5_pass = results.get(5, {}).get("pass", False)
    print(f"  Test 5 ({TESTS[5][0]}): {'PASS' if t5_pass else 'FAIL'}")

    # Test 6 critical
    t6_pass = results.get(6, {}).get("pass", False)
    t6_acc = results.get(6, {}).get("overall_accuracy", 0)
    print(f"  Test 6 ({TESTS[6][0]}): {'PASS' if t6_pass else 'FAIL'}  (accuracy={t6_acc:.1%})")

    # Test 7 (informational)
    t7_pass = results.get(7, {}).get("pass", False)
    print(f"  Test 7 ({TESTS[7][0]}): {'PASS' if t7_pass else 'FAIL'}")

    # Gate decision
    print_separator()
    print(f"  Tests 1–4 passing: {tests_1_4_pass}/4  (need >= 3)")
    print(f"  Test 6 accuracy:   {t6_acc:.1%}     (need > 55%)")

    gate_pass = tests_1_4_pass >= 3 and t6_pass
    gate_status = "GO" if gate_pass else "NO-GO"

    if not gate_pass:
        reasons = []
        if tests_1_4_pass < 3:
            reasons.append(f"only {tests_1_4_pass}/4 of Tests 1-4 pass (need 3)")
        if not t6_pass:
            reasons.append(f"LLM direction accuracy {t6_acc:.1%} <= 55%")
        recommendation = "Iterate on signal quality before expanding to Block 3."
        print(f"\n  GATE: {gate_status}")
        print(f"  Reason: {'; '.join(reasons)}")
        print(f"  Recommendation: {recommendation}")
    else:
        print(f"\n  GATE: {gate_status}  — proceed to Block 3 (Charting & Sentiment)")

    total_pass = sum(1 for r in results.values() if r.get("pass"))
    print(f"\n  Total: {total_pass}/{len(results)} tests passed")
    print(f"  Finished at {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    results["gate"] = {"status": gate_status, "tests_1_4": tests_1_4_pass, "test_6_acc": t6_acc}
    _append_build_log(results, [tid for tid in test_ids if tid in TESTS])
    return results


if __name__ == "__main__":
    ids = None
    if len(sys.argv) > 1:
        ids = [int(x) for x in sys.argv[1:]]
    run(ids)
