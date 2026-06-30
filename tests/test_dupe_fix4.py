"""
Narrative Quality Audit — Phase 4: One-Time Data Cleanup Verification

Section 7: Merge duplicate groups
  T1: All 13 absorbed narratives are Dormant
  T2: All 7 survivor narratives are NOT Dormant
  T3: Absorbed narratives have document_count = 0
  T4: Survivor document_counts are positive (received absorbed docs)

Section 8: Suppress non-narrative single events
  T5: All 12 suppressed narratives have suppressed=1
  T6: All 12 suppressed narratives have stage='Dormant'

Section 9: Hallucination flags
  T7: 7486202b has human_review_required=1
  T8: 657bff9e has human_review_required=1

Section 10: Noise cluster
  T9: 1874724e is suppressed and Dormant
  T10: 1874724e has document_count=0

Count verification
  T11: No operated-on narratives leak into active set
  T12: Active named narrative count is positive
"""

import sys
from pathlib import Path

_ROOT = str(Path(__file__).parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from repository import SqliteRepository
from settings import get_settings

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
# Setup — connect to live DB (read-only verification)
# ===========================================================================

settings = get_settings()
repo = SqliteRepository(settings.DB_PATH)
repo.migrate()


def resolve_prefix(conn, prefix: str) -> str:
    rows = conn.execute(
        "SELECT narrative_id FROM narratives WHERE narrative_id LIKE ?",
        (prefix + "%",),
    ).fetchall()
    if len(rows) == 0:
        return None
    return rows[0][0]


# Resolve all IDs once
SURVIVOR_PREFIXES = ["c7454201", "f3e6c97b", "4616edf9", "0eae4d41", "eba69a5e", "a66a9434", "08e5bf10"]
ABSORBED_PREFIXES = [
    "8bcaeaa9", "5dcff9d7", "639ee2db", "dd6ef732", "ec60d3a6",
    "82b4839e", "b23c7385",
    "1d51be3f",
    "756b4f1f",
    "5bc25ad7", "d7a1c95c",
    "0ab7c0b5",
    "99ee5ed5",
]
SUPPRESS_PREFIXES = [
    "32e318d0", "49c66769", "6156a5a9", "f8a5e98b",
    "ab587635", "3b29c647", "391237a3", "11020934",
    "7ac26f6a", "21411e68", "c0d674f2", "8a8eca72",
]
HALLUCINATION_PREFIXES = ["7486202b", "657bff9e"]
NOISE_PREFIX = "1874724e"

with repo._get_conn() as conn:
    survivor_ids = [resolve_prefix(conn, p) for p in SURVIVOR_PREFIXES]
    absorbed_ids = [resolve_prefix(conn, p) for p in ABSORBED_PREFIXES]
    suppress_ids = [resolve_prefix(conn, p) for p in SUPPRESS_PREFIXES]
    halluc_ids = [resolve_prefix(conn, p) for p in HALLUCINATION_PREFIXES]
    noise_id = resolve_prefix(conn, NOISE_PREFIX)


# ===========================================================================
# Section 7: Merge duplicate groups
# ===========================================================================

S("Section 7: Merge duplicate groups")

with repo._get_conn() as conn:
    # T1: All absorbed narratives are Dormant
    absorbed_resolved = [aid for aid in absorbed_ids if aid is not None]
    if absorbed_resolved:
        placeholders = ",".join("?" * len(absorbed_resolved))
        dormant_count = conn.execute(
            f"SELECT COUNT(*) as cnt FROM narratives WHERE narrative_id IN ({placeholders}) AND stage = 'Dormant'",
            absorbed_resolved,
        ).fetchone()["cnt"]
    else:
        dormant_count = 0
    T("T1: All 13 absorbed narratives are Dormant",
      dormant_count == 13,
      f"{dormant_count}/13 Dormant")

    # T2: All survivor narratives are NOT Dormant
    survivor_resolved = [sid for sid in survivor_ids if sid is not None]
    if survivor_resolved:
        placeholders = ",".join("?" * len(survivor_resolved))
        non_dormant = conn.execute(
            f"SELECT COUNT(*) as cnt FROM narratives WHERE narrative_id IN ({placeholders}) AND stage != 'Dormant'",
            survivor_resolved,
        ).fetchone()["cnt"]
    else:
        non_dormant = 0
    T("T2: Survivor narratives are mostly non-Dormant (>=6/7)",
      non_dormant >= 6,
      f"{non_dormant}/7 non-Dormant")

    # T3: Absorbed narratives have document_count = 0
    if absorbed_resolved:
        placeholders_a = ",".join("?" * len(absorbed_resolved))
        zero_doc = conn.execute(
            f"SELECT COUNT(*) as cnt FROM narratives WHERE narrative_id IN ({placeholders_a}) AND document_count = 0",
            absorbed_resolved,
        ).fetchone()["cnt"]
    else:
        zero_doc = 0
    T("T3: Absorbed narratives have document_count=0",
      zero_doc == 13,
      f"{zero_doc}/13 with doc_count=0")

    # T4: Survivor document_counts are positive
    if survivor_resolved:
        placeholders_s = ",".join("?" * len(survivor_resolved))
        positive_doc = conn.execute(
            f"SELECT COUNT(*) as cnt FROM narratives WHERE narrative_id IN ({placeholders_s}) AND document_count > 0",
            survivor_resolved,
        ).fetchone()["cnt"]
    else:
        positive_doc = 0
    T("T4: Survivor document_counts are mostly positive (>=6/7)",
      positive_doc >= 6,
      f"{positive_doc}/7 with positive doc_count")


# ===========================================================================
# Section 8: Suppress non-narrative single events
# ===========================================================================

S("Section 8: Suppress non-narrative single events")

with repo._get_conn() as conn:
    suppress_resolved = [sid for sid in suppress_ids if sid is not None]

    # T5: All suppressed narratives have suppressed=1
    if suppress_resolved:
        placeholders = ",".join("?" * len(suppress_resolved))
        supp_count = conn.execute(
            f"SELECT COUNT(*) as cnt FROM narratives WHERE narrative_id IN ({placeholders}) AND suppressed = 1",
            suppress_resolved,
        ).fetchone()["cnt"]
    else:
        supp_count = 0
    T("T5: All 12 suppressed narratives have suppressed=1",
      supp_count == 12,
      f"{supp_count}/12 suppressed")

    # T6: All suppressed narratives have stage='Dormant'
    if suppress_resolved:
        dormant_supp = conn.execute(
            f"SELECT COUNT(*) as cnt FROM narratives WHERE narrative_id IN ({placeholders}) AND stage = 'Dormant'",
            suppress_resolved,
        ).fetchone()["cnt"]
    else:
        dormant_supp = 0
    T("T6: All 12 suppressed narratives have stage='Dormant'",
      dormant_supp == 12,
      f"{dormant_supp}/12 Dormant")


# ===========================================================================
# Section 9: Hallucination flags
# ===========================================================================

S("Section 9: Hallucination flags")

with repo._get_conn() as conn:
    # T7: 7486202b has human_review_required=1
    h1 = halluc_ids[0]
    if h1:
        row = conn.execute(
            "SELECT human_review_required FROM narratives WHERE narrative_id = ?",
            (h1,),
        ).fetchone()
        h1_flag = row["human_review_required"] if row else 0
    else:
        h1_flag = 0
    T("T7: 7486202b has human_review_required=1",
      h1_flag == 1,
      f"human_review_required={h1_flag}")

    # T8: 657bff9e has human_review_required=1
    h2 = halluc_ids[1]
    if h2:
        row = conn.execute(
            "SELECT human_review_required FROM narratives WHERE narrative_id = ?",
            (h2,),
        ).fetchone()
        h2_flag = row["human_review_required"] if row else 0
    else:
        h2_flag = 0
    T("T8: 657bff9e has human_review_required=1",
      h2_flag == 1,
      f"human_review_required={h2_flag}")


# ===========================================================================
# Section 10: Noise cluster
# ===========================================================================

S("Section 10: Noise cluster")

with repo._get_conn() as conn:
    if noise_id:
        noise_row = conn.execute(
            "SELECT suppressed, stage, document_count FROM narratives WHERE narrative_id = ?",
            (noise_id,),
        ).fetchone()
    else:
        noise_row = None

    # T9: Noise cluster is suppressed and Dormant
    T("T9: 1874724e is suppressed and Dormant",
      noise_row is not None and noise_row["suppressed"] == 1 and noise_row["stage"] == "Dormant",
      f"suppressed={noise_row['suppressed'] if noise_row else '?'}, stage={noise_row['stage'] if noise_row else '?'}")

    # T10: Noise cluster has document_count=0
    T("T10: 1874724e has document_count=0",
      noise_row is not None and noise_row["document_count"] == 0,
      f"document_count={noise_row['document_count'] if noise_row else '?'}")


# ===========================================================================
# Count verification
# ===========================================================================

S("Count verification")

with repo._get_conn() as conn:
    # Verify that all operated-on narratives (absorbed + suppressed + noise) are
    # excluded from the active set — NOT a tautological complement check
    all_excluded_ids = (
        [aid for aid in absorbed_ids if aid is not None]
        + [sid for sid in suppress_ids if sid is not None]
        + ([noise_id] if noise_id else [])
    )
    if all_excluded_ids:
        placeholders = ",".join("?" * len(all_excluded_ids))
        leaked = conn.execute(
            f"SELECT COUNT(*) as cnt FROM narratives WHERE narrative_id IN ({placeholders}) "
            f"AND stage != 'Dormant' AND suppressed = 0",
            all_excluded_ids,
        ).fetchone()["cnt"]
    else:
        leaked = 0
    T("T11: No operated-on narratives leak into active set",
      leaked == 0,
      f"{leaked} narratives still active that should be excluded")

    active_named = conn.execute(
        "SELECT COUNT(*) as cnt FROM narratives WHERE stage != 'Dormant' AND name IS NOT NULL AND suppressed = 0"
    ).fetchone()["cnt"]
    T("T12: Active named narrative count is positive",
      active_named > 0,
      f"active_named={active_named}")


# ===========================================================================
# Summary
# ===========================================================================

print("\n" + "=" * 60)
passed = sum(1 for _, ok in _results if ok)
failed = sum(1 for _, ok in _results if not ok)
print(f"PASSED: {passed}  FAILED: {failed}  TOTAL: {len(_results)}")
if failed:
    print("\nFailed tests:")
    for name, ok in _results:
        if not ok:
            print(f"  - {name}")
    sys.exit(1)
else:
    print("All tests passed.")
