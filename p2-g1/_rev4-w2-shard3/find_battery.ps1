Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" |
  Where-Object { $_.CommandLine -like '*_rev4-w2-shard3*' } |
  ForEach-Object {
    $cl = $_.CommandLine
    if ($cl.Length -gt 140) { $cl = $cl.Substring(0,140) }
    "PID=$($_.ProcessId) CL=$cl"
  }
