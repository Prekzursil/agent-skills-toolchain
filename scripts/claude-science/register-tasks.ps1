# register-tasks — install the always-on supervision (no admin needed):
#   1. ClaudeScienceWatchdog  — cs-watchdog.ps1 at logon (self-restarts; survives reboot)
#   2. ClaudeScienceMaintain  — weekly offline SQLite maintenance (Sun 04:00)
# Falls back to a Startup-folder launcher for the watchdog if Task Scheduler registration is denied.
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$watch = Join-Path $here 'cs-watchdog.ps1'

# --- 1. Watchdog at logon ---
try {
  $a = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$watch`""
  $t = New-ScheduledTaskTrigger -AtLogOn
  $s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
  Register-ScheduledTask -TaskName 'ClaudeScienceWatchdog' -Action $a -Trigger $t -Settings $s -Force | Out-Null
  Write-Host "[ok] ClaudeScienceWatchdog registered (logon)"
} catch {
  Write-Host "[fallback] Task Scheduler denied ($($_.Exception.Message)); using Startup folder."
  $startup = [Environment]::GetFolderPath('Startup')
  $vbs = Join-Path $startup 'cs-watchdog.vbs'
  @"
Set s = CreateObject("WScript.Shell")
s.Run "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ""$watch""", 0, False
"@ | Set-Content -Encoding ascii $vbs
  Write-Host "[ok] Startup launcher -> $vbs"
}

# --- 2. Weekly maintenance ---
try {
  $am = New-ScheduledTaskAction -Execute 'wsl.exe' -Argument '-d Ubuntu -e sh -lc cs-maintain'
  $tm = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 4am
  $sm = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
  Register-ScheduledTask -TaskName 'ClaudeScienceMaintain' -Action $am -Trigger $tm -Settings $sm -Force | Out-Null
  Write-Host "[ok] ClaudeScienceMaintain registered (Sun 04:00)"
} catch {
  Write-Host "[warn] weekly maintenance task not registered: $($_.Exception.Message). Run cs-maintain manually."
}
Write-Host "Start the watchdog now without waiting for logon:  Start-ScheduledTask ClaudeScienceWatchdog  (or run cs-watchdog.ps1)"
