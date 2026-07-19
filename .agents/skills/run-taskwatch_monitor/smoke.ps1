# smoke.ps1 — offline smoke test for taskwatch_monitor.
#
# Proves the register -> list -> status round-trip works against the bundled
# fixture log (no network, no real job, no wall clock). Ends with the longrun
# §4 terminal-state marker: SUCCESS:taskwatch-smoke or FAILED:taskwatch-smoke.
#
# Usage:
#   .\smoke.ps1

$ErrorActionPreference = "Stop"
$Id = "taskwatch-smoke"

function Fail([string]$Reason) {
    Write-Host "FAILED:$Id $Reason"
    exit 1
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RepoRoot  = Resolve-Path (Join-Path $ScriptDir "..\..")
$ToolDir   = Join-Path $RepoRoot "tools\taskwatch_monitor"
$Fixture   = Join-Path $ScriptDir "fixtures\demo.log"

if (-not (Test-Path $ToolDir))  { Fail "tool dir not found: $ToolDir" }
if (-not (Test-Path $Fixture))  { Fail "fixture not found: $Fixture" }

# Prefer uv (matches install/launch); fall back to python on PATH.
$UvExe = "C:\Users\Prekzursil\.local\bin\uv.exe"
if (-not (Test-Path $UvExe)) {
    $UvExe = (Get-Command uv -ErrorAction SilentlyContinue)?.Source
}
if ($UvExe) {
    $Runner = @($UvExe, "run", "python", "-m", "cli.app")
} else {
    $py = (Get-Command python -ErrorAction SilentlyContinue)?.Source
    if (-not $py) { Fail "neither uv nor python found on PATH" }
    $Runner = @($py, "-m", "cli.app")
}

# The CLI uses relative imports, so it MUST run as a module from the tool dir.
Push-Location $ToolDir
try {
    $Registry = Join-Path ([System.IO.Path]::GetTempPath()) ("tw-smoke-{0}.toml" -f ([guid]::NewGuid().ToString("N")))

    # 1. register a task from the generic-logfile template against the fixture.
    & $Runner[0] @($Runner[1..($Runner.Count - 1)]) `
        register generic-logfile demo-build --config "path=$Fixture" --registry $Registry
    if ($LASTEXITCODE -ne 0) { Fail "register exited $LASTEXITCODE" }
    if (-not (Test-Path $Registry)) { Fail "registry not written: $Registry" }

    # 2. list must show the registered id.
    $listOut = & $Runner[0] @($Runner[1..($Runner.Count - 1)]) list --registry $Registry 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0)          { Fail "list exited $LASTEXITCODE" }
    if ($listOut -notmatch "demo-build") { Fail "list missing 'demo-build': $listOut" }

    # 3. status --json must report a BLIND-aware view with a computed fraction.
    $jsonOut = & $Runner[0] @($Runner[1..($Runner.Count - 1)]) status --registry $Registry --json 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0)              { Fail "status exited $LASTEXITCODE" }
    if ($jsonOut -notmatch '"id": "demo-build"') { Fail "status missing demo-build view" }
    if ($jsonOut -notmatch '"fraction": 0\.925') { Fail "status fraction wrong (expected 37/40): $jsonOut" }
    if ($jsonOut -notmatch '"blind": false')     { Fail "status view missing blind field" }

    Remove-Item -Path $Registry -Force -ErrorAction SilentlyContinue
}
finally {
    Pop-Location
}

Write-Host "SUCCESS:$Id register+list+status round-trip verified (37/40 = 92%, blind-aware)"
exit 0
