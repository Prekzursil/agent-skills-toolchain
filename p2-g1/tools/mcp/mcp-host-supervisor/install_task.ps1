<#
.SYNOPSIS
    Register (or remove) the MCPHostSupervisor logon Scheduled Task.

.DESCRIPTION
    Mirrors the proven MCPAgentMailSupervisor registration: a per-user logon task that
    runs the supervisor hidden, restarts it if it ever exits, and survives reboot.

    Additive and reversible:
      * -WhatIf     shows the registration without writing it
      * -Uninstall  removes the task and stops supervisor-owned hosts
      * an existing task is BACKED UP to a timestamped .xml before being replaced

    The task is inert until you enable servers in fleet.json - a fleet with every
    entry `"enabled": false` starts nothing.

.PARAMETER Uninstall  Remove the task (and stop the hosts it owns).
.PARAMETER TaskName   Override the task name. Default MCPHostSupervisor.
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$TaskName = 'MCPHostSupervisor',
    [string]$PythonExe = 'C:/Python314/python.exe',
    [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$SupervisorPs1 = Join-Path $PSScriptRoot 'mcp_host_supervisor.ps1'
$Manifest      = Join-Path $PSScriptRoot 'fleet.json'
$BackupDir     = Join-Path $PSScriptRoot 'logs'

function Write-Info { param([string]$Message) Write-Host "[install_task] $Message" }

if (-not (Test-Path $SupervisorPs1)) { throw "supervisor not found: $SupervisorPs1" }

# ------------------------------------------------------------------ uninstall
if ($Uninstall) {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $existing) { Write-Info "task '$TaskName' is not registered; nothing to do"; return }
    if ($PSCmdlet.ShouldProcess($TaskName, 'stop hosts and unregister scheduled task')) {
        try { & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $SupervisorPs1 -StopExisting } catch {
            Write-Warning "could not stop hosts cleanly: $_"
        }
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Info "removed task '$TaskName'"
    }
    return
}

# -------------------------------------------------------------------- install
if (-not (Test-Path $Manifest)) {
    Write-Warning "fleet.json not found at $Manifest - copy fleet.example.json to fleet.json first."
}

# Validate BEFORE registering: a task that can only ever fail is worse than none.
$validation = & $PythonExe (Join-Path $PSScriptRoot 'fleet.py') validate --manifest $Manifest 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) {
    Write-Warning "fleet.json is INVALID - fix it before the task can do anything:`n$validation"
} else {
    Write-Info "fleet.json validates: $($validation.Trim())"
}

# Back up an existing registration so this is reversible.
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    if (-not (Test-Path $BackupDir)) { New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null }
    $stamp  = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backup = Join-Path $BackupDir "$TaskName.BEFORE-$stamp.xml"
    Export-ScheduledTask -TaskName $TaskName | Set-Content -Path $backup -Encoding utf8
    Write-Info "backed up existing task to $backup"
}

$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -Manifest "{1}"' -f $SupervisorPs1, $Manifest) `
    -WorkingDirectory $PSScriptRoot

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -RestartCount 999 `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

if ($PSCmdlet.ShouldProcess($TaskName, 'register logon scheduled task')) {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Force | Out-Null
    Write-Info "registered '$TaskName' (logon trigger, restarts every 1 min, no time limit)"
    Write-Info "start it now with:  Start-ScheduledTask -TaskName $TaskName"
    Write-Info "remove it with:     ./install_task.ps1 -Uninstall"
}
