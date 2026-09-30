# watch-actions-runner.ps1 — keep WSL Ubuntu + the GitHub self-hosted runner + docker alive.
# Estate pattern: MCPAgentMailSupervisor (health-poll + auto-restart, never silent, never kills).
# Installed as scheduled task WSLActionsRunnerWatchdog (logon + every 10 min).
# Backstory (2026-09-30): the runner had been silently dead for weeks after the WSL
# /etc/environment corruption broke apt/docker; nobody noticed until CI went red on main.
$ErrorActionPreference = "SilentlyContinue"
$logDir = "$env:USERPROFILE\.agents\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$log = Join-Path $logDir "runner-watchdog.log"
function Log($m) { Add-Content $log "$(Get-Date -Format o) $m" }

$UNIT = "actions.runner.Prekzursil-agent-skills-toolchain.home-wsl.service"

# 1. Wake WSL (no-op if already running; also provides boot persistence at logon).
wsl.exe -d Ubuntu -- true | Out-Null

# 2. Runner service: check + start (never restart-if-active; no disruption).
$st = (wsl.exe -d Ubuntu -u root -- systemctl is-active $UNIT | Out-String).Trim()
if ($st -ne "active") {
    Log "runner service not active ($st) - starting"
    wsl.exe -d Ubuntu -u root -- systemctl start $UNIT | Out-Null
    Start-Sleep -Seconds 5
    $st2 = (wsl.exe -d Ubuntu -u root -- systemctl is-active $UNIT | Out-String).Trim()
    if ($st2 -ne "active") { Log "FAILED: still not active after start ($st2)" }
    else { Log "SUCCESS: restarted after state '$st'" }
}

# 3. Docker (CI jobs need service containers).
$ds = (wsl.exe -d Ubuntu -u root -- systemctl is-active docker | Out-String).Trim()
if ($ds -ne "active") {
    Log "docker not active ($ds) - starting"
    wsl.exe -d Ubuntu -u root -- systemctl start docker | Out-Null
    Start-Sleep -Seconds 3
    $ds2 = (wsl.exe -d Ubuntu -u root -- systemctl is-active docker | Out-String).Trim()
    if ($ds2 -ne "active") { Log "FAILED: docker still not active ($ds2)" }
}
