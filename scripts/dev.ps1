<#
.SYNOPSIS
    Start Suraksha in development mode (hot reload; runs the engine from source).
#>
# Native tools (pip, PyInstaller, npm, cargo) write progress to stderr;
# Windows PowerShell 5.1 would treat that as an error under "Stop".
# Their exit codes are checked explicitly instead.
$ErrorActionPreference = "Continue"
$App = Join-Path (Split-Path -Parent $PSScriptRoot) "app"
Push-Location $App
try {
    if (-not (Test-Path "node_modules")) { npm ci --no-audit --no-fund }
    npm run tauri dev
}
finally { Pop-Location }
