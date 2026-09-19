$ErrorActionPreference = 'SilentlyContinue'
# R2 settling probe: fresh Win32_Process cmdline sweep grouped by playwright variant.
# Timestamped; read-only; bounded output.
"SWEEP_TS=" + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
$all = Get-CimInstance Win32_Process
"TOTAL_PROCS=$(@($all).Count)"
$withcmd = @($all | Where-Object { $_.CommandLine })
"WITH_CMDLINE=$($withcmd.Count)"
$map = @{}
foreach ($p in $all) { $map[[uint32]$p.ProcessId] = $p.Name }
$node = @($all | Where-Object { $_.Name -eq 'node.exe' })
"NODE_TOTAL=$($node.Count)"
# detector control: known-present pattern (this session's own CLI + harness)
$ctl = @($withcmd | Where-Object { $_.CommandLine -match 'claude' })
"CONTROL_CLAUDE_MATCH=$($ctl.Count)"
$pw = @($node | Where-Object { $_.CommandLine -match 'playwright' })
"NODE_PW_MATCH=$($pw.Count)"
foreach ($p in $pw) {
  $c = ($p.CommandLine -replace '\s+',' ')
  $v = 'other'
  if ($c -match '--extension') { $v = 'extension' }
  elseif ($c -match '--cdp-endpoint') { $v = 'cdp' }
  elseif ($c -match '@playwright/mcp') { $v = 'base' }
  $r = 'server'
  if ($c -match 'npx-cli') { $r = 'launcher' }
  elseif ($c -match '(^| )cmd(\.exe)? /c') { $r = 'cmd-wrapper' }
  $pin = 'nopin'
  if ($c -match '@playwright/mcp@([0-9.]+)') { $pin = $Matches[1] }
  elseif ($c -match '@playwright/mcp@latest') { $pin = 'latest' }
  $age = ((Get-Date) - $p.CreationDate).TotalMinutes
  $par = $map[[uint32]$p.ParentProcessId]
  if (-not $par) { $par = 'DEAD(' + $p.ParentProcessId + ')' }
  $cl = $c; if ($cl.Length -gt 105) { $cl = $cl.Substring(0,105) }
  "PW variant=$v role=$r pin=$pin pid=$($p.ProcessId) ppid=$($p.ParentProcessId) parent=$par age_min=$([math]::Round($age,0)) cmd=$cl"
}
"GROUP_DONE"
