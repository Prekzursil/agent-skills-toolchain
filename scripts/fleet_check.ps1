$ErrorActionPreference = 'SilentlyContinue'
"--- supervisor.log tail ---"
Get-Content 'D:\opt\cyberstrike-mcp\logs\supervisor.log' -Tail 25
""
"--- fleet ports ---"
foreach ($port in 31380,31381,31410,31411,31412,31413,31414,31415,31416,31417,31418,31419,18888) {
  $t = New-Object System.Net.Sockets.TcpClient
  $iar = $t.BeginConnect('127.0.0.1', $port, $null, $null)
  $ok = $iar.AsyncWaitHandle.WaitOne(300, $false) -and $t.Connected
  $t.Close()
  "{0,-6} {1}" -f $port, $(if ($ok) {'UP'} else {'down'})
}
""
"--- supervisor process ---"
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
  Where-Object { $_.CommandLine -like '*start-cyberstrike-mcp-http*' } |
  ForEach-Object { "supervisor pid=$($_.ProcessId)" }
