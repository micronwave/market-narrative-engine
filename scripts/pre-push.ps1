# Pre-push check — mirrors .github/workflows/tests.yml exactly.
# Run from repo root: .\scripts\pre-push.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

function Step($label) { Write-Host "`n=== $label ===" -ForegroundColor Cyan }
function Fail($msg)  { Write-Host "FAILED: $msg" -ForegroundColor Red; exit 1 }

function Run {
    param([string]$label, [scriptblock]$cmd)
    & $cmd
    if ($LASTEXITCODE -ne 0) { Fail $label }
}

# ── Backend ──────────────────────────────────────────────────────────────────

Step "Backend targeted scripts"
Run "test_c1_api"        { python -X utf8 tests/test_c1_api.py }
Run "test_signal_p1"     { python -X utf8 tests/test_signal_p1.py }
Run "test_sentiment_api" { python -X utf8 tests/test_sentiment_api.py }
Run "test_signal_p4"     { python -X utf8 tests/test_signal_p4.py }

Step "Backend accuracy tests"
Run "accuracy 1-3" { python -X utf8 -m pytest tests/test_accuracy_1.py tests/test_accuracy_2.py tests/test_accuracy_3.py }
Run "accuracy 4-7" { python -X utf8 -m pytest tests/test_accuracy_4.py tests/test_accuracy_5.py tests/test_accuracy_6.py tests/test_accuracy_7.py }

# ── Frontend ─────────────────────────────────────────────────────────────────

Step "Frontend tests"
Set-Location "$root\frontend"
Run "jest"       { npm run test }

Step "Frontend build"
Run "next build" { npm run build }

Set-Location $root
Write-Host "`nAll checks passed." -ForegroundColor Green
