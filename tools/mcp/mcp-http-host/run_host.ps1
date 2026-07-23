<#
.SYNOPSIS
  Launch ONE shared mcp-http-host wrapping a hub's stdio MCP server, so every
  Claude / Codex session dials the single running instance over HTTP instead of
  each spawning its own stdio copy.

.EXAMPLE
  .\run_host.ps1 -Server search-hub -Port 8900
  .\run_host.ps1 -Server social-hub -Port 8901

.NOTES
  ALWAYS-ON: register a per-user logon Scheduled Task, exactly like the proven
  MCPAgentMailSupervisor pattern, so the shared host survives logout/reboot:

    schtasks /Create /TN McpHttpHost-search-hub /SC ONLOGON /RL LIMITED /F `
      /TR "powershell -WindowStyle Hidden -NoProfile -File `"$PWD\run_host.ps1`" -Server search-hub -Port 8900"

  Then register the endpoint (Claude CLOSED) with apply_registration.py and restart.
#>
param(
    [Parameter(Mandatory = $true)][string]$Server,
    [int]$Port = 8900,
    [string]$Python = 'C:\Python314\python.exe',
    [string]$Repo = "$HOME\source\agent-skills-toolchain"
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$hostScript = Join-Path $here 'mcp_http_host.py'
$hub = Join-Path $Repo "tools\mcp\$Server\hub.py"

if (-not (Test-Path $Python)) { throw "python not found: $Python" }
if (-not (Test-Path $hub)) { throw "hub not found: $hub (is -Server correct?)" }

Write-Host "mcp-http-host: serving $Server at http://127.0.0.1:$Port/mcp (health /healthz)"
& $Python $hostScript --eager --port $Port -- $Python $hub
