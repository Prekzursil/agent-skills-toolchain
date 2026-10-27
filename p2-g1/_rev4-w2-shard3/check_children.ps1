$parent = (Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" |
  Where-Object { $_.CommandLine -like '*_rev4*' } | Select-Object -First 1)
if ($parent) {
  "battery PID=$($parent.ProcessId) CPU=$($parent.KernelModeTime+$parent.UserModeTime)"
  Get-CimInstance Win32_Process -Filter "ParentProcessId=$($parent.ProcessId)" |
    ForEach-Object {
      $cl = $_.CommandLine
      if ($cl -and $cl.Length -gt 130) { $cl = $cl.Substring(0,130) }
      "child PID=$($_.ProcessId) started=$($_.CreationDate) CL=$cl"
    }
} else { "no battery process found" }
