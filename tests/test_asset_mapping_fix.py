"""
Asset Mapping Fix Tests

Covers two fixes to pipeline.py asset mapping that were starving the swing layer
(observed: 1/695 narratives retained linked_assets):

  #1 Name-aware evidence gate (_ticker_has_evidence / _name_in_evidence):
     news prose names the company, not the bare ticker — match on name tokens.
  #2 Non-destructive persistence (_map_narrative_assets):
     an empty recompute must not wipe a previously good linked_assets mapping.

Run:  python -X utf8 tests/test_asset_mapping_fix.py
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np

_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from pipeline import _ticker_has_evidence, _name_in_evidence, _map_narrative_assets

_results = []


def S(section: str):
    print(f"\n--- {section} ---")


def T(name: str, condition: bool, details: str = ""):
    _results.append((name, bool(condition)))
    marker = "✓" if condition else "✗"
    msg = f"  [{marker}] {name}"
    if details and not condition:
        msg += f"\n      details: {details}"
    print(msg)


# ===========================================================================
# Section 1: _name_in_evidence
# ===========================================================================
S("NAME: _name_in_evidence")
T("brand token matches", _name_in_evidence("Nvidia Corporation", "nvidia surged today"))
T("multi-word brand matches on first token",
  _name_in_evidence("CrowdStrike Holdings Inc.", "shares of crowdstrike fell"))
T("generic-only name does NOT match",
  _name_in_evidence("Global Holdings Group Inc", "the group and its holdings expanded") is False)
T("short tokens (<4) ignored", _name_in_evidence("AB Co", "ab co reported") is False)
T("empty name → False", _name_in_evidence("", "anything") is False)
T("name absent from blob → False",
  _name_in_evidence("Palantir Technologies", "oil prices climbed") is False)
T("stopword 'technologies' alone insufficient, brand carries it",
  _name_in_evidence("Palantir Technologies", "palantir won a contract"))


# ===========================================================================
# Section 2: _ticker_has_evidence (name-aware)
# ===========================================================================
S("THE: _ticker_has_evidence")
T("cashtag still works", _ticker_has_evidence("CRWD", "CrowdStrike", ["$CRWD rose 4%"]))
T("parenthetical still works", _ticker_has_evidence("NVDA", "Nvidia", ["chipmaker (NVDA) gained"]))
T("company name recovers the link (the fix)",
  _ticker_has_evidence("CRWD", "CrowdStrike Holdings Inc.", ["CrowdStrike disclosed a breach"]))
T("name in non-first position matches",
  _ticker_has_evidence("TSLA", "Tesla Inc.", ["EV demand lifted Tesla this week"]))
T("no symbol and no name → False",
  _ticker_has_evidence("NVDA", "Nvidia Corp", ["oil supply disruption drove markets"]) is False)
T("generic-name collision rejected",
  _ticker_has_evidence("XYZ", "Holdings Group Inc", ["the group expanded its holdings"]) is False)
T("bare ticker x2 + name still works (legacy weak path)",
  _ticker_has_evidence("AAA", "Aaa Mining", ["AAA up", "AAA down again", "mining boom"]))


# ===========================================================================
# Section 3: _map_narrative_assets — non-destructive persistence
# ===========================================================================
S("MAP: non-destructive persistence")


def _make_mocks(existing_linked, computed_assets, evidence=None):
    repo = MagicMock()
    repo.get_document_evidence.return_value = evidence or []
    vs = MagicMock()
    vs.get_vector.return_value = np.ones(8, dtype=np.float32)
    am = MagicMock()
    am.map_narrative.return_value = computed_assets
    am.get_name.side_effect = lambda t: t
    narrative = {
        "narrative_id": "n1",
        "topic_tags": json.dumps([]),
        "linked_assets": json.dumps(existing_linked) if existing_linked is not None else None,
    }
    return repo, am, vs, narrative


def _linked_assets_written(repo):
    """Return the linked_assets value passed to update_narrative, or 'NOT_CALLED'."""
    for call in repo.update_narrative.call_args_list:
        args, kwargs = call
        updates = args[1] if len(args) > 1 else kwargs.get("updates", {})
        if "linked_assets" in updates:
            return json.loads(updates["linked_assets"])
    return "NOT_CALLED"


# Case A: empty recompute + existing non-empty → preserve, no wipe
existing = [{"ticker": "NVDA", "asset_name": "Nvidia", "asset_type": "equity",
             "similarity_score": 0.8}]
repo, am, vs, nar = _make_mocks(existing, computed_assets=[])
result = _map_narrative_assets(repo, am, vs, nar)
T("A: returns preserved existing assets", result == existing, f"got {result}")
T("A: did NOT overwrite linked_assets with []", _linked_assets_written(repo) == "NOT_CALLED",
  f"wrote {_linked_assets_written(repo)}")

# Case B: empty recompute + existing empty → writes [] (well-formed)
repo, am, vs, nar = _make_mocks([], computed_assets=[])
result = _map_narrative_assets(repo, am, vs, nar)
T("B: returns []", result == [])
T("B: writes [] when nothing before", _linked_assets_written(repo) == [])

# Case C: non-empty recompute → persists computed assets
computed = [{"ticker": "AMZN", "asset_name": "Amazon ETF Trust", "asset_type": "etf",
             "similarity_score": 0.9}]
repo, am, vs, nar = _make_mocks(existing, computed_assets=computed)
result = _map_narrative_assets(repo, am, vs, nar)
T("C: returns computed assets", result and result[0]["ticker"] == "AMZN")
T("C: persisted computed assets", _linked_assets_written(repo) and
  _linked_assets_written(repo)[0]["ticker"] == "AMZN")

# Case D: malformed existing JSON + empty recompute → treated as empty, writes []
repo, am, vs, nar = _make_mocks(None, computed_assets=[])
nar["linked_assets"] = "{not valid json"
result = _map_narrative_assets(repo, am, vs, nar)
T("D: malformed existing handled, returns []", result == [])
T("D: writes [] on malformed+empty", _linked_assets_written(repo) == [])


# ===========================================================================
# Section 4: trust-similarity bypass (fix #3)
# ===========================================================================
S("TRUST: high-similarity bypass of evidence gate")
from settings import settings as _settings

# Equity match above trust threshold, with NO evidence at all → still kept.
hi = [{"ticker": "PLTR", "asset_name": "Palantir Technologies",
       "asset_type": "equity",
       "similarity_score": _settings.ASSET_MAPPING_TRUST_SIMILARITY + 0.05}]
repo, am, vs, nar = _make_mocks([], computed_assets=hi, evidence=[])
result = _map_narrative_assets(repo, am, vs, nar)
T("high-sim equity kept without evidence", result and result[0]["ticker"] == "PLTR")

# Equity match below trust + below entity-min, no evidence → dropped (gate holds).
lo = [{"ticker": "ZZZ", "asset_name": "Zzz Holdings",
       "asset_type": "equity",
       "similarity_score": _settings.ASSET_MAPPING_TRUST_SIMILARITY - 0.08}]
repo, am, vs, nar = _make_mocks([], computed_assets=lo,
                                evidence=[{"excerpt": "oil prices climbed today"}])
result = _map_narrative_assets(repo, am, vs, nar)
T("low-sim equity without evidence still dropped", result == [], f"got {result}")


# ===========================================================================
print("\n" + "=" * 50)
passed = sum(1 for _, ok in _results if ok)
total = len(_results)
print(f"Asset Mapping Fix Results: {passed}/{total} passed")
if passed == total:
    print("All asset mapping fix tests passed.")
else:
    failed = [name for name, ok in _results if not ok]
    print(f"FAILED: {failed}")
    sys.exit(1)
