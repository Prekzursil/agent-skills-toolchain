<#
.SYNOPSIS
    Always-on supervisor for the mcp_agent_mail Streamable-HTTP server (canonical port 8812).

.DESCRIPTION
    Ensures exactly ONE `serve-http --host 127.0.0.1 --port 18812` process (from the vendored
    venv at C:/Users/Prekzursil/.local/opt/mcp_agent_mail) is running at all times.

    Guarantees:
      * Single-instance   - a named system mutex prevents two supervisors racing.
      * No double-bind     - a health-gate probes /api/health before every (re)start; if the
                             port is already serving healthy (owned by anyone), it does NOT spawn.
      * Restart-on-exit    - if the child dies OR goes unhealthy, it is restarted with
                             exponential backoff (capped).
      * Idempotent         - safe to run repeatedly; adopts a healthy pre-existing server.
      * Logged             - all activity appended to a rotating log file.

.PARAMETER InstallDir   Root of the vendored mcp_agent_mail checkout (holds .venv).
.PARAMETER BindHost     Interface to bind (localhost only). Default 127.0.0.1.
.PARAMETER Port         TCP port. Default 8812 (canonical).
.PARAMETER Path         HTTP path where the MCP endpoint is exposed. Default /mcp.
.PARAMETER Once         Run a single ensure-pass and exit (for testing / task-triggered runs).
.PARAMETER StopExisting Kill any supervisor-owned server, release the mutex, and exit.

.NOTES
    The health endpoint /api/health is auth-bypassed for localhost and returns {"status":"ok"}.
    The MCP itself is mounted at both /mcp and /api regardless of --path.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = 'C:/Users/Prekzursil/.local/opt/mcp_agent_mail',
    [string]$BindHost   = '127.0.0.1',
    [int]   $Port = 18812,
    [string]$Path       = '/mcp',
    [switch]$Once,
    [switch]$StopExisting
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# --------------------------------------------------------------------------- config
$PythonExe   = Join-Path $InstallDir '.venv/Scripts/python.exe'
$LogDir      = Join-Path $InstallDir 'logs'
$LogFile     = Join-Path $LogDir 'agentmail_supervisor.log'
$ChildOut    = Join-Path $LogDir 'agentmail_server.out.log'
$ChildErr    = Join-Path $LogDir 'agentmail_server.err.log'
$PidFile     = Join-Path $LogDir 'agentmail_server.pid'
$HealthUrl   = "http://${BindHost}:${Port}/api/health"
$MutexName   = "Global\mcp_agent_mail_supervisor_$Port"
$MaxLogBytes = 5MB

# Backoff (seconds): grows on repeated fast failures, resets after a stable run.
$BackoffMin      = 2
$BackoffMax      = 60
$HealthPollSec   = 10     # steady-state health re-check cadence
$StartupGraceSec = 240    # how long to wait for a fresh child to report healthy. Measured 2026-07-23:
                          # the uv CPython-3.14 child cold-starts in ~8s idle but ~90-150s under this
                          # box's memory/commit pressure (import-heavy: fastapi/uvicorn/sqlalchemy/mcp/rich).
                          # A 90s grace killed near-ready children 2-60s before they bound -> a
                          # non-converging crash loop. 240s lets a slow-but-healthy cold start converge.
$StableRunSec    = 60     # a child that stays up this long resets backoff
$MaxHealthFailStreak = 3  # consecutive failed health polls before recycling a RUNNING child (load tolerance)

# --------------------------------------------------------------------------- logging
function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $line = ('{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message)
    try {
        if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }
        if ((Test-Path $LogFile) -and ((Get-Item $LogFile).Length -gt $MaxLogBytes)) {
            Move-Item -Force -Path $LogFile -Destination "$LogFile.1"
        }
        Add-Content -Path $LogFile -Value $line -Encoding utf8
    } catch { }
    Write-Host $line
}

# --------------------------------------------------------------------------- health
function Test-Healthy {
    param([int]$TimeoutSec = 8)
    # Bypass system proxy (Fiddler etc.) for localhost — otherwise 502/ConnectionFailed.
    try {
        $handler = [System.Net.Http.HttpClientHandler]::new()
        $handler.UseProxy = $false
        $client = [System.Net.Http.HttpClient]::new($handler)
        $client.Timeout = [TimeSpan]::FromSeconds($TimeoutSec)
        $resp = $client.GetAsync($HealthUrl).GetAwaiter().GetResult()
        $body = $resp.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        $client.Dispose(); $handler.Dispose()
        if ([int]$resp.StatusCode -eq 200 -and $body -match '"status"\s*:\s*"ok"') { return $true }
    } catch {
        try {
            $savedProxy = $env:HTTP_PROXY; $savedHttps = $env:HTTPS_PROXY
            $env:HTTP_PROXY = ''; $env:HTTPS_PROXY = ''; $env:NO_PROXY = '127.0.0.1,localhost'
            $resp = Invoke-WebRequest -Uri $HealthUrl -TimeoutSec $TimeoutSec -UseBasicParsing
            if ($resp.StatusCode -eq 200 -and $resp.Content -match '"status"\s*:\s*"ok"') { return $true }
        } catch { }
        finally {
            if ($null -ne $savedProxy) { $env:HTTP_PROXY = $savedProxy }
            if ($null -ne $savedHttps) { $env:HTTPS_PROXY = $savedHttps }
        }
    }
    return $false
}

function Test-PortOpen {
    try {
        $c = [System.Net.Sockets.TcpClient]::new()
        $iar = $c.BeginConnect($BindHost, $Port, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne(1000, $false)
        if ($ok -and $c.Connected) { $c.EndConnect($iar); $c.Close(); return $true }
        $c.Close(); return $false
    } catch { return $false }
}

# --------------------------------------------------------------------------- child lifecycle
function Get-TrackedProcess {
    if (-not (Test-Path $PidFile)) { return $null }
    try {
        $trackedPid = [int](Get-Content $PidFile -ErrorAction Stop | Select-Object -First 1)
        $p = Get-Process -Id $trackedPid -ErrorAction Stop
        # Confirm it is our python (defends against PID reuse).
        if ($p.Path -and ($p.Path -ieq (Resolve-Path $PythonExe).Path)) { return $p }
        return $null
    } catch { return $null }
}

function Get-RogueServers {
    # Any `mcp_agent_mail.cli serve-http` process that is NOT bound to our canonical port.
    # Only one server can own the storage root at a time, so a differently-ported instance
    # blocks us from binding $Port -> it must be reclaimed.
    #
    # INFO-ONLY EXCLUSION: `--help` / `--version` make typer print and exit(0). Such a process
    # never binds a port and never opens the storage root, so it is NEVER a rogue -- but the bare
    # `-notmatch "--port $Port"` test matched it anyway and force-killed it. Measured: 4 of the 6
    # lifetime "Reclaiming storage root" events (2026-08-07 03:51:46 / 03:51:54 / 03:57:27 /
    # 03:57:28, agentmail_supervisor.log:3134,3135,3141,3142) were operator `serve-http --help`
    # diagnostics, not rogues. A bare `serve-http` carrying NO --port is STILL a rogue: it binds
    # the HTTP_PORT setting default (config.py:395 -> 8765) and still holds the storage root.
    $portToken = "--port $Port"
    $infoOnly  = '(^|\s)--(help|version)(\s|$)'
    $rogues = @()
    try {
        $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction Stop
        foreach ($pr in $procs) {
            $cl = $pr.CommandLine
            if ($null -eq $cl) { continue }
            if ($cl -match 'mcp_agent_mail\.cli' -and $cl -match 'serve-http' -and $cl -notmatch $infoOnly -and $cl -notmatch [regex]::Escape($portToken)) {
                $rogues += $pr
            }
        }
    } catch { }
    return $rogues
}

function Get-AllServers {
    # Every `mcp_agent_mail.cli serve-http` python process, regardless of port.
    $all = @()
    try {
        $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction Stop
        foreach ($pr in $procs) {
            $cl = $pr.CommandLine
            if ($null -ne $cl -and $cl -match 'mcp_agent_mail\.cli' -and $cl -match 'serve-http') { $all += $pr }
        }
    } catch { }
    return $all
}

function Invoke-StorageRootReclaim {
    # Stop any differently-ported agent-mail server holding the shared storage root, so the
    # canonical-port server can take ownership. Prevents a split-brain bridge on a stale port.
    $rogues = @(Get-RogueServers)
    foreach ($r in $rogues) {
        Write-Log "Reclaiming storage root: stopping rogue agent-mail server pid=$($r.ProcessId) [$($r.CommandLine)]" 'WARN'
        try { Stop-Process -Id $r.ProcessId -Force -ErrorAction Stop } catch { Write-Log "Failed to stop pid=$($r.ProcessId): $($_.Exception.Message)" 'WARN' }
    }
    if ($rogues.Count -gt 0) { Start-Sleep -Seconds 2 }  # let the OS release the lock + port
    return $rogues.Count
}

function Start-Child {
    Write-Log "Starting agent-mail server: $PythonExe -m mcp_agent_mail.cli serve-http --host $BindHost --port $Port --path $Path"
    $argList = @('-m', 'mcp_agent_mail.cli', 'serve-http', '--host', $BindHost, '--port', "$Port", '--path', $Path)
    $p = Start-Process -FilePath $PythonExe -ArgumentList $argList `
        -WorkingDirectory $InstallDir `
        -RedirectStandardOutput $ChildOut `
        -RedirectStandardError  $ChildErr `
        -WindowStyle Hidden -PassThru
    Set-Content -Path $PidFile -Value $p.Id -Encoding ascii
    Write-Log "Spawned child pid=$($p.Id); waiting up to ${StartupGraceSec}s for health."
    $deadline = (Get-Date).AddSeconds($StartupGraceSec)
    while ((Get-Date) -lt $deadline) {
        if ($p.HasExited) { Write-Log "Child pid=$($p.Id) exited early (code=$($p.ExitCode))." 'WARN'; return $null }
        if (Test-Healthy) { Write-Log "Health OK on $HealthUrl (pid=$($p.Id))."; return $p }
        Start-Sleep -Seconds 1
    }
    Write-Log "Child pid=$($p.Id) did not become healthy within ${StartupGraceSec}s." 'WARN'
    return $p   # return anyway; caller decides via health whether to keep or kill
}

function Stop-Child {
    param($Proc)
    if ($null -eq $Proc) { return }
    try {
        if (-not $Proc.HasExited) {
            Write-Log "Stopping child pid=$($Proc.Id)."
            Stop-Process -Id $Proc.Id -Force -ErrorAction SilentlyContinue
        }
    } catch { }
    Remove-Item -Path $PidFile -ErrorAction SilentlyContinue
}

# --------------------------------------------------------------------------- preflight
if (-not (Test-Path $PythonExe)) {
    Write-Log "FATAL: venv python not found at $PythonExe" 'ERROR'
    exit 1
}

# --------------------------------------------------------------------------- single-instance mutex
$createdNew = $false
$mutex = [System.Threading.Mutex]::new($true, $MutexName, [ref]$createdNew)

if ($StopExisting) {
    # Tear down the channel for this storage root: stop the tracked child (if any) AND every
    # mcp_agent_mail serve-http process (covers re-exec'd workers + manually-started servers,
    # which the pidfile alone does not track). Used by the uninstall path.
    $tracked = Get-TrackedProcess
    if ($tracked) { Stop-Child $tracked }
    $all = @(Get-AllServers)
    foreach ($s in $all) {
        Write-Log "StopExisting: stopping agent-mail server pid=$($s.ProcessId) [$($s.CommandLine)]"
        try { Stop-Process -Id $s.ProcessId -Force -ErrorAction Stop } catch { Write-Log "  failed: $($_.Exception.Message)" 'WARN' }
    }
    Remove-Item -Path $PidFile -ErrorAction SilentlyContinue
    if (($null -eq $tracked) -and ($all.Count -eq 0)) { Write-Log 'StopExisting: no agent-mail server found.' }
    else { Write-Log "StopExisting: stopped $($all.Count) server process(es)." }
    if ($createdNew) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
    exit 0
}

if (-not $createdNew) {
    Write-Log 'Another supervisor instance already owns the mutex; exiting (idempotent).' 'WARN'
    $mutex.Dispose()
    exit 0
}

Write-Log "Supervisor started (mutex=$MutexName, port=$Port, once=$($Once.IsPresent))."

# --------------------------------------------------------------------------- graceful shutdown
$script:child = $null
function Invoke-Cleanup {
    if ($script:child) { Stop-Child $script:child }
    try { if ($createdNew) { $mutex.ReleaseMutex() } } catch { }
    $mutex.Dispose()
    Write-Log 'Supervisor exiting; released mutex.'
}

# --------------------------------------------------------------------------- main loop
$backoff = $BackoffMin
$startedAt = Get-Date   # tracks current child's start time (for backoff reset); pre-set for StrictMode
$script:healthFailStreak = 0  # consecutive failed health polls for the current running child
try {
    do {
        # 1) Adopt a healthy pre-existing server (avoid double-bind).
        $script:child = Get-TrackedProcess
        if ($null -eq $script:child -and (Test-Healthy)) {
            Write-Log "Port $Port already serving healthy (unmanaged). Adopting: will NOT spawn." 'WARN'
            if ($Once) { break }
            Start-Sleep -Seconds $HealthPollSec
            continue
        }

        # 2) Ensure a child is running and healthy. A RUNNING child is recycled only after
        # $MaxHealthFailStreak CONSECUTIVE failed health checks, so transient slowness under
        # heavy box load (OOM / CPU thrash) does not needlessly recycle an otherwise-fine server.
        # A genuinely dead child (HasExited) still recycles immediately.
        $childGone = ($null -eq $script:child -or $script:child.HasExited)
        $recycleRunning = $false
        if (-not $childGone) {
            if (Test-Healthy) {
                $script:healthFailStreak = 0
            } else {
                $script:healthFailStreak++
                Write-Log "Health check failed (streak $($script:healthFailStreak)/$MaxHealthFailStreak) for running pid=$($script:child.Id); tolerating transient load." 'WARN'
                if ($script:healthFailStreak -ge $MaxHealthFailStreak) { $recycleRunning = $true }
            }
        }
        if ($childGone -or $recycleRunning) {
            $script:healthFailStreak = 0
            if ($script:child -and (-not $script:child.HasExited)) {
                Write-Log 'Tracked child unhealthy past tolerance; recycling.' 'WARN'
                Stop-Child $script:child
            }
            # Storage-root reclaim: a stale agent-mail server on a DIFFERENT port holds the
            # single-owner storage lock and would block us from binding $Port. Take it over.
            Invoke-StorageRootReclaim | Out-Null

            # Refuse to spawn if some OTHER process holds the port but is unhealthy? We still
            # avoid spawning onto an occupied port to prevent bind errors.
            if ((Test-PortOpen) -and -not (Test-Healthy)) {
                Write-Log "Port $Port is occupied by an unhealthy/unknown process; backing off ${backoff}s instead of double-binding." 'WARN'
                if ($Once) { break }
                Start-Sleep -Seconds $backoff
                $backoff = [Math]::Min($backoff * 2, $BackoffMax)
                continue
            }

            $startedAt = Get-Date
            $script:child = Start-Child
            if ($null -eq $script:child -or -not (Test-Healthy)) {
                if ($script:child) { Stop-Child $script:child }
                Write-Log "Start failed; backing off ${backoff}s." 'WARN'
                if ($Once) { break }
                Start-Sleep -Seconds $backoff
                $backoff = [Math]::Min($backoff * 2, $BackoffMax)
                continue
            }
            Write-Log "Server healthy and supervised (pid=$($script:child.Id))."
        }

        if ($Once) { Write-Log 'Once mode: ensure-pass complete, server healthy. Exiting.'; break }

        # 3) Steady state: poll health; reset backoff after a stable run.
        Start-Sleep -Seconds $HealthPollSec
        if (-not $script:child.HasExited -and (Test-Healthy)) {
            if (((Get-Date) - $startedAt).TotalSeconds -ge $StableRunSec) { $backoff = $BackoffMin }
        }
    } while ($true)
}
finally {
    # In Once mode we intentionally leave the healthy server running (do NOT stop it);
    # only release the mutex. In loop mode a real exit means stop the child.
    if ($Once) {
        try { if ($createdNew) { $mutex.ReleaseMutex() } } catch { }
        $mutex.Dispose()
        Write-Log 'Once mode: leaving server running; released mutex.'
    } else {
        Invoke-Cleanup
    }
}

