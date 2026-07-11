<#
VERIFY_PLAN.ps1 — PRIMARY (native Windows 11) smoke test for mcp_agent_mail.

Proves, before AgentBridge is retired, that the shared http channel works symmetrically
(claude<->codex message visibility) and that a file-lease acquire/release round-trips.

Self-contained: starts an ISOLATED serve-http instance on a temp STORAGE_ROOT, discovers the
bearer token, runs agent_mail_probe.py as an MCP client, prints SUCCESS:/FAILED: lines, then
tears everything down (never touches the real mailbox).

Usage:
    pwsh -File VERIFY_PLAN.ps1 -Repo C:\path\to\mcp_agent_mail [-Port 8799]

Requires: uv on PATH, a cloned mcp_agent_mail repo (uv sync already run), Git for Windows.
Exit 0 == all checks green.
#>
[CmdletBinding()]
param(
    [string]$Repo = $env:AM_REPO,
    [int]$Port = 8799,
    [int]$StartupTimeoutSec = 90
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Probe = Join-Path $ScriptDir 'agent_mail_probe.py'

function Fail($id, $msg) { Write-Host "FAILED:$id $msg"; }

# ---- preconditions ----
if (-not $Repo) { $Repo = Join-Path $env:USERPROFILE 'mcp_agent_mail' }
if (-not (Test-Path $Repo)) { Fail 'precondition_repo' "repo not found at $Repo (set -Repo or `$env:AM_REPO)"; exit 1 }
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { Fail 'precondition_uv' 'uv not on PATH'; exit 1 }
if (-not (Test-Path $Probe)) { Fail 'precondition_probe' "agent_mail_probe.py missing next to this script"; exit 1 }
Write-Host "SUCCESS:preconditions"

# ---- isolated workspace ----
$Stamp    = Get-Date -Format 'yyyyMMdd-HHmmss'
$Mark     = "probe$Stamp$([System.Guid]::NewGuid().ToString('N').Substring(0,6))"
$Storage  = Join-Path $env:TEMP "am_verify_$Stamp\storage"
$Project  = Join-Path $env:TEMP "am_verify_$Stamp\project"
$LogFile  = Join-Path $env:TEMP "am_verify_$Stamp\server.log"
New-Item -ItemType Directory -Force -Path $Storage, $Project | Out-Null
New-Item -ItemType File -Force -Path $LogFile | Out-Null

$serverProc = $null
$overall = 1
try {
    # ---- start isolated serve-http ----
    $env:STORAGE_ROOT = $Storage
    Push-Location $Repo
    $serverProc = Start-Process -FilePath 'uv' `
        -ArgumentList @('run','python','-m','mcp_agent_mail.cli','serve-http','--host','127.0.0.1','--port',"$Port") `
        -WorkingDirectory $Repo -RedirectStandardOutput $LogFile -RedirectStandardError "$LogFile.err" `
        -PassThru -WindowStyle Hidden
    Pop-Location

    # ---- wait for the port ----
    $up = $false
    for ($i = 0; $i -lt $StartupTimeoutSec; $i++) {
        if ($serverProc.HasExited) { break }
        try {
            $t = Test-NetConnection -ComputerName '127.0.0.1' -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
            if ($t) { $up = $true; break }
        } catch {}
        Start-Sleep -Seconds 1
    }
    if (-not $up) {
        Fail 'server_start' "serve-http did not open port $Port within ${StartupTimeoutSec}s"
        if (Test-Path $LogFile) { Write-Host '--- server.log tail ---'; Get-Content $LogFile -Tail 30 }
        if (Test-Path "$LogFile.err") { Write-Host '--- server.err tail ---'; Get-Content "$LogFile.err" -Tail 30 }
        exit 1
    }
    Write-Host "SUCCESS:server_up port=$Port"

    # ---- discover bearer token (env file, then server log) ----
    $token = ''
    $envFile = Join-Path $Storage '.env'
    foreach ($src in @($envFile, $LogFile, "$LogFile.err")) {
        if ($token) { break }
        if (Test-Path $src) {
            $m = Select-String -Path $src -Pattern 'BEARER[A-Z_]*\s*[=:]\s*["'']?([A-Za-z0-9._\-]+)' -AllMatches |
                 Select-Object -First 1
            if ($m) { $token = $m.Matches[0].Groups[1].Value }
        }
    }
    if ($token) { Write-Host "SUCCESS:token_discovered (len=$($token.Length))" }
    else { Write-Host "note: no bearer token discovered; attempting unauthenticated (probe will report if auth is required)" }

    # ---- run the MCP-client probe (inside repo so mcp SDK resolves) ----
    $env:AM_URL     = "http://127.0.0.1:$Port/mcp"
    $env:AM_TOKEN   = $token
    $env:AM_PROJECT = $Project
    $env:AM_MARK    = $Mark

    Push-Location $Repo
    & uv run python $Probe
    $overall = $LASTEXITCODE
    Pop-Location
}
finally {
    if ($serverProc -and -not $serverProc.HasExited) {
        try { Stop-Process -Id $serverProc.Id -Force -ErrorAction SilentlyContinue } catch {}
    }
    Remove-Item -Recurse -Force (Split-Path $Storage -Parent) -ErrorAction SilentlyContinue
}

if ($overall -eq 0) { Write-Host 'SUCCESS:verify_plan_complete'; exit 0 }
else { Write-Host "FAILED:verify_plan $overall check(s) failed"; exit 1 }
