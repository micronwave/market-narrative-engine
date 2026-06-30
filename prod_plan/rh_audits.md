# Pipeline Stage Audits

Each section below is a self-contained audit prompt for one pipeline stage. Feed each prompt to an audit agent independently. The agent should produce a concise report covering findings at the substantive level — blockers and non-trivial issues, not style nits.

---

## Audit 1 — Ingest (robots.txt + Financial Relevance Filter)

You are auditing the **Ingest stage** of a Python narrative intelligence pipeline. The stage is responsible for fetching documents from external sources, checking robots.txt compliance before making HTTP requests, and filtering documents for financial relevance before passing them downstream.

Explore the codebase and audit this stage. Look at the actual implementation — do not assume how it works. Focus on:

- Whether the robots.txt check is correctly wired up and actually enforced (not just present). Check for edge cases: failures, missing headers, redirects, wildcard rules, caching.
- Whether the financial relevance filter is meaningful (not trivially permissive or trivially restrictive) and whether its logic is correct.
- Whether the ingest stage handles errors, timeouts, and malformed responses in a way that prevents downstream corruption or silent data loss.
- Whether the volume, diversity, and freshness of ingested documents are appropriate for a narrative intelligence use case.
- Any other issues you find that could cause wrong behavior, data quality problems, or silent failures.

Produce a concise report: list each finding with a severity (BLOCKER / MINOR), a one-line description, and the relevant file and line if applicable.

---

## Audit 2 — Deduplication (LSH MinHash, 0.85 Jaccard threshold)

You are auditing the **Deduplication stage** of a Python narrative intelligence pipeline. The stage uses LSH MinHash to estimate Jaccard similarity between documents and drops any pair scoring above 0.85 similarity.

Explore the codebase and audit this stage. Look at the actual implementation. Focus on:

- Whether the MinHash and LSH configuration (number of permutations, band/row settings) is tuned appropriately for 0.85 Jaccard recall. Check for off-by-one errors or misuse of the library.
- Whether the threshold direction is correct — does the code drop documents *above* 0.85 or accidentally invert the check?
- Whether tokenization/shingles used for MinHash are appropriate for short financial news snippets vs. long documents.
- Whether the dedup logic is stateful across pipeline runs or only within a single run, and whether that's the intended behavior.
- Whether documents are correctly compared (e.g., not comparing a document to itself, not skipping comparisons due to indexing bugs).
- Any edge cases: empty documents, very short documents, duplicate titles with different bodies.

Produce a concise report: list each finding with a severity (BLOCKER / MINOR), a one-line description, and the relevant file and line if applicable.

---

## Audit 3 — Embed (768-dim dense vectors, all-mpnet-base-v2)

You are auditing the **Embedding stage** of a Python narrative intelligence pipeline. The stage generates 768-dimensional dense vectors using the `all-mpnet-base-v2` sentence-transformer model. These embeddings are used downstream for clustering and asset mapping.

Explore the codebase and audit this stage. Look at the actual implementation. Focus on:

- Whether the model is loaded and applied correctly (batch sizes, device placement, normalization).
- Whether embeddings are cached or re-computed on every run, and whether that behavior is correct given the pipeline's design.
- Whether the embedding output format (shape, dtype, normalization state) matches what downstream stages expect.
- Whether very long documents are handled correctly (truncation behavior, chunking, or silently dropped tokens).
- Whether error handling is in place for embedding failures without silently propagating zero-vectors or nulls downstream.
- Whether the embedding model version is pinned and reproducible.

Produce a concise report: list each finding with a severity (BLOCKER / MINOR), a one-line description, and the relevant file and line if applicable.

---

## Audit 4 — Cluster (HDBSCAN + centroid momentum tracking)

You are auditing the **Clustering stage** of a Python narrative intelligence pipeline. The stage runs HDBSCAN over document embeddings and additionally tracks centroid momentum across pipeline runs to detect narrative movement.

Explore the codebase and audit this stage. Look at the actual implementation. Focus on:

- Whether HDBSCAN hyperparameters (`min_cluster_size`, `min_samples`, `metric`) are appropriate for high-dimensional dense embeddings (768-dim). Check for known pitfalls like Euclidean distance on cosine-intended embeddings.
- Whether noise points (HDBSCAN label -1) are handled explicitly and correctly — are they dropped, stored, or silently mixed into clusters?
- Whether cluster IDs are stable across runs (HDBSCAN cluster IDs are not inherently stable) and whether the pipeline has a mechanism to reconcile old vs. new cluster assignments.
- Whether centroid momentum tracking is implemented correctly: how centroids are computed, how momentum is persisted between runs, and whether stale momentum from dead narratives causes issues.
- Whether the clustering stage degrades gracefully when document volume is very low (e.g., fewer docs than `min_cluster_size`).

Produce a concise report: list each finding with a severity (BLOCKER / MINOR), a one-line description, and the relevant file and line if applicable.

---

## Audit 5 — Score (velocity, cohesion, polarization, entropy, burst detection)

You are auditing the **Scoring stage** of a Python narrative intelligence pipeline. The stage computes multiple signals per narrative cluster: velocity (document growth rate), cohesion (intra-cluster embedding similarity), polarization (sentiment divergence), entropy (topic diversity), and burst detection (abnormal velocity spikes).

Explore the codebase and audit this stage. Look at the actual implementation. Focus on:

- Whether each signal is computed correctly given its definition. Look for formula errors, off-by-one errors in time windows, or division-by-zero cases.
- Whether signals are normalized or scaled consistently, and whether the ranges are appropriate for downstream consumption.
- Whether burst detection is robust to low-volume noise (e.g., 1 doc vs. 2 docs triggering a false burst).
- Whether signals are persisted correctly and whether stale scores from previous runs can contaminate current output.
- Whether missing data (e.g., no documents in a time window) causes NaN/None to propagate silently into the output.
- Whether the signal definitions match what the downstream LLM labeling and asset mapping stages expect.

Produce a concise report: list each finding with a severity (BLOCKER / MINOR), a one-line description, and the relevant file and line if applicable.

---

## Audit 6 — Centrality (betweenness centrality + catalyst flagging)

You are auditing the **Centrality stage** of a Python narrative intelligence pipeline. The stage computes betweenness centrality over a narrative co-occurrence or similarity graph to identify influential narratives, and flags high-centrality narratives as "catalysts."

Explore the codebase and audit this stage. Look at the actual implementation. Focus on:

- Whether the graph construction is correct: what nodes and edges represent, how edge weights are derived, and whether the graph is connected or fragmented in ways that would make centrality meaningless.
- Whether betweenness centrality is computed on the correct graph object and whether the result is normalized appropriately for graphs of varying size.
- Whether the catalyst flagging threshold is hardcoded or configurable, and whether it's calibrated to the expected graph sizes.
- Whether the centrality computation is performant — betweenness centrality is O(VE) and can be slow on large graphs. Check whether approximations or cutoffs are used.
- Whether centrality scores are stored and compared across runs, or recomputed fresh each time, and whether either choice creates issues.

Produce a concise report: list each finding with a severity (BLOCKER / MINOR), a one-line description, and the relevant file and line if applicable.

---

## Audit 7 — Adversarial Detection (coordination burst: 5+ sources in 300s)

You are auditing the **Adversarial Detection stage** of a Python narrative intelligence pipeline. The stage flags coordinated inauthentic behavior by detecting when 5 or more distinct sources publish on the same narrative within a 300-second window.

Explore the codebase and audit this stage. Look at the actual implementation. Focus on:

- Whether the time window is computed correctly (rolling vs. tumbling, timestamp precision, timezone handling).
- Whether "distinct sources" is defined and enforced correctly — can a single domain or IP flood through multiple subdomains and evade the check?
- Whether the 5-source threshold and 300-second window are hardcoded or configurable, and whether they are tuned appropriately.
- Whether flagged narratives are correctly marked in the output and whether downstream stages respect the flag.
- Whether the detection logic produces false positives on legitimate high-velocity news events (e.g., major earnings releases).
- Whether the adversarial flag persists between runs or resets, and whether either behavior is correct.

Produce a concise report: list each finding with a severity (BLOCKER / MINOR), a one-line description, and the relevant file and line if applicable.

---

## Audit 8 — LLM Labeling (Haiku for labels/topics, Sonnet for mutation analysis)

You are auditing the **LLM Labeling stage** of a Python narrative intelligence pipeline. The stage uses Claude Haiku for narrative labeling and topic classification, and Claude Sonnet for mutation analysis (budget-gated). All calls are logged to an `llm_audit_log` table.

Explore the codebase and audit this stage. Look at the actual implementation. Focus on:

- Whether Haiku and Sonnet are called via the correct method signatures (`call_haiku` / `call_sonnet` on `LlmClient`). The class is `LlmClient`, not `LLMClient`.
- Whether the budget gate for Sonnet calls is correctly implemented — what triggers it, how it's tracked, and whether it can be bypassed or exhausted silently.
- Whether prompt construction for labeling and mutation analysis is correct and includes sufficient narrative context.
- Whether LLM responses are parsed and validated before being stored — bad JSON, empty responses, or unexpected formats.
- Whether the `llm_audit_log` table is written to on every call (including failures) as required by compliance rules.
- Whether retry logic and error handling are appropriate for transient API failures without causing the entire pipeline run to abort.

Produce a concise report: list each finding with a severity (BLOCKER / MINOR), a one-line description, and the relevant file and line if applicable.

---

## Audit 9 — Asset Mapping (FAISS cosine similarity vs. S&P 500 ticker embeddings)

You are auditing the **Asset Mapping stage** of a Python narrative intelligence pipeline. The stage uses FAISS to find the closest S&P 500 ticker embeddings to each narrative's centroid embedding via cosine similarity, linking narratives to financial assets.

Explore the codebase and audit this stage. Look at the actual implementation. Focus on:

- Whether the FAISS index is built with the correct metric (inner product on normalized vectors for cosine, or L2 — check which is used and whether vectors are actually normalized).
- Whether the S&P 500 ticker embedding library is complete, up-to-date, and correctly loaded.
- Whether the similarity threshold used to accept or reject a ticker match is appropriate (not too permissive — everything matches something).
- Whether asset mappings are stored correctly and consistently with the `linked_assets` column format (JSON string, always `json.loads()` before use).
- Whether the stage handles narratives whose centroid is far from all tickers gracefully (no match vs. forced match).
- Whether the FAISS index is rebuilt from scratch on every run or cached, and whether either choice is correct.

Produce a concise report: list each finding with a severity (BLOCKER / MINOR), a one-line description, and the relevant file and line if applicable.

---

## Audit 10 — Persist (SQLite + structured JSON output)

You are auditing the **Persist stage** of a Python narrative intelligence pipeline. The stage writes narrative data to SQLite and produces structured JSON output files. The repository pattern uses `with self._get_conn() as conn:` exclusively — never `self.conn` directly.

Explore the codebase and audit this stage. Look at the actual implementation. Focus on:

- Whether all database writes use the repository pattern correctly (`with self._get_conn() as conn:`). Flag any direct `self.conn` usage.
- Whether schema migrations are idempotent (using `ALTER TABLE ... ADD COLUMN` style). Check for any non-idempotent migration that would fail on re-run.
- Whether the exact column names defined in CLAUDE.md are used consistently: `narrative_id`, `stage`, `document_count`, `name`, `linked_assets`, `topic_tags`, `burst_ratio`. Flag any mismatches.
- Whether JSON fields (`linked_assets`, `topic_tags`) are always serialized on write and deserialized on read without assumptions.
- Whether the structured JSON output format is complete and consistent with what downstream consumers (API, frontend) expect.
- Whether transaction handling is correct — are partial writes possible if a run fails mid-persist?
- Whether old narrative records are updated correctly vs. accidentally duplicated on re-runs.

Produce a concise report: list each finding with a severity (BLOCKER / MINOR), a one-line description, and the relevant file and line if applicable.
