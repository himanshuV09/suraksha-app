<#
.SYNOPSIS
    Build the Suraksha installers (engine executable + desktop app).

.DESCRIPTION
    1. Installs the engine's build dependencies (skip with -SkipDeps).
    2. Runs the test suites (skip with -SkipTests).
    3. Builds the engine with PyInstaller (one-folder build).
    4. Copies it into app/src-tauri/resources/engine, which the
       installer ships as the "engine" resource folder.
    5. Builds the Tauri app and installers (NSIS .exe and .msi).

    Requires Python 3.12, Node.js 20+, and the Rust toolchain with the
    Tauri prerequisites for Windows (WebView2, MSVC build tools).

.EXAMPLE
    .\scripts\build.ps1
    .\scripts\build.ps1 -SkipTests
#>
param(
    [switch]$SkipDeps,
    [switch]$SkipTests,
    [string]$Python = "python"
)

# Native tools (pip, PyInstaller, npm, cargo) write progress to stderr;
# Windows PowerShell 5.1 would treat that as an error under "Stop".
# Their exit codes are checked explicitly instead.
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
$Engine = Join-Path $Root "engine"
$App = Join-Path $Root "app"
$Work = Join-Path $Root "build"
$Resources = Join-Path $App "src-tauri\resources\engine"

function Step($message) { Write-Host "`n==> $message" -ForegroundColor Cyan }
function Check($what) { if ($LASTEXITCODE -ne 0) { throw "$what failed (exit code $LASTEXITCODE)" } }

if (-not $SkipDeps) {
    Step "Installing engine build dependencies"
    & $Python -m pip install --disable-pip-version-check -q -r (Join-Path $Engine "requirements-dev.txt"); Check "pip install"
    if (-not (Test-Path (Join-Path $App "node_modules"))) {
        Step "Installing frontend dependencies"
        Push-Location $App; npm ci --no-audit --no-fund; $code = $LASTEXITCODE; Pop-Location
        $LASTEXITCODE = $code; Check "npm ci"
    }
}

if (-not $SkipTests) {
    Step "Running tests"
    & (Join-Path $PSScriptRoot "test.ps1") -Python $Python; Check "tests"
}

Step "Building the engine executable (PyInstaller)"
Push-Location $Engine
& $Python -m PyInstaller suraksha-engine.spec --noconfirm --clean `
    --distpath (Join-Path $Work "engine-dist") --workpath (Join-Path $Work "engine-work")
$code = $LASTEXITCODE; Pop-Location; $LASTEXITCODE = $code; Check "PyInstaller"

$Built = Join-Path $Work "engine-dist\suraksha-engine"
Step "Checking the built engine"
$version = & (Join-Path $Built "suraksha-engine.exe") version | ConvertFrom-Json
if (-not $version.success -or -not $version.frozen) { throw "The built engine did not start correctly." }
Write-Host "engine $($version.engine_version) (Python $($version.python_version))"

Step "Placing the engine into the app resources"
Get-ChildItem $Resources -Exclude "README.txt" | Remove-Item -Recurse -Force -ErrorAction Stop
Copy-Item -Path (Join-Path $Built "*") -Destination $Resources -Recurse -ErrorAction Stop

Step "Building the desktop app and installers"
Push-Location $App
npm run tauri build
$code = $LASTEXITCODE; Pop-Location; $LASTEXITCODE = $code; Check "tauri build"

$Bundles = Join-Path $App "src-tauri\target\release\bundle"
Step "Installers"
Get-ChildItem $Bundles -Recurse -Include *.exe, *.msi | ForEach-Object {
    "{0}  ({1:N1} MB)" -f $_.FullName, ($_.Length / 1MB)
}
