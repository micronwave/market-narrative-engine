# AGENTS.md

Instructions for Codex CLI when working in this repository.

## Loop Detection & Bailout Protocol (LDBP)

**CRITICAL: Follow this protocol to avoid hour-long hangs.**

1.  **Turn Tracking**: Explicitly count your turns for the current task. If you have taken more than **5 turns** without a successful test run or verifiable progress, you MUST stop and ask the user for guidance.
2.  **Error Fingerprinting**: If you see the SAME error message (exception type + message) more than **2 times**, even if you changed code in between, you are in a "Blind Fix Loop." STOP immediately. Do not attempt a third fix.
3.  **Environment Check**: Before fixing code, verify if the error is environmental (e.g., `ModuleNotFoundError`, `ValidationError` on API keys, `sqlite3.OperationalError: database is locked`). Environmental errors should be reported once and never "fixed" by modifying business logic.
4.  **The "Circuit Breaker" Statement**: If you hit turn or error limits, your next response must start with the phrase: **"CIRCUIT BREAKER TRIGGERED: I am stuck in a loop."** followed by a summary of your last 3 attempts and the persistent error.

## Retry and loop-avoidance policy

**This is the most important section. Read it before running any commands.**

- If a command fails, diagnose the root cause before retrying. Do not retry the same command more than **2 times** without a change.
- If a test suite or process runs for more than **3 minutes** without progress, kill it and report what happened. Do not wait indefinitely.
- For long-running commands (tests, build, dev servers), use `scripts/run_timed.ps1` so the shell enforces a hard timeout.
- Never run multiple long-running commands in parallel. Run one at a time.
- If you hit the same blocker twice (missing dependency, locked file, port conflict, import error), stop and report it rather than looping. These are environment issues that require human intervention.
- Common blockers and how to handle them:
  - **Missing package**: run `pip install <package>` once, then retry. If it fails again, report and stop.
  - **Port in use**: report the conflict, do not attempt to kill processes.
  - **SQLite locked**: this means another test file is still holding a connection. Wait 5 seconds and retry once. If still locked, report and stop. **Never run multiple test files in parallel** — always run one at a time sequentially.
  - **Network/API call hanging in tests**: the test likely needs mocking or an API key. Report and stop — do not wait.
  - **Windows encoding error**: add `-X utf8` to the Python command.
- If you are unsure whether progress is being made, stop and report your current state rather than continuing to run commands.

### Required timeout wrapper usage

Use this wrapper for any potentially long command:

```powershell
& .\scripts\run_timed.ps1 -TimeoutSec 120 -Command 'python -X utf8 tests/test_c2_api.py' -WorkingDirectory 'E:\narrative_engine'
& .\scripts\run_timed.ps1 -TimeoutSec 120 -Command 'python -X utf8 tests/test_d9_api.py' -WorkingDirectory 'E:\narrative_engine'
& .\scripts\run_timed.ps1 -TimeoutSec 180 -Command 'cd frontend; npx jest --watchAll=false' -WorkingDirectory 'E:\narrative_engine'
```

Rules:
- First timeout: switch to a narrower command or direct import probe immediately.
- Do not rerun the same timed-out command unchanged.
- For script-style tests in this repo, prefer direct execution (`python -X utf8 tests/test_*.py`) over `pytest` collection.

## Commands

```bash
# One-time setup (required before first pipeline run)
python build_asset_library.py

# Run the pipeline
python pipeline.py

# FastAPI backend (port 8000)
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

# Next.js frontend (port 3000, proxies /api/* to 8000)
cd frontend && npm run dev

# Backend tests (always use -X utf8 on Windows)
python -X utf8 tests/test_c2_api.py

# Frontend tests / type check
cd frontend && npx jest --watchAll=false
cd frontend && npx tsc --noEmit
```

No lint step. Backend is pure Python, frontend is Next.js with Tailwind.

## Architecture

FastAPI on port 8000 (`api/main.py`) + Next.js on port 3000 (`frontend/`).

**Pipeline** (`pipeline.py`): 11-stage `run()`. Steps are non-fatal — catch exceptions, call `_log_step(..., "ERROR", ...)`, continue. Never abort the run.

**Repository pattern** (`repository.py`): Always `with self._get_conn() as conn:`, never `self.conn`. Schema migrations via idempotent `ALTER TABLE ... ADD COLUMN` in `_ensure_tables()`.

**Plug-in interfaces**: `Repository`, `VectorStore`, `EmbeddingModel` are abstract. Swap at `# TODO SCALE` markers.

## SQLite `narratives` Column Names

These differ from intuitive names — use exactly:
- Primary key: `narrative_id` (not `id`)
- Stage: `stage` (not `lifecycle_stage`) — values: Emerging, Growing, Mature, Declining, Dormant
- Doc count: `document_count` (not `doc_count`)
- Label: `name` (not `label`)
- `linked_assets` — JSON string, always `json.loads()` before membership checks
- `topic_tags` — JSON string array, always `json.loads()` before use
- `burst_ratio` — REAL, computed by pipeline

## LLM Client (`llm_client.py`)

Class is `LlmClient` (not `LLMClient`).
- `call_haiku(task_type, narrative_id, prompt)` — labeling, topic classification
- `call_sonnet(narrative_id, prompt)` — mutation analysis (budget-gated)
- Every call logged to `llm_audit_log` table

## Frontend (`frontend/`)

Next.js 14 App Router, TypeScript, Tailwind CSS, Lucide React. **No component library** (no shadcn, Radix, etc.). Terminal aesthetic: 2px border-radius, no glass/blur, Palantir Blueprint dark grays. ~65 CSS custom properties in `globals.css`.

API client (`src/lib/api.ts`): all calls use relative `/api/*` paths, proxied to FastAPI via `next.config.mjs`.

## Extension Modules

Instantiated in `api/main.py`, backed by `SqliteRepository`:
- `NotificationManager` (`notifications.py`) — rules: `ns_above`, `ns_below`, `new_narrative`, `mutation`, `stage_change`, `catalyst`
- `PortfolioManager` (`portfolio.py`) — holdings, narrative impact scoring, CSV import (max 1000 rows)
- `WatchlistManager` (`watchlist.py`) — ticker/narrative watchlists
- `ExportManager` (`export.py`) — JSON/CSV export, social share text

## Data Layer

Multi-provider price data: `FinnhubAdapter`, `TwelveDataAdapter`, `CoinGeckoAdapter` in `api/adapters/`, chained by `DataNormalizer`. Circuit breaker in `api/services/circuit_breaker.py` (opens after 5 failures, recovers after 5 min). TwelveData and CoinGecko enabled via `ENABLE_TWELVE_DATA` / `ENABLE_COINGECKO` env vars.

## Configuration

`.env.example` → `.env`. Only `ANTHROPIC_API_KEY` required. Pydantic v2 (`settings.py`). New fields use plain Python defaults — no `Field()`.

Key settings:
- `AUTH_MODE: str = "stub"` — `"stub"` (single-user) or `"jwt"` (requires `JWT_SECRET_KEY` ≥ 32 chars)
- `FINNHUB_API_KEY` — live stock prices
- `BURST_VELOCITY_ALERT_RATIO: float = 3.0`
- `IMPACT_SCORE_REFRESH_SECONDS: int = 600`
- `CONVERGENCE_INDEPENDENCE_THRESHOLD: float = 0.30`
- `ENABLE_TWELVE_DATA` / `ENABLE_COINGECKO` — additional price adapters

## Testing

Custom S/T runner: `S(section)`, `T(name, condition, details)`. Run with `-X utf8` on Windows. All backend tests in `tests/`. Frontend Jest suites in `frontend/src/__tests__/`.

**Test naming:** `tests/test_{phase}{N}_api.py`. Phases: C, D, F. Also: `test_v3_phase{N}.py`, `test_signal_p{N}.py`, `test_*_audit.py`, `test_phase{N}_integration.py`.

**CSS class test assertions:** Tests match `bullish`, `bearish`, `alert`, `critical`, `accent-muted`, `accent-text`, `purple`, `line-through`. Don't rename these Tailwind classes.

Build results → `BUILD_LOG.md`. Frontend build log → `frontend_build_log`.

## Compliance

- robots.txt checked before every HTTP request (defaults ALLOW on failure)
- Disclaimer: `INTELLIGENCE ONLY — NOT FINANCIAL ADVICE` hardcoded in `output.py`
- Source attribution (`source_url`, `source_domain`, `published_at`) mandatory on every document
- LLM calls logged to `llm_audit_log` table

## Archived

Twitter bot outbound posting retired. Legacy: `archive/twitter_bot_retired.py`, `archive/test_twitter_bot_retired.py`. Excluded from normal test runs.
