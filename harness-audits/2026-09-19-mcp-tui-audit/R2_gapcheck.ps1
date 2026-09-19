$ErrorActionPreference = 'SilentlyContinue'
$p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'playwright' -and $_.Name -ne 'node.exe' }
"NONNODE_PW=$(@($p).Count)"
$p | Select-Object -First 8 | ForEach-Object {
  $c = ($_.CommandLine -replace '\s+',' ')
  if ($c.Length -gt 90) { $c = $c.Substring(0,90) }
  "NN name=$($_.Name) pid=$($_.ProcessId) cmd=$c"
}
"GAPCHECK_TS=" + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
