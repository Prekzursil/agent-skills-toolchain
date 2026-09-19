# Keep-alive watchdog for the Basic Memory session-healing proxy (127.0.0.1:8765).
# Deploy to C:\Users\Prekzursil\.basic-memory\; run every 3 min + at logon by the
# "BasicMemory-SessionProxy-Watchdog" task (Register-BmSessionProxyTasks.ps1).
#
# WHAT IT MEASURES: the PROXY, via GET http://127.0.0.1:8765/healthz. Any HTTP answer
# means the proxy is alive; the body reports the DAEMON's state, which this script only
# logs. A daemon outage is NOT a proxy fault: the proxy answers /healthz "degraded" and
# its clients get 503 + Retry-After until BasicMemory-Watchdog (probing :8766 after the
# port move) brings the daemon back. Restarting the proxy for that would help nobody.
# This watchdog therefore acts on exactly two conditions:
#   * :8765 refuses connections                 -> force-recover the proxy at once;
#   * bound but no HTTP answer within 15 s      -> two-strike rule (state file), then force-recover,
#     so one slow probe on this RAM-starved box never thrash-kills a busy-but-healthy proxy.
# STARTUP GRACE: a (re)launch stamps $env:TEMP\bm-session-proxy-relaunch.marker (its own
# marker, not the daemon's bm-relaunch.marker); if that is <75 s old, DEFER.
# DOCTRINE (mirrors bm-watchdog.ps1): LOG + restart only. Never kills a healthy proxy,
# never touches the daemon (no Get-Process basic-memory, no BasicMemory-HTTP-MCP), fail-open.

$Port          = 8765
$Task          = 'BasicMemory-SessionProxy'
$Log           = 'C:\Users\Prekzursil\.basic-memory\logs\bm-session-proxy-watchdog.log'
$SupervisorLog = 'C:\Users\Prekzursil\.agents\logs\basic-memory-supervisor.log'
$Marker        = Join-Path $env:TEMP 'bm-session-proxy-relaunch.marker'
$Strike        = Join-Path $env:TEMP 'bm-session-proxy-degraded.strike'
$Lock          = Join-Path $env:TEMP 'bm-session-proxy.lock'
$ProbeTimeoutSec = 15
$GraceSec        = 75

function Write-Log([string]$Message) {
    try { "$(Get-Date -Format o)  $Message" | Add-Content $Log } catch {}
    try { "$(Get-Date -Format o)  [proxy-watchdog] $Message" | Add-Content $SupervisorLog } catch {}
}

# 1. Probe. TCP first (refused = down), then a real HTTP GET /healthz (any status = alive).
$tcpUp = $false
try {
    $tcpUp = Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
} catch { $tcpUp = $false }
$httpUp = $false
$upstreamState = 'n/a'
if ($tcpUp) {
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/healthz" -Method GET -UseBasicParsing `
            -TimeoutSec $ProbeTimeoutSec -ErrorAction Stop
        $httpUp = $true
        try { $upstreamState = ($resp.Content | ConvertFrom-Json).upstream.state } catch {}
    } catch {
        # Invoke-WebRequest throws on 4xx/5xx too; any HTTP response still means alive.
        if ($_.Exception.Response) { $httpUp = $true } else { $httpUp = $false }
    }
}
if ($httpUp) {
    Remove-Item $Strike -Force -ErrorAction SilentlyContinue
    if ($upstreamState -ne 'up') {
        Write-Log "proxy alive on :$Port; upstream state '$upstreamState' is the DAEMON's (BasicMemory-Watchdog's job) - nothing to do here"
    }
    return   # healthy -> never touches a live proxy
}
if ($tcpUp) {
    # Bound but HTTP-unresponsive: two strikes before acting.
    if (Test-Path $Strike) {
        Write-Log ":$Port bound but HTTP unresponsive for two probes -> force-recover"
        Remove-Item $Strike -Force -ErrorAction SilentlyContinue
    } else {
        Set-Content -Path $Strike -Value (Get-Date -Format o) -ErrorAction SilentlyContinue
        Write-Log ":$Port bound but HTTP unresponsive - first strike, deferring one cycle"
        return
    }
}

# 2. Startup grace (marker-based anti-thrash): a launcher may be mid-start right now.
if (Test-Path $Marker) {
    $age = ((Get-Date) - (Get-Item $Marker).LastWriteTime).TotalSeconds
    if ($age -lt $GraceSec) {
        Write-Log ":$Port down but relaunched $([int]$age)s ago - DEFER (launcher mid-start, no thrash)"
        return
    }
}
Set-Content -Path $Marker -Value (Get-Date -Format o) -ErrorAction SilentlyContinue   # stamp THIS relaunch

# 3. Force-recover the PROXY only.
try {
    Write-Log ":$Port DOWN -> force-recover (kill stuck launcher/proxy, End task, clear lock, relaunch)"
    # a) a blocked launcher (WaitForExit on a dead proxy pins the task 'Running') - never this script itself
    Get-CimInstance Win32_Process -Filter "Name='pwsh.exe' OR Name='powershell.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -like '*bm-session-proxy.ps1*' } |
        ForEach-Object { taskkill /PID $_.ProcessId /F /T 2>&1 | Out-Null }
    # b) a stale proxy process (scoped by its own script name; the daemon is never matched)
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*bm_session_proxy.py*' } |
        ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {} }
    # c) End the (possibly stuck-'Running') task + clear a stale start-lock so the relaunch is
    #    not refused with 0x800710E0 while IgnoreNew still sees it Running.
    schtasks /End /TN $Task 2>&1 | Out-Null
    Remove-Item $Lock -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    # d) relaunch cleanly (task is now Ready)
    Start-ScheduledTask -TaskName $Task
    Write-Log "relaunch requested via task '$Task'"
} catch {
    Write-Log "watchdog error: $($_.Exception.Message)"
}
