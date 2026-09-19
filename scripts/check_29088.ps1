$ErrorActionPreference = 'SilentlyContinue'
$all = Get-CimInstance Win32_Process
$byPid = @{}
foreach ($p in $all) { $byPid[[uint32]$p.ProcessId] = $p }

"=== who is 29088 ==="
$c = $byPid[29088]
if ($c) {
  "created: $($c.CreationDate)"
  "cmdline: $($c.CommandLine)"
  $par = $byPid[[uint32]$c.ParentProcessId]
  if ($par) { "parent ALIVE: $($par.Name)($($par.ProcessId))" } else { "parent DEAD: $($c.ParentProcessId)" }
  "children of 29088:"
  $all | Where-Object { [uint32]$_.ParentProcessId -eq 29088 } | ForEach-Object { "  $($_.Name)($($_.ProcessId))" }
} else { "29088 already gone" }

""
"=== conhost count + orphans (parent dead) ==="
$ch = $all | Where-Object { $_.Name -eq 'conhost.exe' }
"total conhost: $($ch.Count)"
$orphans = $ch | Where-Object { -not $byPid.ContainsKey([uint32]$_.ParentProcessId) }
"orphaned conhost: $($orphans.Count)"
$orphans | ForEach-Object { "  conhost pid=$($_.ProcessId) ppid=$($_.ParentProcessId) created=$($_.CreationDate.ToString('HH:mm'))" }
