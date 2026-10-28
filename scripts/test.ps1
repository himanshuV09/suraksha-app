<#
.SYNOPSIS
    Run every test suite: engine (pytest), frontend (type check), backend (cargo test).
#>
param([string]$Python = "python")

# Native tools (pip, PyInstaller, npm, cargo) write progress to stderr;
# Windows PowerShell 5.1 would treat that as an error under "Stop".
# Their exit codes are checked explicitly instead.
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
$failed = @()

function Run($name, $directory, [scriptblock]$command) {
    Write-Host "`n==> $name" -ForegroundColor Cyan
    Push-Location $directory
    try { & $command; if ($LASTEXITCODE -ne 0) { $script:failed += $name } }
    finally { Pop-Location }
}

Run "Engine tests (pytest)" (Join-Path $Root "engine") { & $Python -m pytest -q }
Run "Frontend type check" (Join-Path $Root "app") { npm run typecheck }
Run "Backend tests (cargo)" (Join-Path $Root "app\src-tauri") { cargo test --quiet }

if ($failed.Count) {
    Write-Host "`nFAILED: $($failed -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host "`nAll test suites passed." -ForegroundColor Green
