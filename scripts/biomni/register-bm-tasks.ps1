# register-bm-tasks - installs the BiominiStackGuard scheduled task (watchdog).
# Run once (as the user; no admin needed for per-user tasks).
$ErrorActionPreference = 'Stop'
$script = Join-Path $PSScriptRoot 'bm-watchdog.ps1'
if (-not (Test-Path $script)) { throw "missing $script" }

$a = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -WindowStyle Hidden -File "' + $script + '"')
# Once-trigger + 10-min repetition (the shape proven on this box by FirecrawlStackGuard).
# StartWhenAvailable restarts it after downtime/reboot; the watchdog itself loops.
$t = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 10)
$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName 'BiominiStackGuard' -Action $a -Trigger $t -Settings $s -Force | Out-Null
Start-ScheduledTask -TaskName 'BiominiStackGuard'
"SUCCESS:bm-tasks-registered state=$((Get-ScheduledTask -TaskName 'BiominiStackGuard').State)"
