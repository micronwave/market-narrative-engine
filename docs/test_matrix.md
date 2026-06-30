# Test Matrix — Narrative Intelligence Platform

## Automated test runners

Backend tests are standalone Python scripts using local `S(...)` / `T(...)` helpers.

```bash
# Backend (from project root; use -X utf8 on Windows)
python -X utf8 tests/test_c2_api.py
python -X utf8 tests/test_f1_api.py
```

Frontend tests use Jest + Testing Library, plus TypeScript type checking.

```bash
cd frontend && npx jest --watchAll=false
cd frontend && npx tsc --noEmit
```

## Coverage map by suite family

| Family | Path pattern | Focus |
|---|---|---|
| Customer API | `tests/test_c*_api.py` | core narrative/list/detail API behavior |
| Data pipeline API | `tests/test_d*_api.py` | data/coordination/ingestion-adjacent API features |
| Feature API | `tests/test_f*_api.py` | staged feature surfaces |
| Signal redesign | `tests/test_v3_phase*.py`, `tests/test_signal_p*.py` | signal/model redesign behavior |
| Integration | `tests/test_phase*_integration.py`, `tests/test_full_integration.py` | end-to-end and cross-module flows |
| Audit/quality | `tests/test_*_audit.py` | contract and quality guardrails |
| Frontend Jest | `frontend/src/__tests__/*.test.tsx` | UI and client contract behavior |

## Manual checks (examples)

Manual checks should target active pages and flows (`/`, `/narrative/[id]`, `/signals`, `/stocks`, `/portfolio`, `/analytics`) and avoid retired billing/credits flows.

