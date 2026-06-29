<#
.SYNOPSIS
  Restart the shared basic-memory streamable-http MCP daemon (127.0.0.1:8765).

  Launched DETACHED by liveness.py when the keystone memory store is found dead.
  Idempotent + safe: only ever kills a process that owns :8765 AND positively
  matches basic-memory (never an unrelated port-squatter), then relaunches via the
  scheduled task (whole-tree reap), falling back to the launcher script.

.PARAMETER KillCorpse
  Kill the basic-memory process holding :8765 first (the dead-but-listening case).

.PARAMETER DryRun
  Log the plan WITHOUT killing/restarting anything (used by the test suite so the
  live daemon is never disturbed).
#>
param(
    [switch]$KillCorpse,
    [switch]$DryRun
)

$ErrorActionPreference = 'SilentlyContinue'
$Port    = 8765
$Task    = 'BasicMemory-HTTP-MCP'
$Launcher = 'C:\Users\Prekzursil\.basic-memory\bm-http-server.ps1'
$LogDir  = 'C:\Users\Prekzursil\.basic-memory\logs'
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }
$Log = Join-Path $LogDir 'liveness-restart.log'

function Log($m) {
    $tag = if ($DryRun) { 'DRYRUN' } else { 'RESTART' }
    "$(Get-Date -Format o)  [$tag] $m" | Add-Content -Path $Log -Encoding utf8
}

function Get-PortOwnerPid([int]$p) {
    try {
        $c = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue |
             Select-Object -First 1
        if ($c) { return [int]$c.OwningProcess }
    } catch {}
    return $null
}

function Is-BasicMemoryPid([int]$procId) {
    # Positively confirm the PID is a basic-memory process before we ever kill it.
    try {
        $ci = Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue
        if ($ci) {
            $hay = "$($ci.Name) $($ci.ExecutablePath) $($ci.CommandLine)".ToLower()
            return ($hay -match 'basic-memory' -or $hay -match 'basic_memory')
        }
    } catch {}
    return $false
}

Log "begin (KillCorpse=$KillCorpse)"

try {
    if ($KillCorpse) {
        $ownerPid = Get-PortOwnerPid $Port
        if ($ownerPid -and (Is-BasicMemoryPid $ownerPid)) {
            if ($DryRun) {
                Log "would Stop-Process -Id $ownerPid (basic-memory corpse on :$Port)"
            } else {
                Log "killing basic-memory corpse PID $ownerPid on :$Port"
                Stop-Process -Id $ownerPid -Force -ErrorAction SilentlyContinue
                Start-Sleep -Milliseconds 400
            }
        } elseif ($ownerPid) {
            Log "PID $ownerPid owns :$Port but is NOT basic-memory - NOT killing (safety)"
        } else {
            Log "no listener on :$Port to kill"
        }
    }

    if ($DryRun) {
        Log "would Stop-ScheduledTask + Start-ScheduledTask '$Task' (fallback: launch $Launcher detached)"
        Log "end (dry-run, nothing changed)"
        return
    }

    $taskOk = $false
    $t = Get-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue
    if ($t) {
        Log "Stop+Start scheduled task '$Task'"
        Stop-ScheduledTask  -TaskName $Task -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 500
        Start-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue
        $taskOk = $true
    }

    if (-not $taskOk) {
        if (Test-Path $Launcher) {
            Log "scheduled task absent - launching $Launcher detached"
            Start-Process -FilePath 'powershell' `
                -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',$Launcher) `
                -WindowStyle Hidden
        } else {
            Log "ERROR: no scheduled task AND no launcher script ($Launcher) - cannot restart"
        }
    }

    # Best-effort confirmation (the daemon may still be warming up; don't block long).
    Start-Sleep -Seconds 2
    $owner = Get-PortOwnerPid $Port
    Log "end (port :$Port owner now: $owner)"
}
catch {
    Log "EXCEPTION: $($_.Exception.Message)"
}
