<#
.SYNOPSIS
  Register (or remove) the two scheduled tasks for the Basic Memory session-healing proxy.

.DESCRIPTION
  Mirrors the daemon's own pair (BasicMemory-HTTP-MCP / BasicMemory-Watchdog, receipt
  .agents/BASIC-MEMORY-RELIABILITY_2026-08-27.md):

    BasicMemory-SessionProxy           logon + every 5 min (IgnoreNew), restart-on-failure 3x/1 min,
                                       no time limit, hidden, LIMITED run level
                                       -> pwsh -File <ScriptDir>\bm-session-proxy.ps1
                                          (idempotent: the launcher skips when :8765 is already bound)
    BasicMemory-SessionProxy-Watchdog  logon + every 3 min, 2-min time limit, IgnoreNew
                                       -> pwsh -File <ScriptDir>\bm-session-proxy-watchdog.ps1

  Additive and reversible: -WhatIf shows the registrations without writing them; an existing
  task is BACKED UP to <ScriptDir>\backups\<task>.BEFORE-<stamp>.xml before it is replaced;
  -Uninstall removes both tasks and reaps only the proxy (never the daemon).

  Registering the tasks does NOT move the daemon's port: that is the owner-approved cutover
  step in ../deploy/README.md (move_daemon_port.py). Until the daemon is on :8766 the proxy
  cannot bind :8765 and its launcher logs "port 8765 already in use" and exits - harmless.

.PARAMETER ScriptDir   Where bm-session-proxy.ps1 and bm-session-proxy-watchdog.ps1 were deployed.
.PARAMETER Uninstall   Remove both tasks and stop the proxy.
.PARAMETER Start       Start the proxy task right after registering (default: register only).

.EXAMPLE
  .\Register-BmSessionProxyTasks.ps1 -WhatIf
  .\Register-BmSessionProxyTasks.ps1 -Start
  .\Register-BmSessionProxyTasks.ps1 -Uninstall
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$ScriptDir = 'C:\Users\Prekzursil\.basic-memory',
    [switch]$Uninstall,
    [switch]$Start
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ProxyTask    = 'BasicMemory-SessionProxy'
$WatchdogTask = 'BasicMemory-SessionProxy-Watchdog'
$Launcher     = Join-Path $ScriptDir 'bm-session-proxy.ps1'
$Watchdog     = Join-Path $ScriptDir 'bm-session-proxy-watchdog.ps1'
$BackupDir    = Join-Path $ScriptDir 'backups'

function Write-Info { param([string]$Message) Write-Host "[register] $Message" }

# The daemon's tasks run pwsh; fall back to Windows PowerShell only when pwsh is absent.
$shell = Get-Command pwsh.exe -ErrorAction SilentlyContinue
$shellExe = if ($shell) { $shell.Source } else { (Get-Command powershell.exe).Source }

function Backup-ExistingTask {
    param([string]$Name)
    $existing = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
    if (-not $existing) { return }
    if (-not (Test-Path $BackupDir)) { New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null }
    $stamp  = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backup = Join-Path $BackupDir "$Name.BEFORE-$stamp.xml"
    Export-ScheduledTask -TaskName $Name | Set-Content -Path $backup -Encoding utf8
    Write-Info "backed up existing '$Name' to $backup"
}

# ------------------------------------------------------------------ uninstall
if ($Uninstall) {
    foreach ($name in @($WatchdogTask, $ProxyTask)) {   # watchdog FIRST, so it cannot relaunch what we stop
        $existing = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        if (-not $existing) { Write-Info "task '$name' is not registered; nothing to do"; continue }
        if ($PSCmdlet.ShouldProcess($name, 'stop and unregister scheduled task')) {
            try { Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue } catch {}
            Unregister-ScheduledTask -TaskName $name -Confirm:$false
            Write-Info "removed task '$name'"
        }
    }
    if ($PSCmdlet.ShouldProcess('bm_session_proxy.py', 'stop the proxy process (scoped by script name)')) {
        Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like '*bm_session_proxy.py*' } |
            ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; Write-Info "stopped proxy pid $($_.ProcessId)" } catch {} }
        Remove-Item (Join-Path $env:TEMP 'bm-session-proxy.lock') -Force -ErrorAction SilentlyContinue
    }
    Write-Info ':8765 is free for the daemon again once its scripts are rolled back (move_daemon_port.py --rollback)'
    return
}

# -------------------------------------------------------------------- install
foreach ($file in @($Launcher, $Watchdog)) {
    if (-not (Test-Path $file)) { throw "not deployed: $file (copy the two .ps1 files from tools/mcp/mcp-http-host/deploy first)" }
}

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$logon     = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

# --- BasicMemory-SessionProxy: logon + every 5 min (belt-and-braces; the launcher is idempotent)
$every5 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
$proxyAction = New-ScheduledTaskAction -Execute $shellExe `
    -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f $Launcher) `
    -WorkingDirectory $ScriptDir
$proxySettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

# --- BasicMemory-SessionProxy-Watchdog: logon + every 3 min, short time limit
$every3 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes 3)
$watchdogAction = New-ScheduledTaskAction -Execute $shellExe `
    -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f $Watchdog) `
    -WorkingDirectory $ScriptDir
$watchdogSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -MultipleInstances IgnoreNew

if ($PSCmdlet.ShouldProcess($ProxyTask, 'register logon + 5-min scheduled task')) {
    Backup-ExistingTask -Name $ProxyTask
    Register-ScheduledTask -TaskName $ProxyTask -Action $proxyAction -Trigger @($logon, $every5) `
        -Settings $proxySettings -Principal $principal -Force `
        -Description 'Basic Memory session-healing reverse proxy on 127.0.0.1:8765 (upstream daemon on :8766).' | Out-Null
    Write-Info "registered '$ProxyTask' (logon + every 5 min, IgnoreNew, restart-on-failure, no time limit)"
}
if ($PSCmdlet.ShouldProcess($WatchdogTask, 'register logon + 3-min scheduled task')) {
    Backup-ExistingTask -Name $WatchdogTask
    Register-ScheduledTask -TaskName $WatchdogTask -Action $watchdogAction -Trigger @($logon, $every3) `
        -Settings $watchdogSettings -Principal $principal -Force `
        -Description 'Probes http://127.0.0.1:8765/healthz; force-recovers ONLY the proxy, never the daemon.' | Out-Null
    Write-Info "registered '$WatchdogTask' (logon + every 3 min)"
}
if ($Start -and $PSCmdlet.ShouldProcess($ProxyTask, 'start now')) {
    Start-ScheduledTask -TaskName $ProxyTask
    Write-Info "started '$ProxyTask'; verify with: Invoke-RestMethod http://127.0.0.1:8765/healthz"
} elseif (-not $Start) {
    Write-Info "registered only. Start after the daemon is on :8766:  Start-ScheduledTask -TaskName $ProxyTask"
}
