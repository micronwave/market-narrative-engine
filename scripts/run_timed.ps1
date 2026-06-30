param(
    [Parameter(Mandatory = $true)]
    [string]$Command,
    [int]$TimeoutSec = 120,
    [string]$WorkingDirectory = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($TimeoutSec -lt 1) {
    throw "TimeoutSec must be >= 1"
}

if ($WorkingDirectory -and -not (Test-Path -LiteralPath $WorkingDirectory)) {
    throw "WorkingDirectory does not exist: $WorkingDirectory"
}

$job = Start-Job -ScriptBlock {
    param($cmd, $wd)

    if ($wd) {
        Set-Location -LiteralPath $wd
    }

    & "C:\Program Files\PowerShell\7\pwsh.exe" -NoProfile -Command $cmd
    $code = $LASTEXITCODE
    if ($null -eq $code) { $code = 0 }
    [pscustomobject]@{ ExitCode = [int]$code }
} -ArgumentList $Command, $WorkingDirectory

try {
    $completed = Wait-Job -Id $job.Id -Timeout $TimeoutSec
    if (-not $completed) {
        Stop-Job -Id $job.Id
        throw "TIMEOUT after ${TimeoutSec}s: $Command"
    }

    $output = Receive-Job -Id $job.Id
    $exitCode = 0
    foreach ($item in $output) {
        if ($item -is [pscustomobject] -and $item.PSObject.Properties.Name -contains "ExitCode") {
            $exitCode = [int]$item.ExitCode
        }
        else {
            $item
        }
    }
    exit $exitCode
}
finally {
    if (Get-Job -Id $job.Id -ErrorAction SilentlyContinue) {
        Remove-Job -Id $job.Id -Force
    }
}
