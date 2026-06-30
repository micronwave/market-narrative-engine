# Robinhood Signal Execution — Fix Plan

Codex audit + independent code review. Nine findings ordered by implementation sequence
(dependencies first, no-dep fixes before structural refactors, gating logic last).

---

## Fix 1 — Signal components not recomputed when documents are assigned (BLOCKER)

**File:** `pipeline.py:996–999`

**What the code does:**
```python
if not new_narrative_ids:
    _log_step(..., "OK", ..., "skipped:no_new_narratives")
```
The entire signal recomputation body is guarded by `new_narrative_ids`. In the latest run,
19 documents were assigned to existing narratives but no new narratives were created. All
of `burst_ratio`, `cohesion`, `velocity_windowed`, `document_count` stayed at prior-run
values.

**Fix:**

Change the guard to include any run where documents were assigned:

```python
assigned_this_cycle = repository.count_documents_assigned_in_cycle(cycle_id)
# (add this lightweight query to repository.py)

if not new_narrative_ids and assigned_this_cycle == 0:
    _log_step(..., "SKIPPED", ..., "skipped:no_new_narratives_no_assignments")
else:
    # existing signal recomputation body
    ...
    _log_step(..., "OK", ...,
              f"narratives={len(active_narratives)} assigned_docs={assigned_this_cycle}")
```

The query: `SELECT COUNT(*) FROM documents WHERE cycle_id = ? AND assignment_status = 'assigned'`.
If `cycle_id` isn't on the documents table, use `assigned_at` timestamp vs `cycle_started_at`.

---

## Fix 2 — Position sizing divides by candidate count, not max_positions (BLOCKER)

**File:** `swing_signal.py:439–450`

**What the code does:**
```python
n_slots = max(1, min(len(candidates), max_positions))
base_slot = deployable / n_slots
```
With 2 candidates and `max_positions=5`, `n_slots=2`, `base_slot=deployable/2`. Each
position consumes up to 50% of deployable cash. With a $579.65 account and 15% reserve,
deployable=$492.70 → `base_slot=$246.35` but `max_slot` cap fires at
`579.65×0.25=$144.91` — so both positions hit the cap, deploying $289.82 total when 2 of
5 slots are filled. Size rationale breaks down.

Also: `max_slot = buying_power * MAX_POSITION_PCT` is unrounded; if it becomes the applied
cap, fractional cents appear in JSON.

**Fix:**

```python
# Always divide by max_positions, not candidate count.
# Weak-signal candidates naturally stay small via score_weight.
base_slot = deployable / max(1, max_positions)
max_slot = round(buying_power * MAX_POSITION_PCT, 2)

for c in candidates:
    score_weight = 0.60 + 0.40 * min(c["swing_score"] / 0.60, 1.0)
    dollar_size = base_slot * score_weight
    dollar_size = round(max(MIN_POSITION_USD, min(dollar_size, max_slot)), 2)
    c["dollar_size"] = dollar_size
```

Remove line 439 `n_slots = ...` entirely (it was only used for `base_slot`).

---

## Fix 3 — Undocumented additive impact bonus in scoring formula (SUBSTANTIVE)

**File:** `swing_signal.py:293–298`

**What the code does:**
```python
impact_bonus = min(impact_score * 0.05, 0.05)
final = raw * stage_mult * quality_mult + impact_bonus
```
The module docstring formula (lines 25–33) does not include this term. The
`impact_scores` table is written during the **current** run's Step 19, but
`_fetch_impact_scores()` is called before `build_candidates()` — so the scores read are
from the **previous** run. A candidate with a false impact link (e.g., AIG from Fix 5)
gets up to +0.05 to its score, direction-blind.

**Fix:**

Remove the additive bonus. The impact score is already a component of the direction
enrichment; double-counting it as a tiebreaker adds noise and conceals false positives.

```python
# Remove these two lines:
impact_bonus = min(impact_score * 0.05, 0.05)
final = raw * stage_mult * quality_mult + impact_bonus

# Replace with:
final = raw * stage_mult * quality_mult
```

Update the docstring formula to match. If impact scoring is meant to influence swing
scores, add `impact_score_norm` as an explicit named component with its own weight, after
Fixes 5 and 6 ensure the scores are direction- and evidence-gated.

---

## Fix 4 — Convergence runs on stale linked_assets (step ordering bug) (BLOCKER)

**Files:** `pipeline.py:1277–1290` (Step 11.5), `pipeline.py:1872–1941` (Step 19)

**What the code does:** Step 11.5 calls `compute_all_convergences(active_narratives, ...)`,
which reads `linked_assets` from the DB. Step 19 is where fresh `linked_assets` are
computed via `asset_mapper.map_narrative()` and persisted. So convergence always runs one
pipeline cycle behind the asset map.

**Fix:**

Split the asset-mapping portion of Step 19 into a new earlier step. Concretely:

- **New Step 12 — Asset Mapping:** Extract the `asset_mapper.map_narrative()` call and
  text-fallback from Step 19. Run for all active non-suppressed narratives. Persist fresh
  `linked_assets` to DB. Log as `"asset_mapping"`.

- **Step 11.5 (unchanged position):** Now runs after Step 12, so it reads today's
  `linked_assets`. Convergence results will reflect today's asset links.

- **Step 19 (trimmed):** Reads the already-persisted `linked_assets`, runs impact
  enrichment + role classification, formats output. No more asset mapping here.

Renumber steps in `_log_step` calls accordingly (12 = asset_mapping; 12.5 = convergence
or keep 11.5 if log numbering continuity matters).

---

## Fix 5 — Fixed stop-limit gap is unsafe for news-driven names (SUBSTANTIVE)

**File:** `swing_signal.py:65,463–465`

**What the code does:** `stop_limit_floor_pct = stop_loss_pct + STOP_LIMIT_GAP_PCT` where
`STOP_LIMIT_GAP_PCT = 2.0`. For a news-catalyst equity that gaps 15%, the stop triggers
at -8% but the limit floor at -10% never fills. The position stays open.

**Fix:**

Add `stop_order_type` field to each candidate. Default to `"stop_market"` to guarantee
fill. Only use `"stop_limit"` when narrative entropy is low (stable, not news-driven):

```python
# In size_positions():
if entropy > 1.0 or c.get("is_catalyst"):
    c["stop_order_type"] = "stop_market"
    c["stop_limit_floor_pct"] = None   # not applicable
else:
    c["stop_order_type"] = "stop_limit"
    c["stop_limit_floor_pct"] = round(adjusted_stop + STOP_LIMIT_GAP_PCT, 1)
```

Add `STOP_DEFAULT_ORDER_TYPE: str = "stop_market"` to `settings.py`.

Update the execution step (or documentation) to confirm that Robinhood `stop_market`
orders are used, not `stop_limit`, for high-entropy candidates.

---

## Fix 6 — Asset mapping accepts false single-name equity links (BLOCKER)

**Files:** `asset_mapper.py:89–93`, `pipeline.py:1872–1877`, `signals.py:291–308`,
`settings.py:37`

**Depends on Fix 4** (asset mapping is now an isolated step, easier to gate here).

**What the code does:** `map_narrative()` uses cosine similarity with `min_similarity=0.60`
only. Sector filtering only fires when `topic_tags` map to a narrow domain (line 122–130).
For general or logistics narratives, no sector gate fires. AIG passes at 0.686 because its
company description embedding has semantic overlap with AI/governance text. The denylist in
`swing_signal.py:89` is a symptom patch — it won't catch new false positives.

Text-fallback (`_accept_fallback_ticker`, `signals.py:291`) accepts plain uppercase
mentions in ≥2 excerpts with `similarity_score=0.0`. No company-name co-reference, no
role gate.

**Fix:**

### Part A — Evidence gate for single-name equities

In the new Step 12 (asset mapping), after `asset_mapper.map_narrative()` and text-fallback
produce `linked_assets`, apply an evidence gate before persisting:

```python
def _ticker_has_evidence(ticker: str, asset_name: str, excerpts: list[str]) -> bool:
    blob = " ".join(excerpts).lower()
    if f"${ticker.lower()}" in blob:
        return True
    if f"({ticker.lower()})" in blob:
        return True
    # Company name: first meaningful word of asset_name must appear in evidence
    first_word = asset_name.split()[0].lower() if asset_name else ""
    return len(first_word) > 3 and first_word in blob
```

Apply to all non-ETF, non-TOPIC: tickers from both paths. Tickers that fail the gate are
logged and dropped.

Add setting: `ASSET_MAPPING_REQUIRE_EVIDENCE: bool = True`.

### Part B — Raise minimum similarity

Raise `ASSET_MAPPING_MIN_SIMILARITY` from `0.60` to `0.70` in `settings.py`. At 0.70,
AIG (0.686) is eliminated before the evidence gate even runs. Evidence gate is the primary
guard; threshold is defense-in-depth.

Add `ASSET_MAPPING_ENTITY_MIN_SIMILARITY: float = 0.80` — single-name equities must also
exceed this higher bar OR pass the evidence gate. ETFs are exempt.

### Part C — Text-fallback hardening

In `_accept_fallback_ticker` (`signals.py:291`), require company-name co-reference: a
ticker accepted by plain uppercase mention is only kept if the company name (from asset
library) also appears in the same excerpt(s).

---

## Fix 7 — Text ticker fallback creates tradeable mappings at similarity=0.0 (SUBSTANTIVE)

**Files:** `pipeline.py:1882–1903`, `swing_signal.py:306–327`

**Depends on Fix 6** (evidence gate reduces bad text-mention entries; this adds the
swing_signal.py defense-in-depth gate).

**What the code does:** The enriched `linked_assets` dict includes `"source": "text_mention"`
(set at `pipeline.py:1898`). `_parse_linked_assets()` in `swing_signal.py` strips this
metadata when it extracts ticker strings. Text-mention tickers therefore enter `ticker_best`
with the same weight as embedding-mapped tickers.

**Fix:**

Change `_parse_linked_assets()` to return `list[dict]` with ticker + source, then gate on
source in `build_candidates()`:

```python
# In build_candidates(), when iterating over linked_assets:
if isinstance(a, dict) and a.get("source") == "text_mention":
    # Excluded by default until role classification (Fix 9) is in place.
    continue
```

Add `--allow-text-mentions` CLI flag defaulting to `False` for manual override when
debugging. The flag does not override Fix 9's role gate once that is implemented.

---

## Fix 8 — Pipeline health status does not distinguish OK from SKIPPED/DEGRADED (SUBSTANTIVE)

**Files:** `pipeline.py` (`_log_step` call sites), `swing_signal.py`

**Depends on Fix 1** (which introduces `SKIPPED` status) and **Fix 4** (which introduces
`asset_mapping` as a named step whose freshness can be checked).

**What the code does:** `_log_step(..., "OK", ...)` is written even for skipped or
stale steps. A run with `compute_signals: skipped`, `convergence: tickers=1 (stale)`, and
zero role classifications still produces `errors=0`.

**Fix:**

1. Add `SKIPPED` and `DEGRADED` as valid status strings to `_log_step`. Fix 1 already
   introduces `SKIPPED` for the signal skip path; apply it consistently everywhere.

2. Add `_pipeline_health_summary()` at the end of `run()` that evaluates:
   - `asset_mapping_fresh` — did Step 12 run this cycle?
   - `convergence_fresh` — did convergence run after asset mapping?
   - `signals_fresh` — did compute_signals run (not SKIPPED)?
   - `roles_classified` — did any ticker role classification run? (after Fix 9)

   Log as a `"pipeline_health"` step with status `"OK"` or `"DEGRADED"`.

3. At the top of `swing_signal.py:main()`, query the latest run's `pipeline_health` step:

   ```
   WARNING: Last pipeline run was DEGRADED (signals stale, convergence stale).
   Signals may be unreliable. Re-run pipeline or pass --bypass-health-check to proceed.
   ```

   Exit non-zero if DEGRADED and `--bypass-health-check` is not set.

---

## Fix 9 — Per-ticker direction is not modeled (direction fan-out bug) (BLOCKER)

**Files:** `impact_scorer.py:166,195–221`, `swing_signal.py:352–356`

**Depends on Fix 6** (clean asset links) and **Fix 4** (asset mapping isolated in Step 12,
so role classification can run there before impact scoring in Step 19).

**What the code does:** `enrich_linked_assets()` fetches one `narrative_signals` row per
`narrative_id` (line 166), then stamps `signal.get("direction")` onto every ticker in the
loop (lines 210–221 call `compute_directional_impact(signal=signal, ...)` — same signal
object for all). `build_candidates()` in `swing_signal.py` checks direction at line 352
on the narrative signal, not per-ticker. Result: AMZN and UPS both receive `bullish` from
"Amazon Disrupts Traditional Logistics Industry".

**Fix:**

1. Add `ticker_role TEXT` column to `impact_scores` table:
   `ALTER TABLE impact_scores ADD COLUMN ticker_role TEXT`.

2. In Step 12 (asset mapping, from Fix 4), after `linked_assets` are mapped and
   evidence-gated, classify each ticker's role with a Haiku call:

   ```
   prompt: "Narrative: {name}\n\nTicker: {ticker} ({asset_name})\n\n
            Is this company a beneficiary, victim, or neutral in this narrative?
            Reply with exactly one word: beneficiary, victim, or neutral."
   ```

   Budget-gate: if daily Haiku budget is exhausted, fall back to `neutral` for all tickers
   and set `role_classified: False` on the asset entry.

3. Persist `ticker_role` into `linked_assets` JSON (add `"role"` key) and into
   `impact_scores` table.

4. In `swing_signal.py:build_candidates()`, read the `"role"` field from enriched
   `linked_assets` entries. If `direction_filter == "bullish"`, skip tickers where
   `role == "victim"`. Add `"ticker_role"` key to each candidate dict for audit output.

5. **Gate:** block `write_json()` and print a BLOCKED message if any candidate has no
   `ticker_role` in its `linked_assets` entry — treat absent classification as unverified,
   not bullish.
