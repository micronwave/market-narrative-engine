"""
Narrative Quality Audit — Phase 2: Merge Infrastructure & Leak Prevention

Section 4: Repository merge method
  T1: merge_narrative reassigns document_evidence rows to survivor
  T2: merge_narrative reassigns narrative_assignments rows to survivor
  T3: survivor document_count equals combined total after merge
  T4: absorbed narrative becomes Dormant with merge note
  T5: vector_store.delete() called on absorbed narrative centroid
  T6: merging an already-Dormant narrative is a no-op (idempotency)

Section 6: Suppressed narrative document leak
  T7: One-time cleanup removes centroids for suppressed narratives
  T8: Step 7 guard skips suppressed narrative matches
  T9: Step 7 guard set is loaded from DB before assignment loop (source check)
"""

import sys
from pathlib import Path

_ROOT = str(Path(__file__).parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import os
import sqlite3
import tempfile

import numpy as np

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
# Helpers
# ===========================================================================

class FakeVectorStore:
    """Minimal vector store mock that tracks delete calls."""
    def __init__(self, fail_on_delete: bool = False):
        self.deleted_ids = []
        self.fail_on_delete = fail_on_delete

    def delete(self, doc_id: str):
        if self.fail_on_delete:
            raise RuntimeError("simulated vector delete failure")
        self.deleted_ids.append(doc_id)


def make_test_repo(db_path: str):
    """Create a SqliteRepository with test data for merge tests."""
    from repository import SqliteRepository
    repo = SqliteRepository(db_path)
    repo.migrate()

    with repo._get_conn() as conn:
        # Create two narratives
        conn.execute(
            "INSERT INTO narratives (narrative_id, name, stage, document_count) VALUES (?, ?, ?, ?)",
            ("surv-001", "Survivor Narrative", "Growing", 3),
        )
        conn.execute(
            "INSERT INTO narratives (narrative_id, name, stage, document_count) VALUES (?, ?, ?, ?)",
            ("absorb-001", "Absorbed Narrative", "Emerging", 2),
        )

        # Create document_evidence rows for both
        for i in range(3):
            conn.execute(
                "INSERT INTO document_evidence (doc_id, narrative_id, source_url, source_domain, excerpt) "
                "VALUES (?, ?, ?, ?, ?)",
                (f"doc-s{i}", "surv-001", f"http://example.com/s{i}", "example.com", f"excerpt-s{i}"),
            )
        for i in range(2):
            conn.execute(
                "INSERT INTO document_evidence (doc_id, narrative_id, source_url, source_domain, excerpt) "
                "VALUES (?, ?, ?, ?, ?)",
                (f"doc-a{i}", "absorb-001", f"http://example.com/a{i}", "example.com", f"excerpt-a{i}"),
            )

        # Create narrative_assignments rows for both
        for i in range(3):
            conn.execute(
                "INSERT INTO narrative_assignments (narrative_id, doc_id, assigned_at) VALUES (?, ?, ?)",
                ("surv-001", f"doc-s{i}", "2026-04-01"),
            )
        for i in range(2):
            conn.execute(
                "INSERT INTO narrative_assignments (narrative_id, doc_id, assigned_at) VALUES (?, ?, ?)",
                ("absorb-001", f"doc-a{i}", "2026-04-01"),
            )

    return repo


# ===========================================================================
# Section 4: Repository Merge Method
# ===========================================================================
S("Section 4: merge_narrative()")

tmpdir = tempfile.mkdtemp()
db_path = os.path.join(tmpdir, "test_merge.db")
repo = make_test_repo(db_path)
vs = FakeVectorStore()

repo.merge_narrative("surv-001", "absorb-001", vector_store=vs)

with repo._get_conn() as conn:
    # T1: document_evidence reassigned
    absorbed_docs = conn.execute(
        "SELECT COUNT(*) as cnt FROM document_evidence WHERE narrative_id = ?", ("absorb-001",)
    ).fetchone()["cnt"]
    survivor_docs = conn.execute(
        "SELECT COUNT(*) as cnt FROM document_evidence WHERE narrative_id = ?", ("surv-001",)
    ).fetchone()["cnt"]
    T("T1: document_evidence rows reassigned to survivor",
      absorbed_docs == 0 and survivor_docs == 5,
      f"absorbed={absorbed_docs}, survivor={survivor_docs}")

    # T2: narrative_assignments reassigned
    absorbed_assigns = conn.execute(
        "SELECT COUNT(*) as cnt FROM narrative_assignments WHERE narrative_id = ?", ("absorb-001",)
    ).fetchone()["cnt"]
    survivor_assigns = conn.execute(
        "SELECT COUNT(*) as cnt FROM narrative_assignments WHERE narrative_id = ?", ("surv-001",)
    ).fetchone()["cnt"]
    T("T2: narrative_assignments rows reassigned to survivor",
      absorbed_assigns == 0 and survivor_assigns == 5,
      f"absorbed={absorbed_assigns}, survivor={survivor_assigns}")

    # T3: survivor document_count updated
    survivor = conn.execute(
        "SELECT document_count FROM narratives WHERE narrative_id = ?", ("surv-001",)
    ).fetchone()
    T("T3: survivor document_count is combined total (5)",
      survivor["document_count"] == 5,
      f"got {survivor['document_count']}")

    # T4: absorbed becomes Dormant with merge note (description preserved)
    absorbed = conn.execute(
        "SELECT stage, description FROM narratives WHERE narrative_id = ?", ("absorb-001",)
    ).fetchone()
    T("T4: absorbed narrative is Dormant with merge note",
      absorbed["stage"] == "Dormant" and "Merged into surv-001" in absorbed["description"],
      f"stage={absorbed['stage']}, desc={absorbed['description']}")

# T5: vector_store.delete() called
T("T5: vector_store.delete() called on absorbed narrative",
  vs.deleted_ids == ["absorb-001"],
  f"deleted_ids={vs.deleted_ids}")

# T6: idempotency — merging an already-Dormant narrative is a no-op
vs2 = FakeVectorStore()
repo.merge_narrative("surv-001", "absorb-001", vector_store=vs2)

with repo._get_conn() as conn:
    survivor_after = conn.execute(
        "SELECT document_count FROM narratives WHERE narrative_id = ?", ("surv-001",)
    ).fetchone()
T("T6: merging already-Dormant is idempotent (no-op)",
      survivor_after["document_count"] == 5 and vs2.deleted_ids == [],
      f"doc_count={survivor_after['document_count']}, deletes={vs2.deleted_ids}")

# T6b: vector delete failure aborts DB merge to avoid inconsistency
tmpdir_fail = tempfile.mkdtemp()
db_path_fail = os.path.join(tmpdir_fail, "test_merge_fail.db")
repo_fail = make_test_repo(db_path_fail)
vs_fail = FakeVectorStore(fail_on_delete=True)
merge_failed = False
try:
    repo_fail.merge_narrative("surv-001", "absorb-001", vector_store=vs_fail)
except RuntimeError:
    merge_failed = True
T("T6b: merge raises when centroid delete fails", merge_failed, "expected RuntimeError")
with repo_fail._get_conn() as conn:
    survivor_fail = conn.execute(
        "SELECT stage, document_count FROM narratives WHERE narrative_id = ?",
        ("surv-001",),
    ).fetchone()
    absorbed_fail = conn.execute(
        "SELECT stage, description, document_count FROM narratives WHERE narrative_id = ?",
        ("absorb-001",),
    ).fetchone()
    absorb_docs_fail = conn.execute(
        "SELECT COUNT(*) as cnt FROM document_evidence WHERE narrative_id = ?",
        ("absorb-001",),
    ).fetchone()["cnt"]
    T(
        "T6c: DB merge is not applied when centroid delete fails",
        survivor_fail["document_count"] == 3
        and absorbed_fail["stage"] == "Emerging"
        and absorb_docs_fail == 2,
        f"survivor={dict(survivor_fail)}, absorbed={dict(absorbed_fail)}, absorb_docs={absorb_docs_fail}",
    )


# ===========================================================================
# Section 6: Suppressed Narrative Document Leak
# ===========================================================================
S("Section 6: Suppressed narrative document leak")

# --- T7: One-time cleanup removes centroids for suppressed narratives ---
import faiss
from vector_store import FaissVectorStore

tmpdir2 = tempfile.mkdtemp()
db_path2 = os.path.join(tmpdir2, "test_suppressed.db")
index_path = os.path.join(tmpdir2, "test_index.pkl")

from repository import SqliteRepository
repo2 = SqliteRepository(db_path2)
repo2.migrate()

# Create a suppressed narrative and put its centroid in the vector store
with repo2._get_conn() as conn:
    conn.execute(
        "INSERT INTO narratives (narrative_id, name, stage, suppressed, document_count) "
        "VALUES (?, ?, ?, ?, ?)",
        ("supp-001", "Suppressed Narrative", "Emerging", 1, 10),
    )
    conn.execute(
        "INSERT INTO narratives (narrative_id, name, stage, suppressed, document_count) "
        "VALUES (?, ?, ?, ?, ?)",
        ("supp-002", "Another Suppressed", "Growing", 1, 5),
    )
    conn.execute(
        "INSERT INTO narratives (narrative_id, name, stage, suppressed, document_count) "
        "VALUES (?, ?, ?, ?, ?)",
        ("active-001", "Active Narrative", "Growing", 0, 20),
    )
    conn.execute(
        "INSERT INTO narratives (narrative_id, name, stage, suppressed, document_count) "
        "VALUES (?, ?, ?, ?, ?)",
        ("dormant-099", "Dormant Narrative", "Dormant", 0, 3),
    )

vs_real = FaissVectorStore(index_path)
vs_real.initialize(4)
rng = np.random.RandomState(42)
vecs = rng.randn(4, 4).astype(np.float32)
for i in range(4):
    vecs[i] /= np.linalg.norm(vecs[i])
vs_real.add(vecs, ["supp-001", "supp-002", "active-001", "dormant-099"])

# Simulate the one-time cleanup logic (must match cleanup_suppressed_centroids.py query)
with repo2._get_conn() as conn:
    excluded = conn.execute(
        "SELECT narrative_id FROM narratives WHERE suppressed = 1 OR stage = 'Dormant'"
    ).fetchall()
for row in excluded:
    nid = row[0]
    if nid in vs_real.id_to_index:
        vs_real.delete(nid)

T("T7: cleanup removes excluded centroids (suppressed + Dormant), keeps active",
  vs_real.count() == 1 and "active-001" in vs_real.id_to_index,
  f"count={vs_real.count()}, ids={list(vs_real.id_to_index.keys())}")


# --- T8: Step 7 guard skips excluded narrative matches (suppressed + Dormant) ---
# Simulate the guard logic from pipeline.py Step 7
tmpdir3 = tempfile.mkdtemp()
db_path3 = os.path.join(tmpdir3, "test_guard.db")
repo3 = SqliteRepository(db_path3)
repo3.migrate()

with repo3._get_conn() as conn:
    conn.execute(
        "INSERT INTO narratives (narrative_id, name, stage, suppressed, document_count) "
        "VALUES (?, ?, ?, ?, ?)",
        ("supp-100", "Suppressed", "Emerging", 1, 0),
    )
    conn.execute(
        "INSERT INTO narratives (narrative_id, name, stage, suppressed, document_count) "
        "VALUES (?, ?, ?, ?, ?)",
        ("active-100", "Active", "Growing", 0, 5),
    )

# Load excluded IDs (same logic as pipeline guard)
with repo3._get_conn() as conn:
    _excluded_ids = {
        row[0] for row in conn.execute(
            "SELECT narrative_id FROM narratives WHERE suppressed = 1 OR stage = 'Dormant'"
        ).fetchall()
    }

# Simulate assignment loop: vector store returns suppressed ID
test_ids = ["supp-100", "active-100"]
assigned = []
skipped = []
for nid in test_ids:
    if nid in _excluded_ids:
        skipped.append(nid)
        continue
    assigned.append(nid)

T("T8: Step 7 guard skips excluded, assigns active",
  skipped == ["supp-100"] and assigned == ["active-100"],
  f"skipped={skipped}, assigned={assigned}")


# --- T9: Source verification — pipeline.py contains the guard ---
S("Section 6b: Source verification")

pipeline_path = Path(_ROOT) / "pipeline.py"
source = pipeline_path.read_text(encoding="utf-8")

T("T9: pipeline.py loads _excluded_ids set before assignment loop",
  '_excluded_ids' in source and "WHERE suppressed = 1 OR stage = 'Dormant'" in source
  and 'if narrative_id in _excluded_ids' in source,
  "Expected _excluded_ids guard in pipeline.py Step 7")


# ===========================================================================
# Section 7: Phase 2v2 — Post-Audit Hardening Tests
# ===========================================================================
S("Section 7: Phase 2v2 hardening")

# --- T10: Self-merge guard ---
tmpdir10 = tempfile.mkdtemp()
db_path10 = os.path.join(tmpdir10, "test_selfmerge.db")
repo10 = make_test_repo(db_path10)
vs10 = FakeVectorStore()

repo10.merge_narrative("surv-001", "surv-001", vector_store=vs10)

with repo10._get_conn() as conn:
    surv = conn.execute(
        "SELECT stage, document_count FROM narratives WHERE narrative_id = ?", ("surv-001",)
    ).fetchone()

T("T10: self-merge is a no-op (narrative unchanged)",
  surv["stage"] == "Growing" and surv["document_count"] == 3 and vs10.deleted_ids == [],
  f"stage={surv['stage']}, doc_count={surv['document_count']}, deletes={vs10.deleted_ids}")


# --- T11: Invalid survivor_id raises ValueError ---
tmpdir11 = tempfile.mkdtemp()
db_path11 = os.path.join(tmpdir11, "test_invalid_survivor.db")
repo11 = make_test_repo(db_path11)

t11_raised = False
try:
    repo11.merge_narrative("NONEXISTENT", "absorb-001")
except ValueError as e:
    t11_raised = "does not exist" in str(e)

T("T11: invalid survivor_id raises ValueError",
  t11_raised,
  "Expected ValueError for non-existent survivor")


# --- T12: Invalid absorbed_id raises ValueError ---
tmpdir12 = tempfile.mkdtemp()
db_path12 = os.path.join(tmpdir12, "test_invalid_absorbed.db")
repo12 = make_test_repo(db_path12)

t12_raised = False
try:
    repo12.merge_narrative("surv-001", "NONEXISTENT")
except ValueError as e:
    t12_raised = "does not exist" in str(e)

T("T12: invalid absorbed_id raises ValueError",
  t12_raised,
  "Expected ValueError for non-existent absorbed")


# --- T13: Description preserved after merge ---
tmpdir13 = tempfile.mkdtemp()
db_path13 = os.path.join(tmpdir13, "test_desc.db")
repo13 = make_test_repo(db_path13)

# Set a description on the absorbed narrative
with repo13._get_conn() as conn:
    conn.execute(
        "UPDATE narratives SET description = ? WHERE narrative_id = ?",
        ("Important analysis", "absorb-001"),
    )

repo13.merge_narrative("surv-001", "absorb-001")

with repo13._get_conn() as conn:
    absorbed = conn.execute(
        "SELECT description FROM narratives WHERE narrative_id = ?", ("absorb-001",)
    ).fetchone()

T("T13: description preserved with merge note appended",
  "Important analysis" in absorbed["description"] and "Merged into surv-001" in absorbed["description"],
  f"desc={absorbed['description']}")


# --- T14: Document buffered (not dropped) when best match is excluded ---
tmpdir14 = tempfile.mkdtemp()
db_path14 = os.path.join(tmpdir14, "test_buffer.db")
repo14 = SqliteRepository(db_path14)
repo14.migrate()

with repo14._get_conn() as conn:
    # Create a Dormant narrative (simulating post-merge state)
    conn.execute(
        "INSERT INTO narratives (narrative_id, name, stage, suppressed, document_count) "
        "VALUES (?, ?, ?, ?, ?)",
        ("dormant-001", "Dormant Narrative", "Dormant", 0, 0),
    )
    # Create an active narrative
    conn.execute(
        "INSERT INTO narratives (narrative_id, name, stage, suppressed, document_count) "
        "VALUES (?, ?, ?, ?, ?)",
        ("active-200", "Active Narrative", "Growing", 0, 5),
    )

# Load excluded IDs (same logic as pipeline guard)
with repo14._get_conn() as conn:
    _excluded_ids_14 = {
        row[0] for row in conn.execute(
            "SELECT narrative_id FROM narratives WHERE suppressed = 1 OR stage = 'Dormant'"
        ).fetchall()
    }

# Simulate: best match is the Dormant narrative -> should buffer, not drop
test_doc = {
    "doc_id": "doc-buffer-001",
    "raw_text": "Test document",
    "source_url": "http://example.com/test",
    "source_domain": "example.com",
    "published_at": "2026-04-01",
    "ingested_at": "2026-04-01",
    "author": "test",
    "raw_text_hash": "abc123",
    "embedding_blob": b"\x00" * 16,
    "status": "pending",
    "narrative_id_assigned": None,
}

buffered = False
if "dormant-001" in _excluded_ids_14:
    repo14.insert_candidate(test_doc)
    buffered = True

with repo14._get_conn() as conn:
    candidate = conn.execute(
        "SELECT doc_id, status FROM candidate_buffer WHERE doc_id = ?", ("doc-buffer-001",)
    ).fetchone()

T("T14: excluded narrative match buffers doc (not dropped)",
  buffered and candidate is not None and candidate["status"] == "pending",
  f"buffered={buffered}, candidate={'found' if candidate else 'missing'}")

# --- T14c: duplicate candidate insert is idempotent ---
repo14.insert_candidate(test_doc)  # same doc_id, should be ignored
with repo14._get_conn() as conn:
    dup_count = conn.execute(
        "SELECT COUNT(*) FROM candidate_buffer WHERE doc_id = ?", ("doc-buffer-001",)
    ).fetchone()[0]
T("T14c: duplicate candidate insert ignored (no UNIQUE crash, count stays 1)",
  dup_count == 1,
  f"count={dup_count}")


# --- T14b: Dormant centroid excluded by Step 7 guard ---
T("T14b: Dormant narrative included in _excluded_ids",
  "dormant-001" in _excluded_ids_14,
  f"excluded_ids={_excluded_ids_14}")


# ===========================================================================
# Summary
# ===========================================================================
print("\n" + "=" * 60)
passed = sum(1 for _, ok in _results if ok)
failed = sum(1 for _, ok in _results if not ok)
print(f"Phase 2 Merge & Leak Prevention: {passed} passed, {failed} failed out of {len(_results)}")
if failed:
    print("\nFailed tests:")
    for name, ok in _results:
        if not ok:
            print(f"  FAIL: {name}")
    sys.exit(1)
else:
    print("All tests passed.")
