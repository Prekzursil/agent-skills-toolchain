# gateway-autostart-install.ps1 - register boot lifecycle for the ONE process.
# This is the entire lifecycle mechanism of the kit: a logon-triggered
# scheduled task that starts the gateway if it is not already running.
# No periodic probing, no restart loops, no fleet.
$ErrorActionPreference = "Stop"
$Kit = $PSScriptRoot
$Py  = "C:\Python314\python.exe"

$action  = New-ScheduledTaskAction -Execute $py -Argument "`"$Kit\gateway-server.py`"" `
             -WorkingDirectory $Kit
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:COMPUTERNAME\prekzursil"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
             -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "CyberStrikeGateway" -Action $action -Trigger $trigger `
    -Settings $settings -Description "CyberStrike MCP gateway (single process; no watchdog)" `
    -Force | Out-Null
Write-Host "registered scheduled task 'CyberStrikeGateway' (starts at logon, single instance)."
Write-Host "start now:  Start-ScheduledTask -TaskName CyberStrikeGateway"
Write-Host "stop  via:  $Kit\gateway-stop.ps1"
