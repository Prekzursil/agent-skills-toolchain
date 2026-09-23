#Requires -Version 5.1
<#
.SYNOPSIS
  Stop EVERY answer-engine profile (vane, ldr, ollama) and reclaim the RAM.
.DESCRIPTION
  Thin wrapper over `run-answer-engines.ps1 -Action down` with all three profile
  switches, because `docker compose down` skips profiled services it was not told
  about and would leave them running. -Print shows what would be stopped instead.
.EXAMPLE
  .\stop-answer-engines.ps1
  .\stop-answer-engines.ps1 -Print
#>
param(
  [switch]$Print
)
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $Here 'run-answer-engines.ps1') -Action down -Vane -Ldr -Ollama -Print:$Print
exit $LASTEXITCODE
