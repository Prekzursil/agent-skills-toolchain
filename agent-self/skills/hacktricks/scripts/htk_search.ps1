#requires -version 5.1
<#
.SYNOPSIS  Offline search of the local HackTricks corpus (ripgrep, no network).
.EXAMPLE   pwsh htk_search.ps1 -Query "AWS IAM privilege escalation" -Context 3
#>
param(
  [Parameter(Mandatory)][string]$Query,
  [int]$Context = 2,
  [int]$MaxFiles = 12
)
$ErrorActionPreference = 'Stop'
$corpus = if ($env:HACKTRICKS_CORPUS) { $env:HACKTRICKS_CORPUS } else { 'D:\knowledge\hacktricks' }
if (-not (Test-Path $corpus)) { Write-Error "Corpus not found at $corpus (run htk_update.ps1)"; exit 1 }

$rg = Get-Command rg -ErrorAction SilentlyContinue
if ($rg) {
  # files-with-matches first (ranked by match count), then show context for the top files
  $files = & rg -i -l --type md -- "$Query" $corpus 2>$null | Select-Object -First $MaxFiles
  if (-not $files) { "No matches for '$Query'."; exit 0 }
  foreach ($f in $files) {
    "===== $f ====="
    & rg -i -n -C $Context --type md -m 3 -- "$Query" $f 2>$null
    ""
  }
} else {
  Get-ChildItem -Recurse -Filter *.md $corpus |
    Select-String -Pattern $Query -Context 0, $Context |
    Select-Object -First ($MaxFiles * 4) |
    Format-List Path, LineNumber, Line
}
