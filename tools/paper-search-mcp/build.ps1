# paper-search-mcp build/rebuild stub — D:-resident venv; repo-side wrapper is docs-only.
# Dry-run by default (prints the exact commands). -Apply executes them. -Rebuild renames
# the existing venv aside first (never deletes). NO registry change either way:
# .agents/agents.json keeps pointing at
# D:/ReverseTools/mcp/paper-search-mcp/venv/Scripts/paper-search-mcp.exe
[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$Rebuild
)
$ErrorActionPreference = 'Stop'

$py      = 'C:\Python314\python.exe'          # Python 3.14.6, verified 2026-09-19
$venvDir = 'D:\ReverseTools\mcp\paper-search-mcp\venv'
$pyExe   = "$venvDir\Scripts\python.exe"
$pkg     = 'paper-search-mcp==0.1.4'           # verified installed version 2026-09-19

if (-not (Test-Path $py)) { throw "Interpreter not found: $py" }
if ($Rebuild -and -not (Test-Path $venvDir)) { throw "-Rebuild set but no existing venv at $venvDir" }

$stamp  = Get-Date -Format 'yyyyMMdd-HHmmss'
$steps = @()
if ($Rebuild) { $steps += "Rename-Item '$venvDir' 'venv.old-$stamp'" }
$steps += "& '$py' -m venv '$venvDir'"
$steps += "& '$pyExe' -m pip install --upgrade pip"
$steps += "& '$pyExe' -m pip install $pkg"
$steps += "Test-Path '$venvDir\Scripts\paper-search-mcp.exe'"
$steps += "& '$pyExe' -m pip show paper-search-mcp"

if (-not $Apply) {
    Write-Host 'DRY-RUN (stub). Re-run with -Apply to execute:'
    $steps
    exit 0
}
foreach ($s in $steps) { Write-Host "> $s"; Invoke-Expression $s }
