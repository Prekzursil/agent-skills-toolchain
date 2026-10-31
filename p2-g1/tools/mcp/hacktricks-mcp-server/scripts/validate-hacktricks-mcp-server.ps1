#requires -Version 7
<#
.SYNOPSIS
  Validate a deployed hardened HackTricks MCP server install root (read-only).

.DESCRIPTION
  Confirms the toolchain, the built entrypoint, the pinned corpus (origin, exact
  HEAD, clean tracked tree, src/SUMMARY.md), and a harmless read-only MCP smoke
  test that exactly seven tools are advertised. Prints a JSON verdict and exits
  non-zero on any failure. Mutates nothing.
#>
[CmdletBinding()]
param(
  [string]$InstallRoot = (Join-Path $env:USERPROFILE '.local\opt\hacktricks-mcp-server'),
  [string]$CorpusCommit = '346301958c8bf94120ba0aaaaf9cd963997bdac3',
  [string]$OfficialOrigin = 'https://github.com/hacktricks-wiki/hacktricks'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Normalize-Origin {
  param([string]$Url)
  $u = $Url.Trim()
  if ($u.EndsWith('.git')) { $u = $u.Substring(0, $u.Length - 4) }
  if ($u.EndsWith('/')) { $u = $u.Substring(0, $u.Length - 1) }
  return $u.ToLowerInvariant()
}

$failures = New-Object System.Collections.Generic.List[string]
function Check {
  param([string]$Label, [bool]$Ok, [string]$Detail)
  if (-not $Ok) { $failures.Add("$Label ($Detail)") }
}

foreach ($tool in @('node', 'git', 'rg')) {
  Check "$tool-on-path" ($null -ne (Get-Command $tool -ErrorAction SilentlyContinue)) 'missing'
}

$entry = Join-Path $InstallRoot 'dist/index.js'
Check 'entrypoint-exists' (Test-Path -LiteralPath $entry) $entry

$book = Join-Path $InstallRoot 'hacktricks'
$origin = ''
$head = ''
if (Test-Path -LiteralPath $book) {
  $origin = (& git '-C' $book remote get-url origin 2>$null)
  $head = (& git '-C' $book rev-parse HEAD 2>$null)
  $porcelain = (& git '-C' $book status --porcelain --untracked-files=no 2>$null)
  Check 'corpus-origin' ((Normalize-Origin ($origin | Out-String)) -eq (Normalize-Origin $OfficialOrigin)) ($origin | Out-String).Trim()
  Check 'corpus-head' (($head | Out-String).Trim() -eq $CorpusCommit) ($head | Out-String).Trim()
  Check 'corpus-clean' ([string]::IsNullOrWhiteSpace(($porcelain -join ''))) 'dirty'
  Check 'corpus-summary' (Test-Path -LiteralPath (Join-Path $book 'src/SUMMARY.md')) 'missing'
} else {
  Check 'corpus-present' $false $book
}

$smokeOut = ''
if (Test-Path -LiteralPath $entry) {
  $env:HACKTRICKS_CORPUS = $book
  $smokeScript = Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts/smoke.mjs'
  $smokeOut = & node $smokeScript $entry
  Check 'mcp-smoke-7-tools' ($LASTEXITCODE -eq 0) ($smokeOut | Out-String).Trim()
}

$verdict = [ordered]@{
  install_root  = $InstallRoot
  ok            = ($failures.Count -eq 0)
  failures      = @($failures)
  corpus_head   = ($head | Out-String).Trim()
  smoke         = ($smokeOut | Out-String).Trim()
  checked_at    = (Get-Date -Format 'o')
}
($verdict | ConvertTo-Json -Depth 4) | Write-Output

if ($failures.Count -ne 0) { exit 1 }
