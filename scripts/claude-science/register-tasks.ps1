# register-tasks — always-on supervision, no admin. Idempotent; FIXES the dual-watchdog bug
# (deletes any stale Startup-folder launcher so it can't fire alongside the Task; the watchdog's
# named mutex is the belt, this is the suspenders).
#   ClaudeScienceWatchdog  — cs-watchdog.ps1 at logon (single-instance via mutex + IgnoreNew)
#   ClaudeScienceMaintain  — weekly offline SQLite maintenance (Sun 04:00)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$watch = Join-Path $here 'cs-watchdog.ps1'

# --- kill the OLD dual-registration path: remove any stale Startup watchdog launcher ---
$startupVbs = Join-Path ([Environment]::GetFolderPath('Startup')) 'cs-watchdog.vbs'
if (Test-Path $startupVbs) { Remove-Item $startupVbs -Force; Write-Host '[cleanup] removed stale Startup cs-watchdog.vbs (dual-watchdog fix)' }

# --- 1. Watchdog at logon (single mechanism; IgnoreNew so the Task never self-dupes) ---
try {
  $a = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$watch`""
  $t = New-ScheduledTaskTrigger -AtLogOn
  $s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
  Register-ScheduledTask -TaskName 'ClaudeScienceWatchdog' -Action $a -Trigger $t -Settings $s -Force | Out-Null
  Write-Host '[ok] ClaudeScienceWatchdog (logon)'
} catch {
  Write-Host "[fallback] Task Scheduler denied ($($_.Exception.Message)); using Startup folder."
  @"
Set s = CreateObject("WScript.Shell")
s.Run "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ""$watch""", 0, False
"@ | Set-Content -Encoding ascii $startupVbs
  Write-Host "[ok] Startup launcher -> $startupVbs"
}

# --- 2. Weekly offline maintenance (DB is tiny + already WAL; weekly light-hygiene is enough) ---
try {
  $am = New-ScheduledTaskAction -Execute 'wsl.exe' -Argument '-d Ubuntu -e sh -lc cs-maintain'
  $tm = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 4am
  $sm = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
  Register-ScheduledTask -TaskName 'ClaudeScienceMaintain' -Action $am -Trigger $tm -Settings $sm -Force | Out-Null
  Write-Host '[ok] ClaudeScienceMaintain (Sun 04:00)'
} catch { Write-Host "[warn] maintenance task not registered: $($_.Exception.Message). Run cs-maintain manually." }

Write-Host 'Start the watchdog now without waiting for logon:  Start-ScheduledTask ClaudeScienceWatchdog'
