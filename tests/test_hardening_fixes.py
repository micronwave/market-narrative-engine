import os
import sqlite3
import sys
import uuid
from pathlib import Path

import faiss
import numpy as np

sys.path.insert(0, ".")

import clustering
from asset_mapper import AssetMapper
from output import DISCLAIMER, build_output_object, validate_output
from repository import SqliteRepository
from settings import Settings

_results = []


def S(name: str):
    print(f"\n--- {name} ---")


def T(name: str, ok: bool, details: str = ""):
    _results.append((name, ok))
    mark = "PASS" if ok else "FAIL"
    suffix = f" ({details})" if details else ""
    print(f"  {mark}: {name}{suffix}")


_BASE_NARRATIVE = {
    "narrative_id": str(uuid.uuid4()),
    "name": "Test",
    "description": "Desc",
    "stage": "Emerging",
    "velocity": 0.0,
    "velocity_windowed": 0.0,
    "centrality": 0.0,
    "is_catalyst": 0,
    "is_coordinated": 0,
    "suppressed": 0,
    "human_review_required": 0,
    "ns_score": 0.0,
    "entropy": 0.0,
    "intent_weight": 0.0,
    "cross_source_score": 0.0,
    "document_count": 1,
}


class _Embedder:
    def dimension(self):
        return 4


class _VS:
    def count(self):
        return 0

    def initialize(self, _dim):
        return None

    def get_all_ids(self):
        return []

    def get_vector(self, _nid):
        return None


class _NoiseClusterer:
    def __init__(self, *args, **kwargs):
        pass

    def fit_predict(self, all_embeddings):
        return np.full(len(all_embeddings), -1, dtype=int)


def _repo_path() -> str:
    base = Path(".tmp")
    base.mkdir(exist_ok=True)
    return str(base / f"hardening_{uuid.uuid4().hex}.db")


S("Settings validation")
try:
    Settings(ENVIRONMENT="development", ANTHROPIC_API_KEY="")
    T("development rejects missing ANTHROPIC_API_KEY", False, "no error raised")
except Exception:
    T("development rejects missing ANTHROPIC_API_KEY", True)

try:
    s = Settings(ENVIRONMENT="test", ANTHROPIC_API_KEY="")
    T("test environment gets placeholder key", s.ANTHROPIC_API_KEY == "placeholder-key-for-test", s.ANTHROPIC_API_KEY)
except Exception as exc:
    T("test environment gets placeholder key", False, str(exc))


S("Output attribution validation")
try:
    bad = build_output_object(
        narrative=_BASE_NARRATIVE,
        linked_assets=[],
        supporting_evidence=[{"source_url": "", "source_domain": "reuters.com", "published_at": "2026-01-01", "excerpt": "x"}],
        lifecycle_reasoning="ok",
        mutation_analysis=None,
        score_components={"v": 1.0},
    )
    T("blank source_url fails validation", validate_output(bad) is False)
except Exception as exc:
    T("blank source_url fails validation", False, str(exc))

try:
    mismatch = build_output_object(
        narrative=_BASE_NARRATIVE,
        linked_assets=[],
        supporting_evidence=[{"source_url": "https://reuters.com/a", "source_domain": "reuters.com", "published_at": "2026-01-01", "excerpt": "x"}],
        lifecycle_reasoning="ok",
        mutation_analysis=None,
        score_components={"v": 1.0},
    )
    mismatch["source_attribution_metadata"]["domains"] = ["apnews.com"]
    T("metadata domains must match evidence domains", validate_output(mismatch) is False)
except Exception as exc:
    T("metadata domains must match evidence domains", False, str(exc))

try:
    good = build_output_object(
        narrative=_BASE_NARRATIVE,
        linked_assets=[],
        supporting_evidence=[{"source_url": "https://reuters.com/a", "source_domain": "reuters.com", "published_at": "2026-01-01", "excerpt": "x"}],
        lifecycle_reasoning="ok",
        mutation_analysis=None,
        score_components={"v": 1.0},
    )
    T("valid attribution still passes", validate_output(good) is True)
    T("disclaimer constant unchanged", DISCLAIMER == "INTELLIGENCE ONLY — NOT FINANCIAL ADVICE. For informational purposes only.")
except Exception as exc:
    T("valid attribution still passes", False, str(exc))


S("Document evidence deduplication")
db = _repo_path()
repo = SqliteRepository(db)
repo.migrate()
try:
    repo.insert_document_evidence({
        "doc_id": "d1",
        "narrative_id": "n1",
        "source_url": "https://example.com/story?utm_source=rss&id=1",
        "source_domain": "example.com",
        "published_at": "2026-01-01T00:00:00+00:00",
        "author": "a",
        "excerpt": "same story",
    })
    repo.insert_document_evidence({
        "doc_id": "d2",
        "narrative_id": "n1",
        "source_url": "https://example.com/story?id=1",
        "source_domain": "example.com",
        "published_at": "2026-01-01T00:00:00+00:00",
        "author": "b",
        "excerpt": "same story",
    })
    T("canonical URL duplicate suppressed", repo.count_document_evidence("n1") == 1, str(repo.count_document_evidence("n1")))

    repo.insert_document_evidence({
        "doc_id": "d3",
        "narrative_id": "n2",
        "source_url": "",
        "source_domain": "example.com",
        "published_at": "2026-01-01T00:00:00+00:00",
        "author": "a",
        "excerpt": "same excerpt",
    })
    repo.insert_document_evidence({
        "doc_id": "d4",
        "narrative_id": "n2",
        "source_url": "",
        "source_domain": "example.com",
        "published_at": "2026-01-01T00:00:00+00:00",
        "author": "b",
        "excerpt": "same excerpt",
    })
    T("fingerprint duplicate suppressed", repo.count_document_evidence("n2") == 1, str(repo.count_document_evidence("n2")))
except Exception as exc:
    T("document evidence deduplication", False, str(exc))


S("Asset mapping asset_type")
try:
    mapper = AssetMapper.__new__(AssetMapper)
    mapper._tickers = ["AAPL", "SPY"]
    mapper._names = ["Apple Inc.", "SPDR S&P 500 ETF Trust"]
    mapper._pipeline_dim = 4
    mapper._index = faiss.IndexFlatIP(4)
    matrix = np.array([
        [1.0, 0.0, 0.0, 0.0],
        [0.9, 0.1, 0.0, 0.0],
    ], dtype=np.float32)
    faiss.normalize_L2(matrix)
    mapper._index.add(matrix)
    results = mapper.map_narrative(np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32), top_k=2, min_similarity=0.0)
    types = {r["ticker"]: r.get("asset_type") for r in results}
    T("equity asset_type emitted", types.get("AAPL") == "equity", str(types))
    T("ETF asset_type emitted", types.get("SPY") == "etf", str(types))
except Exception as exc:
    T("asset mapping asset_type", False, str(exc))


S("Sparse clustering escalation")
db2 = _repo_path()
repo2 = SqliteRepository(db2)
repo2.migrate()
for i in range(2):
    repo2.insert_candidate(
        {
            "doc_id": f"noise-{i}",
            "raw_text": f"text {i}",
            "source_url": f"https://example.com/{i}",
            "source_domain": "example.com",
            "published_at": f"2026-01-0{i+1}T00:00:00+00:00",
            "ingested_at": f"2026-01-0{i+1}T00:00:00+00:00",
            "author": "",
            "raw_text_hash": f"h{i}",
            "embedding_blob": np.array([float(i + 1), 0.0, 0.0, 0.0], dtype=np.float32).tobytes(),
            "status": "pending",
            "narrative_id_assigned": None,
        }
    )

class _SparseSettings:
    HDBSCAN_MIN_CLUSTER_SIZE = 2
    HDBSCAN_MIN_SAMPLES = 2
    CLUSTER_MAX_PENDING_BATCH = 2
    CLUSTER_SPARSE_RETRY_LIMIT = 2
    PIPELINE_FREQUENCY_HOURS = 4

orig_clusterer = clustering.hdbscan.HDBSCAN
clustering.hdbscan.HDBSCAN = _NoiseClusterer
try:
    out1 = clustering.run_clustering(repo2, _VS(), _Embedder(), _SparseSettings())
    out2 = clustering.run_clustering(repo2, _VS(), _Embedder(), _SparseSettings())
    pending = repo2.get_candidate_buffer_count("pending")
    deferred = repo2.get_candidate_buffer_count("deferred_sparse")
    T("zero-cluster run returns empty list", out1 == [] and out2 == [], f"out1={out1}, out2={out2}")
    T("repeated sparse batch is deferred", pending == 0 and deferred == 2, f"pending={pending}, deferred={deferred}")
except Exception as exc:
    T("sparse clustering escalation", False, str(exc))
finally:
    clustering.hdbscan.HDBSCAN = orig_clusterer

for p in (db, db2):
    try:
        sqlite3.connect(p).close()
        os.remove(p)
    except Exception:
        pass

total = len(_results)
passed = sum(1 for _, ok in _results if ok)
print(f"\nHardening verification summary: {passed}/{total} passed")
if passed != total:
    sys.exit(1)
