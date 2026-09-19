$ErrorActionPreference = 'SilentlyContinue'
$all = Get-CimInstance Win32_Process
$byPid = @{}
foreach ($p in $all) { $byPid[[uint32]$p.ProcessId] = $p }

# Ancestor chain of THIS powershell (finds which cyberstrike.exe hosts me)
"=== my ancestor chain ==="
$cur = [uint32]$PID
$chain = @()
for ($i=0; $i -lt 15 -and $cur -and $byPid.ContainsKey($cur); $i++) {
  $p = $byPid[$cur]
  $chain += "$($p.Name)($cur)"
  $cur = [uint32]$p.ParentProcessId
}
$chain -join ' -> '

""

# Children still alive under DEAD parents (63832 = old TUI, 79896 = old node host)
"=== orphans of dead TUI hosts ==="
$dead = @(63832,79896)
foreach ($p in $all) {
  if ($dead -contains [uint32]$p.ParentProcessId -and -not $byPid.ContainsKey([uint32]$p.ParentProcessId)) {
    '{0,-22} pid={1,-7} ppid={2}' -f $p.Name, $p.ProcessId, $p.ParentProcessId
  }
}

""
"=== all cmd/node/python under either live cyberstrike (60008/35152) ==="
foreach ($p in $all) {
  if (60008,35152 -contains [uint32]$p.ParentProcessId) {
    '{0,-22} pid={1,-7} parent={2}' -f $p.Name, $p.ProcessId, $p.ParentProcessId
  }
}
