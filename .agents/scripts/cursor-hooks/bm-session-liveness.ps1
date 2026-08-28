# Fail-open Cursor sessionStart hook: if 127.0.0.1:8765 is not serving,
# kick the existing BasicMemory-HTTP-MCP task. Never binds 8765, never
# blocks the session (always prints {} and exits 0), no secrets.
try { [void][Console]::In.ReadToEnd() } catch {}
$alive = $false
try {
    $req = [System.Net.HttpWebRequest]::Create('http://127.0.0.1:8765/mcp')
    $req.Method = 'GET'
    $req.Timeout = 1500
    $req.ReadWriteTimeout = 1500
    try {
        $resp = $req.GetResponse()
        $resp.Close()
        $alive = $true
    } catch [System.Net.WebException] {
        if ($_.Exception.Response) { $alive = $true }
    }
} catch {}
if (-not $alive) {
    try { Start-ScheduledTask -TaskName 'BasicMemory-HTTP-MCP' } catch {}
    try {
        $line = "$(Get-Date -Format o)  [sessionStart] :8765 not serving - kicked BasicMemory-HTTP-MCP"
        Add-Content 'C:\Users\Prekzursil\.agents\logs\basic-memory-supervisor.log' $line
    } catch {}
}
Write-Output '{}'
exit 0
