# Basic Memory session-healing reverse proxy (bm-session-proxy) on 127.0.0.1:8765.
# ONE always-on process owns the client-facing port every client already holds
# (http://127.0.0.1:8765/mcp) and forwards MCP Streamable HTTP to the daemon on the
# INTERNAL port 127.0.0.1:8766, healing stale sessions (404 / -32600 Session not
# found -> re-initialize + replay once) and answering the daemon's dead-port window
# with a clean 503 + Retry-After instead of a connection refused.
# Started at logon by the "BasicMemory-SessionProxy" scheduled task
# (Register-BmSessionProxyTasks.ps1). Deploy to C:\Users\Prekzursil\.basic-memory\.
#
# Mirrors bm-http-server.ps1 (receipt .agents/BASIC-MEMORY-RELIABILITY_2026-08-27.md):
#   1) a held-open lock file makes concurrent launches mutually exclusive over the
#      start+bind window only (never for the process's whole life: that deadlocked
#      restarts once);
#   2) if the port is genuinely in use, skip (idempotent: the task's 5-min trigger
#      and the watchdog may both arrive);
#   3) kill-stale is SCOPED TO THIS PROXY (python.exe running bm_session_proxy.py).
#      It never touches the daemon: no Get-Process basic-memory, no *basic-memory*
#      filter. BasicMemory-HTTP-MCP / BasicMemory-Watchdog own the daemon (:8766).
#   4) per-launch timestamped stdout/stderr files pruned to the newest 8, so a
#      crash's evidence survives the next launch;
#   5) the relaunch marker is re-stamped during the bind wait, so the proxy
#      watchdog's 75 s grace keeps deferring while a start is genuinely underway.

$Port          = 8765
$UpstreamPort  = 8766
$Python        = 'C:\Python314\python.exe'
# The EXECUTED checkout (CLAUDE.md SSOT wire): the only checkout anything runs from.
$Repo          = 'C:\Users\Prekzursil\source\agent-skills-toolchain'
$Script        = Join-Path $Repo 'tools\mcp\mcp-http-host\bm_session_proxy.py'
$LogDir        = 'C:\Users\Prekzursil\.basic-memory\logs'
$AgentLogDir   = 'C:\Users\Prekzursil\.agents\logs'
$RestartLog    = Join-Path $AgentLogDir 'bm-session-proxy.jsonl'
$SupervisorLog = Join-Path $AgentLogDir 'basic-memory-supervisor.log'
$Log           = Join-Path $LogDir 'bm-session-proxy.log'
$Lock          = Join-Path $env:TEMP 'bm-session-proxy.lock'
$Marker        = Join-Path $env:TEMP 'bm-session-proxy-relaunch.marker'
$BindWaitCycles = 30        # the proxy binds in well under a second; 30 x 1 s is generous
$KeepLaunchLogs = 8

foreach ($dir in @($LogDir, $AgentLogDir)) {
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
}

function Write-Log([string]$Message) {
    "$(Get-Date -Format o)  $Message" | Add-Content $Log
    # Restart visibility, the receipt's convention: mirror to the shared supervisor log.
    "$(Get-Date -Format o)  [proxy-launcher] $Message" | Add-Content $SupervisorLog -ErrorAction SilentlyContinue
}

# Preflight: log and exit rather than crash-loop the task on a missing file.
if (-not (Test-Path $Python)) { Write-Log "python not found: $Python - not starting"; return }
if (-not (Test-Path $Script)) { Write-Log "proxy script not found: $Script - not starting (is the toolchain checkout in place?)"; return }

# 1) start-lock (mutex over the start+bind critical section only)
$lockStream = $null
try {
    $lockStream = [System.IO.File]::Open($Lock, 'OpenOrCreate', 'ReadWrite', 'None')
} catch {
    Write-Log "another launch holds the lock - not starting a duplicate"
    return
}

# 2) port in use -> idempotent skip (never start a second proxy on :$Port)
$inUse = $false
try {
    $inUse = Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
} catch { $inUse = $false }
if ($inUse) {
    Write-Log "port $Port already in use - not starting a second proxy"
    $lockStream.Close(); return
}

# 3) kill-stale, scoped to THIS proxy only (a half-dead copy from a crash race).
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*bm_session_proxy.py*' } |
    ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {} }
Start-Sleep -Seconds 1

# 4) per-launch timestamped stdout/stderr, pruned to the newest $KeepLaunchLogs each
$stamp  = Get-Date -Format 'yyyyMMdd-HHmmss'
$OutLog = Join-Path $LogDir "bm-session-proxy-$stamp.out.log"
$ErrLog = Join-Path $LogDir "bm-session-proxy-$stamp.err.log"
foreach ($pattern in @('bm-session-proxy-*.out.log', 'bm-session-proxy-*.err.log')) {
    Get-ChildItem -Path $LogDir -Filter $pattern -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -Skip $KeepLaunchLogs |
        Remove-Item -Force -ErrorAction SilentlyContinue
}

Write-Log "starting bm-session-proxy on 127.0.0.1:$Port -> http://127.0.0.1:$UpstreamPort/mcp"
# 5) anti-thrash: stamp the relaunch marker so the proxy watchdog DEFERS while this start binds
Set-Content -Path $Marker -Value (Get-Date -Format o) -ErrorAction SilentlyContinue

# The argv deliberately contains none of the daemon's identity tokens (basic_memory,
# streamable-http, *basic-memory*<port>*): neither the fleet supervisor's processMatch
# nor the daemon's own kill-stale filters may ever mistake the proxy for the daemon.
# Pinned by tools/mcp/mcp-http-host/tests/test_deploy_assets.py.
$argv = @("`"$Script`"", '--host', '127.0.0.1', '--port', "$Port",
          '--upstream', "http://127.0.0.1:$UpstreamPort/mcp",
          '--restart-log', "`"$RestartLog`"")
$proc = Start-Process -FilePath $Python -ArgumentList $argv -NoNewWindow -PassThru `
    -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog
$bound = $false
for ($i = 0; $i -lt $BindWaitCycles; $i++) {
    if ($proc.HasExited) { Write-Log "proxy exited during startup (code $($proc.ExitCode)) - see $ErrLog"; break }
    if (Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue) {
        Write-Log "bound on :$Port (pid $($proc.Id)) - releasing start-lock, holding proxy"; $bound = $true; break
    }
    Set-Content -Path $Marker -Value (Get-Date -Format o) -ErrorAction SilentlyContinue   # still genuinely mid-start
    Start-Sleep -Seconds 1
}
try { $lockStream.Close() } catch {}   # release the start-lock (bound or failed) -> restarts never deadlock
if ($bound) {
    # Healthy: hold the task Running (blocks duplicate launches); the task's restart-on-failure
    # relaunches when the proxy exits.
    if (-not $proc.HasExited) { $proc.WaitForExit() }
    Write-Log "proxy exited (code $($proc.ExitCode)) - the task's restart-on-failure relaunches it"
} else {
    # Did NOT bind: do NOT WaitForExit on a non-serving process (that pins the task 'Running'
    # and IgnoreNew then refuses every relaunch). Kill it and exit so a clean retry can run.
    Write-Log "did NOT bind in ${BindWaitCycles}s - killing stale proxy + exiting so a retry can run"
    try { if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } } catch {}
}
