<#
.SYNOPSIS
  Register (or remove) a per-user Scheduled Task that sweeps abandoned Claude Code
  plugin-install staging clones out of ~/.claude/plugins/cache.

.DESCRIPTION
  MITIGATION, not a fix -- the writer is the Claude Code binary itself and cannot be
  patched here. See README.md for the measurement that identifies it.

  Nothing in CI or in any hook runs this file; registering the task is an explicit
  owner action. The task itself runs reap.py, which is dry-run by default -- this
  installer passes --apply on purpose, since an unattended dry-run would only log.

.PARAMETER MinAgeMinutes
  Only husks older than this by BOTH age signals are reaped. Default 120, which is
  well past the CLI's own 120-second clone timeout.

.PARAMETER MaxEntries
  IMP-0042: entry ceiling for the development-loop cache (tools/plugin/cache_policy).
  Passed to reap.py as --max-entries; retention itself is cache_policy.apply_retention.

.PARAMETER MaxBytes
  IMP-0042: byte ceiling for the development-loop cache, passed as --max-bytes.

.PARAMETER RetentionFloor
  IMP-0042: never evict below this many newest dev-cache entries (--retention-floor).

.PARAMETER Uninstall
  Remove the task instead of creating it.

.NOTES
  The task is ONE task, PluginCacheReaper. When it already exists it is UPDATED in
  place with Set-ScheduledTask (history, enabled state and last-run result survive);
  it is newly registered only when absent (one registration call). The retention argv
  rides on that same task -- there is no second task for retention. The pre-IMP-0042
  name ClaudePluginCacheReaper is migrated once: if that legacy task exists it is
  retired and PluginCacheReaper takes over the schedule.

.EXAMPLE
  pwsh -File install_reaper_task.ps1
  pwsh -File install_reaper_task.ps1 -MinAgeMinutes 720 -MaxBytes 250000000
  pwsh -File install_reaper_task.ps1 -Uninstall
#>
[CmdletBinding()]
param(
    [int]$MinAgeMinutes = 120,
    [int]$MaxEntries = 32,
    [long]$MaxBytes = 1000000,
    [int]$RetentionFloor = 1,
    [string]$TaskName = 'PluginCacheReaper',
    [string]$LegacyTaskName = 'ClaudePluginCacheReaper',
    [string]$At = '03:20',
    [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'

if ($Uninstall) {
    $removed = @()
    foreach ($name in @($TaskName, $LegacyTaskName)) {
        if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
            Unregister-ScheduledTask -TaskName $name -Confirm:$false
            $removed += $name
        }
    }
    if ($removed.Count -gt 0) {
        "SUCCESS:reaper-task removed $($removed -join ', ')"
    }
    else {
        "SUCCESS:reaper-task $TaskName was not registered; nothing to do"
    }
    return
}

if ($MinAgeMinutes -lt 1) {
    Write-Error 'FAILED:reaper-task -MinAgeMinutes must be >= 1'
}
if ($MaxEntries -lt 0 -or $MaxBytes -lt 0 -or $RetentionFloor -lt 0) {
    Write-Error 'FAILED:reaper-task -MaxEntries, -MaxBytes and -RetentionFloor must be >= 0'
}

$script = Join-Path $PSScriptRoot 'reap.py'
if (-not (Test-Path -LiteralPath $script)) {
    Write-Error "FAILED:reaper-task reap.py not found next to this installer ($script)"
}

$python = (Get-Command python -ErrorAction SilentlyContinue)?.Source
if (-not $python) {
    Write-Error 'FAILED:reaper-task no python on PATH (checked with Get-Command, not which)'
}

# The retention argv is the SAME flags, in the same order, that the probe below and
# the scheduled action pass -- one list, so the probe cannot prove a different command
# than the one that gets scheduled.
$retentionArgv = @(
    '--max-entries', $MaxEntries,
    '--max-bytes', $MaxBytes,
    '--retention-floor', $RetentionFloor
)

# Prove the exact command works BEFORE scheduling it: a task that fails nightly and
# silently is worse than no task. Dry-run, so this probe deletes nothing.
$probe = & $python $script --min-age-minutes $MinAgeMinutes @retentionArgv 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "FAILED:reaper-task dry-run probe exited $LASTEXITCODE`n$probe"
}
"probe: $($probe | Select-Object -Last 1)"

$argument = "`"$script`" --apply --min-age-minutes $MinAgeMinutes " + ($retentionArgv -join ' ')
$action = New-ScheduledTaskAction -Execute $python -Argument $argument
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
$description = (
    'Reap abandoned Claude Code plugin-install staging clones from ' +
    '~/.claude/plugins/cache (mitigation for a vendor leak; see ' +
    'tools/plugin-cache-reaper/README.md) and bound the development-loop ' +
    'cache via tools/plugin/cache_policy retention (IMP-0042).')

# One-time migration off the pre-IMP-0042 name. The legacy task is retired here, not
# updated, because a scheduled task cannot be renamed in place; the schedule continues
# under $TaskName below.
if ($LegacyTaskName -and $LegacyTaskName -ne $TaskName -and
    (Get-ScheduledTask -TaskName $LegacyTaskName -ErrorAction SilentlyContinue)) {
    Unregister-ScheduledTask -TaskName $LegacyTaskName -Confirm:$false
    "migrated: retired legacy task $LegacyTaskName; $TaskName takes over"
}

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    # Update the EXISTING task in place: same name, new action/trigger/settings.
    Set-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Settings $settings | Out-Null
    $verb = 'updated'
}
else {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Settings $settings -Description $description | Out-Null
    $verb = 'registered'
}

"SUCCESS:reaper-task $verb $TaskName daily at $At (--apply --min-age-minutes $MinAgeMinutes $($retentionArgv -join ' '))"
