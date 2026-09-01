# register-tasks -- always-on supervision, no admin. Idempotent; FIXES the dual-watchdog bug
# (deletes any stale Startup-folder launcher so it can't fire alongside the Task; the watchdog's
# named mutex is the belt, this is the suspenders).
#   ClaudeScienceWatchdog  -- cs-watchdog.ps1 at logon (single-instance via mutex + IgnoreNew)
#   ClaudeScienceMaintain  -- weekly offline SQLite maintenance (Sun 04:00)
#
# THE LAUNCH PATH IS PART OF THE FIX, NOT AN INCIDENTAL DETAIL. This script used to register
# whatever copy of cs-watchdog.ps1 sat beside ITSELF ($here), and install.ps1 invokes it from the
# source directory -- so running the installer from a checkout registered an always-on supervisor
# against that checkout. Measured 2026-08-12: the live task launched
#   C:\Users\Prekzursil\source\ast-integrate\scripts\claude-science\cs-watchdog.ps1
# where `.git` is a FILE reading `gitdir: .../worktrees/ast-integrate` -- a LINKED WORKTREE created
# for one integration run. `git worktree remove` would have deleted the supervisor's script, and
# Task Scheduler reports a missing -File target as a task that ran, so the death would have been as
# silent as the 3.3-day logon-only outage this same file exists to prevent. The durable copy at
# ~/.local/bin/cs-watchdog.ps1 already existed, byte-identical, and nothing pointed at it.
# Default is now that durable copy; -WatchdogPath overrides; falling back to $here is loud.
[CmdletBinding()]
param([string]$WatchdogPath)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $PSCommandPath
. (Join-Path $here 'cs-lib.ps1')      # cs.conf -> $script:CSDistro (was hardcoded in the maintain action)

$installed = Join-Path $env:USERPROFILE '.local\bin\cs-watchdog.ps1'
$watch = if ($WatchdogPath) { $WatchdogPath }
elseif (Test-Path -LiteralPath $installed) { $installed }
else { Join-Path $here 'cs-watchdog.ps1' }
if (-not (Test-Path -LiteralPath $watch)) { throw "cs-watchdog.ps1 not found at '$watch' - refusing to register a task that cannot start (that failure mode is invisible in Task Scheduler)." }
$eph = Test-CSEphemeralWorktree $watch
if ($eph) {
  Write-Information -InformationAction Continue "[WARN] registering the watchdog OUT OF AN EPHEMERAL GIT WORKTREE ($eph): $watch"
  Write-Information -InformationAction Continue '[WARN] it will stop working the moment that worktree is removed, and Task Scheduler will not say so. Run install.ps1 (deploys to ~\.local\bin) or pass -WatchdogPath.'
}

# --- kill the OLD dual-registration path: remove any stale Startup watchdog launcher ---
$startupVbs = Join-Path ([Environment]::GetFolderPath('Startup')) 'cs-watchdog.vbs'
if (Test-Path $startupVbs) { Remove-Item $startupVbs -Force; Write-Information -InformationAction Continue '[cleanup] removed stale Startup cs-watchdog.vbs (dual-watchdog fix)' }

# --- 1. Watchdog at logon PLUS a repeating re-launch (IgnoreNew so the Task never self-dupes) ---
# MEASURED 2026-08-12: a logon-ONLY trigger left the watchdog dead for 3.3 days. Its own log shows
# two instances raced at logon on 2026-08-08; the loser hit the mutex guard and `exit 0` (recorded
# as lastResult=0), the winner died silently at 17:16 under host-RAM pressure (the log's last lines
# are LOW HOST RAM 1.1-2.3GB free, vmmemWSL ~5GB), and with no logon since, NOTHING restarted it:
# Get-ScheduledTaskInfo reported State=Ready with an EMPTY NextRunTime and a heartbeat 285,033s old.
#
# RestartCount 999 did not save it either, and that is the subtle half of the bug: restart-on-failure
# only fires when a task FAILS, and the mutex guard exits ZERO, which Task Scheduler reads as success.
# A clean exit is not a failure, so the 999 restarts were never eligible.
#
# THE FIX IS THE PATTERN ALREADY PROVEN ON THIS BOX. MCPAgentMailSupervisor -- documented
# self-healing, ~27s recovery from a hard kill -- carries TWO triggers: MSFT_TaskLogonTrigger plus an
# MSFT_TaskTimeTrigger with Repetition.Interval=PT10M. Read back live, its LastTaskResult is
# 2147946720 (0x80070420, "an instance of this task is already running"), which is IgnoreNew working
# as intended: the repeating trigger fires every 10 minutes, is ignored while the supervisor is alive,
# and STARTS it whenever it is not. That is the whole self-healing mechanism, and it is exactly what
# this task lacked.
#
# This does NOT reintroduce the dual-watchdog race the header warns about. That race came from a
# Startup-folder launcher firing ALONGSIDE the Task (cleaned up above). Duplication is blocked twice
# over: MultipleInstances IgnoreNew at the scheduler, and the script's own Global\ mutex at line 22.
try {
  $a = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$watch`""
  $t = @(
    (New-ScheduledTaskTrigger -AtLogOn),
    (New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 10))
  )
  $s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
  Register-ScheduledTask -TaskName 'ClaudeScienceWatchdog' -Action $a -Trigger $t -Settings $s -Force | Out-Null
  # VERIFY THEN TRUST: a registration that silently drops the repetition would restore the exact bug
  # this block exists to fix, and it would look identical from the outside. Read the interval back.
  $live = Get-ScheduledTask -TaskName 'ClaudeScienceWatchdog'
  $rep = @($live.Triggers | ForEach-Object { $_.Repetition.Interval } | Where-Object { $_ })
  if ($rep -contains 'PT10M') {
    Write-Information -InformationAction Continue '[ok] ClaudeScienceWatchdog (logon + PT10M re-launch, verified)'
  } else {
    Write-Information -InformationAction Continue "[WARN] ClaudeScienceWatchdog registered but repetition NOT set (got: $($rep -join ',')) - it will die on the next silent exit and stay dead. Set it by hand in taskschd.msc."
  }
  # VERIFY THE ACTION TOO, for the same reason the repetition is read back: a registration that
  # silently kept a previous action, or wrote a path that does not exist, is indistinguishable from
  # success at the API. This is the identical judgement cs-doctor's 'Watchdog action path' row makes,
  # applied at the moment of writing so the defect cannot be introduced in the first place.
  $v = Get-CSWatchdogActionVerdict -Task $live -ReferenceScript $watch
  if ($v.Status -eq 'PASS') { Write-Information -InformationAction Continue "[ok] action verified -> $($v.Detail)" }
  else { Write-Information -InformationAction Continue "[$($v.Status)] watchdog action: $($v.Detail)" }
} catch {
  Write-Information -InformationAction Continue "[fallback] Task Scheduler denied ($($_.Exception.Message)); using Startup folder."
  @"
Set s = CreateObject("WScript.Shell")
s.Run "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ""$watch""", 0, False
"@ | Set-Content -Encoding ascii $startupVbs
  Write-Information -InformationAction Continue "[ok] Startup launcher -> $startupVbs"
}

# --- 2. Weekly offline maintenance (DB is tiny + already WAL; weekly light-hygiene is enough) ---
try {
  $am = New-ScheduledTaskAction -Execute 'wsl.exe' -Argument "-d $script:CSDistro -e sh -lc cs-maintain"
  $tm = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 4am
  $sm = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
  Register-ScheduledTask -TaskName 'ClaudeScienceMaintain' -Action $am -Trigger $tm -Settings $sm -Force | Out-Null
  Write-Information -InformationAction Continue '[ok] ClaudeScienceMaintain (Sun 04:00)'
} catch { Write-Information -InformationAction Continue "[warn] maintenance task not registered: $($_.Exception.Message). Run cs-maintain manually." }

Write-Information -InformationAction Continue 'Start the watchdog now without waiting for logon:  Start-ScheduledTask ClaudeScienceWatchdog'
