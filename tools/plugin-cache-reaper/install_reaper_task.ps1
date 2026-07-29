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

.PARAMETER Uninstall
  Remove the task instead of creating it.

.EXAMPLE
  pwsh -File install_reaper_task.ps1
  pwsh -File install_reaper_task.ps1 -MinAgeMinutes 720
  pwsh -File install_reaper_task.ps1 -Uninstall
#>
[CmdletBinding()]
param(
    [int]$MinAgeMinutes = 120,
    [string]$TaskName = 'ClaudePluginCacheReaper',
    [string]$At = '03:20',
    [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'

if ($Uninstall) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        "SUCCESS:reaper-task removed $TaskName"
    }
    else {
        "SUCCESS:reaper-task $TaskName was not registered; nothing to do"
    }
    return
}

if ($MinAgeMinutes -lt 1) {
    Write-Error 'FAILED:reaper-task -MinAgeMinutes must be >= 1'
}

$script = Join-Path $PSScriptRoot 'reap.py'
if (-not (Test-Path -LiteralPath $script)) {
    Write-Error "FAILED:reaper-task reap.py not found next to this installer ($script)"
}

$python = (Get-Command python -ErrorAction SilentlyContinue)?.Source
if (-not $python) {
    Write-Error 'FAILED:reaper-task no python on PATH (checked with Get-Command, not which)'
}

# Prove the exact command works BEFORE scheduling it: a task that fails nightly and
# silently is worse than no task. Dry-run, so this probe deletes nothing.
$probe = & $python $script --min-age-minutes $MinAgeMinutes 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "FAILED:reaper-task dry-run probe exited $LASTEXITCODE`n$probe"
}
"probe: $($probe | Select-Object -Last 1)"

$action = New-ScheduledTaskAction -Execute $python `
    -Argument "`"$script`" --apply --min-age-minutes $MinAgeMinutes"
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Description (
        'Reap abandoned Claude Code plugin-install staging clones from ' +
        '~/.claude/plugins/cache (mitigation for a vendor leak; see ' +
        'tools/plugin-cache-reaper/README.md).') | Out-Null

"SUCCESS:reaper-task registered $TaskName daily at $At (--apply --min-age-minutes $MinAgeMinutes)"
