#requires -version 5.1
<#
.SYNOPSIS
  Unified offline search across ALL local security corpora under D:\knowledge, with
  per-source provenance tags. No network, no quota.
.DESCRIPTION
  Runs one ripgrep query over the whole knowledge tree (default glob **/*.md), ranks the
  matching files by match count, and prints each file's context block under a
  "[<corpus>] <path>" header so you always know which corpus a hit came from. The corpus
  is the first path segment after "knowledge".
.EXAMPLE
  pwsh secsearch.ps1 -Query "kerberoast" -Context 2
.EXAMPLE
  pwsh secsearch.ps1 -Query "SSRF" -Glob "**/*.{md,yml}" -MaxFiles 20
#>
param(
  [Parameter(Mandatory)][string]$Query,
  [int]$Context = 2,
  [int]$MaxFiles = 12,
  [string]$Glob = '**/*.md',
  [string]$Root = $(if ($env:SEC_CORPORA_ROOT) { $env:SEC_CORPORA_ROOT } else { 'D:\knowledge' })
)
$ErrorActionPreference = 'Stop'

if (-not (Test-Path $Root)) { Write-Error "Corpora root not found at $Root (see D:\knowledge\CORPORA.md)"; exit 1 }

function Get-Corpus([string]$path) {
  if ($path -match '[\\/]knowledge[\\/]([^\\/]+)') { return $Matches[1] } else { return '?' }
}

$rg = Get-Command rg -ErrorAction SilentlyContinue
if (-not $rg) {
  Write-Error "ripgrep (rg) not found on PATH. Install ripgrep, or use the Grep tool with path=$Root glob=$Glob -i -C $Context."
  exit 1
}

# Rank files by match count (descending), cap to MaxFiles.
$files = & rg -i -l --glob $Glob -- "$Query" $Root 2>$null |
  Sort-Object { (& rg -i -c --glob $Glob -- "$Query" $_ 2>$null) -as [int] } -Descending |
  Select-Object -First $MaxFiles

if (-not $files) { "No matches for '$Query' under $Root (glob $Glob)."; exit 0 }

$byCorpus = $files | ForEach-Object { Get-Corpus $_ } | Group-Object | Sort-Object Count -Descending
"# secsearch '$Query' — $($files.Count) file(s) across $($byCorpus.Count) corpus/corpora:"
($byCorpus | ForEach-Object { "$($_.Name)=$($_.Count)" }) -join '  '
""

foreach ($f in $files) {
  $corpus = Get-Corpus $f
  "===== [$corpus] $f ====="
  & rg -i -n -C $Context --glob $Glob -m 3 -- "$Query" $f 2>$null
  ""
}
