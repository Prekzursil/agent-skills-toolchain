# CRCP health renderer for mon/wfmon — prints a compact table and exits 0/1.
# Usage: pwsh -File crcp_health_render.ps1
#        pwsh -File crcp_health_render.ps1 -Json
param(
    [switch]$Json,
    [switch]$WriteOnly
)
$ErrorActionPreference = 'Stop'
$CrpRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = $CrpRoot + [IO.Path]::PathSeparator + ($env:PYTHONPATH ?? '')
if ($Json) {
    python -m crcp health --json
} elseif ($WriteOnly) {
    python -m crcp health 2>$null | Out-Null
    $snippet = Join-Path $CrpRoot "reports\wfmon_crcp_health.json"
    if (Test-Path $snippet) { Get-Content -LiteralPath $snippet -Raw }
} else {
    python -m crcp health
}
exit $LASTEXITCODE
