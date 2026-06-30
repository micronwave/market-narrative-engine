"""
Narrative Quality Audit — Phase 6: Monitoring & Observability Tests

Section 14: Pipeline Quality Metrics (Step 21)
  T1: Step 21 code block exists in pipeline.py
  T2: Step 21 logs to pipeline_run_log with step_name='quality_metrics'
  T3: Step 21 metrics include all four required keys
  T4: Step 21 is non-fatal (wrapped in try/except)
  T5: count_suppressed_with_documents repository method exists

Section 15: Admin Duplicate Detection Endpoint
  T6: GET /api/admin/narrative-quality returns 200
  T7: Response contains all required top-level fields
  T8: potential_duplicates entries have correct shape
  T9: Similarity values are between 0 and 1
  T10: Singletons have correct shape
  T11: total_active matches known narrative count
  T12: Endpoint handles gracefully when DB exists
  T13: Admin auth gates JWT non-admin users (code inspection)
"""

import json
import sys
import time
from pathlib import Path

_ROOT = str(Path(__file__).parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_results = []


def S(section: str):
    print(f"\n--- {section} ---")


def T(name: str, condition: bool, details: str = ""):
    _results.append((name, condition))
    marker = "\u2713" if condition else "\u2717"
    msg = f"  [{marker}] {name}"
    if details and not condition:
        msg += f"\n      details: {details}"
    elif details and condition:
        msg += f"  ({details})"
    print(msg)


# ===========================================================================
# Section 14: Pipeline Quality Metrics (Step 21)
# ===========================================================================
S("Section 14: Pipeline Quality Metrics")

pipeline_src = Path(_ROOT, "pipeline.py").read_text(encoding="utf-8")

T(
    "T1: Step 21 quality_metrics block exists in pipeline.py",
    "Step 21: Quality Metrics" in pipeline_src and "quality_metrics" in pipeline_src,
)

T(
    "T2: Step 21 logs via _log_step with step_name='quality_metrics'",
    '_log_step(repository, cycle_id, 21, "quality_metrics"' in pipeline_src,
)

# Verify all four metric keys are present in the step
T(
    "T3: Step 21 computes all four metrics (active, dupes, singletons, leak)",
    all(k in pipeline_src for k in [
        "active=", "potential_dupes=", "singletons=", "suppressed_leak="
    ]),
)

# Verify non-fatal pattern
T(
    "T4: Step 21 is non-fatal (has except Exception handler)",
    'Step 21 (quality metrics) failed' in pipeline_src,
)

# Verify repository method exists
from repository import SqliteRepository
from settings import get_settings

settings = get_settings()
repo = SqliteRepository(settings.DB_PATH)
repo.migrate()

T(
    "T5: count_suppressed_with_documents method exists and returns int",
    hasattr(repo, "count_suppressed_with_documents")
    and isinstance(repo.count_suppressed_with_documents(), int),
    f"value={repo.count_suppressed_with_documents()}",
)

# ===========================================================================
# Section 15: Admin Duplicate Detection Endpoint
# ===========================================================================
S("Section 15: Admin Narrative Quality Endpoint")

from fastapi.testclient import TestClient  # noqa: E402
from api.main import app  # noqa: E402

with TestClient(app) as client:
    start = time.monotonic()
    resp = client.get("/api/admin/narrative-quality")
    elapsed_ms = (time.monotonic() - start) * 1000

    T(
        "T6: GET /api/admin/narrative-quality returns 200",
        resp.status_code == 200,
        f"got {resp.status_code}",
    )

    data = resp.json()

    required_fields = {"total_active", "potential_duplicates", "singletons",
                       "unlabeled_count", "human_review_pending"}
    T(
        "T7: Response contains all required top-level fields",
        required_fields.issubset(set(data.keys())),
        f"missing: {required_fields - set(data.keys())}" if not required_fields.issubset(set(data.keys())) else "",
    )

    # Check duplicate pair shape
    dupes = data.get("potential_duplicates", [])
    dupe_shape_ok = True
    dupe_fields = {"narrative_a", "narrative_b", "name_a", "name_b", "similarity"}
    for d in dupes:
        if not dupe_fields.issubset(set(d.keys())):
            dupe_shape_ok = False
            break

    T(
        "T8: potential_duplicates entries have correct shape",
        dupe_shape_ok,
        f"{len(dupes)} duplicate pairs found",
    )

    # Check similarity values
    sims_valid = all(0 <= d["similarity"] <= 1 for d in dupes) if dupes else True
    T(
        "T9: Similarity values are between 0 and 1",
        sims_valid,
        f"checked {len(dupes)} pairs",
    )

    # Check singleton shape
    singletons = data.get("singletons", [])
    singleton_fields = {"narrative_id", "name", "document_count"}
    singleton_shape_ok = all(
        singleton_fields.issubset(set(s.keys())) for s in singletons
    ) if singletons else True

    T(
        "T10: Singletons have correct shape",
        singleton_shape_ok,
        f"{len(singletons)} singletons found",
    )

    # Cross-check total_active with repository
    active_narratives = repo.get_all_active_narratives()
    T(
        "T11: total_active matches repository count",
        data.get("total_active") == len(active_narratives),
        f"endpoint={data.get('total_active')} repo={len(active_narratives)}",
    )

    T(
        "T12: Response time acceptable (< 2s)",
        elapsed_ms < 2000,
        f"{elapsed_ms:.0f}ms",
    )

    # Verify admin auth gating code exists
    main_src = Path(_ROOT, "api", "app_legacy.py").read_text(encoding="utf-8")
    T(
        "T13: Admin auth gates JWT non-admin users",
        'get_admin_user' in main_src and 'Requires role: admin' in main_src,
    )

# ===========================================================================
# Summary
# ===========================================================================
print("\n" + "=" * 50)
passed = sum(1 for _, c in _results if c)
total = len(_results)
print(f"RESULTS: {passed}/{total} passed")
if passed < total:
    for name, c in _results:
        if not c:
            print(f"  FAILED: {name}")
    sys.exit(1)
else:
    print("ALL TESTS PASSED")
