<#
.SYNOPSIS
  Register CRCPChatGPTBridge as an always-on logon Scheduled Task.

.DESCRIPTION
  Runs `python -m crcp chatgpt live` with tools/crcp on PYTHONPATH, HTTP on :8820,
  auto-publish enabled. Restarts on failure. Health: GET http://127.0.0.1:8820/health

.PARAMETER Uninstall  Remove the task and stop any matching python live process (best-effort).
.PARAMETER NoStartNow Register without starting immediately.
#>
[CmdletBinding()]
param(
    [string]$TaskName = 'CRCPChatGPTBridge',
    [switch]$Uninstall,
    [switch]$NoStartNow,
    [int]$HttpPort = 8820,
    [int]$PollInterval = 60
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$CrpRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = (Get-Command python -ErrorAction Stop).Source
$Wrapper = Join-Path $CrpRoot 'scripts\run_crcp_live_bridge.ps1'

if ($Uninstall) {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        try { Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue } catch { }
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Removed task '$TaskName'."
    } else {
        Write-Host "No task '$TaskName'."
    }
    return
}

if (-not (Test-Path $Wrapper)) {
    throw "Missing wrapper: $Wrapper"
}

$psExe = (Get-Command powershell.exe).Source
$actArgs = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Wrapper`" -HttpPort $HttpPort -PollInterval $PollInterval"
$action = New-ScheduledTaskAction -Execute $psExe -Argument $actArgs -WorkingDirectory $CrpRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description "CRCP ChatGPT live poller + HTTP status on 127.0.0.1:$HttpPort (auto-publish to agent-mail)." | Out-Null

Write-Host "Registered scheduled task '$TaskName'."
if (-not $NoStartNow) {
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "Started '$TaskName'."
}
Write-Host "Health: http://127.0.0.1:$HttpPort/health (bypass system proxy for localhost)"
