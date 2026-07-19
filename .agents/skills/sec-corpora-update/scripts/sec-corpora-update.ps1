#requires -version 5.1
<#
.SYNOPSIS
  Refresh the local security-knowledge corpora under D:\knowledge (git pull --depth 1 each).
.DESCRIPTION
  Idempotent and FAIL-OPEN per repo: each corpus is pulled inside its own try/catch, a failure
  on one repo never aborts the rest, and the script always exits 0. Shallow (--depth 1) so the
  clones stay small. HackTricks is intentionally skipped here — it is a sparse, nested
  (hacktricks/ + hacktricks-cloud/) checkout refreshed by its own htk_update.ps1.
.EXAMPLE
  pwsh sec-corpora-update.ps1
#>
param(
  [string]$Root = $(if ($env:SEC_CORPORA_ROOT) { $env:SEC_CORPORA_ROOT } else { 'D:\knowledge' })
)
$ErrorActionPreference = 'Continue'
$env:GIT_TERMINAL_PROMPT = '0'  # never block on credential prompts

$corpora = 'payloadsallthethings', 'gtfobins', 'lolbas', 'owasp-wstg', 'owasp-cheatsheets', 'atomic-red-team'

$ok = 0; $fail = 0; $skip = 0
foreach ($name in $corpora) {
  $p = Join-Path $Root $name
  if (-not (Test-Path (Join-Path $p '.git'))) {
    Write-Host "SKIP   $name (not a git clone at $p)"; $skip++; continue
  }
  try {
    $out = & git -C $p pull --depth 1 --no-edit 2>&1
    if ($LASTEXITCODE -eq 0) {
      Write-Host "OK     $name : $(($out | Select-Object -Last 1))"; $ok++
    } else {
      Write-Host "FAILED $name : $(($out | Select-Object -Last 1))"; $fail++
    }
  } catch {
    Write-Host "FAILED $name : $($_.Exception.Message)"; $fail++
  }
}
Write-Host "sec-corpora-update done: ok=$ok failed=$fail skipped=$skip (HackTricks uses htk_update.ps1)"
exit 0
