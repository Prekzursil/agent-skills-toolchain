# Keep-alive watchdog for the shared basic-memory MCP daemon (127.0.0.1:8765).
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
$Port = 8765
$Task = 'BasicMemory-HTTP-MCP'
$Log  = 'C:\Users\Prekzursil\.basic-memory\logs\bm-watchdog.log'
try {
    $up = Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
} catch { $up = $false }
if ($up) { return }   # healthy -> nothing to do (never touches a live server)
try {
    "$(Get-Date -Format o)  :$Port DOWN -> restarting via hardened launcher (task $Task)" | Add-Content $Log
    Stop-ScheduledTask  -TaskName $Task -ErrorAction SilentlyContinue   # clear any stuck 'Running'
    Start-Sleep -Seconds 1
    Start-ScheduledTask -TaskName $Task
} catch {
    try { "$(Get-Date -Format o)  watchdog error: $($_.Exception.Message)" | Add-Content $Log } catch {}
}
