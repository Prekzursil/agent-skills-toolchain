#requires -version 5.1
<#
.SYNOPSIS  Refresh the local HackTricks sparse clones (keeps src-only, images excluded).
#>
param([string]$Corpus = $(if ($env:HACKTRICKS_CORPUS) { $env:HACKTRICKS_CORPUS } else { 'D:\knowledge\hacktricks' }))
$ErrorActionPreference = 'Stop'
$env:GIT_TERMINAL_PROMPT = '0'
foreach ($d in 'hacktricks', 'hacktricks-cloud') {
  $p = Join-Path $Corpus $d
  if (-not (Test-Path $p)) { Write-Warning "missing $p — run the initial sparse clone first"; continue }
  Push-Location $p
  try {
    git fetch --depth 1 origin master 2>&1 | Select-Object -Last 1
    git reset --hard origin/master   2>&1 | Select-Object -Last 1
    git sparse-checkout set "/src/**" "!/src/images/**" 2>&1 | Out-Null
  } finally { Pop-Location }
  $md = (Get-ChildItem -Recurse -Filter *.md $p | Measure-Object).Count
  "updated $d : md=$md"
}
