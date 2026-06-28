<#
.SYNOPSIS
  Monitor Claude Code subagents: one terminal per running agent + a live dashboard.

.DESCRIPTION
  Read-only. Reads each subagent's append-only transcript
  (~/.claude/projects/<project>/<session>/subagents/agent-*.jsonl) — completely
  decoupled from the inline TUI, so it can't interfere with the live Claude Code.

.EXAMPLE
  .\Monitor-Agents.ps1                 # spawn tail windows for running agents + dashboard
  .\Monitor-Agents.ps1 -All            # include finished agents
  .\Monitor-Agents.ps1 -Tabs           # tail tabs in one Windows-Terminal window
  .\Monitor-Agents.ps1 -DashboardOnly  # just the overview, no spawning
  .\Monitor-Agents.ps1 -SpawnOnly      # just open the per-agent terminals
#>
[CmdletBinding()]
param(
  [switch]$All,
  [switch]$Tabs,
  [switch]$NoWt,
  [string]$Dir,
  [double]$ActiveSecs = 150,
  [switch]$DashboardOnly,
  [switch]$SpawnOnly
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

# --- resolve python ---
$py = $null
if (Get-Command py -ErrorAction SilentlyContinue)      { $py = 'py';     $pyArgs = @('-3') }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $py = 'python'; $pyArgs = @() }
else { throw 'Python 3 not found on PATH. Install Python 3 and retry.' }

# --- shared flags ---
$common = @()
if ($All)        { $common += '--all' }
if ($Tabs)       { $common += '--tabs' }
if ($NoWt)       { $common += '--no-wt' }
if ($Dir)        { $common += @('--dir', $Dir) }
$common += @('--active-secs', "$ActiveSecs")

if (-not $DashboardOnly) {
  Write-Host 'Spawning one terminal per running agent...' -ForegroundColor Cyan
  & $py @pyArgs 'agent_monitor.py' '--spawn' @common
}
if (-not $SpawnOnly) {
  Write-Host 'Opening dashboard (Ctrl-C to quit)...' -ForegroundColor Cyan
  & $py @pyArgs 'agent_monitor.py' '--watch' @common
}
