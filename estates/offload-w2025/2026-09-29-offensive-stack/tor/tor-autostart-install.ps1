# tor-autostart-install.ps1 - register the estate Tor proxy (single process,
# same lifecycle pattern as CyberStrikeGateway - no supervisor, no watchdog).
$ErrorActionPreference = "Stop"
$action = New-ScheduledTaskAction -Execute "D:\opt\tor\tor.exe" -Argument "-f D:\opt\tor\torrc" -WorkingDirectory "D:\opt\tor"
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:COMPUTERNAME\prekzursil"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "TorProxy" -Action $action -Trigger $trigger -Settings $settings `
    -Description "Estate Tor SOCKS proxy 127.0.0.1:9050 + 9150 (single process)" -Force | Out-Null
Write-Host "registered task 'TorProxy' (D:\opt\tor, SocksPort 9050 + 9150)"
