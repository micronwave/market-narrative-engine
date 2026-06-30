"""
D5 API test suite — Analytics Endpoints (Phase 2 Batch 2).

Tests: D5-U1 through D5-U4 (narrative-histories, momentum-leaderboard,
       narrative-overlap, sector-convergence).

Uses the project's custom S/T runner + FastAPI TestClient (in-process).

Run with:
    python -X utf8 test_d5_api.py

Exit code 0 if all tests pass, 1 if any fail.
"""

import logging
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s %(message)s",
    stream=sys.stderr,
)

# ---------------------------------------------------------------------------
# Custom test runner
# ---------------------------------------------------------------------------

_results: list[dict] = []
_current_section: str = "Unset"
_pass = 0
_fail = 0


def S(section_name: str) -> None:
    global _current_section
    _current_section = section_name


def T(name: str, condition: bool, details: str = "") -> None:
    global _pass, _fail
    _results.append({
        "section": _current_section,
        "name": name,
        "passed": bool(condition),
        "details": details,
    })
    if condition:
        _pass += 1
    else:
        _fail += 1
        print(
            f"  FAIL [{_current_section}] {name}" + (f" — {details}" if details else ""),
            file=sys.stderr,
        )


def _print_summary() -> None:
    sections: dict[str, dict] = {}
    for r in _results:
        sec = r["section"]
        if sec not in sections:
            sections[sec] = {"pass": 0, "fail": 0}
        if r["passed"]:
            sections[sec]["pass"] += 1
        else:
            sections[sec]["fail"] += 1

    print("\n" + "=" * 60)
    print(f"{'Section':<35} {'Pass':>5} {'Fail':>5}")
    print("-" * 60)
    for sec, counts in sections.items():
        marker = "" if counts["fail"] == 0 else " <--"
        print(f"  {sec:<33} {counts['pass']:>5} {counts['fail']:>5}{marker}")
    print("=" * 60)
    print(f"  TOTAL: {_pass} passed, {_fail} failed out of {_pass + _fail} tests")
    print("=" * 60)


# ---------------------------------------------------------------------------
# TestClient + imports
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from api.main import app  # noqa: E402
from repository import SqliteRepository  # noqa: E402

VALID_SLOPE_DIRECTIONS = {"accelerating", "decelerating", "steady"}

with TestClient(app) as client:

    # ===========================================================================
    # D5-U1: GET /api/analytics/narrative-histories — schema + structure
    # ===========================================================================
    S("D5-U1: GET /api/analytics/narrative-histories")

    resp = client.get("/api/analytics/narrative-histories?days=7")
    T("status 200", resp.status_code == 200, f"got {resp.status_code}")

    data = resp.json()
    T("has 'days' key", "days" in data)
    T("has 'generated_at' key", "generated_at" in data)
    T("has 'narratives' key", "narratives" in data)
    T("days matches query param", data.get("days") == 7)
    T("narratives is dict", isinstance(data.get("narratives"), dict))

    # Check narrative entry structure if any narratives exist
    if data["narratives"]:
        first_nid = next(iter(data["narratives"]))
        first_entry = data["narratives"][first_nid]
        T("entry has 'name'", "name" in first_entry)
        T("entry has 'stage'", "stage" in first_entry)
        T("entry has 'history'", "history" in first_entry)
        T("history is list", isinstance(first_entry.get("history"), list))

        if first_entry.get("history"):
            day0 = first_entry["history"][0]
            T("history entry has 'date'", "date" in day0)
            T("history entry has 'velocity'", "velocity" in day0)
            T("history entry has 'ns_score'", "ns_score" in day0)
            T("history entry has 'entropy'", "entropy" in day0)
            T("history entry has 'cohesion'", "cohesion" in day0)
            T("history entry has 'polarization'", "polarization" in day0)
            T("history entry has 'doc_count'", "doc_count" in day0)
            T("history entry has 'burst_ratio'", "burst_ratio" in day0)
            T("history entry has 'gap_filled'", "gap_filled" in day0)
            T("gap_filled is bool", isinstance(day0.get("gap_filled"), bool))
    else:
        T("empty narratives is valid", True, "no narratives in DB — shape OK")

    # Default days parameter
    resp_default = client.get("/api/analytics/narrative-histories")
    T("default days=30 status 200", resp_default.status_code == 200)
    T("default days=30", resp_default.json().get("days") == 30)

    # ===========================================================================
    # D5-U2: GET /api/analytics/momentum-leaderboard — schema + structure
    # ===========================================================================
    S("D5-U2: GET /api/analytics/momentum-leaderboard")

    resp = client.get("/api/analytics/momentum-leaderboard")
    T("status 200", resp.status_code == 200, f"got {resp.status_code}")

    data = resp.json()
    T("has 'generated_at'", "generated_at" in data)
    T("has 'leaderboard'", "leaderboard" in data)
    T("leaderboard is list", isinstance(data.get("leaderboard"), list))

    if data["leaderboard"]:
        entry = data["leaderboard"][0]
        T("entry has 'narrative_id'", "narrative_id" in entry)
        T("entry has 'name'", "name" in entry)
        T("entry has 'stage'", "stage" in entry)
        T("entry has 'current_velocity'", "current_velocity" in entry)
        T("entry has 'momentum_score'", "momentum_score" in entry)
        T("entry has 'slope'", "slope" in entry)
        T("entry has 'slope_direction'", "slope_direction" in entry)
        T("slope_direction valid", entry.get("slope_direction") in VALID_SLOPE_DIRECTIONS,
          f"got {entry.get('slope_direction')}")
        T("entry has 'linked_assets'", "linked_assets" in entry)
        T("linked_assets is list", isinstance(entry.get("linked_assets"), list))
        T("linked_assets max 3", len(entry.get("linked_assets", [])) <= 3)
        T("entry has 'burst_active'", "burst_active" in entry)
        T("burst_active is bool", isinstance(entry.get("burst_active"), bool))
        T("entry has 'data_quality'", "data_quality" in entry)
        T("data_quality has snapshots_available",
          "snapshots_available" in entry.get("data_quality", {}))
        T("snapshots_available is int",
          isinstance(entry.get("data_quality", {}).get("snapshots_available"), int))

        # Verify sorted by momentum_score descending
        scores = [e.get("momentum_score", 0) for e in data["leaderboard"]]
        T("sorted by momentum desc", scores == sorted(scores, reverse=True),
          f"scores: {scores[:5]}")
    else:
        T("empty leaderboard is valid", True, "no narratives — shape OK")

    # ===========================================================================
    # D5-U3: GET /api/analytics/narrative-overlap — schema + matrix properties
    # ===========================================================================
    S("D5-U3: GET /api/analytics/narrative-overlap")

    resp = client.get("/api/analytics/narrative-overlap?days=30")
    T("status 200", resp.status_code == 200, f"got {resp.status_code}")

    data = resp.json()
    T("has 'generated_at'", "generated_at" in data)
    T("has 'cached'", "cached" in data)
    T("has 'narratives'", "narratives" in data)
    T("has 'matrix'", "matrix" in data)
    T("narratives is list", isinstance(data.get("narratives"), list))
    T("matrix is list", isinstance(data.get("matrix"), list))

    n_count = len(data.get("narratives", []))
    matrix = data.get("matrix", [])
    T("matrix is square", len(matrix) == n_count, f"matrix {len(matrix)} vs narratives {n_count}")

    if n_count > 0:
        # Check narrative entry structure
        nm = data["narratives"][0]
        T("narrative has 'id'", "id" in nm)
        T("narrative has 'name'", "name" in nm)
        T("narrative has 'stage'", "stage" in nm)
        T("narrative has 'ns_score'", "ns_score" in nm)

        # Matrix properties
        T("matrix rows match size", all(len(row) == n_count for row in matrix))

        # Diagonal = 1.0
        diagonal_ok = all(
            abs(matrix[i][i] - 1.0) < 0.001 for i in range(n_count)
        )
        T("diagonal is 1.0", diagonal_ok)

        # Symmetric
        symmetric = True
        for i in range(n_count):
            for j in range(i + 1, n_count):
                if abs(matrix[i][j] - matrix[j][i]) > 0.0001:
                    symmetric = False
                    break
        T("matrix is symmetric", symmetric)

        # Values in [0.0, 1.0]
        in_range = all(
            0.0 <= matrix[i][j] <= 1.0
            for i in range(n_count) for j in range(n_count)
        )
        T("all values in [0, 1]", in_range)
    else:
        T("empty matrix is valid", len(matrix) == 0, "no narratives — shape OK")

    # Cache test: second call should be cached
    resp2 = client.get("/api/analytics/narrative-overlap?days=30")
    T("second call status 200", resp2.status_code == 200)
    T("second call cached=true", resp2.json().get("cached") is True)

    # ===========================================================================
    # D5-U4: GET /api/analytics/sector-convergence — schema + structure
    # ===========================================================================
    S("D5-U4: GET /api/analytics/sector-convergence")

    resp = client.get("/api/analytics/sector-convergence")
    T("status 200", resp.status_code == 200, f"got {resp.status_code}")

    data = resp.json()
    T("has 'generated_at'", "generated_at" in data)
    T("has 'sectors'", "sectors" in data)
    T("sectors is list", isinstance(data.get("sectors"), list))

    if data["sectors"]:
        sec = data["sectors"][0]
        T("sector has 'name'", "name" in sec)
        T("sector has 'narrative_count'", "narrative_count" in sec)
        T("sector has 'weighted_pressure'", "weighted_pressure" in sec)
        T("sector has 'contributing_narratives'", "contributing_narratives" in sec)
        T("sector has 'top_assets'", "top_assets" in sec)
        T("contributing_narratives is list", isinstance(sec.get("contributing_narratives"), list))
        T("top_assets is list", isinstance(sec.get("top_assets"), list))

        if sec["contributing_narratives"]:
            cn = sec["contributing_narratives"][0]
            T("contrib has 'narrative_id'", "narrative_id" in cn)
            T("contrib has 'name'", "name" in cn)
            T("contrib has 'ns_score'", "ns_score" in cn)
            T("contrib has 'stage'", "stage" in cn)

        if sec["top_assets"]:
            ta = sec["top_assets"][0]
            T("top_asset has 'ticker'", "ticker" in ta)
            T("top_asset has 'similarity_score'", "similarity_score" in ta)

        # Sorted by weighted_pressure descending
        pressures = [s.get("weighted_pressure", 0) for s in data["sectors"]]
        T("sorted by pressure desc", pressures == sorted(pressures, reverse=True),
          f"pressures: {pressures[:5]}")
    else:
        T("empty sectors is valid", True, "no narratives with linked_assets — shape OK")

    # ===========================================================================
    # D5-U5: atomically_persist_cluster rolls back when a step fails
    # ===========================================================================
    S("D5-U5: atomically_persist_cluster rollback on failure")

    tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_db.close()
    try:
        repo = SqliteRepository(tmp_db.name)
        repo.migrate()

        nid = str(uuid.uuid4())
        doc_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()

        repo.insert_candidate(
            {
                "doc_id": doc_id,
                "narrative_id_assigned": None,
                "embedding_blob": b"",
                "raw_text_hash": "h",
                "source_url": "https://example.com/a",
                "source_domain": "example.com",
                "published_at": now_iso,
                "ingested_at": now_iso,
                "status": "pending",
                "raw_text": "example",
                "author": None,
            }
        )

        narrative = {
            "narrative_id": nid,
            "name": "Cluster TX rollback",
            "description": "",
            "stage": "Emerging",
            "created_at": now_iso,
            "last_updated_at": now_iso,
            "is_coordinated": 0,
            "coordination_flag_count": 0,
            "suppressed": 0,
            "linked_assets": None,
            "disclaimer": None,
            "human_review_required": 0,
            "is_catalyst": 0,
            "document_count": 1,
            "velocity": 0.0,
            "velocity_windowed": 0.0,
            "centrality": 0.0,
            "entropy": None,
            "intent_weight": 0.0,
            "ns_score": 0.0,
            "cohesion": 0.0,
            "polarization": 0.0,
            "cross_source_score": 0.0,
            "last_assignment_date": now_iso[:10],
            "consecutive_declining_cycles": 0,
        }
        member_docs = [
            {
                "doc_id": doc_id,
                "source_url": "https://example.com/a",
                "source_domain": "example.com",
                "published_at": now_iso,
                "author": "",
                "raw_text": "cluster text",
            }
        ]

        raised = False
        try:
            repo.atomically_persist_cluster(
                narrative=narrative,
                cycle_slot=now_iso,
                centroid_blob=b"abc",
                member_docs=member_docs,
                today=now_iso[:10],
                post_write_hook=lambda: (_ for _ in ()).throw(RuntimeError("forced failure")),
            )
        except RuntimeError:
            raised = True
        T("forced failure raises", raised)
        T("narrative insert rolled back", repo.get_narrative(nid) is None)
        pending_docs = repo.get_candidate_buffer(status="pending")
        T("candidate status rolled back to pending", any(d.get("doc_id") == doc_id for d in pending_docs))
    finally:
        Path(tmp_db.name).unlink(missing_ok=True)

    # ===========================================================================
    # D5-U6: consistency check flags missing vectors
    # ===========================================================================
    S("D5-U6: cluster consistency check")

    tmp_db2 = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_db2.close()
    try:
        repo2 = SqliteRepository(tmp_db2.name)
        repo2.migrate()

        nid2 = str(uuid.uuid4())
        doc_id2 = str(uuid.uuid4())
        now_iso2 = datetime.now(timezone.utc).isoformat()

        repo2.insert_candidate(
            {
                "doc_id": doc_id2,
                "narrative_id_assigned": None,
                "embedding_blob": b"",
                "raw_text_hash": "h2",
                "source_url": "https://example.com/b",
                "source_domain": "example.com",
                "published_at": now_iso2,
                "ingested_at": now_iso2,
                "status": "pending",
                "raw_text": "example",
                "author": None,
            }
        )

        narrative2 = {
            "narrative_id": nid2,
            "name": "Cluster TX consistency",
            "description": "",
            "stage": "Emerging",
            "created_at": now_iso2,
            "last_updated_at": now_iso2,
            "is_coordinated": 0,
            "coordination_flag_count": 0,
            "suppressed": 0,
            "linked_assets": None,
            "disclaimer": None,
            "human_review_required": 0,
            "is_catalyst": 0,
            "document_count": 1,
            "velocity": 0.0,
            "velocity_windowed": 0.0,
            "centrality": 0.0,
            "entropy": None,
            "intent_weight": 0.0,
            "ns_score": 0.0,
            "cohesion": 0.0,
            "polarization": 0.0,
            "cross_source_score": 0.0,
            "last_assignment_date": now_iso2[:10],
            "consecutive_declining_cycles": 0,
        }
        repo2.atomically_persist_cluster(
            narrative=narrative2,
            cycle_slot=now_iso2,
            centroid_blob=b"def",
            member_docs=[
                {
                    "doc_id": doc_id2,
                    "source_url": "https://example.com/b",
                    "source_domain": "example.com",
                    "published_at": now_iso2,
                    "author": "",
                    "raw_text": "cluster text",
                }
            ],
            today=now_iso2[:10],
        )
        mismatch = repo2.verify_cluster_consistency(set())
        T("consistency check detects missing vector id", mismatch.get("missing_count", 0) >= 1)
        ok = repo2.verify_cluster_consistency({nid2})
        T("consistency check passes when vector exists", ok.get("missing_count", 0) == 0)
    finally:
        Path(tmp_db2.name).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
_print_summary()
sys.exit(0 if _fail == 0 else 1)
