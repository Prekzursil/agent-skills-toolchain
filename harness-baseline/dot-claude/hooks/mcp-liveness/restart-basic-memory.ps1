<#
.SYNOPSIS
  Restart the shared basic-memory streamable-http MCP daemon (127.0.0.1:18765).

  Launched DETACHED by liveness.py when the keystone memory store is found dead.
  Idempotent + safe: only ever kills a process that owns :18765 AND positively
  matches basic-memory (never an unrelated port-squatter), then relaunches via the
  scheduled task (whole-tree reap), falling back to the launcher script.

.PARAMETER KillCorpse
  Kill the basic-memory process holding :18765 first (the dead-but-listening case).

.PARAMETER DryRun
  Log the plan WITHOUT killing/restarting anything (used by the test suite so the
  live daemon is never disturbed).
#>
param(
    [switch]$KillCorpse,
    [switch]$DryRun
)

$ErrorActionPreference = 'SilentlyContinue'
$Port    = 18765
$Task    = 'BasicMemory-HTTP-MCP'
$Launcher = 'C:\Users\Prekzursil\.basic-memory\bm-http-server.ps1'
# DIRECT-launch tier: zero external dependencies (no Scheduled Task, no out-of-tree script).
# Pinned from the daemon's OWN recorded invocation; matches the memory-contract URL
# http://127.0.0.1:18765/mcp. This is the tier that works on a host where NEITHER the task
# NOR $Launcher exists -- measured 2026-09-29 on offload-w2025, where the chain dead-ended.
$Exe      = 'C:\Users\prekzursil\.local\bin\basic-memory.exe'
$ExeArgs  = @('mcp','--transport','streamable-http','--host','127.0.0.1','--port',"$Port",'--path','/mcp')
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

# STARTUP GRACE (anti-thrash, marker-based): if a (re)launch was stamped <75s ago and the port is NOT
# bound yet, a server is mid-start (its 60s bind-wait is running) -> force-recovering kills the warming-up
# server before it binds = a restart thrash on every memory-op probe. Defer. File mtime avoids the CIM
# CreationDate subtraction (op_Subtraction throw) that silently defeated the previous guard.
$Marker = Join-Path $env:TEMP 'bm-relaunch.marker'
if (-not $DryRun -and (Test-Path $Marker)) {
    $mAge = ((Get-Date) - (Get-Item $Marker).LastWriteTime).TotalSeconds
    if ($mAge -lt 75 -and -not (Get-PortOwnerPid $Port)) {
        Log "relaunched $([int]$mAge)s ago and port not bound (launcher mid-start) - DEFER, no thrash"
        return
    }
}

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
        $plan = if (Test-Path $Exe)          { "DIRECT launch $Exe $($ExeArgs -join ' ')" }
                elseif (Test-Path $Launcher) { "launch $Launcher detached" }
                elseif (Get-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue) { "Stop/Start-ScheduledTask '$Task'" }
                else                         { "NOTHING AVAILABLE (no exe, no launcher, no task)" }
        Log "would: $plan"
        Log "end (dry-run, nothing changed)"
        return
    }

    $taskOk = $false
    # TIER GATE (zero-scheduled-task doctrine, owner 2026-09-29): never PREFER a registered task
    # over the self-contained direct launch. Only consider the task tier when $Exe is unavailable.
    $t = if (Test-Path $Exe) { $null } else { Get-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue }
    if ($t) {
        # Force-recover, not a plain Stop+Start: a blocked launcher (WaitForExit on a server that never
        # bound) pins the task 'Running', so Start-ScheduledTask fails with 0x800710E0 ('operator refused')
        # and the daemon stays DOWN. Kill any stuck launcher + stale server procs, End the task, and clear
        # the start-lock FIRST, so the relaunch is always accepted.
        Set-Content -Path $Marker -Value (Get-Date -Format o) -ErrorAction SilentlyContinue   # stamp THIS relaunch (anti-thrash cooldown for all restarters)
        Log "force-recover: kill stuck launcher/procs + End task '$Task', clear lock, then relaunch"
        Get-CimInstance Win32_Process -Filter "Name='pwsh.exe' OR Name='powershell.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like '*bm-http-server.ps1*' } |
            ForEach-Object { taskkill /PID $_.ProcessId /F /T 2>&1 | Out-Null }
        Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like '*basic-memory*18765*' } |
            ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force } catch {} }
        schtasks /End /TN $Task 2>&1 | Out-Null
        Remove-Item (Join-Path $env:TEMP 'bm-http-server.lock') -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 800
        Start-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue
        $taskOk = $true
    }

    if (-not $taskOk) {
        if (Test-Path $Exe) {
            # ZERO-DEPENDENCY tier -- PREFERRED. Owner doctrine 2026-09-29: zero scheduled tasks,
            # and depend on nothing that is not in the repo or a real filesystem path. So the
            # self-contained direct launch runs BEFORE the out-of-tree $Launcher script and before
            # any registered task (see the TIER GATE above). Measured 2026-09-29 on offload-w2025:
            # task MISSING, launcher ABSENT, liveness-restart.log never written -- this tier is
            # what removed that dead end.
            Log "DIRECT launch (preferred tier): $Exe $($ExeArgs -join ' ')"
            Start-Process -FilePath $Exe -ArgumentList $ExeArgs -WindowStyle Hidden
            # Stamp the anti-thrash marker the STARTUP GRACE guard above reads, so a second
            # session start DEFERS instead of killing a server that is still binding.
            Set-Content -Path $Marker -Value (Get-Date -Format o) -Encoding utf8
        } elseif (Test-Path $Launcher) {
            Log "no direct exe - falling back to launcher: $Launcher (detached)"
            Start-Process -FilePath 'powershell' `
                -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',$Launcher) `
                -WindowStyle Hidden
        } else {
            Log "ERROR: no exe ($Exe), no launcher ($Launcher), no scheduled task - cannot restart"
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
