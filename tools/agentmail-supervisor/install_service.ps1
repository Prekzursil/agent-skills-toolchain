<#
.SYNOPSIS
    Register the agent-mail supervisor as an always-on logon Scheduled Task (no nssm / no admin
    service). Runs at user logon AND starts it immediately.

.DESCRIPTION
    Creates a Scheduled Task "MCPAgentMailSupervisor" that launches agentmail_supervisor.ps1
    (loop mode) hidden at logon of the current user. The supervisor's own mutex + health-gate
    make repeated starts idempotent, so re-running this installer is safe.

.PARAMETER SupervisorPath  Full path to agentmail_supervisor.ps1. Defaults to sibling of this script.
.PARAMETER TaskName        Scheduled Task name. Default MCPAgentMailSupervisor.
.PARAMETER Uninstall       Remove the task (and stop the running supervisor) instead of installing.
.PARAMETER NoStartNow      Register the task but do not start it immediately.

.NOTES
    Runs in the user's own security context (no elevation needed for a per-user logon task).
    Uninstall snippet is included below and also runnable via -Uninstall.
#>
[CmdletBinding()]
param(
    [string]$SupervisorPath = (Join-Path $PSScriptRoot 'agentmail_supervisor.ps1'),
    [string]$TaskName       = 'MCPAgentMailSupervisor',
    [switch]$Uninstall,
    [switch]$NoStartNow
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# ---------------------------------------------------------------- uninstall
if ($Uninstall) {
    Write-Host "Uninstalling scheduled task '$TaskName'..."
    # ORDER MATTERS: remove the task (kills the running loop supervisor) BEFORE stopping the
    # server, otherwise the still-running supervisor immediately restarts it.
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        try { Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue } catch { }
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Removed scheduled task '$TaskName'."
    } else {
        Write-Host "No scheduled task '$TaskName' found."
    }
    # Now stop the (orphaned) server child; nothing left to restart it.
    if (Test-Path $SupervisorPath) {
        try {
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $SupervisorPath -StopExisting | Out-Null
        } catch { Write-Warning "StopExisting failed: $($_.Exception.Message)" }
    }
    return
}

# ---------------------------------------------------------------- install
if (-not (Test-Path $SupervisorPath)) {
    throw "Supervisor script not found at: $SupervisorPath"
}
$SupervisorPath = (Resolve-Path $SupervisorPath).Path

# powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File <supervisor>
$psExe   = (Get-Command powershell.exe).Source
$actArgs = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$SupervisorPath`""

$action    = New-ScheduledTaskAction   -Execute $psExe -Argument $actArgs
$trigger   = New-ScheduledTaskTrigger  -AtLogOn -User $env:USERNAME
# Keep it alive: no time limit, restart on failure, run whether or not on AC power.
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
                -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) `
                -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Task '$TaskName' exists; updating definition."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description 'Always-on supervisor for the mcp_agent_mail HTTP channel (port 8812).' | Out-Null
Write-Host "Registered scheduled task '$TaskName' (runs agentmail_supervisor.ps1 at logon)."

if (-not $NoStartNow) {
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "Started task '$TaskName' now."
}

Write-Host ''
Write-Host '--- Uninstall snippet -------------------------------------------------'
Write-Host "  powershell -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Uninstall"
Write-Host '  # or manually:'
Write-Host "  Stop-ScheduledTask -TaskName '$TaskName' -ErrorAction SilentlyContinue"
Write-Host "  Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
Write-Host '-----------------------------------------------------------------------'

