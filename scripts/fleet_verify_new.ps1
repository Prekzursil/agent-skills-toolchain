$ErrorActionPreference = 'SilentlyContinue'
"--- new band listeners ---"
foreach ($port in 31100,31101,31110,31111,31112,31113,31114,31115,31116,31117,31118,31119) {
  $t = New-Object System.Net.Sockets.TcpClient
  $iar = $t.BeginConnect('127.0.0.1', $port, $null, $null)
  $ok = $iar.AsyncWaitHandle.WaitOne(300, $false) -and $t.Connected
  $t.Close()
  "{0,-6} {1}" -f $port, $(if ($ok) {'UP'} else {'down'})
}

""
"--- MCP initialize handshakes ---"
$init = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"verify","version":"1"}}}'
foreach ($ep in @('github-security:31110','hexstrike-ai:31113','metasploit:31116','sliver-full:31101')) {
  $name,$port = $ep -split ':'
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/mcp" -Method POST -Body $init `
      -ContentType 'application/json' -Headers @{ Accept = 'application/json, text/event-stream' } `
      -TimeoutSec 12 -UseBasicParsing
    $body = $r.Content
    if ($body.Length -gt 160) { $body = $body.Substring(0,160) + '...' }
    "{0,-15} HTTP {1}  {2}" -f $name, $r.StatusCode, ($body -replace "`n",' ')
  } catch {
    "{0,-15} FAIL: {1}" -f $name, $_.Exception.Message
  }
}
