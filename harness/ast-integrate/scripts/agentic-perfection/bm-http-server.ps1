# Basic Memory shared MCP server (streamable-http).
# ONE process for ALL Claude/Codex sessions -> single FastEmbed model load,
# no per-session startup hang, no 4x RAM duplication.
# Started at logon by the "BasicMemory-HTTP-MCP" scheduled task.

$Port = 8765
$BmExe = 'C:\Users\Prekzursil\.local\bin\basic-memory.exe'
$LogDir = 'C:\Users\Prekzursil\.basic-memory\logs'
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }
$Log = Join-Path $LogDir 'bm-http-server.log'
$ErrLog = Join-Path $LogDir 'bm-http-server.err.log'

# Singleton + anti-race hardening (fixes the [Errno 10048] flapping caused by
# concurrent launch paths - scheduled task + mcp-liveness restart + manual - racing
# for the port when it is briefly free between a crash and a restart):
#   1) a held-open lock file makes concurrent launches mutually exclusive (true mutex);
#   2) if the port is genuinely in use, skip (idempotent);
#   3) otherwise clear any stale/half-bound basic-memory processes and let the OS
#      release the socket (TIME_WAIT) before we bind, so only ONE instance ever owns it.
$Lock = Join-Path $env:TEMP 'bm-http-server.lock'
$lockStream = $null
try {
    $lockStream = [System.IO.File]::Open($Lock, 'OpenOrCreate', 'ReadWrite', 'None')
} catch {
    "$(Get-Date -Format o)  another launch holds the lock - not starting a duplicate" | Add-Content $Log
    return
}
$inUse = $false
try {
    $inUse = Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
} catch { $inUse = $false }
if ($inUse) {
    "$(Get-Date -Format o)  port $Port already in use - not starting a second server" | Add-Content $Log
    $lockStream.Close(); return
}
# Port is free but stale/half-bound basic-memory processes may linger from a crash
# race - clear them so exactly one instance binds, then wait for socket release.
Get-Process basic-memory -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3

$env:BASIC_MEMORY_HOME    = 'D:\basic-memory'
$env:FASTEMBED_CACHE_PATH = 'D:\basic-memory\.models'
$env:DO_NOT_TRACK         = '1'
# HF_HOME is inherited from the global User env var; basic-memory itself uses
# FASTEMBED_CACHE_PATH (.models), not HF_HOME.

"$(Get-Date -Format o)  starting basic-memory streamable-http on 127.0.0.1:$Port" | Add-Content $Log
# Anti-thrash: stamp the relaunch marker so the watchdog + liveness-restart DEFER while this start binds
# (their 75s grace reads this file's mtime), instead of killing a warming-up server on their next probe.
Set-Content -Path (Join-Path $env:TEMP 'bm-relaunch.marker') -Value (Get-Date -Format o) -ErrorAction SilentlyContinue

# Launch with -PassThru (NOT -Wait) so the start-lock can be RELEASED once the port
# binds, then wait on the daemon WITHOUT holding the lock. Holding the lock for the
# daemon's whole life deadlocked restarts: a hung launcher's lock made every watchdog /
# mcp-liveness restart skip with "another launch holds the lock" -> basic-memory stayed
# down. The lock now guards only the start+bind critical section (the actual race window).
$args = @('mcp', '--transport', 'streamable-http', '--host', '127.0.0.1',
          '--port', "$Port", '--path', '/mcp')
$proc = Start-Process -FilePath $BmExe -ArgumentList $args -NoNewWindow -PassThru `
    -RedirectStandardOutput $Log -RedirectStandardError $ErrLog
$bound = $false
for ($i = 0; $i -lt 60; $i++) {
    if ($proc.HasExited) { "$(Get-Date -Format o)  daemon exited during startup (code $($proc.ExitCode))" | Add-Content $Log; break }
    if (Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue) {
        "$(Get-Date -Format o)  bound on :$Port - releasing start-lock, holding daemon" | Add-Content $Log; $bound = $true; break
    }
    Start-Sleep -Seconds 1
}
try { $lockStream.Close() } catch {}   # release the start-lock (bound or failed) -> future restarts never deadlock
if ($bound) {
    if (-not $proc.HasExited) { $proc.WaitForExit() }   # healthy: hold task Running + block duplicate launches
} else {
    # Did NOT bind within 60s but the shim chain may still be alive (port-collision / hung startup).
    # Do NOT WaitForExit on a non-serving process: that pins the task 'Running', so IgnoreNew blocks the
    # 5-min relaunch AND the watchdog's Start-ScheduledTask is refused (0x800710E0) -> permanent DOWN.
    # Kill the stale chain and EXIT so the task returns to Ready and a clean retry can run.
    "$(Get-Date -Format o)  did NOT bind in 60s - killing stale chain + exiting so a retry can run" | Add-Content $Log
    try { if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } } catch {}
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*basic-memory*8765*' } |
        ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {} }
}
