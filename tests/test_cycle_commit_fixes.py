"""
Cycle commit hardening regression tests.
"""

import json
import os
import sqlite3
import sys
import tempfile
import uuid
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from llm_client import parse_signal_json
import output as output_module
from output import write_outputs
import repository._legacy as legacy_loader
from repository import SqliteRepository
import swing_signal

_results = []


def S(section: str):
    print(f"\n--- {section} ---")


def T(name: str, condition: bool, details: str = ""):
    _results.append((name, condition))
    marker = "PASS" if condition else "FAIL"
    msg = f"[{marker}] {name}"
    if details:
        msg += f" :: {details}"
    print(msg)


_keepers = []
_repository_module = legacy_loader._legacy
_orig_sqlite_connect = _repository_module.sqlite3.connect

def _connect_with_uri(path, *args, **kwargs):
    kwargs.setdefault("uri", str(path).startswith("file:"))
    return _orig_sqlite_connect(path, *args, **kwargs)

_repository_module.sqlite3.connect = _connect_with_uri


def _repo() -> tuple[SqliteRepository, str]:
    db_path = f"file:cycle_commit_{uuid.uuid4().hex}?mode=memory&cache=shared"
    keeper = _orig_sqlite_connect(db_path, uri=True)
    _keepers.append(keeper)
    repo = SqliteRepository(db_path)
    repo.migrate()
    return repo, db_path


def _insert_narrative(repo: SqliteRepository, narrative_id: str, linked_assets: str = '[{"ticker":"NVDA"}]') -> None:
    repo.insert_narrative({
        "narrative_id": narrative_id,
        "name": f"Narrative {narrative_id[:6]}",
        "description": "test",
        "stage": "Growing",
        "suppressed": 0,
        "document_count": 1,
        "linked_assets": linked_assets,
        "topic_tags": "[]",
        "ns_score": 0.8,
        "burst_ratio": 1.0,
        "cohesion": 0.4,
        "polarization": 0.1,
        "velocity": 0.2,
        "velocity_windowed": 0.3,
        "centrality": 0.1,
        "entropy": 0.2,
        "is_coordinated": 0,
        "cycles_in_current_stage": 2,
        "consecutive_declining_cycles": 0,
        "is_catalyst": 0,
        "created_at": "2026-06-29T00:00:00+00:00",
        "last_updated_at": "2026-06-29T00:00:00+00:00",
    })


S("CC1: parse_signal_json explicit failure")
parsed = parse_signal_json("garbage {broken", allow_hardcoded_fallback=False)
T("CC1 parse failure returns None when fallback disabled", parsed is None, str(parsed))

S("CC2: per-cycle snapshots preserve same-day transitions")
repo2, db2 = _repo()
nid2 = str(uuid.uuid4())
_insert_narrative(repo2, nid2)
repo2.save_snapshot({
    "id": str(uuid.uuid4()),
    "narrative_id": nid2,
    "snapshot_date": "2026-06-29",
    "pipeline_cycle_id": "cycle-a",
    "doc_count": 3,
    "lifecycle_stage": "Growing",
    "created_at": "2026-06-29T01:00:00+00:00",
})
repo2.save_snapshot({
    "id": str(uuid.uuid4()),
    "narrative_id": nid2,
    "snapshot_date": "2026-06-29",
    "pipeline_cycle_id": "cycle-b",
    "doc_count": 9,
    "lifecycle_stage": "Dormant",
    "created_at": "2026-06-29T02:00:00+00:00",
})
with sqlite3.connect(db2) as conn:
    row_count = conn.execute(
        "SELECT COUNT(*) FROM narrative_snapshots WHERE narrative_id = ? AND snapshot_date = ?",
        (nid2, "2026-06-29"),
    ).fetchone()[0]
latest = repo2.get_snapshot(nid2, "2026-06-29")
T("CC2 same-day snapshots retain multiple rows", row_count == 2, str(row_count))
T("CC2 latest snapshot resolves to newest cycle", (latest or {}).get("pipeline_cycle_id") == "cycle-b", json.dumps(latest or {}))

S("CC3: pending assignment recovery is cycle-based")
repo3, _db3 = _repo()
nid3 = str(uuid.uuid4())
_insert_narrative(repo3, nid3)
repo3.begin_pipeline_cycle("old-cycle", "2026-06-29", "2026-06-29T00:00:00+00:00")
repo3.record_narrative_assignment(nid3, "2026-06-29", "doc-1", "old-cycle")
repo3.record_narrative_assignment(nid3, "2026-06-29", "doc-2", "old-cycle")
pending = repo3.get_pending_assignment_doc_ids_by_narrative(exclude_cycle_id="new-cycle")
T("CC3 pending assignments returned by narrative", pending.get(nid3) == ["doc-1", "doc-2"], json.dumps(pending))
T("CC3 cycle assignment count keyed by cycle_id", repo3.count_documents_assigned_in_cycle("old-cycle") == 2)

S("CC4: published cycle snapshot is the swing_signal read boundary")
repo4, db4 = _repo()
nid4 = str(uuid.uuid4())
_insert_narrative(repo4, nid4)
repo4.upsert_narrative_signal({
    "narrative_id": nid4,
    "direction": "bullish",
    "confidence": 0.7,
    "timeframe": "near_term",
    "magnitude": "significant",
    "certainty": "expected",
    "key_actors": ["actor"],
    "affected_sectors": ["chips"],
    "catalyst_type": "corporate",
    "extracted_at": "2026-06-29T03:00:00+00:00",
    "raw_response": "ok",
})
repo4.upsert_impact_score({
    "narrative_id": nid4,
    "ticker": "NVDA",
    "direction": "bullish",
    "impact_score": 0.91,
    "confidence": 0.8,
    "time_horizon": "swing",
    "signal_components": {"x": 1},
    "computed_at": "2026-06-29T03:05:00+00:00",
    "pipeline_cycle_id": "cycle-pub",
})
repo4.begin_pipeline_cycle("cycle-pub", "2026-06-29", "2026-06-29T03:00:00+00:00")
repo4.publish_swing_cycle_snapshot(
    "cycle-pub",
    "2026-06-29T03:10:00+00:00",
    convergences={
        "NVDA": {
            "convergence_count": 2,
            "direction_agreement": 0.8,
            "direction_consensus": 0.7,
            "weighted_confidence": 0.9,
            "source_diversity": 3,
            "pressure_score": 0.88,
            "contributing_narrative_ids": [nid4],
            "computed_at": "2026-06-29T03:09:00+00:00",
        }
    },
)
repo4.mark_pipeline_cycle_committed("cycle-pub", "2026-06-29T03:10:00+00:00")
conn4 = sqlite3.connect(db4, uri=True)
conn4.row_factory = sqlite3.Row
repo_cycle_id = repo4.get_latest_committed_cycle_id()
cycle_id = "cycle-pub"
fetch_narratives = swing_signal._fetch_narratives(conn4, cycle_id)
fetch_signals = swing_signal._fetch_signals(conn4, cycle_id)
fetch_conv = swing_signal._fetch_convergences(conn4, cycle_id)
fetch_impact = swing_signal._fetch_impact_scores(conn4, cycle_id)
conn4.close()
T("CC4 repository records latest committed cycle id", repo_cycle_id == "cycle-pub", str(repo_cycle_id))
T("CC4 swing_signal narratives come from published snapshot", len(fetch_narratives) == 1, str(fetch_narratives))
T("CC4 swing_signal signal snapshot excludes failures and includes published row", fetch_signals.get(nid4, {}).get("direction") == "bullish", json.dumps(fetch_signals))
T("CC4 swing_signal convergence snapshot is current-cycle scoped", abs(fetch_conv.get("NVDA", {}).get("pressure_score", 0.0) - 0.88) < 1e-9, json.dumps(fetch_conv))
T("CC4 swing_signal impact snapshot is current-cycle scoped", abs(fetch_impact.get("NVDA", 0.0) - 0.91) < 1e-9, json.dumps(fetch_impact))

S("CC5: output freshness envelope")
output_dir = Path.cwd() / '.tmp_output_cycle'
output_dir.mkdir(exist_ok=True)
old_cwd = os.getcwd()
orig_replace = output_module.os.replace

def _safe_replace(src: str, dst: str) -> None:
    Path(dst).write_text(Path(src).read_text(encoding="utf-8"), encoding="utf-8")

output_module.os.replace = _safe_replace
os.chdir(output_dir)
try:
    write_outputs([], "2026-06-29", pipeline_cycle_id="cycle-out", committed_at="2026-06-29T04:00:00+00:00")
    payload = json.loads(Path("data/outputs/2026-06-29/narratives.json").read_text(encoding="utf-8"))
finally:
    os.chdir(old_cwd)
    output_module.os.replace = orig_replace
T("CC5 output envelope includes pipeline_cycle_id", payload.get("pipeline_cycle_id") == "cycle-out", json.dumps(payload))
T("CC5 output envelope includes committed_at", payload.get("committed_at") == "2026-06-29T04:00:00+00:00", json.dumps(payload))
T("CC5 output envelope keeps narratives list", payload.get("narratives") == [], json.dumps(payload))

failed = [name for name, ok in _results if not ok]
print(f"\nSummary: {len(_results) - len(failed)}/{len(_results)} passed")
if failed:
    print("Failed tests:")
    for name in failed:
        print(f" - {name}")
    raise SystemExit(1)
