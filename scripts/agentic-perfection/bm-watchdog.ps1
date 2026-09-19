# Keep-alive watchdog for the shared basic-memory MCP daemon (127.0.0.1:18765).
#
# WHY: the BasicMemory-HTTP-MCP logon task launches the daemon ONCE; if the daemon
# later dies (observed: clean termination with no crash event, sometimes under tight
# RAM), nothing re-launches it until the mcp-liveness hook fires on an actual memory
# call. Between uses it stays dead -> the durability heartbeat keeps reporting mem:DOWN
# and recall is unavailable. This watchdog closes that gap: every few minutes, if the
# port is not serving, relaunch via the HARDENED launcher (lockfile mutex + kill-stale,
# so a watchdog restart can never race the logon task or an mcp-liveness restart).
#
# DOCTRINE (mirrors mcp-drift-audit.ps1): LOG + restart only. It never kills a healthy
# server (it acts solely when the port is already down) and is fully fail-open.
$Port = 18765
$Task = 'BasicMemory-HTTP-MCP'
$Log  = 'C:\Users\Prekzursil\.basic-memory\logs\bm-watchdog.log'
try {
    $up = Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
} catch { $up = $false }
if ($up) { return }   # healthy -> nothing to do (never touches a live server)
# STARTUP GRACE (anti-thrash, marker-based): a (re)launch stamps $env:TEMP\bm-relaunch.marker. If one
# happened <75s ago (by ANY restarter or the launcher), a server is mid-start (its 60s bind-wait is
# running) -> force-recovering now kills the WARMING-UP server = thrash. Defer. Uses a FILE mtime, not
# the CIM CreationDate subtraction (which throws op_Subtraction and silently defeated the guard).
$marker = Join-Path $env:TEMP 'bm-relaunch.marker'
if (Test-Path $marker) {
    $age = ((Get-Date) - (Get-Item $marker).LastWriteTime).TotalSeconds
    if ($age -lt 75) {
        "$(Get-Date -Format o)  :$Port down but relaunched $([int]$age)s ago - DEFER (launcher mid-start, no thrash)" | Add-Content $Log
        return
    }
}
Set-Content -Path $marker -Value (Get-Date -Format o) -ErrorAction SilentlyContinue   # stamp THIS relaunch
try {
    "$(Get-Date -Format o)  :$Port DOWN -> force-recover (clear stuck launcher/procs/task, then relaunch)" | Add-Content $Log
    # 1. Kill any blocked launcher (a WaitForExit deadlock pins the task 'Running') + stale server procs.
    Get-CimInstance Win32_Process -Filter "Name='pwsh.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*bm-http-server.ps1*' } |
        ForEach-Object { taskkill /PID $_.ProcessId /F /T 2>&1 | Out-Null }
    Get-Process basic-memory -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*basic-memory*18765*' } |
        ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force } catch {} }
    # 2. End the (possibly stuck-'Running') task + clear a stale start-lock so the relaunch is NOT
    #    refused with 0x800710E0 ('operator refused' = can't Start while IgnoreNew still sees it Running).
    schtasks /End /TN $Task 2>&1 | Out-Null
    Remove-Item (Join-Path $env:TEMP 'bm-http-server.lock') -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    # 3. Relaunch cleanly (task is now Ready).
    Start-ScheduledTask -TaskName $Task
} catch {
    try { "$(Get-Date -Format o)  watchdog error: $($_.Exception.Message)" | Add-Content $Log } catch {}
}
